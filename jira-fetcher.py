#!/usr/bin/env python3
"""
Script to fetch Jira items related to DWDEV-6812
Run with: uv run jira-fetcher.py
Outputs: JSON file with all fetched data for easy LLM consumption
"""

import requests
import json
from datetime import datetime
from requests.auth import HTTPBasicAuth
import os
import io # Added for Google Drive downloads
import logging # Added logging module
import argparse # Added argparse module
import time # For basic delays
import threading # For Semaphores
import queue # For thread-safe queue
from concurrent.futures import ThreadPoolExecutor, as_completed # For concurrent processing
from confluence_client import ConfluenceClient

# Configure basic logging as early as possible
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Attempt to import Google Drive libraries
try:
    from googleapiclient.discovery import build
    from google.auth import default as gauth_default
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    print("WARNING: Google API libraries not found. Google Drive fetching will be disabled.")
    print("Please install them: pip install google-api-python-client google-auth")

# Load environment variables from .env file
from dotenv import load_dotenv
# Determine the absolute path to the directory containing the script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the .env file
dotenv_path = os.path.join(script_dir, '.env')
# Load the .env file from the explicit path, overriding system environment variables if present
loaded_env_success = load_dotenv(dotenv_path=dotenv_path, override=True)

# --- Start Debugging --- 
if loaded_env_success:
    logging.info(f"Successfully attempted to load .env file from {dotenv_path} (overriding system vars if any conflicts).")
    # Check what dotenv_values() parsed from the file directly
    from dotenv import dotenv_values
    parsed_values = dotenv_values(dotenv_path)
    logging.info(f"Values parsed by dotenv_values from {dotenv_path}: {parsed_values}")
else:
    logging.warning(f"Did not load .env file from {dotenv_path}. It might be missing or empty. Will rely on available environment variables.")

logging.info("Checking os.getenv immediately after load_dotenv:")
logging.info(f"  os.getenv('JIRA_BASE_URL'): {os.getenv('JIRA_BASE_URL')}")
logging.info(f"  os.getenv('JIRA_USERNAME'): {os.getenv('JIRA_USERNAME')}")
logging.info(f"  os.getenv('JIRA_API_TOKEN'): {os.getenv('JIRA_API_TOKEN')}")
logging.info(f"  os.getenv('CONFLUENCE_BASE_URL'): {os.getenv('CONFLUENCE_BASE_URL')}")
# --- End Debugging ---

# Configuration from environment variables
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL") # Added Confluence URL from env
USERNAME = os.getenv("JIRA_USERNAME")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") # Optional, for ADC

# Validate essential configurations
if not JIRA_BASE_URL or not USERNAME or not API_TOKEN or not CONFLUENCE_BASE_URL:
    # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Already configured globally
    logging.error("CRITICAL: JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN, and/or CONFLUENCE_BASE_URL are not set after attempting to load .env. Please ensure they are in your .env file or system environment.")
    exit(1)

# Initialize Confluence client
confluence_client = ConfluenceClient(
    base_url=CONFLUENCE_BASE_URL,
    username=USERNAME,
    api_token=API_TOKEN,
    max_concurrent_calls=5,
    api_call_delay=0.1
)

MAX_RESULTS_PER_JIRA_PAGE = 100 # Configurable page size for Jira API calls
API_CALL_DELAY_SECONDS = 0.1 # Basic delay after each significant API call

# Semaphores to limit concurrent API calls to each service
# These values can be tuned based on observed API behavior and rate limits.
MAX_CONCURRENT_JIRA_CALLS = 5
MAX_CONCURRENT_GDRIVE_CALLS = 2

JIRA_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_JIRA_CALLS)
GDRIVE_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_GDRIVE_CALLS)

# Global variable for the Drive service to avoid re-initializing it repeatedly.
DRIVE_SERVICE = None

# --- Helper to process an issue (print, get remote links, get epic children) ---
# This set tracks keys for all issues processed to avoid redundant fetching of epic children or remote links.
# It's modified by process_issue_fully.
globally_processed_issue_keys = set()

