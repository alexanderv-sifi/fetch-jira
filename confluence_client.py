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
    
    def fetch_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch content of a Confluence page.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            Dictionary with page data or error information
        """
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=body.storage,space,version"
        
        logging.debug(f"Fetching Confluence page: {page_id}")
        self.semaphore.acquire()
        try:
            time.sleep(self.api_call_delay)
            response = requests.get(url, headers=self.headers, auth=self.auth)
            response.raise_for_status()
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
        Fetch child pages of a Confluence page.
        
        Args:
            page_id: Parent page ID
            
        Returns:
            List of child page summaries
        """
        url = f"{self.base_url}/rest/api/content/{page_id}/child/page"
        
        child_pages_summary = []
        logging.debug(f"Fetching Confluence child pages for: {page_id}")
        self.semaphore.acquire()
        try:
            time.sleep(self.api_call_delay)
            response = requests.get(url, headers=self.headers, auth=self.auth)
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
            return []
        finally:
            self.semaphore.release()
    
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
            "version": page_content_data.get("version"),
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