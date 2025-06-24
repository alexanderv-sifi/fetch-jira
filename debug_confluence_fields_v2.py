#!/usr/bin/env python3
"""
Debug script to fetch ALL available fields from Confluence API for specific pages.
"""

import json
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load environment
load_dotenv()
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
USERNAME = os.getenv("JIRA_USERNAME")
API_TOKEN = os.getenv("JIRA_API_TOKEN")

def fetch_page_all_fields(page_id: str) -> dict:
    """Fetch a page with comprehensive field expansion."""
    
    # Try different expand combinations to see what gives us the most data
    expand_attempts = [
        # Attempt 1: Basic comprehensive
        "body.storage,body.view,body.export_view,body.styled_view,space,version,metadata.labels,metadata.properties,metadata.frontend,history,ancestors,restrictions,extensions",
        
        # Attempt 2: Everything possible from the _expandable we saw
        "body.storage,body.view,body.export_view,body.styled_view,body.atlas_doc_format,body.editor,body.editor2,body.dynamic,body.anonymous_export_view,space,version,metadata.labels,metadata.properties,metadata.frontend,metadata.simple,metadata.comments,history,ancestors,restrictions.read,restrictions.update,extensions,children,descendants,operations,status",
        
        # Attempt 3: Just the most critical ones
        "body.storage,body.view,space,version,metadata.labels,metadata.properties,history.lastUpdated,ancestors,restrictions.read"
    ]
    
    base_url = CONFLUENCE_BASE_URL.rstrip('/')
    auth = HTTPBasicAuth(USERNAME, API_TOKEN)
    headers = {"Accept": "application/json"}
    
    for i, expand in enumerate(expand_attempts, 1):
        print(f"\nAttempt {i} - Expand: {expand[:100]}{'...' if len(expand) > 100 else ''}")
        
        url = f"{base_url}/rest/api/content/{page_id}?expand={expand}"
        
        try:
            response = requests.get(url, headers=headers, auth=auth)
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ Success! Got {len(data)} top-level fields")
            
            # Check what we got in body
            body = data.get("body", {})
            if body and "_expandable" not in str(body):
                print(f"Body fields successfully expanded: {list(body.keys())}")
                for body_type, content in body.items():
                    if isinstance(content, dict) and "value" in content:
                        value_len = len(content["value"]) if content["value"] else 0
                        print(f"  {body_type}: {value_len} characters")
            else:
                print(f"Body still unexpanded: {body}")
            
            # Check metadata
            metadata = data.get("metadata", {})
            if metadata and "_expandable" not in str(metadata):
                print(f"Metadata successfully expanded: {list(metadata.keys())}")
                labels = metadata.get("labels", {})
                if labels:
                    print(f"  Labels: {labels}")
            else:
                print(f"Metadata still unexpanded: {metadata}")
                
            return data
            
        except Exception as e:
            print(f"❌ Failed: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text[:200]}")
            continue
    
    return {}

# Test pages
test_pages = [
    ("4027383817", "onetrust Privacy Platform"),
    ("3621945384", "Security Groups"),
    ("3836215311", "Miro Tableau Integration")
]

for page_id, title in test_pages:
    print(f"\n{'='*80}")
    print(f"FETCHING ALL FIELDS FOR: {title} (ID: {page_id})")
    print(f"{'='*80}")
    
    data = fetch_page_all_fields(page_id)
    
    if data:
        # Save the best result
        filename = f"complete_page_{page_id}_{title.replace(' ', '_').replace('/', '_')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n📁 Complete data saved to: {filename}")
        
        # Print summary of what we found
        print(f"\nSUMMARY for {title}:")
        print(f"Total fields: {len(data)}")
        
        body = data.get("body", {})
        if body:
            for body_type, content in body.items():
                if isinstance(content, dict) and content.get("value"):
                    print(f"  📄 {body_type}: {len(content['value'])} chars")
                    # Show first 200 chars of content
                    preview = content["value"][:200].replace('\n', ' ')
                    print(f"      Preview: {preview}...")
        
        metadata = data.get("metadata", {})
        if metadata and metadata.get("labels"):
            labels_data = metadata["labels"]
            if isinstance(labels_data, dict) and "results" in labels_data:
                label_names = [label.get("name", "") for label in labels_data["results"]]
                print(f"  🏷️  Labels: {label_names}")
    else:
        print(f"❌ Failed to fetch data for {title}")