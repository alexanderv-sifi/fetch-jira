"""RAG-specific formatting and output generation."""

import json
import os
from typing import Dict, List, Any, Tuple
from .content import ContentProcessor


class RagProcessor:
    """Handles RAG-specific document formatting and output."""
    
    @staticmethod
    def convert_confluence_to_rag(confluence_data: Dict[str, Any], 
                                 base_url: str,
                                 simplified: bool = False) -> Dict[str, Any]:
        """
        Convert Confluence page data to RAG format.
        
        Args:
            confluence_data: Raw Confluence page data
            base_url: Base URL for constructing full URLs
            simplified: Whether to use simplified format with minimal metadata
            
        Returns:
            RAG-formatted document
        """
        # Clean the main content
        base_content = ContentProcessor.clean_html_content(confluence_data.get('content', ''))
        
        # Add child page information for better context
        enhanced_content = ContentProcessor.add_child_pages_to_content(
            base_content, 
            confluence_data.get('children', []), 
            0, 
            confluence_data.get('title', '')
        )
        
        # Add labels for better searchability
        enhanced_content = ContentProcessor.add_labels_to_content(
            enhanced_content, 
            confluence_data.get('labels', [])
        )
        
        if simplified:
            # Simplified format with minimal metadata for better RAG performance
            return {
                "id": f"confluence_{confluence_data.get('id', 'unknown')}",
                "title": confluence_data.get('title', ''),
                "content": enhanced_content,
                "url": f"{base_url}{confluence_data.get('url', '')}"
            }
        else:
            # Full format with extensive metadata
            return {
                "id": f"confluence_{confluence_data.get('id', 'unknown')}",
                "title": confluence_data.get('title', ''),
                "content": enhanced_content,
                "url": f"{base_url}{confluence_data.get('url', '')}",
                "metadata": {
                    "source": "confluence",
                    "space": confluence_data.get('space'),
                    "space_name": confluence_data.get('space_name'),
                    "page_id": confluence_data.get('id'),
                    "version": confluence_data.get('version'),
                    "last_modified": confluence_data.get('last_modified'),
                    "author": confluence_data.get('author'),
                    "ancestors": confluence_data.get('ancestors', []),
                    "child_count": len(confluence_data.get('children', [])),
                    "permissions": confluence_data.get('permissions', {}),
                    "is_restricted": confluence_data.get('permissions', {}).get('is_restricted', False)
                }
            }
    
    @staticmethod
    def flatten_confluence_tree(confluence_data: Dict[str, Any], 
                               base_url: str,
                               simplified: bool = False) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Recursively flatten Confluence content tree into individual page documents.
        
        Args:
            confluence_data: Root Confluence page data
            base_url: Base URL for constructing full URLs
            simplified: Whether to use simplified format
            
        Returns:
            List of (page_id, rag_document) tuples
        """
        documents = []
        RagProcessor._flatten_tree_recursive(confluence_data, documents, base_url, simplified)
        return documents
    
    @staticmethod
    def _flatten_tree_recursive(node: Dict[str, Any], 
                               documents: List[Tuple[str, Dict[str, Any]]],
                               base_url: str,
                               simplified: bool = False):
        """Recursive helper for flattening tree."""
        if not node or node.get('error'):
            return
        
        # Convert current page to RAG format
        rag_doc = RagProcessor.convert_confluence_to_rag(node, base_url, simplified)
        page_id = node.get('id', 'unknown')
        documents.append((page_id, rag_doc))
        
        # Process children recursively
        for child in node.get('children', []):
            RagProcessor._flatten_tree_recursive(child, documents, base_url, simplified)
    
    @staticmethod
    def save_individual_jsonl_files(documents: List[Tuple[str, Dict[str, Any]]], 
                                   base_filename: str,
                                   simplified: bool = False) -> int:
        """
        Save individual JSONL files per document.
        
        Args:
            documents: List of (page_id, rag_document) tuples
            base_filename: Base filename for output directory
            simplified: Whether files are simplified format
            
        Returns:
            Number of files created
        """
        # Create directory for individual files
        dir_name = base_filename.replace('.json', '_jsonl_files')
        if simplified:
            dir_name += '_simplified'
        os.makedirs(dir_name, exist_ok=True)
        
        file_count = 0
        for page_id, rag_doc in documents:
            page_filename = os.path.join(dir_name, f"confluence_{page_id}.jsonl")
            with open(page_filename, 'w', encoding='utf-8') as f:
                f.write(json.dumps(rag_doc, ensure_ascii=False, default=str) + '\n')
            file_count += 1
        
        return file_count
    
    @staticmethod
    def save_combined_jsonl(documents: List[Tuple[str, Dict[str, Any]]], 
                           filename: str) -> int:
        """
        Save all documents to a single JSONL file.
        
        Args:
            documents: List of (page_id, rag_document) tuples
            filename: Output filename
            
        Returns:
            Number of documents saved
        """
        with open(filename, 'w', encoding='utf-8') as f:
            for page_id, rag_doc in documents:
                f.write(json.dumps(rag_doc, ensure_ascii=False, default=str) + '\n')
        
        return len(documents)