def process_issue_fully(issue_json, indent_str="", skip_remote=False):
    if not issue_json or not issue_json.get('key'):
        return
    
    issue_key = issue_json['key']
    
    # Print main issue summary using logging
    # print_issue_summary(issue_json) # Keep this if you want separate detailed print output
    logging.info(f"{indent_str}Processing details for issue: {issue_key} - {issue_json.get('fields', {}).get('summary', 'N/A')}")

    # Fetch and process remote links
    # Check if remote links are already expanded in the issue_json
    expanded_remote_links = issue_json.get('fields', {}).get('remotelink')

    if expanded_remote_links:
        logging.info(f"{indent_str}  Using {len(expanded_remote_links)} expanded remote link(s) for {issue_key}.")
        # The structure of expanded remote links might be directly usable or need slight adaptation.
        # Assuming it's a list of objects similar to what fetch_remote_links returns.
        remote_links = expanded_remote_links 
        # Ensure it's stored in the same way for downstream processing if it was fetched separately
        if "remote_links_data" not in issue_json: 
            issue_json["remote_links_data"] = remote_links
    elif issue_key not in globally_processed_issue_keys or not skip_remote: # Only process if new or if not skipping remote, and not expanded
        logging.info(f"{indent_str}  Expanded remote links not found for {issue_key}. Fetching separately.")
        remote_links = fetch_remote_links(issue_key)
        if remote_links:
            issue_json["remote_links_data"] = remote_links
    else:
        remote_links = issue_json.get("remote_links_data", []) # Get already fetched if any

    if remote_links:
        logging.info(f"{indent_str}  Processing {len(remote_links)} remote link(s) for {issue_key}.")
        for idx, r_link in enumerate(remote_links):
            link_obj = r_link.get('object', {})
            if not isinstance(link_obj, dict):
                logging.warning(f"{indent_str}    Skipping malformed remote link object: {link_obj}")
                continue
            link_title = link_obj.get('title', 'N/A')
            link_url = link_obj.get('url', 'N/A')
            logging.info(f"{indent_str}    - Link {idx+1}: {link_title} ({link_url})")

            if skip_remote:
                logging.debug(f"{indent_str}      Skipping remote content fetch for {link_url} due to --skip-remote-content flag.")
                if isinstance(issue_json.get("remote_links_data"), list) and idx < len(issue_json["remote_links_data"]) and isinstance(issue_json["remote_links_data"][idx], dict):
                    issue_json["remote_links_data"][idx]["content_skipped"] = True
                continue

            # Confluence
            if confluence_client.is_confluence_url(link_url):
                page_id = confluence_client.extract_page_id_from_url(link_url)
                
                if page_id:
                    logging.info(f"{indent_str}      Fetching Confluence content for page ID: {page_id}...")
                    confluence_content = confluence_client.fetch_content_recursive(page_id)
                    if confluence_content and isinstance(issue_json["remote_links_data"][idx], dict):
                        issue_json["remote_links_data"][idx]["confluence_content_fetched"] = confluence_content
                        logging.info(f"{indent_str}      Successfully attached Confluence content for page ID: {page_id}")
                    elif not confluence_content:
                         logging.info(f"{indent_str}      No Confluence content found or error for page ID: {page_id}")
                else: logging.warning(f"{indent_str}      Could not determine Confluence page ID from URL: {link_url}")
            # Google Drive
            elif GOOGLE_LIBS_AVAILABLE and is_google_drive_link(link_url):
                gdrive_service = get_google_drive_service()
                if gdrive_service:
                    gdrive_id = extract_google_drive_id(link_url)
                    if gdrive_id:
                        logging.info(f"{indent_str}      Fetching Google Drive item for ID: {gdrive_id} (from URL: {link_url})...")
                        gdrive_content = fetch_google_drive_item_recursive(gdrive_service, gdrive_id, visited_ids=set())
                        if gdrive_content and isinstance(issue_json["remote_links_data"][idx], dict):
                            issue_json["remote_links_data"][idx]["gdrive_content_fetched"] = gdrive_content
                            logging.info(f"{indent_str}      Successfully processed Google Drive link for ID: {gdrive_id}")
                        elif not gdrive_content:
                            logging.info(f"{indent_str}      No Google Drive content found or error for ID: {gdrive_id}")
                    else: logging.warning(f"{indent_str}      Could not extract Google Drive ID from URL: {link_url}")
                else: logging.warning(f"{indent_str}      Google Drive service not available, skipping GDrive link: {link_url}")
    
    # If this issue is an Epic, fetch its children (summaries)
    # This should only happen once per epic due to globally_processed_issue_keys check.
    # Note: The actual *processing* of these children happens when they are picked up by a worker from the queue.
    if issue_json.get('fields', {}).get('issuetype', {}).get('name') == 'Epic' and issue_key not in globally_processed_issue_keys:
        logging.info(f"{indent_str}  Epic {issue_key}: Fetching children summaries.")
        epic_children_list = fetch_epic_children(issue_key) # Returns list of issue JSONs (summaries)
        if epic_children_list:
            issue_json["epic_children_data"] = epic_children_list # Store summaries
            logging.info(f"{indent_str}    Found {len(epic_children_list)} children for Epic {issue_key}.")
        else:
            logging.info(f"{indent_str}    No children found for Epic {issue_key}.")
    
    globally_processed_issue_keys.add(issue_key)

def get_google_drive_service():
    """Initializes and returns the Google Drive API service using ADC."""
    global DRIVE_SERVICE
    if DRIVE_SERVICE is None and GOOGLE_LIBS_AVAILABLE:
        try:
            if GOOGLE_CLOUD_PROJECT:
                logging.info(f"Using GOOGLE_CLOUD_PROJECT: {GOOGLE_CLOUD_PROJECT} for ADC context if applicable.")
            credentials, project = gauth_default() 
            DRIVE_SERVICE = build('drive', 'v3', credentials=credentials)
            logging.info("Google Drive API service initialized successfully.")
            if project:
                logging.info(f"Authenticated with Google Cloud project: {project}")
            else:
                logging.info("Google Cloud project not explicitly identified by ADC, or not applicable to auth method.")
        except Exception as e:
            logging.error(f"Error initializing Google Drive service: {e}")
            return None
    return DRIVE_SERVICE

