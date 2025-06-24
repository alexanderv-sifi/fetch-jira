#!/usr/bin/env python3
"""
Enhanced Confluence API client that includes permissions and outputs JSONL for RAG ingestion.
"""

import requests
import logging
import time
import threading
import json
import html
import re
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, List, Set, Any
from datetime import datetime

class EnhancedConfluenceClient:
    """Enhanced Confluence client that captures permissions and outputs JSONL for RAG."""
    
    def __init__(self, base_url: str, username: str, api_token: str, 
                 max_concurrent_calls: int = 5, api_call_delay: float = 0.1):
        """Initialize enhanced Confluence client."""
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.api_token = api_token
        self.api_call_delay = api_call_delay
        self.auth = HTTPBasicAuth(username, api_token)
        self.headers = {"Accept": "application/json"}
        self.semaphore = threading.Semaphore(max_concurrent_calls)
        
        logging.debug(f"Initialized Enhanced Confluence client for {base_url}")
    
    def fetch_page_content_with_permissions(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch content of a Confluence page including permissions.
        
        Args:
            page_id: Confluence page ID
            
        Returns:
            Dictionary with page data, permissions, and metadata
        """
        # Fetch page content with expanded fields including restrictions
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=body.storage,body.view,body.export_view,space,version,metadata.labels,metadata.properties,history.lastUpdated,ancestors,restrictions.read,restrictions.update,extensions"
        
        logging.debug(f"Fetching Confluence page with permissions: {page_id}")
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
                logging.info(f"Enhanced client extracted labels for page {page_id}: {labels}")
            
            # Extract permissions
            permissions = self._extract_permissions(page_data.get('restrictions', {}))
            
            # Extract ancestors for context
            ancestors = []
            for ancestor in page_data.get('ancestors', []):
                ancestors.append({
                    'id': ancestor.get('id'),
                    'title': ancestor.get('title'),
                    'type': ancestor.get('type')
                })
            
            # Extract last modified info from history
            history = page_data.get("history", {})
            last_updated = history.get("lastUpdated", {})
            
            return {
                "id": page_data.get("id"),
                "title": page_data.get("title"),
                "url": page_data.get("_links", {}).get("webui"),
                "content": page_data.get("body", {}).get("storage", {}).get("value"),
                "space": page_data.get("space", {}).get("key"),
                "space_name": page_data.get("space", {}).get("name"),
                "version": page_data.get("version", {}).get("number"),
                "labels": labels,
                "permissions": permissions,
                "ancestors": ancestors,
                "created_date": page_data.get("history", {}).get("createdDate"),
                "last_modified": last_updated.get("when"),
                "author": last_updated.get("by", {}).get("displayName")
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching Confluence page {page_id}: {e}")
            return {"error": str(e), "id": page_id}
        finally:
            self.semaphore.release()
    
    def _extract_permissions(self, restrictions: Dict) -> Dict[str, Any]:
        """Extract permission information from restrictions."""
        permissions = {
            "read_restrictions": {
                "users": [],
                "groups": []
            },
            "update_restrictions": {
                "users": [],
                "groups": []
            },
            "is_restricted": False
        }
        
        # Check read restrictions
        read_restrictions = restrictions.get("read", {}).get("restrictions", {})
        if read_restrictions.get("user", {}).get("results"):
            permissions["read_restrictions"]["users"] = [
                user.get("displayName") for user in read_restrictions["user"]["results"]
            ]
            permissions["is_restricted"] = True
        
        if read_restrictions.get("group", {}).get("results"):
            permissions["read_restrictions"]["groups"] = [
                group.get("name") for group in read_restrictions["group"]["results"]
            ]
            permissions["is_restricted"] = True
        
        # Check update restrictions
        update_restrictions = restrictions.get("update", {}).get("restrictions", {})
        if update_restrictions.get("user", {}).get("results"):
            permissions["update_restrictions"]["users"] = [
                user.get("displayName") for user in update_restrictions["user"]["results"]
            ]
        
        if update_restrictions.get("group", {}).get("results"):
            permissions["update_restrictions"]["groups"] = [
                group.get("name") for group in update_restrictions["group"]["results"]
            ]
        
        return permissions
    
    def clean_html_content(self, html_content: str) -> str:
        """Clean HTML content for RAG ingestion."""
        if not html_content:
            return ""
        
        # Remove Confluence-specific macros
        content = re.sub(r'<ac:[^>]*>.*?</ac:[^>]*>', '', html_content, flags=re.DOTALL)
        content = re.sub(r'<ac:[^>]*/?>', '', content)
        content = re.sub(r'<ri:[^>]*/?>', '', content)
        
        # Remove HTML tags but keep the content
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Decode HTML entities
        content = html.unescape(content)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
    
    def convert_page_to_rag_format(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert page data to format suitable for Vertex AI RAG ingestion."""
        clean_content = self.clean_html_content(page_data.get('content', ''))
        
        # Create document structure for RAG
        rag_document = {
            "id": f"confluence_{page_data.get('id')}",
            "title": page_data.get('title', ''),
            "content": clean_content,
            "url": f"{self.base_url}{page_data.get('url', '')}",
            "metadata": {
                "source": "confluence",
                "space": page_data.get('space'),
                "space_name": page_data.get('space_name'),
                "page_id": page_data.get('id'),
                "version": page_data.get('version'),
                "last_modified": page_data.get('last_modified'),
                "author": page_data.get('author'),
                "ancestors": page_data.get('ancestors', []),
                "permissions": page_data.get('permissions', {}),
                "is_restricted": page_data.get('permissions', {}).get('is_restricted', False)
            }
        }
        
        return rag_document
    
    def fetch_content_recursive_with_permissions(self, page_id: str, visited_pages: Optional[Set] = None) -> Optional[Dict[str, Any]]:
        """Fetch page content recursively with permissions for all pages."""
        if visited_pages is None:
            visited_pages = set()
        
        if page_id in visited_pages:
            logging.debug(f"Skipping already visited page: {page_id}")
            return None
        
        visited_pages.add(page_id)
        
        # Fetch page content with permissions
        page_data = self.fetch_page_content_with_permissions(page_id)
        if not page_data or "error" in page_data:
            return {"id": page_id, "error": page_data.get("error", "Failed to fetch content")}
        
        # Fetch child pages
        child_pages = self.fetch_child_pages(page_id)
        children_data = []
        
        if child_pages:
            logging.info(f"  Found {len(child_pages)} children for page {page_id}")
            for child in child_pages:
                child_id = child.get("id")
                if child_id:
                    child_content = self.fetch_content_recursive_with_permissions(child_id, visited_pages)
                    if child_content:
                        children_data.append(child_content)
        
        page_data["children"] = children_data
        return page_data
    
    def fetch_child_pages(self, page_id: str) -> List[Dict[str, Any]]:
        """Fetch child pages of a Confluence page with pagination support."""
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
                logging.error(f"Error fetching child pages for page {page_id}: {e}")
                break
            finally:
                self.semaphore.release()
        
        if len(child_pages_summary) > 25:
            logging.info(f"Enhanced client found {len(child_pages_summary)} child pages for {page_id} (using pagination)")
        
        return child_pages_summary
    
    def export_to_jsonl(self, content_tree: Dict[str, Any], output_file: str):
        """Export content tree to JSONL format for Vertex AI RAG ingestion."""
        documents = []
        self._flatten_content_tree(content_tree, documents)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for doc in documents:
                rag_doc = self.convert_page_to_rag_format(doc)
                f.write(json.dumps(rag_doc, ensure_ascii=False) + '\n')
        
        logging.info(f"✅ Exported {len(documents)} documents to JSONL: {output_file}")
        return len(documents)
    
    def _flatten_content_tree(self, node: Dict[str, Any], documents: List[Dict[str, Any]]):
        """Recursively flatten content tree into list of documents."""
        # Add current page if it has content
        if not node.get("error") and node.get("content"):
            documents.append(node)
        
        # Process children
        for child in node.get("children", []):
            self._flatten_content_tree(child, documents)