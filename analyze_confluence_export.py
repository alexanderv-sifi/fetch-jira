#!/usr/bin/env python3
"""
Script to analyze and summarize the structure of a Confluence export.
"""

import json
import sys

def count_pages_and_structure(data, level=0):
    """Recursively count pages and show structure."""
    indent = "  " * level
    title = data.get('title', 'Unknown Title')
    page_id = data.get('id', 'Unknown ID')
    children = data.get('children', [])
    
    print(f"{indent}📄 {title} (ID: {page_id})")
    
    total_count = 1  # Current page
    for child in children:
        total_count += count_pages_and_structure(child, level + 1)
    
    return total_count

def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze_confluence_export.py <export_file.json>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("🔍 Confluence Export Analysis")
        print("=" * 50)
        
        # Show metadata
        metadata = data.get('export_metadata', {})
        print(f"Export Type: {metadata.get('export_type', 'Unknown')}")
        print(f"Page ID: {metadata.get('page_id', 'Unknown')}")
        print(f"Timestamp: {metadata.get('timestamp', 'Unknown')}")
        print(f"Base URL: {metadata.get('base_url', 'Unknown')}")
        print()
        
        # Show structure
        content = data.get('confluence_content', {})
        if content:
            print("📋 Page Structure:")
            print("-" * 30)
            total_pages = count_pages_and_structure(content)
            print()
            print(f"✅ Total pages downloaded: {total_pages}")
        else:
            print("❌ No confluence content found in export")
            
    except FileNotFoundError:
        print(f"❌ Error: File '{filename}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file '{filename}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error analyzing file: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()