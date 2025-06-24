import json
import argparse
from datetime import datetime, timezone

def parse_datetime(iso_string):
    """Parses an ISO 8601 datetime string, handling potential timezone offsets."""
    if iso_string is None:
        return None
    # Handle 'Z' for UTC explicitly if present, otherwise assume offset or naive
    if iso_string.endswith('Z'):
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    elif '+' in iso_string or '-' in iso_string[10:]: # Check for offset after date part
        # Python's fromisoformat handles offsets like -0500 or +05:00
        # Ensure there's no unexpected '-' at the beginning for negative years (unlikely in Jira)
        try:
            dt = datetime.fromisoformat(iso_string)
        except ValueError:
            # Fallback for formats that fromisoformat might struggle with, e.g. missing seconds in offset
            # This is a basic fallback and might need refinement for specific Jira formats
            if '.' in iso_string:
                 main_part, tz_part = iso_string.rsplit('.', 1)
                 if '+' in tz_part : tz_part_main, tz_offset = tz_part.rsplit('+',1)
                 elif '-' in tz_part : tz_part_main, tz_offset = tz_part.rsplit('-',1)
                 else: tz_offset = None

                 if tz_offset and len(tz_offset) == 4: # e.g. -0500
                     iso_string = main_part + '.' + tz_part_main + ('+' if '+' in tz_part else '-') + tz_offset[:2] + ':' + tz_offset[2:]
                     dt = datetime.fromisoformat(iso_string)
                 else: # Could not reliably parse
                    print(f"Warning: Could not parse datetime string with offset: {iso_string}")
                    return None
            else:
                print(f"Warning: Could not parse datetime string: {iso_string}")
                return None


    else: # Naive datetime string (no timezone info)
        dt = datetime.fromisoformat(iso_string)
        # It's often better to assume UTC if naive, or configure based on Jira instance's timezone
        # For now, let's make it timezone-aware by assuming UTC if no info
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def analyze_workflow(export_file_path):
    """
    Analyzes Jira issue changelogs to determine handoffs, delays, and friction.

    Args:
        export_file_path (str): Path to the Jira export JSON file.
    """
    try:
        with open(export_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Export file not found at {export_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {export_file_path}")
        return

    processed_issues_data = data.get("processed_issues_data", [])
    if not processed_issues_data:
        print("No processed issue data found in the export.")
        return

    print(f"Analyzing {len(processed_issues_data)} issues from {export_file_path}\n")

    all_issue_events = {} # To store timelines for each issue

    for issue in processed_issues_data:
        issue_key = issue.get("key")
        if not issue_key:
            print("Warning: Found an issue without a key. Skipping.")
            continue

        print(f"Processing issue: {issue_key}")
        issue_events = []

        changelog = issue.get("changelog")
        if not changelog or not changelog.get("histories"):
            print(f"  - No changelog history found for {issue_key}.")
            # Even if no changelog, we can record its creation date
            created_str = issue.get("fields", {}).get("created")
            if created_str:
                created_dt = parse_datetime(created_str)
                if created_dt:
                    issue_events.append({
                        "timestamp": created_dt,
                        "author": issue.get("fields",{}).get("reporter",{}).get("displayName", "Unknown"),
                        "type": "created",
                        "field": "issue",
                        "fromString": None,
                        "toString": issue.get("fields", {}).get("status", {}).get("name", "Unknown")
                    })
            all_issue_events[issue_key] = sorted(issue_events, key=lambda x: x["timestamp"])
            continue

        # Add creation event from main fields as the first event
        created_str = issue.get("fields", {}).get("created")
        initial_status = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
        reporter = issue.get("fields",{}).get("reporter",{}).get("displayName", "Unknown")
        if created_str:
            created_dt = parse_datetime(created_str)
            if created_dt:
                issue_events.append({
                    "timestamp": created_dt,
                    "author": reporter,
                    "type": "created",
                    "field": "issue",
                    "fromString": None,
                    "toString": initial_status # Initial status at creation
                })


        for history_entry in changelog.get("histories", []):
            author_details = history_entry.get("author", {})
            author_name = author_details.get("displayName", "Unknown")
            created_timestamp_str = history_entry.get("created")
            created_dt = parse_datetime(created_timestamp_str)

            if not created_dt:
                print(f"Warning: Could not parse created timestamp '{created_timestamp_str}' for an event in {issue_key}. Skipping this history entry.")
                continue

            for item in history_entry.get("items", []):
                field_changed = item.get("field", "").lower() # Normalize to lower case
                
                # Track status changes
                if field_changed == "status":
                    issue_events.append({
                        "timestamp": created_dt,
                        "author": author_name,
                        "type": "status_change",
                        "field": "status",
                        "fromString": item.get("fromString"),
                        "toString": item.get("toString")
                    })

                # Track assignee changes (potential handoffs)
                elif field_changed == "assignee":
                    issue_events.append({
                        "timestamp": created_dt,
                        "author": author_name,
                        "type": "assignee_change",
                        "field": "assignee",
                        "fromString": item.get("fromString"), # Display name of old assignee
                        "toString": item.get("toString")   # Display name of new assignee
                    })
                
                # Future: Add logic here to track other relevant fields
                # e.g., if a custom field "Team" (customfield_XXXXX) changes.
                # elif field_changed == "team_custom_field_id_lower_case":
                #     issue_events.append({
                #         "timestamp": created_dt,
                #         "author": author_name,
                #         "type": "team_change",
                #         "field": item.get("field"), # Original field name
                #         "fromString": item.get("fromString"),
                #         "toString": item.get("toString")
                #     })

        all_issue_events[issue_key] = sorted(issue_events, key=lambda x: x["timestamp"])


    # --- Stage 2: Calculate Metrics from Events ---
    print("\n--- Metrics Calculation ---")
    for issue_key, events in all_issue_events.items():
        if not events:
            print(f"No processable events for {issue_key}.")
            continue

        print(f"\nIssue: {issue_key}")
        
        # Calculate time in each status
        time_in_status = {}
        assignee_changes = 0
        
        # Add creation as the first event if not already there from changelog
        # (Handled by adding 'created' event at the beginning of event processing for an issue)

        for i in range(len(events)):
            current_event = events[i]
            
            if current_event["type"] == "assignee_change":
                assignee_changes += 1
                print(f"  - Handoff: To {current_event['toString'] if current_event['toString'] else 'Unassigned'} (from {current_event['fromString'] if current_event['fromString'] else 'Unassigned'}) at {current_event['timestamp']}")


            if current_event["type"] == "status_change" or current_event["type"] == "created":
                status_name = current_event["toString"] # Status after this event
                if status_name is None: continue # Should not happen if toString is populated

                start_time = current_event["timestamp"]
                end_time = None

                # Find the next status change or the end of events
                next_status_event_time = None
                for j in range(i + 1, len(events)):
                    if events[j]["type"] == "status_change":
                        next_status_event_time = events[j]["timestamp"]
                        break
                
                if next_status_event_time:
                    end_time = next_status_event_time
                else:
                    # If no further status change, this status lasts until the last known event for the issue,
                    # or until now if we want to consider it ongoing.
                    # For simplicity, let's say it lasts until the last event's timestamp.
                    # A more robust way would be to consider if the issue is "resolved".
                    if events: # Check if there are any events
                         end_time = events[-1]["timestamp"] # Use timestamp of the very last event for this issue
                    else: # Should not happen if current_event exists
                        end_time = start_time


                if start_time and end_time and status_name:
                    duration = end_time - start_time
                    current_duration = time_in_status.get(status_name, timedelta(0))
                    time_in_status[status_name] = current_duration + duration
        
        print(f"  Time spent in statuses for {issue_key}:")
        for status, total_duration in time_in_status.items():
            print(f"    - {status}: {total_duration}")
        print(f"  Total assignee changes (handoffs) for {issue_key}: {assignee_changes}")

    # Future: Aggregate metrics, identify friction points, etc.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Jira issue workflow from a JSON export.")
    parser.add_argument("export_file", 
                        help="Path to the Jira export JSON file (e.g., jira_export_DWDEV-6969_YYYYMMDD_HHMMSS_raw.json)",
                        default="jira_export_DWDEV-6969_20250608_000516_raw.json",
                        nargs='?') # Makes the argument optional, using default if not provided
    
    args = parser.parse_args()
    
    # Add timedelta import here as it's used in time_in_status calculation
    from datetime import timedelta 

    analyze_workflow(args.export_file) 