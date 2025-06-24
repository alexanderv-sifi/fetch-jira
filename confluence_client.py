#!/usr/bin/env python3
"""
Confluence API client module for fetch-jira utility.
Handles all interactions with Confluence REST API including page content fetching
and recursive child page processing.
"""

import requests
import logging
import time
import threading
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, List, Set, Any

class ConfluenceClient:
    """Client for interacting with Confluence REST API."""
    
    def __init__(self, base_url: str, username: str, api_token: str, 
                 max_concurrent_calls: int = 5, api_call_delay: float = 0.1):
        """
        Initialize Confluence client.
        
        Args:
            base_url: Confluence base URL (e.g., "https://domain.atlassian.net/wiki")
            username: Confluence username/email
            api_token: Confluence API token
            max_concurrent_calls: Maximum concurrent API calls
            api_call_delay: Delay between API calls in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.api_call_delay = api_call_delay
        self.auth = HTTPBasicAuth(username, api_token)
        self.headers = {"Accept": "application/json"}
        self.semaphore = threading.Semaphore(max_concurrent_calls)
        
        logging.debug(f"Initialized Confluence client for {base_url}")
    
    def fetch_page_content_raw(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch RAW content of a Confluence page with ALL fields for debugging.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            Raw dictionary with ALL page data from API
        """
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=body,space,version,metadata,history,ancestors,restrictions,container,extensions,children,descendants,operations,status"
        
        logging.info(f"Fetching RAW Confluence page data: {page_id}")
        self.semaphore.acquire()
        try:
            time.sleep(self.api_call_delay)
            response = requests.get(url, headers=self.headers, auth=self.auth)
            response.raise_for_status()
            page_data = response.json()
            return page_data  # Return everything raw
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching RAW Confluence page {page_id}: {e}")
            return {"error": str(e), "id": page_id}
        finally:
            self.semaphore.release()

    def fetch_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch content of a Confluence page.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            Dictionary with page data or error information
        """
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=body.storage,body.view,body.export_view,space,version,metadata.labels,metadata.properties,history.lastUpdated,ancestors,restrictions.read,restrictions.update,extensions"
        
        logging.debug(f"Fetching Confluence page: {page_id}")
        self.semaphore.acquire()
        try:
            time.sleep(self.api_call_delay)
            response = requests.get(url, headers=self.headers, auth=self.auth)
            response.raise_for_status()
            page_data = response.json()
            # Extract labels
            labels = []
            metadata = page_data.get("metadata", {})
            if "labels" in metadata:
                labels = [label.get("name", "") for label in metadata.get("labels", {}).get("results", [])]
                logging.info(f"Extracted labels for page {page_id}: {labels}")
            
            # Extract ancestors for breadcrumb info
            ancestors = []
            for ancestor in page_data.get("ancestors", []):
                ancestors.append({
                    "id": ancestor.get("id"),
                    "title": ancestor.get("title"),
                    "type": ancestor.get("type")
                })
            
            # Extract restrictions/permissions
            restrictions = page_data.get("restrictions", {})
            read_restrictions = restrictions.get("read", {}).get("restrictions", {})
            update_restrictions = restrictions.get("update", {}).get("restrictions", {})
            
            permissions = {
                "read_restrictions": {
                    "users": [user.get("displayName", "") for user in read_restrictions.get("user", {}).get("results", [])],
                    "groups": [group.get("name", "") for group in read_restrictions.get("group", {}).get("results", [])]
                },
                "update_restrictions": {
                    "users": [user.get("displayName", "") for user in update_restrictions.get("user", {}).get("results", [])],
                    "groups": [group.get("name", "") for group in update_restrictions.get("group", {}).get("results", [])]
                },
                "is_restricted": len(read_restrictions.get("user", {}).get("results", [])) > 0 or len(read_restrictions.get("group", {}).get("results", [])) > 0
            }
            
            # Extract space name and other metadata
            space_info = page_data.get("space", {})
            space_name = space_info.get("name", "")
            
            # Extract last modified info
            history = page_data.get("history", {})
            last_updated = history.get("lastUpdated", {})
            
            return {
                "title": page_data.get("title"),
                "url": page_data.get("_links", {}).get("webui"),
                "content": page_data.get("body", {}).get("storage", {}).get("value"),
                "space": space_info.get("key"),
                "space_name": space_name,
                "version": page_data.get("version", {}).get("number"),
                "labels": labels,
                "ancestors": ancestors,
                "permissions": permissions,
                "created_date": page_data.get("history", {}).get("createdDate"),
                "last_modified": last_updated.get("when"),
                "author": last_updated.get("by", {}).get("displayName")
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching Confluence page {page_id}: {e}")
            error_details = {"error": str(e), "id": page_id}
            if hasattr(e, 'response') and e.response is not None:
                error_details["status_code"] = e.response.status_code
                try:
                    error_details["details"] = e.response.json()
                except ValueError:
                    error_details["details"] = e.response.text
            return error_details
        finally:
            self.semaphore.release()
    
    def fetch_child_pages(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch child pages of a Confluence page with pagination support.
        
        Args:
            page_id: Parent page ID
            
        Returns:
            List of child page summaries
        """
        child_pages_summary = []
        start = 0
        limit = 100  # Increased from default 25 to reduce API calls
        
        logging.debug(f"Fetching Confluence child pages for: {page_id}")
        
        while True:
            url = f"{self.base_url}/rest/api/content/{page_id}/child/page?start={start}&limit={limit}"
            
            self.semaphore.acquire()
            try:
                time.sleep(self.api_call_delay)
                response = requests.get(url, headers=self.headers, auth=self.auth)
                response.raise_for_status()
                children_data = response.json()
                
                results = children_data.get("results", [])
                if not results:
                    # No more results, we're done
                    break
                
                for child in results:
                    child_pages_summary.append({
                        "id": child.get("id"),
                        "title": child.get("title"),
                        "url": child.get("_links", {}).get("webui")
                    })
                
                # Check if we got fewer results than requested (last page)
                if len(results) < limit:
                    break
                
                # Move to next page
                start += limit
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching child pages for Confluence page {page_id}: {e}")
                break
            finally:
                self.semaphore.release()
        
        if len(child_pages_summary) > 25:
            logging.info(f"Found {len(child_pages_summary)} child pages for {page_id} (using pagination)")
        
        return child_pages_summary
    
    def fetch_content_recursive(self, page_id: str, visited_pages: Optional[Set[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch a Confluence page's content and recursively fetch its children.
        Keeps track of visited pages to avoid infinite loops.
        
        Args:
            page_id: Page ID to fetch
            visited_pages: Set of already visited page IDs (for cycle detection)
            
        Returns:
            Dictionary with page content and children, or None if error
        """
        if visited_pages is None:
            visited_pages = set()

        if page_id in visited_pages:
            logging.debug(f"Skipping already visited Confluence page: {page_id}")
            return None
        
        visited_pages.add(page_id)

        page_content_data = self.fetch_page_content(page_id)
        if not page_content_data or "error" in page_content_data:
            return {"id": page_id, "error": page_content_data.get("error", "Failed to fetch content")}

        fetched_data = {
            "id": page_id,
            "title": page_content_data.get("title"),
            "url": page_content_data.get("url"),
            "content": page_content_data.get("content"),
            "space": page_content_data.get("space"),
            "space_name": page_content_data.get("space_name"),
            "version": page_content_data.get("version"),
            "labels": page_content_data.get("labels", []),
            "permissions": page_content_data.get("permissions", {}),
            "ancestors": page_content_data.get("ancestors", []),
            "created_date": page_content_data.get("created_date"),
            "last_modified": page_content_data.get("last_modified"),
            "author": page_content_data.get("author"),
            "children": []
        }

        child_pages_summary = self.fetch_child_pages(page_id)
        if child_pages_summary:
            logging.info(f"  Found {len(child_pages_summary)} children for Confluence page {page_id} ({page_content_data.get('title')})")
            for child_summary in child_pages_summary:
                child_id = child_summary.get("id")
                if child_id:
                    logging.info(f"    Fetching child Confluence page: {child_id} ({child_summary.get('title')})...")
                    child_full_content = self.fetch_content_recursive(child_id, visited_pages)
                    if child_full_content:
                        fetched_data["children"].append(child_full_content)
        
        return fetched_data

    @staticmethod
    def extract_page_id_from_url(url: str) -> Optional[str]:
        """
        Extract page ID from Confluence URL.
        
        Args:
            url: Confluence URL
            
        Returns:
            Page ID string or None if not found
        """
        page_id = None
        if "?pageId=" in url:
            try:
                page_id = url.split('?pageId=')[1].split('&')[0]
            except IndexError:
                logging.warning(f"Could not parse pageId from URL: {url}")
        elif "/pages/" in url:
            parts = url.split('/pages/')
            if len(parts) > 1:
                page_id_part = parts[1].split('/')[0]
                if page_id_part.isdigit():
                    page_id = page_id_part
                else:
                    logging.warning(f"Non-numeric page ID segment: {page_id_part} in URL: {url}")
            else:
                logging.warning(f"Could not parse pageId from Confluence URL structure: {url}")
        
        return page_id

    @staticmethod
    def is_confluence_url(url: str) -> bool:
        """
        Check if URL is a Confluence URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be a Confluence URL
        """
        return ("atlassian.net/wiki/spaces/" in url or 
                "/wiki/pages/" in url or 
                "/wiki/spaces/" in url)