def is_google_drive_link(url_string):
    """Checks if a URL is a Google Drive link."""
    if not url_string:
        return False
    return "drive.google.com/" in url_string

def extract_google_drive_id(url_string):
    """Extracts the file or folder ID from a Google Drive URL."""
    if not url_string:
        return None
    parts = url_string.split('/')
    # Common patterns:
    # /file/d/FILE_ID/edit
    # /drive/folders/FOLDER_ID
    # /open?id=FILE_ID
    if "open?id=" in url_string:
        return url_string.split('open?id=')[1].split('&')[0]
    
    # Find 'd' for files or 'folders' for folders, then take next segment
    try:
        if '/d/' in parts:
            idx = parts.index('d')
            if idx + 1 < len(parts):
                return parts[idx+1]
        elif 'folders' in parts:
            idx = parts.index('folders')
            if idx + 1 < len(parts):
                return parts[idx+1].split('?')[0] # remove query params if any
        elif 'file' in parts: # another common pattern /file/FILE_ID
            idx = parts.index('file')
            if idx + 1 < len(parts):
                 return parts[idx+1].split('?')[0]
    except ValueError:
        logging.debug(f"Element not found during GDrive ID extraction for {url_string}")
        pass # Element not found
    
    logging.warning(f"Could not extract Google Drive ID from URL: {url_string}")
    return None

def fetch_google_drive_file_metadata(service, file_id):
    """Fetches metadata for a Google Drive file/folder."""
    if not service: return {"error": "Drive service not available"}
    logging.debug(f"Fetching GDrive metadata for: {file_id}")
    GDRIVE_SEMAPHORE.acquire()
    try:
        time.sleep(API_CALL_DELAY_SECONDS) 
        file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType, webViewLink, parents, capabilities, driveId", supportsAllDrives=True).execute()
        return file_metadata
    except HttpError as error:
        logging.error(f"An API error occurred while fetching metadata for GDrive ID {file_id}: {error}")
        return {"error": str(error), "id": file_id}
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching metadata for GDrive ID {file_id}: {e}", exc_info=True)
        return {"error": str(e), "id": file_id}
    finally:
        GDRIVE_SEMAPHORE.release()

def download_google_file_content(service, file_id, mime_type, file_name):
    """Downloads or exports Google Drive file content."""
    if not service: return {"error": "Drive service not available"}
    content_data = {"name": file_name, "id": file_id, "mime_type": mime_type, "content": None, "status": "failed"}

    request_object_for_download = None # To store the request object
    # Determine request type first without acquiring semaphore
    if mime_type == 'application/vnd.google-apps.document':
        request_object_for_download = service.files().export_media(fileId=file_id, mimeType='text/plain')
        content_data["exported_mime_type"] = 'text/plain'
    elif mime_type == 'application/vnd.google-apps.spreadsheet':
        request_object_for_download = service.files().export_media(fileId=file_id, mimeType='text/csv')
        content_data["exported_mime_type"] = 'text/csv'
    elif mime_type == 'application/vnd.google-apps.presentation':
        request_object_for_download = service.files().export_media(fileId=file_id, mimeType='text/plain')
        content_data["exported_mime_type"] = 'text/plain'
    elif mime_type.startswith('text/') or mime_type == 'application/json' or mime_type == 'application/csv':
        request_object_for_download = service.files().get_media(fileId=file_id)
    elif mime_type == 'application/pdf':
        logging.info(f"  GDrive PDF: {file_name} ({file_id}). Metadata only.")
        content_data["content"] = f"PDF file ({file_name}) metadata stored. Text extraction not implemented."
        content_data["status"] = "metadata_only (pdf)"
        return content_data
    else:
        logging.info(f"  GDrive unhandled/binary MIME type: {mime_type} for {file_name} ({file_id}). Skipping content download.")
        content_data["content"] = f"File type {mime_type} not configured for content extraction."
        content_data["status"] = "metadata_only (binary_or_unhandled)"
        return content_data

    if not request_object_for_download:
        # Should not happen if logic above is correct, but as a safeguard
        logging.error(f"  GDrive download: No request object created for {file_name} ({file_id}), mime: {mime_type}")
        content_data["error_details"] = "Internal error: download request not prepared."
        return content_data

    logging.info(f"  GDrive: Preparing to download/export {file_name} ({file_id}), mime: {mime_type}")
    GDRIVE_SEMAPHORE.acquire()
    try:
        time.sleep(API_CALL_DELAY_SECONDS)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_object_for_download)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        try:
            file_content_str = fh.read().decode('utf-8')
            content_data["content"] = file_content_str
            content_data["status"] = "success"
            logging.info(f"  Successfully fetched and decoded GDrive content for {file_name}")
        except UnicodeDecodeError:
            logging.warning(f"  Could not decode GDrive content as UTF-8 for {file_name}. Storing as binary.")
            content_data["content"] = "binary_data_not_shown_or_decoding_error"
            content_data["status"] = "error_decoding"
        return content_data
    except HttpError as error:
        logging.error(f"GDrive API error downloading/exporting {file_id}: {error}")
        content_data["error_details"] = str(error)
        return content_data
    except Exception as e:
        logging.error(f"Unexpected GDrive error downloading/exporting {file_id}: {e}", exc_info=True)
        content_data["error_details"] = str(e)
        return content_data
    finally:
        GDRIVE_SEMAPHORE.release()

