#!/usr/bin/env python3
"""
Script to check overall space content and get broader statistics.
"""

import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

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

def get_space_content_count(base_url, username, api_token, space_key="DW"):
    """Get total count of pages in the DW space."""
    auth = HTTPBasicAuth(username, api_token)
    headers = {"Accept": "application/json"}
    
    # Get space content with limit
    url = f"{base_url}/rest/api/content?spaceKey={space_key}&type=page&limit=1000"
    
    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        data = response.json()
        
        total_size = data.get('size', 0)
        total_results = len(data.get('results', []))
        
        print(f"📊 Space '{space_key}' Content Statistics:")
        print(f"   - Total pages in space: {total_size}")
        print(f"   - Pages returned in this query: {total_results}")
        
        # Show some sample pages
        print("\n📄 Sample pages in space (first 10):")
        for i, page in enumerate(data.get('results', [])[:10]):
            print(f"   {i+1}. {page.get('title')} (ID: {page.get('id')})")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching space content: {e}")
        return None

def check_parent_child_relationships(base_url, username, api_token, root_page_id="3492511763"):
    """Check if there are other parent-child relationships we might be missing."""
    auth = HTTPBasicAuth(username, api_token)
    headers = {"Accept": "application/json"}
    
    # Check if this page has any ancestors
    url = f"{base_url}/rest/api/content/{root_page_id}?expand=ancestors"
    
    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        data = response.json()
        
        ancestors = data.get('ancestors', [])
        print(f"\n🔍 Page hierarchy for {root_page_id}:")
        print(f"   - This page has {len(ancestors)} ancestors")
        
        for ancestor in ancestors:
            print(f"   📄 Ancestor: {ancestor.get('title')} (ID: {ancestor.get('id')})")
        
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error checking page ancestors: {e}")
        return None

def main():
    config = load_config()
    if not all(config.values()):
        print("❌ Error: Missing required configuration")
        sys.exit(1)
    
    print("🔍 Checking Confluence space content...")
    
    # Get overall space statistics
    space_data = get_space_content_count(
        config['confluence_base_url'],
        config['username'],
        config['api_token']
    )
    
    # Check parent-child relationships
    hierarchy_data = check_parent_child_relationships(
        config['confluence_base_url'],
        config['username'],
        config['api_token']
    )
    
    print("\n💡 Possible reasons for page count difference:")
    print("   1. Some pages might not be children of the root page")
    print("   2. Pages might have been deleted or moved since last count")
    print("   3. Permission restrictions on certain pages")
    print("   4. Different counting methodology was used previously")

if __name__ == '__main__':
    main()