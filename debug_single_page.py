#!/usr/bin/env python3
"""
Debug script to test label fetching for onetrust page specifically.
"""

import json
import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
USERNAME = os.getenv("JIRA_USERNAME")  
API_TOKEN = os.getenv("JIRA_API_TOKEN")

page_id = "4027383817"  # onetrust Privacy Platform

base_url = CONFLUENCE_BASE_URL.rstrip('/')
auth = HTTPBasicAuth(USERNAME, API_TOKEN)
headers = {"Accept": "application/json"}

# Test the exact expand parameter our confluence client is using
expand = "body.storage,body.view,body.export_view,space,version,metadata.labels,metadata.properties,history.lastUpdated,ancestors,restrictions.read,restrictions.update,extensions"

url = f"{base_url}/rest/api/content/{page_id}?expand={expand}"

print(f"Testing URL: {url}")
print(f"Expand: {expand}")

try:
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()
    data = response.json()
    
    print(f"\n✅ Success! Got response")
    print(f"Top-level fields: {list(data.keys())}")
    
    # Check metadata specifically
    metadata = data.get("metadata", {})
    print(f"\nMetadata structure: {metadata}")
    
    # Check if labels exist
    if "labels" in metadata:
        labels = metadata["labels"]
        print(f"\nLabels found: {labels}")
        if isinstance(labels, dict) and "results" in labels:
            for label in labels["results"]:
                print(f"  - {label.get('name', 'unknown')}")
    else:
        print(f"\n❌ No 'labels' field in metadata")
        if "_expandable" in metadata:
            print(f"Expandable fields in metadata: {metadata['_expandable']}")
    
    # Save for inspection
    with open("debug_onetrust_single.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nFull response saved to: debug_onetrust_single.json")
    
except Exception as e:
    print(f"❌ Error: {e}")
    if hasattr(e, 'response') and e.response:
        print(f"Response status: {e.response.status_code}")
        print(f"Response text: {e.response.text[:500]}")