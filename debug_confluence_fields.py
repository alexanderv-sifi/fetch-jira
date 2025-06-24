#!/usr/bin/env python3
"""
Debug script to fetch ALL available fields from Confluence API for specific pages.
"""

import json
import os
from dotenv import load_dotenv
from confluence_client import ConfluenceClient

# Load environment
load_dotenv()
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
USERNAME = os.getenv("JIRA_USERNAME")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Initialize client
client = ConfluenceClient(
    base_url=CONFLUENCE_BASE_URL,
    username=USERNAME,
    api_token=API_TOKEN
)

# Test pages - the onetrust page and a couple others that were small
test_pages = [
    "4027383817",  # onetrust Privacy Platform
    "3621945384",  # Security Groups  
    "3836215311"   # Miro Tableau Integration
]

for page_id in test_pages:
    print(f"\n{'='*60}")
    print(f"FETCHING RAW DATA FOR PAGE: {page_id}")
    print(f"{'='*60}")
    
    raw_data = client.fetch_page_content_raw(page_id)
    
    if raw_data and "error" not in raw_data:
        title = raw_data.get("title", "Unknown")
        print(f"Title: {title}")
        print(f"Available top-level fields: {list(raw_data.keys())}")
        
        # Check body fields
        body = raw_data.get("body", {})
        if body:
            print(f"Body fields: {list(body.keys())}")
            for body_type, body_content in body.items():
                if isinstance(body_content, dict) and "value" in body_content:
                    content_preview = body_content["value"][:200] + "..." if len(body_content["value"]) > 200 else body_content["value"]
                    print(f"  {body_type} content: {content_preview}")
        
        # Check metadata
        metadata = raw_data.get("metadata", {})
        if metadata:
            print(f"Metadata fields: {list(metadata.keys())}")
            if "labels" in metadata:
                labels = metadata["labels"]
                print(f"  Labels structure: {labels}")
        
        # Check extensions
        extensions = raw_data.get("extensions", {})
        if extensions:
            print(f"Extensions fields: {list(extensions.keys())}")
        
        # Save full raw data to file for inspection
        filename = f"raw_page_{page_id}_{title.replace(' ', '_').replace('/', '_')}.json"
        with open(filename, 'w') as f:
            json.dump(raw_data, f, indent=2)
        print(f"Full raw data saved to: {filename}")
    else:
        print(f"Error fetching page {page_id}: {raw_data}")