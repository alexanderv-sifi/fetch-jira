"""Main CAKE processor that orchestrates content extraction."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from .config import CakeConfig
from ..clients.confluence_client import ConfluenceClient
from ..processors.rag import RagProcessor


class CakeProcessor:
    """Main processor for CAKE operations."""
    
    def __init__(self, config: CakeConfig):
        """Initialize processor with configuration."""
        self.config = config
        self.confluence_client = ConfluenceClient(
            base_url=config.confluence_base_url,
            username=config.jira_username,
            api_token=config.jira_api_token,
            max_concurrent_calls=config.max_concurrent_calls,
            api_call_delay=config.api_call_delay,
            timeout=config.request_timeout
        )
    
    def process_confluence_page(self, page_id: str, 
                               output_format: str = "jsonl-per-page") -> Dict[str, Any]:
        """
        Process a Confluence page and its children.
        
        Args:
            page_id: Confluence page ID to start from
            output_format: Output format ("json", "jsonl", "jsonl-per-page")
            
        Returns:
            Processing results with metadata
        """
        logging.info(f"Starting Confluence processing for page {page_id}")
        start_time = datetime.now()
        
        # Fetch content recursively
        confluence_data = self.confluence_client.fetch_content_recursive(
            page_id, 
            include_permissions=self.config.include_permissions
        )
        
        if not confluence_data or confluence_data.get('error'):
            error_msg = confluence_data.get('error', 'Unknown error') if confluence_data else 'No data returned'
            return {
                "success": False,
                "error": error_msg,
                "page_id": page_id
            }
        
        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"confluence_export_{page_id}_{timestamp}"
        
        # Process based on output format
        results = {
            "success": True,
            "page_id": page_id,
            "export_metadata": {
                "fetch_mode": "confluence",
                "fetch_identifier": f"confluence_{page_id}",
                "exported_at": start_time.isoformat(),
                "base_url": self.config.confluence_base_url,
                "include_permissions": self.config.include_permissions,
                "simplified_output": self.config.simplified_output
            },
            "files_created": []
        }
        
        if output_format == "json":
            # Save raw JSON data
            json_filename = f"{base_filename}_raw.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "export_metadata": results["export_metadata"],
                    "confluence_content": confluence_data
                }, f, indent=2, ensure_ascii=False, default=str)
            
            results["files_created"].append(json_filename)
            
        elif output_format == "jsonl":
            # Save combined JSONL
            documents = RagProcessor.flatten_confluence_tree(
                confluence_data, 
                self.config.confluence_base_url,
                self.config.simplified_output
            )
            jsonl_filename = f"{base_filename}_rag.jsonl"
            doc_count = RagProcessor.save_combined_jsonl(documents, jsonl_filename)
            
            results["files_created"].append(jsonl_filename)
            results["document_count"] = doc_count
            
        elif output_format == "jsonl-per-page":
            # Save individual JSONL files
            documents = RagProcessor.flatten_confluence_tree(
                confluence_data,
                self.config.confluence_base_url, 
                self.config.simplified_output
            )
            
            # Save raw JSON for reference
            json_filename = f"{base_filename}_raw.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "export_metadata": results["export_metadata"],
                    "confluence_content": confluence_data
                }, f, indent=2, ensure_ascii=False, default=str)
            
            # Save individual JSONL files
            file_count = RagProcessor.save_individual_jsonl_files(
                documents, 
                json_filename,
                self.config.simplified_output
            )
            
            results["files_created"].extend([json_filename, f"{json_filename.replace('.json', '_jsonl_files')}/"])
            results["document_count"] = len(documents)
            results["file_count"] = file_count
        
        # Calculate processing time
        end_time = datetime.now()
        results["processing_time"] = str(end_time - start_time)
        
        logging.info(f"✅ Confluence processing completed in {results['processing_time']}")
        
        return results
    
    def get_page_info(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get basic information about a Confluence page."""
        return self.confluence_client.fetch_page_content(page_id, include_permissions=False)