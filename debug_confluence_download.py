#!/usr/bin/env python3
"""
Script to debug Confluence page download with detailed logging.
"""

import os
import sys
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from confluence_client import ConfluenceClient

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
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

def count_pages_with_details(data, level=0):
    """Count pages and show details about each."""
    indent = "  " * level
    title = data.get('title', 'Unknown Title')
    page_id = data.get('id', 'Unknown ID')
    children = data.get('children', [])
    
    print(f"{indent}📄 {title} (ID: {page_id}) - {len(children)} direct children")
    
    total_count = 1
    for child in children:
        total_count += count_pages_with_details(child, level + 1)
    
    return total_count

def main():
    page_id = "3492511763"
    
    # Load configuration
    config = load_config()
    if not all(config.values()):
        print("❌ Error: Missing required configuration")
        sys.exit(1)
    
    # Initialize client with debug logging
    client = ConfluenceClient(
        base_url=config['confluence_base_url'],
        username=config['username'],
        api_token=config['api_token'],
        max_concurrent_calls=5
    )
    
    print(f"🚀 Starting debug download of page {page_id}...")
    
    # First, test basic page fetch
    print("\n🔍 Testing basic page fetch...")
    page_content = client.fetch_page_content(page_id)
    if page_content and 'error' not in page_content:
        print(f"✅ Successfully fetched root page: {page_content.get('title')}")
    else:
        print(f"❌ Failed to fetch root page: {page_content}")
        return
    
    # Test child page fetch
    print("\n🔍 Testing child page fetch...")
    children = client.fetch_child_pages(page_id)
    print(f"✅ Found {len(children)} direct children of root page")
    for child in children[:5]:  # Show first 5
        print(f"   - {child.get('title')} (ID: {child.get('id')})")
    if len(children) > 5:
        print(f"   ... and {len(children) - 5} more")
    
    # Now do the full recursive fetch
    print("\n🚀 Starting full recursive fetch...")
    content = client.fetch_content_recursive(page_id)
    
    if not content or 'error' in content:
        print(f"❌ Error in recursive fetch: {content}")
        return
    
    print("\n📊 Final Results:")
    print("=" * 50)
    total_pages = count_pages_with_details(content)
    print(f"\n✅ Total pages downloaded: {total_pages}")
    
    # Save detailed output
    output_data = {
        'export_metadata': {
            'export_type': 'confluence_debug_recursive',
            'page_id': page_id,
            'timestamp': datetime.now().isoformat(),
            'total_pages': total_pages
        },
        'confluence_content': content
    }
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"confluence_debug_{page_id}_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"💾 Saved debug output to: {filename}")

if __name__ == '__main__':
    main()