def fetch_google_drive_item_recursive(service, item_id, visited_ids=None):
    """
    Fetches a Google Drive item's content (file or folder).
    If it's a folder, recursively fetches its children.
    Keeps track of visited IDs to avoid infinite loops.
    """
    if not GOOGLE_LIBS_AVAILABLE or not service:
        return {"id": item_id, "error": "Google Drive libraries or service not available."}

    if visited_ids is None:
        visited_ids = set()

    if item_id in visited_ids:
        logging.debug(f"Skipping already visited Google Drive item: {item_id}")
        return {"id": item_id, "name": "Already Visited", "status": "skipped_cyclic"}
    
    visited_ids.add(item_id)

    metadata = fetch_google_drive_file_metadata(service, item_id)
    if "error" in metadata:
        return metadata # Contains id and error message

    # Log the full metadata received for this item
    logging.debug(f"  GDrive Item Metadata for {item_id}: {json.dumps(metadata, indent=2)}")

    item_name = metadata.get("name", "Unknown GDrive Item")
    item_mime_type = metadata.get("mimeType")
    item_webview_link = metadata.get("webViewLink")
    
    logging.info(f"Processing GDrive Item: {item_name} ({item_id}), Type: {item_mime_type}")

    fetched_data = {
        "id": item_id,
        "name": item_name,
        "mime_type": item_mime_type,
        "url": item_webview_link,
        "content": None, # For files
        "children": [],  # For folders
        "status": "processed"
    }

    if item_mime_type == 'application/vnd.google-apps.folder':
        logging.info(f"  Listing contents of GDrive folder: {item_name} ({item_id})")
        try:
            #pageToken = None
            children_results = service.files().list(
                q=f"'{item_id}' in parents and trashed=false",
                fields="nextPageToken, files(id, name, mimeType, capabilities, driveId, webViewLink)", # Request more fields for children
                supportsAllDrives=True,
                #pageToken=pageToken # If handling pagination
                pageSize=100 # Max 1000, but keep reasonable for recursive depth
            ).execute()
            
            # Log the raw response from listing children
            logging.debug(f"  GDrive Raw Children List for folder {item_id}: {json.dumps(children_results, indent=2)}")

            children = children_results.get('files', [])
            if children:
                logging.info(f"  Found {len(children)} children in folder {item_name}")
                for child in children:
                    child_id = child.get("id")
                    #print(f"    Recursively fetching GDrive child: {child.get('name')} ({child_id})")
                    child_data = fetch_google_drive_item_recursive(service, child_id, visited_ids)
                    if child_data: # Append even if there was a partial error, error info is in child_data
                        fetched_data["children"].append(child_data)
            else:
                logging.info(f"  No children found in folder {item_name}")
        except HttpError as error:
            logging.error(f"  Error listing GDrive folder {item_name} ({item_id}): {error}")
            fetched_data["error"] = f"Error listing folder contents: {error}"
            fetched_data["status"] = "error_listing_folder"
        except Exception as e:
            logging.error(f"  Unexpected error listing GDrive folder {item_name} ({item_id}): {e}", exc_info=True)
            fetched_data["error"] = f"Unexpected error listing folder: {e}"
            fetched_data["status"] = "error_listing_folder_unexpected"

    else: # It's a file
        file_content_info = download_google_file_content(service, item_id, item_mime_type, item_name)
        fetched_data.update(file_content_info) # This will add 'content', 'status', and potentially 'error_details'
        if "error" in file_content_info or file_content_info.get("status") != "success":
             fetched_data["status"] = file_content_info.get("status", "fetch_failed")
             if "error_details" in file_content_info : fetched_data["error"] = file_content_info["error_details"]


    return fetched_data

def fetch_jira_issue(issue_key):
    """Fetch a single Jira issue"""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    params = {'expand': 'remotelink'}

    logging.debug(f"Fetching Jira issue: {url} with expand=remotelink")
    JIRA_SEMAPHORE.acquire()
    try:
        time.sleep(API_CALL_DELAY_SECONDS)
        response = requests.get(url, headers=headers, auth=auth, params=params)
        response.raise_for_status() # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Jira issue {issue_key}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        return None
    finally:
        JIRA_SEMAPHORE.release()

