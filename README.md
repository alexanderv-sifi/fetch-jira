# Fetch Jira

`fetch-jira` is a Python utility designed to comprehensively extract data from Jira, including issue details, subtasks, linked issues, and epic children. It can also fetch content from linked Confluence pages and Google Drive files. The aggregated data is saved into a structured JSON file, suitable for analysis or input into other systems.

## Features

*   **Multiple Fetch Modes:** Retrieve Jira data based on:
    *   Specific Issue Key
    *   JQL (Jira Query Language) Query
    *   Entire Project Key
*   **Deep Data Extraction:** Fetches not only primary issue details but also:
    *   Subtasks
    *   Linked issues (inward and outward)
    *   Children of Epics
*   **Remote Content Retrieval:**
    *   Fetches content from linked Confluence pages (including child pages recursively).
    *   Fetches metadata and content from linked Google Drive files and folders (supports Google Docs, Sheets, Slides export to text/csv, and other file types).
*   **Concurrency:** Utilizes threading and semaphores for efficient, concurrent API calls to Jira, Confluence, and Google Drive, respecting potential rate limits.
*   **Configuration:** Uses a `.env` file for easy configuration of API endpoints and credentials.
*   **Output:** Generates a detailed JSON file containing all fetched data, including a metadata section about the export.
*   **Flexible Content Fetching:** Option to skip fetching remote content from Confluence and Google Drive for faster metadata-only exports.
*   **Targeted Issue and Children Fetch:** By using the `issue` mode with a specific issue ID, you can fetch that issue along with its direct children (subtasks, linked issues, and children of an Epic). The script will then also process these children to retrieve their full details.

## Prerequisites

*   Python 3.12 or higher
*   `uv` (Python package installer and virtual environment manager, recommended for running)
*   Access credentials for Jira and Confluence.
*   If using Google Drive integration:
    *   Google Cloud Project set up for Application Default Credentials (ADC).
    *   Required Google API libraries (`google-api-python-client`, `google-auth`).

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd fetch-jira
    ```

2.  **Install dependencies:**
    It's recommended to use `uv` to manage dependencies and run the script. If you don't have `uv`, please install it first.
    ```bash
    uv pip install -r requirements.txt 
    # Or, if you are managing dependencies through pyproject.toml with uv:
    # uv pip sync 
    ```
    If you intend to use the Google Drive fetching capabilities, ensure the necessary libraries are installed:
    ```bash
    uv pip install google-api-python-client google-auth
    ```
    The script will warn you if these are missing and Google Drive functionality is attempted.

3.  **Create and configure the `.env` file:**
    Create a file named `.env` in the root directory of the project and add the following environment variables:

    ```env
    JIRA_BASE_URL="https://your-domain.atlassian.net"
    JIRA_USERNAME="your-jira-email@example.com"
    JIRA_API_TOKEN="your-jira-api-token"
    CONFLUENCE_BASE_URL="https://your-domain.atlassian.net/wiki" # Or your Confluence base URL

    # Optional: For Google Drive integration
    # GOOGLE_CLOUD_PROJECT="your-gcp-project-id" 
    # Ensure Application Default Credentials (ADC) are configured for Google Drive access.
    # This can be done by running `gcloud auth application-default login`.
    ```
    *   Replace placeholders with your actual Jira URL, username, API token, and Confluence URL.
    *   For `JIRA_API_TOKEN`, generate one from your Atlassian account settings.
    *   If using Google Drive integration, uncomment and set `GOOGLE_CLOUD_PROJECT` if needed for your ADC setup, and ensure your environment is authenticated with Google Cloud.

## Usage

The script is run via the `jira-fetcher` command-line interface (if installed as a package) or by directly executing `jira-fetcher.py` using `uv run`.

**General command structure:**

```bash
uv run jira-fetcher.py --mode <mode> --query <query_string> [options]
```
Or, if installed as a package (e.g., via `uv pip install .`):
```bash
jira-fetcher --mode <mode> --query <query_string> [options]
```

**Arguments:**

*   `--mode`: (Required) The mode for fetching data.
    *   `issue`: Fetch a single issue and its related data.
    *   `jql`: Fetch issues based on a JQL query.
    *   `project`: Fetch all issues for a specific project.
*   `--query`: (Required) The identifier for the fetch operation.
    *   For `issue` mode: The Jira issue key (e.g., `DWDEV-123`).
    *   For `jql` mode: The JQL query string (e.g., `project = DWDEV AND status = "In Progress"`).
    *   For `project` mode: The Jira project key (e.g., `DWDEV`).
*   `--skip-remote-content`: (Optional) If set, the script will fetch metadata for Confluence and Google Drive links but will not download their actual content.
*   `--debug`: (Optional) Enables detailed debug logging.

**Examples:**

1.  **Fetch a specific issue:**
    ```bash
    uv run jira-fetcher.py --mode issue --query DWDEV-6812
    ```

2.  **Fetch issues using a JQL query:**
    ```bash
    uv run jira-fetcher.py --mode jql --query "project = DWDEV AND issuetype = Epic AND status = Open ORDER BY created DESC"
    ```

3.  **Fetch all issues for a project and skip remote content:**
    ```bash
    uv run jira-fetcher.py --mode project --query DWDEV --skip-remote-content
    ```

4.  **Fetch a specific issue with debug logging:**
    ```bash
    uv run jira-fetcher.py --mode issue --query MYPROJ-101 --debug
    ```

5.  **Fetch a specific issue and its children (subtasks, linked issues, epic children):**
    ```bash
    uv run jira-fetcher.py --mode issue --query PARENT-123
    ```
    The output JSON for `PARENT-123` will contain sections like `subtasks_data`, `linked_issues_data`, and `epic_children_data` listing these children. The full details of these children will also typically be fetched and included as separate entries in the main `processed_issues_data` list as the script processes them from its queue.

## Output

The script generates a JSON file in the root directory named according to the fetch parameters and timestamp, e.g., `jira_export_DWDEV-6812_YYYYMMDD_HHMMSS_raw.json` or `jira_export_jql_xxxxxxxxxx_YYYYMMDD_HHMMSS_raw.json`.

This JSON file contains:
*   `export_metadata`: Information about the fetch operation (mode, query, timestamp, etc.).
*   `processed_issues_data`: A list of all processed Jira issues. Each issue object includes:
    *   Standard Jira issue fields.
    *   `remote_links_data`: Information about linked Confluence pages or Google Drive files, potentially including their fetched content (`confluence_content_fetched`, `gdrive_content_fetched`).
    *   `epic_children_data`: If the issue is an Epic, a list of its child issues (summaries).
    *   `subtasks_data`: A list of subtasks linked to the issue.
    *   `linked_issues_data`: A list of other issues linked to this one.

## Development / Running Locally

Ensure Python 3.12+ and `uv` are installed.

1.  Clone the repository.
2.  Set up your `.env` file as described in the "Setup" section.
3.  You can run the script directly:
    ```bash
    uv run jira-fetcher.py --mode issue --query YOUR-ISSUE-KEY
    ```

### Architecture Notes

The project is being modularized for better maintainability:
- **✅ `confluence_client.py`**: Standalone Confluence API client (completed)
- **🔄 Planned**: Separate modules for Jira client, Google Drive client, data processing, and configuration management

See `PROJECT_DEVELOPMENT_PLAN.md` for detailed modularization roadmap.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

(Consider adding guidelines for code style, testing, etc., if applicable for contributors.)

## License

(Specify your project's license here, e.g., MIT License. If not yet decided, you can state "License to be determined.")
