"""Unified Confluence API client."""

import logging
from typing import Dict, List, Optional, Set, Any
from .base import BaseClient


class ConfluenceClient(BaseClient):
    """Unified Confluence client with comprehensive field extraction."""
    
    def fetch_page_content(self, page_id: str, include_permissions: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch content of a Confluence page with comprehensive field expansion.
        
        Args:
            page_id: Confluence page ID
            include_permissions: Whether to include permission data
            
        Returns:
            Dictionary with page data, permissions, and metadata
        """
        # Comprehensive field expansion
        expand_fields = [
            "body.storage", "body.view", "body.export_view", 
            "space", "version", "metadata.labels", "metadata.properties",
            "history.lastUpdated", "ancestors", "extensions"
        ]
        
        if include_permissions:
            expand_fields.extend(["restrictions.read", "restrictions.update"])
        
        url = f"{self.base_url}/rest/api/content/{page_id}"
        params = {"expand": ",".join(expand_fields)}
        
        logging.debug(f"Fetching Confluence page: {page_id}")
        
        try:
            page_data = self._make_request(url, params)
            
            # Extract comprehensive metadata
            result = {
                "id": page_data.get("id"),
                "title": page_data.get("title"),
                "url": page_data.get("_links", {}).get("webui"),
                "content": page_data.get("body", {}).get("storage", {}).get("value"),
                "space": page_data.get("space", {}).get("key"),
                "space_name": page_data.get("space", {}).get("name"),
                "version": page_data.get("version", {}).get("number"),
                "created_date": page_data.get("history", {}).get("createdDate"),
                "author": page_data.get("version", {}).get("by", {}).get("displayName")
            }
            
            # Extract labels
            labels = []
            metadata = page_data.get("metadata", {})
            if "labels" in metadata:
                labels = [label.get("name", "") for label in metadata.get("labels", {}).get("results", [])]
                if labels:
                    logging.debug(f"Extracted labels for page {page_id}: {labels}")
            result["labels"] = labels
            
            # Extract last modified info
            history = page_data.get("history", {})
            last_updated = history.get("lastUpdated", {})
            if last_updated:
                result["last_modified"] = last_updated.get("when")
                result["author"] = last_updated.get("by", {}).get("displayName")
            
            # Extract ancestors for context
            ancestors = []
            for ancestor in page_data.get("ancestors", []):
                ancestors.append({
                    "id": ancestor.get("id"),
                    "title": ancestor.get("title"),
                    "type": ancestor.get("type")
                })
            result["ancestors"] = ancestors
            
            # Extract permissions if requested
            if include_permissions:
                result["permissions"] = self._extract_permissions(page_data.get("restrictions", {}))
            
            return result
            
        except Exception as e:
            logging.error(f"Error fetching Confluence page {page_id}: {e}")
            return {"error": str(e), "id": page_id}
    
    def fetch_child_pages(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Fetch child pages of a Confluence page with pagination support.
        
        Args:
            page_id: Parent page ID
            
        Returns:
            List of child page summaries
        """
        url = f"{self.base_url}/rest/api/content/{page_id}/child/page"
        
        logging.debug(f"Fetching Confluence child pages for: {page_id}")
        
        try:
            results = self._paginated_request(url, limit=100)
            
            child_pages = []
            for child in results:
                child_pages.append({
                    "id": child.get("id"),
                    "title": child.get("title"),
                    "url": child.get("_links", {}).get("webui")
                })
            
            return child_pages
            
        except Exception as e:
            logging.error(f"Error fetching child pages for page {page_id}: {e}")
            return []
    
    def fetch_content_recursive(self, page_id: str, visited_pages: Optional[Set[str]] = None,
                               include_permissions: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetch a Confluence page's content and recursively fetch its children.
        
        Args:
            page_id: Root page ID
            visited_pages: Set of already visited page IDs (for loop detection)
            include_permissions: Whether to include permission data
            
        Returns:
            Nested dictionary with page content and children
        """
        if visited_pages is None:
            visited_pages = set()
        
        if page_id in visited_pages:
            logging.debug(f"Skipping already visited page: {page_id}")
            return None
        
        visited_pages.add(page_id)
        
        # Fetch page content
        page_data = self.fetch_page_content(page_id, include_permissions)
        if not page_data or "error" in page_data:
            return page_data
        
        # Fetch child pages
        child_pages = self.fetch_child_pages(page_id)
        children_data = []
        
        if child_pages:
            logging.info(f"  Found {len(child_pages)} children for page {page_id}")
            for child in child_pages:
                child_id = child.get("id")
                if child_id:
                    child_content = self.fetch_content_recursive(
                        child_id, visited_pages, include_permissions
                    )
                    if child_content:
                        children_data.append(child_content)
        
        page_data["children"] = children_data
        return page_data
    
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