"""Content processing and cleaning utilities."""

import html
import re
from typing import Dict, List, Any


class ContentProcessor:
    """Handles HTML cleaning and content enhancement."""
    
    @staticmethod
    def clean_html_content(html_content: str) -> str:
        """
        Clean HTML content for RAG ingestion with comprehensive macro handling.
        
        Args:
            html_content: Raw HTML content from Confluence
            
        Returns:
            Cleaned text content suitable for RAG
        """
        if not html_content:
            return ""
        
        content = html_content
        
        # Handle Confluence macros comprehensively
        content = ContentProcessor._extract_macro_content(content)
        
        # Remove remaining Confluence-specific tags
        content = re.sub(r'<ac:[^>]*>.*?</ac:[^>]*>', '', content, flags=re.DOTALL)
        content = re.sub(r'<ac:[^>]*/?>', '', content)
        content = re.sub(r'<ri:[^>]*/?>', '', content)
        
        # Remove HTML tags but keep the content
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Decode HTML entities
        content = html.unescape(content)
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content
    
    @staticmethod
    def _extract_macro_content(content: str) -> str:
        """Extract content from Confluence macros."""
        # Handle info/warning/tip macros
        info_pattern = r'<ac:structured-macro[^>]*ac:name="(info|warning|tip|note)"[^>]*>(.*?)</ac:structured-macro>'
        def replace_info_macro(match):
            macro_type = match.group(1).upper()
            macro_content = match.group(2)
            # Extract rich text body
            body_match = re.search(r'<ac:rich-text-body>(.*?)</ac:rich-text-body>', macro_content, re.DOTALL)
            if body_match:
                return f"[{macro_type}] {body_match.group(1)}"
            return f"[{macro_type}] {macro_content}"
        
        content = re.sub(info_pattern, replace_info_macro, content, flags=re.DOTALL)
        
        # Handle expand macros
        expand_pattern = r'<ac:structured-macro[^>]*ac:name="expand"[^>]*>(.*?)</ac:structured-macro>'
        def replace_expand_macro(match):
            macro_content = match.group(1)
            # Extract title parameter
            title_match = re.search(r'<ac:parameter ac:name="title">([^<]*)</ac:parameter>', macro_content)
            title = title_match.group(1) if title_match else "Details"
            # Extract rich text body
            body_match = re.search(r'<ac:rich-text-body>(.*?)</ac:rich-text-body>', macro_content, re.DOTALL)
            body = body_match.group(1) if body_match else ""
            return f"[EXPAND: {title}] {body}"
        
        content = re.sub(expand_pattern, replace_expand_macro, content, flags=re.DOTALL)
        
        # Handle layout macros - remove wrapper but keep content
        content = re.sub(r'<ac:layout[^>]*>(.*?)</ac:layout>', r'\1', content, flags=re.DOTALL)
        content = re.sub(r'<ac:layout-section[^>]*>(.*?)</ac:layout-section>', r'\1', content, flags=re.DOTALL)
        content = re.sub(r'<ac:layout-cell[^>]*>(.*?)</ac:layout-cell>', r'\1', content, flags=re.DOTALL)
        
        # Handle table of contents and other structural macros
        content = re.sub(r'<ac:structured-macro[^>]*ac:name="(toc|pagetreesearch|children)"[^>]*>.*?</ac:structured-macro>', 
                        '[TABLE OF CONTENTS]', content, flags=re.DOTALL)
        
        return content
    
    @staticmethod
    def add_child_pages_to_content(content: str, children_data: List[Dict[str, Any]], 
                                  level: int = 0, page_title: str = "") -> str:
        """
        Add child page information to content for better RAG context.
        
        Args:
            content: Base content
            children_data: List of child page data
            level: Current nesting level
            page_title: Title of current page
            
        Returns:
            Enhanced content with child page navigation
        """
        if not children_data:
            return content
        
        # If content is very short (likely macro-only), enhance it
        if len(content.strip()) < 50 and level == 0:
            if page_title:
                content = f"This is the {page_title} section containing documentation and guides for the following topics:"
        
        content += "\n\nChild Pages:\n"
        
        for child in children_data:
            child_id = child.get('id', 'unknown')
            child_title = child.get('title', 'Untitled')
            
            # Add indentation based on level
            indent = "  " * level
            child_description = ""
            
            # Try to get a brief description from child content
            child_content = child.get('content', '')
            if child_content:
                clean_child_content = ContentProcessor.clean_html_content(child_content)
                # Get first sentence as description
                first_sentence = clean_child_content.split('.')[0].strip()
                if len(first_sentence) > 10 and len(first_sentence) < 100:
                    child_description = f" - {first_sentence}"
            
            # Add child page entry with description
            content += f"{indent}- {child_title} (ID: {child_id}){child_description}\n"
            
            # Recursively add grandchildren
            if child.get('children'):
                content = ContentProcessor.add_child_pages_to_content(
                    content, child['children'], level + 1
                )
        
        return content
    
    @staticmethod
    def add_labels_to_content(content: str, labels: List[str]) -> str:
        """Add page labels to content for better searchability."""
        if labels:
            content += f"\n\nPage Labels: {', '.join(labels)}"
        return content