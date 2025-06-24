#!/usr/bin/env python3
"""
Script to download a specific Confluence page and all its children recursively.
Usage: python download_confluence_page.py <page_id_or_url>
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from confluence_client import ConfluenceClient

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
    print(f"✅ Saved JSON data to: {filename}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python download_confluence_page.py <page_id_or_url>")
        print("Example: python download_confluence_page.py 3492511763")
        print("Example: python download_confluence_page.py 'https://simplifi.atlassian.net/wiki/spaces/DW/pages/3492511763/Simplifi+Employee+Technical+Guides'")
        sys.exit(1)
    
    page_input = sys.argv[1]
    
    # Load configuration
    config = load_config()
    if not all(config.values()):
        print("❌ Error: Missing required configuration in .env file")
        print("Required: CONFLUENCE_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN")
        sys.exit(1)
    
    # Initialize Confluence client
    client = ConfluenceClient(
        base_url=config['confluence_base_url'],
        username=config['username'],
        api_token=config['api_token'],
        max_concurrent_calls=5
    )
    
    # Extract page ID if URL provided
    if page_input.startswith('http'):
        page_id = client.extract_page_id_from_url(page_input)
        if not page_id:
            print(f"❌ Error: Could not extract page ID from URL: {page_input}")
            sys.exit(1)
        print(f"📄 Extracted page ID: {page_id}")
    else:
        page_id = page_input
    
    print(f"🚀 Starting download of Confluence page {page_id} and all children...")
    
    # Fetch page content recursively
    try:
        content = client.fetch_content_recursive(page_id)
        
        if not content:
            print("❌ Error: Failed to fetch page content")
            sys.exit(1)
        
        if 'error' in content:
            print(f"❌ Error fetching page: {content['error']}")
            sys.exit(1)
        
        # Prepare output data
        output_data = {
            'export_metadata': {
                'export_type': 'confluence_page_recursive',
                'page_id': page_id,
                'timestamp': datetime.now().isoformat(),
                'base_url': config['confluence_base_url']
            },
            'confluence_content': content
        }
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"confluence_export_{page_id}_{timestamp}.json"
        
        # Save to file
        save_to_json(output_data, filename)
        
        # Print summary
        def count_pages(data):
            count = 1  # Current page
            for child in data.get('children', []):
                count += count_pages(child)
            return count
        
        total_pages = count_pages(content)
        print(f"✅ Successfully downloaded {total_pages} pages")
        print(f"📄 Root page: {content.get('title', 'Unknown')}")
        print(f"🔗 URL: {content.get('url', 'Unknown')}")
        
    except Exception as e:
        print(f"❌ Error during download: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()