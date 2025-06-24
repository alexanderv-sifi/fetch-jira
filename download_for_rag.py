#!/usr/bin/env python3
"""
Script to download Confluence content with permissions for RAG ingestion.
Outputs both detailed JSON and JSONL format for Vertex AI.
"""

import os
import sys
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from enhanced_confluence_client import EnhancedConfluenceClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_config():
    """Load configuration from .env file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dotenv_path = os.path.join(script_dir, '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)
    
    return {
        'confluence_base_url': os.getenv('CONFLUENCE_BASE_URL'),
        'username': os.getenv('JIRA_USERNAME'),
        'api_token': os.getenv('JIRA_API_TOKEN')
    }

def save_to_json(data, filename):
    """Save data to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"✅ Saved detailed JSON to: {filename}")

def count_pages_and_restrictions(data, level=0):
    """Count pages and analyze restrictions."""
    indent = "  " * level
    title = data.get('title', 'Unknown Title')
    page_id = data.get('id', 'Unknown ID')
    permissions = data.get('permissions', {})
    is_restricted = permissions.get('is_restricted', False)
    children = data.get('children', [])
    
    restriction_info = ""
    if is_restricted:
        read_users = len(permissions.get('read_restrictions', {}).get('users', []))
        read_groups = len(permissions.get('read_restrictions', {}).get('groups', []))
        restriction_info = f" 🔒 (Users: {read_users}, Groups: {read_groups})"
    
    print(f"{indent}📄 {title} (ID: {page_id}){restriction_info}")
    
    total_count = 1
    restricted_count = 1 if is_restricted else 0
    
    for child in children:
        child_total, child_restricted = count_pages_and_restrictions(child, level + 1)
        total_count += child_total
        restricted_count += child_restricted
    
    return total_count, restricted_count

def main():
    if len(sys.argv) != 2:
        print("Usage: python download_for_rag.py <page_id_or_url>")
        print("Example: python download_for_rag.py 3492511763")
        sys.exit(1)
    
    page_input = sys.argv[1]
    
    # Load configuration
    config = load_config()
    if not all(config.values()):
        print("❌ Error: Missing required configuration in .env file")
        sys.exit(1)
    
    # Initialize enhanced client
    client = EnhancedConfluenceClient(
        base_url=config['confluence_base_url'],
        username=config['username'],
        api_token=config['api_token'],
        max_concurrent_calls=3  # Reduced for permission queries
    )
    
    # Extract page ID if URL provided
    if page_input.startswith('http'):
        # Simple extraction for this example
        import re
        match = re.search(r'/pages/(\d+)/', page_input)
        if match:
            page_id = match.group(1)
            print(f"📄 Extracted page ID: {page_id}")
        else:
            print(f"❌ Error: Could not extract page ID from URL")
            sys.exit(1)
    else:
        page_id = page_input
    
    print(f"🚀 Starting enhanced download with permissions for page {page_id}...")
    
    # Fetch content with permissions
    try:
        content = client.fetch_content_recursive_with_permissions(page_id)
        
        if not content or 'error' in content:
            print(f"❌ Error fetching content: {content}")
            sys.exit(1)
        
        # Generate filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f"confluence_rag_{page_id}_{timestamp}.json"
        jsonl_filename = f"confluence_rag_{page_id}_{timestamp}.jsonl"
        
        # Prepare detailed output data
        output_data = {
            'export_metadata': {
                'export_type': 'confluence_rag_enhanced',
                'page_id': page_id,
                'timestamp': datetime.now().isoformat(),
                'base_url': config['confluence_base_url'],
                'includes_permissions': True,
                'output_format': 'both_json_and_jsonl'
            },
            'confluence_content': content
        }
        
        # Save detailed JSON
        save_to_json(output_data, json_filename)
        
        # Export to JSONL for RAG
        doc_count = client.export_to_jsonl(content, jsonl_filename)
        
        # Analyze results
        print("\n📊 Content Analysis:")
        print("=" * 50)
        total_pages, restricted_pages = count_pages_and_restrictions(content)
        
        print(f"\n✅ Export Complete:")
        print(f"   📄 Total pages processed: {total_pages}")
        print(f"   🔒 Pages with restrictions: {restricted_pages}")
        print(f"   📁 Detailed JSON: {json_filename}")
        print(f"   📋 RAG JSONL: {jsonl_filename}")
        print(f"   🎯 Documents for RAG ingestion: {doc_count}")
        
        if restricted_pages > 0:
            print(f"\n⚠️  Note: {restricted_pages} pages have access restrictions.")
            print("   Consider these permissions when setting up RAG access controls.")
        
    except Exception as e:
        print(f"❌ Error during download: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()