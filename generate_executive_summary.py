import json
from datetime import datetime, timedelta, timezone

# --- Configuration ---
JIRA_EXPORT_FILE = "jira_export_jql_4102e7e0e1_20250602_002729_raw.json" # Input file
OUTPUT_MARKDOWN_FILE = "executive_summary.md" # Output file

TEAM_MEMBERS = {
    "Corporate Systems Engineering (CSE)": [
        "Kinski Wu",
        "Kaitlin Purdham",
        "Bill Price",
        "Rodney Estrada"
    ],
    "Desktop Support (DS)": [
        "Ken Dominiec",
        "Keshon Bowman"
    ],
    "Security (SEC)": [
        "Geoffrey Schuette",
        "Daniel Sherr",
        "Tommy Mills"
    ]
}

# --- Helper Functions ---

def get_field_value(issue_fields, field_path, default=None):
    """Safely get a nested field value from issue_fields dictionary."""
    value = issue_fields
    try:
        for key in field_path.split('.'):
            if value is None: # Check if intermediate key leads to None
                return default
            value = value.get(key)
        return value if value is not None else default
    except AttributeError:
        return default

def format_date(date_str):
    """Format ISO date string to a more readable format, e.g., YYYY-MM-DD."""
    if not date_str:
        return "N/A"
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime('%Y-%m-%d')
    except ValueError:
        return date_str # Return original if parsing fails

def is_recent(date_str, days=7):
    """Check if the date_str is within the last 'days' days."""
    if not date_str:
        return False
    try:
        # Ensure the datetime object is offset-aware for comparison
        date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        # Ensure date_obj is offset-aware before this line
        if date_obj.tzinfo is None or date_obj.tzinfo.utcoffset(date_obj) is None:
             # Make it offset-aware, assuming UTC if not specified (Jira usually uses UTC)
            date_obj = date_obj.replace(tzinfo=timezone.utc)

        now_aware = datetime.now(timezone.utc)
        return (now_aware - date_obj) <= timedelta(days=days)
    except Exception:
        return False # If parsing fails or any other error

# --- Main Processing ---

def generate_summary():
    try:
        with open(JIRA_EXPORT_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{JIRA_EXPORT_FILE}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{JIRA_EXPORT_FILE}'.")
        return

    processed_issues = data.get("processed_issues_data", [])
    if not processed_issues:
        print("No issues found in the export file.")
        return

    # Reverse mapping from member to team for easier lookup
    member_to_team = {}
    for team, members in TEAM_MEMBERS.items():
        for member in members:
            member_to_team[member] = team

    team_updates = {team: {"completed": [], "in_progress": [], "blockers": []} for team in TEAM_MEMBERS}

    for issue in processed_issues:
        fields = issue.get("fields", {})
        assignee_name = get_field_value(fields, "assignee.displayName")
        
        if not assignee_name or assignee_name not in member_to_team:
            continue # Skip if no assignee or assignee not in our teams

        team_name = member_to_team[assignee_name]
        
        issue_key = issue.get("key", "N/A")
        summary = get_field_value(fields, "summary", "No summary")
        status = get_field_value(fields, "status.name", "Unknown Status")
        status_category = get_field_value(fields, "status.statusCategory.name", "Unknown").lower()
        updated_date = get_field_value(fields, "updated")
        # status_category_changed_date = get_field_value(fields, "statuscategorychangedate") # Already filtered by JQL

        # For sub-tasks, try to get parent summary for context
        parent_summary = ""
        if get_field_value(fields, "issuetype.subtask", False):
            parent_s = get_field_value(fields, "parent.fields.summary")
            if parent_s:
                parent_summary = f" (Parent: {parent_s})"

        issue_line = f"- **{issue_key}**: {summary}{parent_summary} (Status: {status}, Assignee: {assignee_name}, Updated: {format_date(updated_date)})"
        
        # --- Categorize for summary ---
        # For now, we rely on the JQL's "statusCategoryChangedDate > -1w" for recency.
        # We can add more specific date checks if needed.

        if status_category == "done":
            team_updates[team_name]["completed"].append(issue_line)
        elif status_category == "in progress" or status_category == "indeterminate": # 'indeterminate' often means 'in progress'
            team_updates[team_name]["in_progress"].append(issue_line)
        # Add blocker detection logic here if specific statuses/keywords are used for blockers
        # For example:
        # if "blocked" in status.lower() or "blocker" in summary.lower():
        #     team_updates[team_name]["blockers"].append(issue_line)


    # --- Generate Markdown Output ---
    with open(OUTPUT_MARKDOWN_FILE, 'w') as md_file:
        md_file.write(f"# Weekly Engineering Update - {datetime.now().strftime('%Y-%m-%d')}\\n\\n")
        
        for team_name, updates in team_updates.items():
            md_file.write(f"## {team_name}\\n\\n")
            
            if updates["completed"]:
                md_file.write("### ✅ Key Accomplishments / Recently Completed\\n")
                for item in updates["completed"]:
                    md_file.write(f"{item}\\n")
                md_file.write("\\n")
            
            if updates["in_progress"]:
                md_file.write("### 🚧 Ongoing Key Initiatives / In Progress\\n")
                for item in updates["in_progress"]:
                    md_file.write(f"{item}\\n")
                md_file.write("\\n")

            if updates["blockers"]: # Only show if there are blockers
                md_file.write("### 🛑 Blockers / Needs Attention\\n")
                for item in updates["blockers"]:
                    md_file.write(f"{item}\\n")
                md_file.write("\\n")
            
            if not updates["completed"] and not updates["in_progress"] and not updates["blockers"]:
                md_file.write("*No significant updates for the past week.*\\n\\n")
            
            md_file.write("---\\n\\n") # Separator between teams

    print(f"Executive summary generated: {OUTPUT_MARKDOWN_FILE}")

if __name__ == "__main__":
    generate_summary() 