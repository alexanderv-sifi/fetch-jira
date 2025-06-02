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
load_dotenv()

# Configuration from environment variables
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL") # Added Confluence URL from env
USERNAME = os.getenv("JIRA_USERNAME")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") # Optional, for ADC

# Validate essential configurations
if not JIRA_BASE_URL or not USERNAME or not API_TOKEN or not CONFLUENCE_BASE_URL:
    # Use logging for this critical startup error before basicConfig might be set in main
    # Or, set up basicConfig at module level if preferred for early errors.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error("JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN, and CONFLUENCE_BASE_URL must be set.")
    exit(1)

MAX_RESULTS_PER_JIRA_PAGE = 100 # Configurable page size for Jira API calls

# Global variable for the Drive service to avoid re-initializing it repeatedly.
DRIVE_SERVICE = None

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
    try:
        file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType, webViewLink, parents, capabilities, driveId", supportsAllDrives=True).execute()
        return file_metadata
    except HttpError as error:
        logging.error(f"An API error occurred while fetching metadata for GDrive ID {file_id}: {error}")
        return {"error": str(error), "id": file_id}
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching metadata for GDrive ID {file_id}: {e}", exc_info=True)
        return {"error": str(e), "id": file_id}

def download_google_file_content(service, file_id, mime_type, file_name):
    """Downloads or exports Google Drive file content."""
    if not service: return {"error": "Drive service not available"}
    
    content_data = {"name": file_name, "id": file_id, "mime_type": mime_type, "content": None, "status": "failed"}

    try:
        # Handle Google Workspace file types by exporting them
        if mime_type == 'application/vnd.google-apps.document':
            logging.info(f"  Exporting Google Doc: {file_name} ({file_id}) as text/plain")
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            content_data["exported_mime_type"] = 'text/plain'
        elif mime_type == 'application/vnd.google-apps.spreadsheet':
            logging.info(f"  Exporting Google Sheet: {file_name} ({file_id}) as text/csv")
            request = service.files().export_media(fileId=file_id, mimeType='text/csv')
            content_data["exported_mime_type"] = 'text/csv'
        elif mime_type == 'application/vnd.google-apps.presentation':
            logging.info(f"  Exporting Google Slides: {file_name} ({file_id}) as text/plain")
            # Note: text/plain export for slides might have limited formatting.
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            content_data["exported_mime_type"] = 'text/plain'
        elif mime_type.startswith('text/') or mime_type == 'application/json' or mime_type == 'application/csv':
            logging.info(f"  Downloading text-based file: {file_name} ({file_id}) with MIME type {mime_type}")
            request = service.files().get_media(fileId=file_id)
        elif mime_type == 'application/pdf':
            logging.info(f"  Downloading PDF: {file_name} ({file_id}). Content will be metadata only for now.")
            # For PDF, we could download, but text extraction isn't implemented here.
            # For now, we'll just mark it as downloaded but won't store binary content.
            content_data["content"] = f"PDF file ({file_name}) metadata stored. Text extraction not implemented in this script."
            content_data["status"] = "metadata_only (pdf)"
            return content_data
        else: # Other binary files or types not handled for direct content extraction
            logging.info(f"  Skipping content download for unhandled/binary MIME type: {mime_type} for file {file_name} ({file_id})")
            content_data["content"] = f"File type {mime_type} not configured for content extraction."
            content_data["status"] = "metadata_only (binary_or_unhandled)"
            return content_data

        # Execute the download/export request
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            # print(F'Download {int(status.progress() * 100)}.') # Optional progress
        
        fh.seek(0)
        try:
            # Try decoding as UTF-8, which is common for text files.
            file_content_str = fh.read().decode('utf-8')
            content_data["content"] = file_content_str
            content_data["status"] = "success"
            logging.info(f"  Successfully fetched and decoded content for {file_name}")
        except UnicodeDecodeError:
            logging.warning(f"  Could not decode content as UTF-8 for {file_name}. Storing as 'binary_data_not_shown'.")
            content_data["content"] = "binary_data_not_shown_or_decoding_error"
            content_data["status"] = "error_decoding"
        
        return content_data

    except HttpError as error:
        logging.error(f"An API error occurred while downloading/exporting GDrive ID {file_id}: {error}")
        content_data["error_details"] = str(error)
        return content_data
    except Exception as e:
        logging.error(f"An unexpected error occurred while downloading/exporting GDrive ID {file_id}: {e}", exc_info=True)
        content_data["error_details"] = str(e)
        return content_data

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
    
    response = requests.get(url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Error fetching {issue_key}: {response.status_code}")
        return None

def fetch_subtasks(parent_issue_key):
    """Fetch all subtasks for a parent issue"""
    # First get the parent issue to find subtasks
    parent = fetch_jira_issue(parent_issue_key)
    
    if not parent:
        return []
    
    subtasks = []
    
    # Get direct subtasks
    if 'subtasks' in parent['fields'] and parent['fields']['subtasks']:
        for subtask in parent['fields']['subtasks']:
            subtask_data = fetch_jira_issue(subtask['key'])
            if subtask_data:
                subtasks.append(subtask_data)
    
    return subtasks

def fetch_linked_issues(issue_key):
    """Fetch issues linked to the given issue"""
    issue = fetch_jira_issue(issue_key)
    
    if not issue:
        return []
    
    linked_issues = []
    
    if 'issuelinks' in issue['fields'] and issue['fields']['issuelinks']:
        for link in issue['fields']['issuelinks']:
            # Check both inward and outward links
            if 'inwardIssue' in link:
                linked_issue_data = fetch_jira_issue(link['inwardIssue']['key'])
                if linked_issue_data:
                    linked_issues.append(linked_issue_data)
            
            if 'outwardIssue' in link:
                linked_issue_data = fetch_jira_issue(link['outwardIssue']['key'])
                if linked_issue_data:
                    linked_issues.append(linked_issue_data)
    
    return linked_issues

def search_related_issues(parent_key):
    """Search for issues in the same epic or with similar labels"""
    # JQL to find related issues
    jql_queries = [
        f'project = DWDEV AND (parent = {parent_key} OR "Epic Link" = {parent_key})',
        f'project = DWDEV AND summary ~ "{parent_key}" OR description ~ "{parent_key}"'
    ]
    
    all_issues = []
    
    for jql in jql_queries:
        url = f"{JIRA_BASE_URL}/rest/api/3/search"
        
        params = {
            'jql': jql,
            'maxResults': 100,
            'fields': 'summary,status,assignee,priority,created,updated,issuetype,parent,labels' # Added more fields for comprehensive data
        }
        
        auth = HTTPBasicAuth(USERNAME, API_TOKEN)
        headers = {"Accept": "application/json"}
        
        response = requests.get(url, headers=headers, auth=auth, params=params)
        
        if response.status_code == 200:
            data = response.json()
            all_issues.extend(data['issues'])
        else:
            logging.error(f"Error searching with JQL '{jql}': {response.status_code} - {response.text}")
    
    return all_issues

def fetch_epic_children(epic_key):
    """Fetch all child issues for a given epic key, handling pagination."""
    logging.info(f"    Fetching children for Epic: {epic_key}...")
    jql = f'(parent = "{epic_key}" OR "Epic Link" = "{epic_key}") AND project = DWDEV' # Assuming DWDEV project context, might need generalization
    
    all_epic_children = []
    start_at = 0
    
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    url = f"{JIRA_BASE_URL}/rest/api/3/search"

    while True:
        params = {
            'jql': jql,
            'startAt': start_at,
            'maxResults': MAX_RESULTS_PER_JIRA_PAGE,
            'fields': '*all' # Fetching all fields for consistency
        }
        logging.info(f"      Fetching children page: startAt={start_at}, maxResults={MAX_RESULTS_PER_JIRA_PAGE}")
        try:
            response = requests.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status()
            data = response.json()
            current_page_children = data.get('issues', [])
            all_epic_children.extend(current_page_children)

            total_children_on_server = data.get('total', 0)
            # print(f"        Fetched {len(current_page_children)} children. Total on server: {total_children_on_server}. Current count: {len(all_epic_children)}")

            if not current_page_children or (start_at + len(current_page_children)) >= total_children_on_server:
                logging.info(f"      Finished fetching children for Epic {epic_key}. Total children retrieved: {len(all_epic_children)}")
                break
            start_at += len(current_page_children)

        except requests.exceptions.RequestException as e:
            logging.error(f"      Error fetching children page for Epic {epic_key} (startAt={start_at}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                 logging.error(f"      Response content: {e.response.text}")
            break # Stop fetching on error
            
    return all_epic_children

def fetch_remote_links(issue_key):
    """Fetch remote links (e.g., Confluence pages) for a given issue"""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/remotelink"
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    
    response = requests.get(url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        return response.json()
    else:
        # It's common for issues to have no remote links, so don't print an error for 404
        if response.status_code != 404:
            logging.warning(f"Error fetching remote links for {issue_key}: {response.status_code} - {response.text}")
        return []

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

def fetch_confluence_page_content(page_id):
    """Fetch content of a Confluence page."""
    # Spaces and expand body.storage to get the raw XHTML
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}?expand=body.storage,space,version"
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()  # Raises an exception for 4XX/5XX errors
        page_data = response.json()
        return {
            "title": page_data.get("title"),
            "url": page_data.get("_links", {}).get("webui"),
            "content": page_data.get("body", {}).get("storage", {}).get("value"),
            "space": page_data.get("space", {}).get("key"),
            "version": page_data.get("version", {}).get("number")
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Confluence page {page_id}: {e}")
        # Optionally, return more specific error info or None
        error_details = {"error": str(e)}
        if hasattr(e, 'response') and e.response is not None:
            error_details["status_code"] = e.response.status_code
            try:
                error_details["details"] = e.response.json()
            except ValueError: # If response is not JSON
                error_details["details"] = e.response.text
        return error_details


def fetch_confluence_child_pages(page_id):
    """Fetch child pages of a Confluence page."""
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}/child/page"
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    
    child_pages_summary = []
    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        children_data = response.json()
        for child in children_data.get("results", []):
            child_pages_summary.append({
                "id": child.get("id"),
                "title": child.get("title"),
                "url": child.get("_links", {}).get("webui")
            })
        return child_pages_summary
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching child pages for Confluence page {page_id}: {e}")
        return [] # Return empty list on error to not break the flow


def fetch_all_confluence_content_recursive(page_id, visited_pages=None):
    """
    Fetches a Confluence page's content and recursively fetches its children.
    Keeps track of visited pages to avoid infinite loops in case of unexpected structures.
    """
    if visited_pages is None:
        visited_pages = set()

    if page_id in visited_pages:
        logging.debug(f"Skipping already visited Confluence page: {page_id}")
        return None
    
    visited_pages.add(page_id)

    page_content_data = fetch_confluence_page_content(page_id)
    if not page_content_data or "error" in page_content_data: # If fetching failed or returned an error structure
        return {"id": page_id, "error": page_content_data.get("error", "Failed to fetch content")}

    # page_content_data will now have title, url, content, space, version
    fetched_data = {
        "id": page_id,
        "title": page_content_data.get("title"),
        "url": page_content_data.get("url"),
        "content": page_content_data.get("content"),
        "space": page_content_data.get("space"),
        "version": page_content_data.get("version"),
        "children": []
    }

    child_pages_summary = fetch_confluence_child_pages(page_id)
    if child_pages_summary:
        logging.info(f"  Found {len(child_pages_summary)} children for Confluence page {page_id} ({page_content_data.get('title')})")
        for child_summary in child_pages_summary:
            child_id = child_summary.get("id")
            if child_id:
                logging.info(f"    Fetching child Confluence page: {child_id} ({child_summary.get('title')})...")
                # Recursively fetch child content
                child_full_content = fetch_all_confluence_content_recursive(child_id, visited_pages)
                if child_full_content: # Only add if successfully fetched
                    fetched_data["children"].append(child_full_content)
    
    return fetched_data

def fetch_issues_by_jql(jql_query):
    """Fetch issues based on a JQL query, handling pagination."""
    logging.info(f"Fetching issues with JQL: {jql_query}")
    
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
            'fields': '*all' 
        }
        
        logging.info(f"  Fetching page: startAt={start_at}, maxResults={MAX_RESULTS_PER_JIRA_PAGE}")
        try:
            response = requests.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()
            current_page_issues = data.get('issues', [])
            all_issues.extend(current_page_issues)

            total_issues_on_server = data.get('total', 0)
            # print(f"    Fetched {len(current_page_issues)} issues. Total on server: {total_issues_on_server}. Current count: {len(all_issues)}")

            if not current_page_issues or (start_at + len(current_page_issues)) >= total_issues_on_server:
                logging.info(f"  Finished fetching for JQL. Total issues retrieved: {len(all_issues)}")
                break 
            start_at += len(current_page_issues)
        
        except requests.exceptions.RequestException as e:
            logging.error(f"  Error fetching page for JQL '{jql_query}' (startAt={start_at}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                 logging.error(f"  Response content: {e.response.text}")
            break # Stop fetching on error for this query

    return all_issues

def fetch_issues_by_project(project_key):
    """Fetch all issues for a given project."""
    logging.info(f"Fetching all issues for project: {project_key}")
    # Construct JQL for project issues
    jql = f'project = "{project_key}" ORDER BY created DESC'
    return fetch_issues_by_jql(jql)

def main():
    # print(f"Fetching all items related to {PARENT_ISSUE}...") # Will be set later
    # print("=" * 60)

    start_choice = input("How do you want to fetch Jira data?\\n1. Specific Issue Key\\n2. JQL Query\\n3. Entire Project\\nEnter choice (1, 2, or 3): ")

    initial_issues_to_process = []
    fetch_mode = ""
    fetch_identifier = "" # For filenames and metadata

    if start_choice == '1':
        issue_key = input("Enter the Jira Issue Key (e.g., DWDEV-123): ")
        if not issue_key:
            logging.error("No issue key provided. Exiting.")
            return
        parent_issue_obj = fetch_jira_issue(issue_key)
        if parent_issue_obj:
            initial_issues_to_process = [parent_issue_obj]
            fetch_mode = "issue"
            fetch_identifier = issue_key
        else:
            logging.error(f"Could not fetch issue {issue_key}. Exiting.")
            return
    elif start_choice == '2':
        jql = input("Enter the JQL query: ")
        if not jql:
            logging.error("No JQL query provided. Exiting.")
            return
        initial_issues_to_process = fetch_issues_by_jql(jql)
        fetch_mode = "jql"
        fetch_identifier = "query_results" # Or a hash of the JQL
        if not initial_issues_to_process:
            logging.error(f"No issues found for JQL: {jql}. Exiting.")
            return
    elif start_choice == '3':
        project_key = input("Enter the Project Key (e.g., DWDEV): ")
        if not project_key:
            logging.error("No project key provided. Exiting.")
            return
        initial_issues_to_process = fetch_issues_by_project(project_key)
        fetch_mode = "project"
        fetch_identifier = project_key
        if not initial_issues_to_process:
            logging.error(f"No issues found for project {project_key}. Exiting.")
            return
    else:
        logging.error("Invalid choice. Exiting.")
        return

    logging.info(f"\nStarting Jira data fetch based on {fetch_mode}: {fetch_identifier}")
    logging.info(f"Found {len(initial_issues_to_process)} initial issue(s) to process.")
    logging.info("=" * 60)
    
    all_data = {
        "export_metadata": {
            # "parent_issue_key": PARENT_ISSUE, # Replaced by fetch_identifier and mode
            "fetch_mode": fetch_mode,
            "fetch_identifier": fetch_identifier,
            "exported_at": datetime.now().isoformat(),
            "base_url": JIRA_BASE_URL,
            "total_initial_issues": len(initial_issues_to_process)
        },
        "processed_issues_data": [] # This will hold all fully processed issues
    }
    
    # --- Helper to process an issue (print, get remote links, get epic children) ---
    # This set tracks keys for all issues processed to avoid redundant fetching of epic children or remote links.
    globally_processed_issue_keys = set() 

    def process_issue_fully(issue_json, indent_str=""):
        if not issue_json or not issue_json.get('key'):
            return
        
        issue_key = issue_json['key']
        
        # Print main issue summary
        print_issue_summary(issue_json) # Assuming print_issue_summary doesn't need indent_str yet

        # Fetch and print remote links
        # We only fetch remote links once per issue globally
        if issue_key not in globally_processed_issue_keys:
            remote_links = fetch_remote_links(issue_key)
            if remote_links:
                issue_json["remote_links_data"] = remote_links # Store in the issue dict
                logging.info(f"{indent_str}  Remote Links:")
                for idx, r_link in enumerate(remote_links):
                    link_obj = r_link.get('object', {})
                    
                    # Ensure link_obj is a dictionary before proceeding
                    if not isinstance(link_obj, dict):
                        logging.warning(f"{indent_str}    Skipping malformed remote link object: {link_obj}")
                        continue # Skip to the next remote link

                    link_title = link_obj.get('title', 'N/A')
                    link_url = link_obj.get('url', 'N/A')
                    logging.info(f"{indent_str}    - {link_title}: {link_url}")

                    # Check if it's a Confluence link and fetch content
                    if "simplifi.atlassian.net/wiki/spaces/" in link_url or "/wiki/pages/" in link_url:
                        # Extract page ID from URL (this might need to be more robust)
                        # Example: https://simplifi.atlassian.net/wiki/pages/viewpage.action?pageId=5252907051
                        # Example: https://simplifi.atlassian.net/wiki/spaces/DW/pages/5252907051/Another+Page+Title
                        page_id = None
                        if "?pageId=" in link_url:
                            try:
                                page_id = link_url.split('?pageId=')[1].split('&')[0]
                            except IndexError:
                                logging.warning(f"{indent_str}      Could not parse pageId from URL: {link_url}")
                        elif "/pages/" in link_url: # for URLs like /spacekey/pages/pageid/title
                            parts = link_url.split('/pages/')
                            if len(parts) > 1:
                                page_id_part = parts[1].split('/')[0]
                                if page_id_part.isdigit(): # check if it's a numeric ID
                                    page_id = page_id_part
                                else:
                                    logging.warning(f"{indent_str}      Non-numeric page ID segment: {page_id_part} in URL: {link_url}")
                            else:
                                logging.warning(f"{indent_str}      Could not parse pageId from Confluence URL structure: {link_url}")
                        
                        if page_id:
                            logging.info(f"{indent_str}      Fetching Confluence content for page ID: {page_id}...")
                            confluence_content = fetch_all_confluence_content_recursive(page_id)
                            if confluence_content:
                                # Ensure the remote_links_data entry exists and is a dict
                                if idx < len(issue_json["remote_links_data"]) and isinstance(issue_json["remote_links_data"][idx], dict):
                                    issue_json["remote_links_data"][idx]["confluence_content_fetched"] = confluence_content
                                else:
                                    # This case should ideally not happen if remote_links is structured as expected
                                    logging.warning(f"{indent_str}      Warning: remote_links_data structure unexpected for link {idx}. Confluence content not directly attached.")
                                    # As a fallback, append to a new list if the original structure is problematic
                                    if "confluence_pages_fallback" not in issue_json:
                                        issue_json["confluence_pages_fallback"] = []
                                    issue_json["confluence_pages_fallback"].append({"original_link": r_link, "fetched_content": confluence_content})

                                logging.info(f"{indent_str}      Successfully fetched and attached Confluence content for page ID: {page_id}")
                            else:
                                logging.info(f"{indent_str}      Failed to fetch Confluence content for page ID: {page_id}")
                        else:
                            logging.warning(f"{indent_str}      Could not determine Confluence page ID from URL: {link_url}")
                    # MOVED Google Drive logic here
                    elif GOOGLE_LIBS_AVAILABLE and is_google_drive_link(link_url):
                        gdrive_service = get_google_drive_service()
                        if gdrive_service:
                            gdrive_id = extract_google_drive_id(link_url)
                            if gdrive_id:
                                logging.info(f"{indent_str}      Fetching Google Drive content for ID: {gdrive_id} (from URL: {link_url})...")
                                # Initialize visited_ids set for each top-level GDrive call from a Jira link
                                gdrive_content = fetch_google_drive_item_recursive(gdrive_service, gdrive_id, visited_ids=set())
                                if gdrive_content:
                                    if idx < len(issue_json["remote_links_data"]) and isinstance(issue_json["remote_links_data"][idx], dict):
                                        issue_json["remote_links_data"][idx]["gdrive_content_fetched"] = gdrive_content
                                        logging.info(f"{indent_str}      Successfully processed Google Drive link for ID: {gdrive_id}")
                                    else: # Fallback, similar to Confluence
                                        logging.warning(f"{indent_str}      Warning: remote_links_data structure unexpected for link {idx}. GDrive content not directly attached to link.")
                                        if "gdrive_items_fallback" not in issue_json:
                                            issue_json["gdrive_items_fallback"] = []
                                        issue_json["gdrive_items_fallback"].append({"original_link": r_link, "fetched_gdrive_item": gdrive_content})
                                else:
                                    logging.info(f"{indent_str}      Failed to fetch or process Google Drive content for ID: {gdrive_id}")
                            else:
                                logging.warning(f"{indent_str}      Could not extract Google Drive ID from URL: {link_url}")
                        else:
                            logging.warning(f"{indent_str}      Google Drive service not available, skipping GDrive link: {link_url}")

        # If this issue is an Epic, fetch and process its children
        # We only fetch children for an epic once per issue globally
        if issue_json['fields'].get('issuetype', {}).get('name') == 'Epic' and \
           issue_key not in globally_processed_issue_keys:
            
            logging.info(f"{indent_str}  Children of Epic {issue_key}:")
            epic_children_list = fetch_epic_children(issue_key)
            if epic_children_list:
                issue_json["epic_children_data"] = epic_children_list # Store in the epic's dict
                for child_idx, child_issue in enumerate(epic_children_list):
                    logging.info(f"{indent_str}  Child {child_idx + 1}/{len(epic_children_list)} of {issue_key}:")
                    process_issue_fully(child_issue, indent_str + "    ") # Recursive call for children
            else:
                logging.info(f"{indent_str}    No children found for Epic {issue_key}.")
        
        # The following block (original Google Drive processing) is removed.
        globally_processed_issue_keys.add(issue_key) # Mark as processed after all its parts are handled

    # New processing loop for all initially fetched issues
    # This map will store all unique issues encountered, keyed by their ID.
    # The value will be the fully processed issue object.
    master_issues_map = {}

    issues_to_process_queue = list(initial_issues_to_process) # Start with the initial list
    # Keep track of keys added to the queue to avoid adding the same issue multiple times for processing
    queued_keys = {issue.get('key') for issue in issues_to_process_queue if issue.get('key')}

    processed_issue_count = 0

    while issues_to_process_queue:
        current_issue_obj_raw = issues_to_process_queue.pop(0) # Get the next issue to process
        current_issue_key = current_issue_obj_raw.get('key')

        if not current_issue_key:
            logging.warning("Skipping an issue with no key.")
            continue

        # If already fully processed and in our master map, skip reprocessing its details.
        # However, we might still want to ensure it's linked correctly if encountered via a new path.
        if current_issue_key in master_issues_map:
            logging.debug(f"Issue {current_issue_key} already processed and in master_issues_map. Skipping full reprocessing.")
            continue

        processed_issue_count += 1
        logging.info(f"\nProcessing issue {processed_issue_count} ({current_issue_key}) from queue...")
        logging.info("-" * 40)

        # `process_issue_fully` fetches remote links, GDrive, Confluence, epic children etc.
        # It uses `globally_processed_issue_keys` to avoid re-fetching these details if called again for the same issue key.
        # However, we want `process_issue_fully` to operate on the *raw* issue object and return the enriched one.
        # The current `process_issue_fully` modifies the input `issue_json` in place.
        
        # Ensure we have the full issue details if `current_issue_obj_raw` is just a summary (e.g. from a search result)
        # The JQL search in `fetch_issues_by_jql` and `fetch_issues_by_project` uses `fields: '*all'` so it should be complete.
        # If it came from `fetch_jira_issue`, it's also complete.
        # For subtasks/linked issues fetched by key later, they are also complete.
        
        # This call will enrich `current_issue_obj_raw` with remote links, GDrive, Confluence, epic children data.
        process_issue_fully(current_issue_obj_raw) 
        master_issues_map[current_issue_key] = current_issue_obj_raw # Add the fully processed issue to our map

        # Now, find related issues (subtasks, linked issues, epic children) and add them to the queue if not already processed or queued.
        # `process_issue_fully` would have populated `epic_children_data` if `current_issue_obj_raw` was an epic.
        # It also populates `remote_links_data`.

        # 1. Subtasks
        # `fetch_subtasks` gets subtask summaries. We need to add them to the queue for full processing.
        # `process_issue_fully` itself does not fetch subtasks (other than epic children).
        subtasks_summaries = fetch_subtasks(current_issue_key) # Returns list of full issue JSONs for subtasks
        if subtasks_summaries:
            # Link these subtasks to the current issue in its processed form
            if "subtasks_data" not in master_issues_map[current_issue_key]:
                master_issues_map[current_issue_key]["subtasks_data"] = []
            
            for sub_summary in subtasks_summaries:
                sub_key = sub_summary.get('key')
                if sub_key:
                    master_issues_map[current_issue_key]["subtasks_data"].append({"key": sub_key, "summary": sub_summary.get('fields',{}).get('summary')}) # Link summary
                    if sub_key not in queued_keys and sub_key not in master_issues_map:
                        issues_to_process_queue.append(sub_summary) # Add full object to queue
                        queued_keys.add(sub_key)
                        logging.info(f"  Queued subtask {sub_key} for processing.")

        # 2. Linked Issues
        # `fetch_linked_issues` gets linked issue summaries. Add to queue for full processing.
        linked_issues_summaries = fetch_linked_issues(current_issue_key) # Returns list of full issue JSONs
        if linked_issues_summaries:
            if "linked_issues_data" not in master_issues_map[current_issue_key]:
                master_issues_map[current_issue_key]["linked_issues_data"] = []

            for linked_summary in linked_issues_summaries:
                linked_key = linked_summary.get('key')
                if linked_key:
                    master_issues_map[current_issue_key]["linked_issues_data"].append({"key": linked_key, "summary": linked_summary.get('fields',{}).get('summary')}) # Link summary
                    if linked_key not in queued_keys and linked_key not in master_issues_map:
                        issues_to_process_queue.append(linked_summary) # Add full object to queue
                        queued_keys.add(linked_key)
                        logging.info(f"  Queued linked issue {linked_key} for processing.")
        
        # 3. Epic Children (if the current issue is an Epic)
        # `process_issue_fully` calls `fetch_epic_children` which returns summaries.
        # These children need to be added to the queue for full processing.
        # `process_issue_fully` stores these summaries in `epic_children_data`.
        if "epic_children_data" in master_issues_map[current_issue_key]:
            epic_children_summaries = master_issues_map[current_issue_key]["epic_children_data"]
            # `epic_children_data` as populated by `process_issue_fully` -> `fetch_epic_children` contains issue JSONs
            for child_summary in epic_children_summaries: # These are already full issue objects from search
                child_key = child_summary.get('key')
                if child_key:
                    # The link is already established by `epic_children_data`.
                    # We just need to ensure the child is queued if not processed.
                    if child_key not in queued_keys and child_key not in master_issues_map:
                        issues_to_process_queue.append(child_summary) # Add full object from epic children data
                        queued_keys.add(child_key)
                        logging.info(f"  Queued epic child {child_key} for processing.")

    # After the loop, master_issues_map contains all unique, fully processed issues.
    all_data["processed_issues_data"] = list(master_issues_map.values())
    all_data["export_metadata"]["total_unique_issues_processed"] = len(all_data["processed_issues_data"])
    # `globally_processed_issue_keys` is used by `process_issue_fully` to avoid re-fetching external data (confluence, gdrive) for an issue.
    # The number of keys in `globally_processed_issue_keys` should ideally match `len(master_issues_map)`
    # if `process_issue_fully` is called exactly once per unique issue that enters the main processing block.
    all_data["export_metadata"]["count_from_globally_processed_keys"] = len(globally_processed_issue_keys)

    logging.info(f"\nTotal distinct issues processed and stored: {len(all_data['processed_issues_data'])}")
    # logging.info(f"Total calls to process_issue_fully (deduplicated by globally_processed_issue_keys): {len(globally_processed_issue_keys)}")

    # Save to files
    logging.info("\n" + "=" * 60)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save raw data
    # Use fetch_identifier for the filename
    raw_filename = f"jira_export_{fetch_identifier.replace('/', '_')}_{timestamp}_raw.json"
    save_to_json(all_data, raw_filename)
    
    logging.info(f"\n📁 File created:")
    logging.info(f"   • {raw_filename} - Complete raw Jira data")
    
    return all_data

if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Initialize Google Drive service once at the start if libs are available
    if GOOGLE_LIBS_AVAILABLE:
        get_google_drive_service() 
        if not DRIVE_SERVICE:
            logging.warning("Failed to initialize Google Drive Service. GDrive fetching will be skipped.")
            # Optionally set GOOGLE_LIBS_AVAILABLE to False here if init failed critically
            # GOOGLE_LIBS_AVAILABLE = False 

    # Make sure to set your credentials before running!
    # The following check is now handled by the .env loading and validation at the top.
    # if USERNAME == "your-email@company.com" or API_TOKEN == "your-api-token":
    #     print("Please update USERNAME and API_TOKEN with your actual credentials!")
    #     print("Generate an API token at: https://id.atlassian.com/manage-profile/security/api-tokens")
    # else:
    #     main()
    main() # Directly call main as validation is done post-env loading