def fetch_subtasks(parent_issue_json):
    """Fetch all subtasks for a parent issue using a batch JQL query."""
    if not parent_issue_json or 'fields' not in parent_issue_json or 'subtasks' not in parent_issue_json['fields']:
        logging.debug(f"No subtasks field found or parent_issue_json invalid for {parent_issue_json.get('key', 'Unknown Key')}.")
        return []

    subtask_keys = []
    for subtask_summary in parent_issue_json['fields']['subtasks']:
        if subtask_summary and 'key' in subtask_summary:
            subtask_keys.append(subtask_summary['key'])

    if not subtask_keys:
        logging.info(f"No subtask keys found for issue {parent_issue_json.get('key', 'Unknown Key')}.")
        return []

    # Construct JQL to fetch all subtasks by their keys in one go
    # Ensure keys are quoted if they contain special characters, though Jira keys typically don't.
    # However, JQL functions sometimes expect quotes for values.
    # For issueKey in (), keys do not need to be quoted.
    jql_subtask_keys = ", ".join(subtask_keys)
    jql = f'issueKey in ({jql_subtask_keys}) ORDER BY created DESC' # Add ordering for consistency
    
    logging.info(f"Fetching details for {len(subtask_keys)} subtasks of {parent_issue_json.get('key')} using JQL: {jql[:100]}...")
    # search_jira_with_jql already handles pagination and semaphore
    # It will also expand remote links for these subtasks due to previous changes.
    detailed_subtasks = search_jira_with_jql(jql, context_log_prefix=f"  Subtasks for {parent_issue_json.get('key')} - ")
    
    return detailed_subtasks

def fetch_linked_issues(parent_issue_json):
    """Fetch issues linked to the given issue using a batch JQL query."""
    if not parent_issue_json or 'fields' not in parent_issue_json or 'issuelinks' not in parent_issue_json['fields']:
        logging.debug(f"No issuelinks field found or parent_issue_json invalid for {parent_issue_json.get('key', 'Unknown Key')}.")
        return []

    linked_issue_keys = set() # Use a set to avoid duplicate keys if linked multiple ways
    for link in parent_issue_json['fields']['issuelinks']:
        if 'inwardIssue' in link and 'key' in link['inwardIssue']:
            linked_issue_keys.add(link['inwardIssue']['key'])
        if 'outwardIssue' in link and 'key' in link['outwardIssue']:
            linked_issue_keys.add(link['outwardIssue']['key'])

    if not linked_issue_keys:
        logging.info(f"No linked issue keys found for issue {parent_issue_json.get('key', 'Unknown Key')}.")
        return []

    jql_linked_keys = ", ".join(list(linked_issue_keys))
    jql = f'issueKey in ({jql_linked_keys}) ORDER BY created DESC'
    
    logging.info(f"Fetching details for {len(linked_issue_keys)} linked issues of {parent_issue_json.get('key')} using JQL: {jql[:100]}...")
    detailed_linked_issues = search_jira_with_jql(jql, context_log_prefix=f"  Linked to {parent_issue_json.get('key')} - ")
    
    return detailed_linked_issues

def search_jira_with_jql(jql_query, context_log_prefix="  "):
    """ Helper function to search Jira with JQL, handling pagination and semaphore """
    all_issues = []
    start_at = 0
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/search"

    while True:
        params = {
            'jql': jql_query,
            'startAt': start_at,
            'maxResults': MAX_RESULTS_PER_JIRA_PAGE,
            'fields': '*all',
            'expand': 'remotelink'
        }
        logging.info(f"{context_log_prefix}Fetching JQL page: startAt={start_at}, maxResults={MAX_RESULTS_PER_JIRA_PAGE} for JQL: {jql_query[:50]}... (expanding remotelink)")
        JIRA_SEMAPHORE.acquire()
        try:
            time.sleep(API_CALL_DELAY_SECONDS)
            response = requests.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status()
            data = response.json()
            current_page_issues = data.get('issues', [])
            all_issues.extend(current_page_issues)
            total_issues_on_server = data.get('total', 0)
            if not current_page_issues or (start_at + len(current_page_issues)) >= total_issues_on_server:
                logging.info(f"{context_log_prefix}Finished fetching for JQL ({jql_query[:50]}...). Total issues retrieved: {len(all_issues)}")
                break
            start_at += len(current_page_issues)
        except requests.exceptions.RequestException as e:
            logging.error(f"{context_log_prefix}Error fetching page for JQL '{jql_query}' (startAt={start_at}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"{context_log_prefix}Response content: {e.response.text}")
            break
        finally:
            JIRA_SEMAPHORE.release()
    return all_issues

def fetch_issues_by_jql(jql_query):
    """Fetch issues based on a JQL query, handling pagination."""
    logging.info(f"Fetching issues with JQL: {jql_query}")
    return search_jira_with_jql(jql_query, context_log_prefix="  JQL Query - ")

def fetch_epic_children(epic_key):
    """Fetch all child issues for a given epic key, handling pagination."""
    logging.info(f"    Fetching children for Epic: {epic_key}...")
    jql = f'(parent = "{epic_key}" OR "Epic Link" = "{epic_key}") AND project = DWDEV' # Assuming DWDEV project context, might need generalization
    return search_jira_with_jql(jql, context_log_prefix=f"    Epic Children {epic_key} - ")

def fetch_remote_links(issue_key):
    """Fetch remote links (e.g., Confluence pages) for a given issue"""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/remotelink"
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    
    logging.debug(f"Fetching remote links for: {issue_key}")
    JIRA_SEMAPHORE.acquire()
    try:
        time.sleep(API_CALL_DELAY_SECONDS) 
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        # It's common for issues to have no remote links, so don't log an error for 404 specifically
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
            logging.debug(f"No remote links found for {issue_key} (404). This is common.")
            return []
        logging.warning(f"Error fetching remote links for {issue_key}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.warning(f"Response content for remote link error: {e.response.text}")
        return []
    finally:
        JIRA_SEMAPHORE.release()

def print_issue_summary(issue):
    """Print a formatted summary of an issue"""
    fields = issue['fields']
    
    logging.info(f"Key: {issue['key']}")
    logging.info(f"Summary: {fields['summary']}")
    logging.info(f"Status: {fields.get('status', {}).get('name', 'None')}")
    logging.info(f"Priority: {fields.get('priority', {}).get('name', 'None')}")
    
    if fields.get('assignee'):
        logging.info(f"Assignee: {fields['assignee']['displayName']}")
    else:
        logging.info("Assignee: Unassigned")
    
    logging.info(f"Created: {fields.get('created', 'N/A')[:10]}")
    logging.info(f"Updated: {fields.get('updated', 'N/A')[:10]}")
    logging.info("-" * 50)

def save_to_json(data, filename):
    """Save data to JSON file.""" # Simplified docstring
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logging.info(f"✅ Saved JSON data to: {filename}")


def fetch_issues_by_project(project_key):
    """Fetch all issues for a given project."""
    logging.info(f"Fetching all issues for project: {project_key}")
    # Construct JQL for project issues
    jql = f'project = "{project_key}" ORDER BY created DESC'
    return fetch_issues_by_jql(jql)

def worker_process_issue(issue_obj_raw, skip_remote, issues_processing_queue, master_issues_map, keys_submitted_to_executor_set, map_and_queue_lock):
    """Worker function to process a single issue and queue its related issues."""
    current_issue_key = issue_obj_raw.get('key')
    if not current_issue_key: 
        logging.warning("Worker: Skipping an issue with no key.")
        return current_issue_key, "skipped_no_key"

    try:
        logging.info(f"Worker: Starting processing for {current_issue_key}")
        
        # process_issue_fully enriches the issue_obj_raw in place
        # It uses its own globally_processed_issue_keys set for its internal deduplication of remote link/epic child fetching.
        # We pass our reference here if we want the worker to also update that global set directly.
        # However, process_issue_fully currently uses a global variable. Let's assume that's fine for now.
        process_issue_fully(issue_obj_raw, skip_remote=skip_remote)

        with map_and_queue_lock:
            master_issues_map[current_issue_key] = issue_obj_raw

        # --- Queue related items --- 
        related_to_queue = [] 

        # 1. Subtasks (fetch_subtasks returns full issue JSONs)
        subtask_summaries = fetch_subtasks(issue_obj_raw)
        if subtask_summaries:
            with map_and_queue_lock:
                if "subtasks_data" not in master_issues_map[current_issue_key]: 
                    master_issues_map[current_issue_key]["subtasks_data"] = []
            for sub_summary in subtask_summaries:
                sub_key = sub_summary.get('key')
                if sub_key:
                    with map_and_queue_lock:
                        master_issues_map[current_issue_key]["subtasks_data"].append({"key": sub_key, "summary": sub_summary.get('fields',{}).get('summary')})
                        if sub_key not in master_issues_map and sub_key not in keys_submitted_to_executor_set:
                            related_to_queue.append(sub_summary)
                            keys_submitted_to_executor_set.add(sub_key)
                            logging.info(f"Worker ({current_issue_key}): Queued subtask {sub_key}")
        
        # 2. Linked Issues (fetch_linked_issues returns full issue JSONs)
        linked_issues_summaries = fetch_linked_issues(issue_obj_raw)
        if linked_issues_summaries:
            with map_and_queue_lock:
                if "linked_issues_data" not in master_issues_map[current_issue_key]: 
                    master_issues_map[current_issue_key]["linked_issues_data"] = []
            for linked_summary in linked_issues_summaries:
                linked_key = linked_summary.get('key')
                if linked_key:
                    with map_and_queue_lock:
                        master_issues_map[current_issue_key]["linked_issues_data"].append({"key": linked_key, "summary": linked_summary.get('fields',{}).get('summary')})
                        if linked_key not in master_issues_map and linked_key not in keys_submitted_to_executor_set:
                            related_to_queue.append(linked_summary)
                            keys_submitted_to_executor_set.add(linked_key)
                            logging.info(f"Worker ({current_issue_key}): Queued linked issue {linked_key}")

        # 3. Epic Children (already part of issue_obj_raw["epic_children_data"] if it was an epic)
        # These are full issue objects from search result by fetch_epic_children
        if "epic_children_data" in issue_obj_raw: 
            for child_summary in issue_obj_raw["epic_children_data"]:
                child_key = child_summary.get('key')
                if child_key:
                    with map_and_queue_lock:
                        if child_key not in master_issues_map and child_key not in keys_submitted_to_executor_set:
                            related_to_queue.append(child_summary) 
                            keys_submitted_to_executor_set.add(child_key)
                            logging.info(f"Worker ({current_issue_key}): Queued epic child {child_key}")
        
        # Add all newly identified related items to the main processing queue
        for item in related_to_queue:
            issues_processing_queue.put(item)

        logging.info(f"Worker: Finished processing for {current_issue_key}. Queued {len(related_to_queue)} related items.")
        return current_issue_key, "success"

    except Exception as e:
        logging.error(f"Worker ({current_issue_key}): Unhandled exception: {e}", exc_info=True)
        # Optionally, mark this issue as failed in master_issues_map or a separate error list
        with map_and_queue_lock:
            if current_issue_key not in master_issues_map:
                 master_issues_map[current_issue_key] = {"key": current_issue_key, "error": str(e), "status": "worker_exception"}
            else: # It was processed by process_issue_fully but failed after
                master_issues_map[current_issue_key]["worker_error"] = str(e)
                master_issues_map[current_issue_key]["status"] = "worker_exception_post_process_fully"
        return current_issue_key, f"exception: {e}"

def main(cli_args):
    args = cli_args 

    initial_issues_to_process = []
    fetch_mode = args.mode
    fetch_identifier = args.query 

    if fetch_mode == 'issue':
        issue_key = args.query
        if not issue_key:
            logging.error("No issue key provided with --query for issue mode. Exiting.")
            return
        parent_issue_obj = fetch_jira_issue(issue_key) # Basic delay will be added inside this func
        if parent_issue_obj:
            initial_issues_to_process = [parent_issue_obj]
        else:
            logging.error(f"Could not fetch issue {issue_key}. Exiting.")
            return
    elif fetch_mode == 'jql':
        jql = args.query
        if not jql:
            logging.error("No JQL query provided with --query for jql mode. Exiting.")
            return
        initial_issues_to_process = fetch_issues_by_jql(jql) # Basic delay will be added inside this func
        if not initial_issues_to_process:
            logging.error(f"No issues found for JQL: {jql}. Exiting.")
            return
        if len(jql) > 50: 
            import hashlib
            fetch_identifier = "jql_" + hashlib.md5(jql.encode()).hexdigest()[:10]
        else:
            fetch_identifier = f"jql_{jql.replace(' ', '_').replace('=', '_').replace('(', '_').replace(')', '_')[:30]}"

    elif fetch_mode == 'project':
        project_key = args.query
        if not project_key:
            logging.error("No project key provided with --query for project mode. Exiting.")
            return
        initial_issues_to_process = fetch_issues_by_project(project_key) # Basic delay will be added inside this func
        fetch_identifier = project_key 
        if not initial_issues_to_process:
            logging.error(f"No issues found for project {project_key}. Exiting.")
            return

    logging.info(f"\nStarting Jira data fetch based on mode='{fetch_mode}', query/identifier='{fetch_identifier}', skip_remote_content={args.skip_remote_content}")
    logging.info(f"Found {len(initial_issues_to_process)} initial issue(s) to process.")
    logging.info("=" * 60)
    
    all_data = {
        "export_metadata": {
            "fetch_mode": fetch_mode,
            "fetch_identifier": fetch_identifier,
            "skip_remote_content": args.skip_remote_content,
            "exported_at": datetime.now().isoformat(),
            "base_url": JIRA_BASE_URL,
            "total_initial_issues": len(initial_issues_to_process)
        },
        "processed_issues_data": []
    }
    
    master_issues_map = {}
    # issues_to_process_queue = list(initial_issues_to_process) # Old list-based queue
    # queued_keys = {issue.get('key') for issue in issues_to_process_queue if issue.get('key')} # Old set

    # Thread-safe queue for issues to be processed by workers
    issues_processing_queue = queue.Queue()
    # Set to keep track of keys ever added to the queue or submitted to executor to avoid redundant work
    keys_submitted_to_executor_set = set() 
    # Lock for synchronized access to master_issues_map and keys_submitted_to_executor
    map_and_queue_lock = threading.Lock()

    # Populate initial queue and submitted set
    for issue_obj in initial_issues_to_process:
        key = issue_obj.get('key')
        if key:
            issues_processing_queue.put(issue_obj)
            keys_submitted_to_executor_set.add(key)
        else:
            logging.warning("Initial issue object missing a key, cannot queue.")

    processed_issue_count = 0
    # Max workers for the ThreadPoolExecutor - can be tuned
    # Should be related to, but not necessarily the sum of, API semaphores, 
    # as workers might wait on semaphores or do CPU work.
    MAX_WORKERS = 10 

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}

        # Initial submission of tasks from the queue
        while not issues_processing_queue.empty():
            try:
                current_issue_obj_raw = issues_processing_queue.get_nowait()
                current_issue_key = current_issue_obj_raw.get('key')

                if not current_issue_key:
                    logging.warning("Skipping an issue from queue with no key.")
                    issues_processing_queue.task_done() # Mark as done even if skipped
                    continue
                
                # Double check if already processed or submitted to avoid race if queue grows fast
                with map_and_queue_lock:
                    if current_issue_key in master_issues_map or current_issue_key in futures:
                        logging.debug(f"Main: Issue {current_issue_key} already processed or submitted. Skipping.")
                        issues_processing_queue.task_done()
                        continue
                
                logging.info(f"Main: Submitting {current_issue_key} to executor.")
                future = executor.submit(worker_process_issue, 
                                         current_issue_obj_raw, 
                                         args.skip_remote_content, 
                                         issues_processing_queue, # Workers can add back to this queue
                                         master_issues_map, 
                                         keys_submitted_to_executor_set, # Workers update this set for new items they queue
                                         map_and_queue_lock
                                         )
                futures[current_issue_key] = future # Track future by key
            except queue.Empty:
                break # Queue is empty for now

        # Process completed futures and any new items added to the queue by workers
        # This loop continues as long as there are active futures or items in the queue.
        active_futures = True
        while active_futures or not issues_processing_queue.empty():
            active_futures = False # Reset for this iteration
            completed_futures_this_round = []

            for key, future_obj in list(futures.items()): # Iterate over a copy for safe removal
                if future_obj.done():
                    completed_futures_this_round.append(key)
                    try:
                        processed_key, status = future_obj.result()
                        logging.info(f"Main: Future for {processed_key} completed with status: {status}")
                        processed_issue_count +=1
                    except Exception as exc:
                        logging.error(f"Main: Future for {key} generated an exception: {exc}", exc_info=True)
                        # Mark as error in master_issues_map if not already handled by worker
                        with map_and_queue_lock:
                            if key not in master_issues_map:
                                master_issues_map[key] = {"key": key, "error": str(exc), "status": "future_exception"}
                else:
                    active_futures = True # At least one future is still running
            
            for key in completed_futures_this_round:
                del futures[key] # Remove completed future

            # Check queue again for items added by workers
            while not issues_processing_queue.empty():
                try:
                    current_issue_obj_raw = issues_processing_queue.get_nowait()
                    current_issue_key = current_issue_obj_raw.get('key')

                    if not current_issue_key:
                        logging.warning("Main: Skipping an issue from queue (worker-added) with no key.")
                        issues_processing_queue.task_done()
                        continue

                    with map_and_queue_lock:
                        if current_issue_key in master_issues_map or current_issue_key in futures:
                            logging.debug(f"Main: Worker-added issue {current_issue_key} already processed/submitted. Skipping.")
                            issues_processing_queue.task_done()
                            continue
                    
                    logging.info(f"Main: Submitting worker-added task {current_issue_key} to executor.")
                    future = executor.submit(worker_process_issue, 
                                             current_issue_obj_raw, 
                                             args.skip_remote_content, 
                                             issues_processing_queue, 
                                             master_issues_map, 
                                             keys_submitted_to_executor_set, 
                                             map_and_queue_lock
                                             )
                    futures[current_issue_key] = future
                    active_futures = True # New future submitted
                except queue.Empty:
                    break
            
            if not active_futures and issues_processing_queue.empty():
                logging.info("Main: No active futures and queue is empty. Exiting processing loop.")
                break
            
            if completed_futures_this_round or active_futures: # Only sleep if work was done or is ongoing
                time.sleep(0.1) # Short sleep to prevent busy-waiting if queue is temporarily empty but futures are active

    # --- Old single-threaded loop (for reference, to be removed/commented) ---
    # while issues_to_process_queue:
    #     current_issue_obj_raw = issues_to_process_queue.pop(0) 
    # ... (rest of old loop) ...

    all_data["processed_issues_data"] = list(master_issues_map.values())
    all_data["export_metadata"]["total_unique_issues_processed"] = len(all_data["processed_issues_data"])

    logging.info(f"\nTotal distinct issues processed and stored: {len(all_data['processed_issues_data'])}")
    
    logging.info("\n" + "=" * 60)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    raw_filename = f"jira_export_{fetch_identifier.replace('/', '_').replace(':', '-')}_{timestamp}_raw.json"
    save_to_json(all_data, raw_filename)
    
    logging.info(f"\n📁 File created:")
    logging.info(f"   • {raw_filename} - Complete raw Jira data")
    
    return all_data

if __name__ == "__main__":
    # Basic logging is already configured at the module level.
    parser = argparse.ArgumentParser(description="Fetch Jira data based on issue, JQL, or project.")
    parser.add_argument("--mode", choices=["issue", "jql", "project"], required=True, help="Mode to fetch Jira data: specific issue, JQL query, or entire project.")
    parser.add_argument("--query", required=True, help="The Jira issue key, JQL query string, or Project key.")
    parser.add_argument("--skip-remote-content", action="store_true", help="Skip fetching content from Confluence and Google Drive links.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    
    cli_args = parser.parse_args()

    if cli_args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug logging enabled.")

    if GOOGLE_LIBS_AVAILABLE:
        get_google_drive_service() 
        if not DRIVE_SERVICE:
            logging.warning("Failed to initialize Google Drive Service. GDrive fetching will be skipped.")

    main(cli_args) # Pass parsed args to main
