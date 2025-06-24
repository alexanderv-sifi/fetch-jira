# CAKE - Corporate Aggregation & Knowledge Extraction

CAKE is a powerful Python utility designed to comprehensively extract and aggregate corporate knowledge from multiple platforms. It extracts content from Jira issues, Confluence pages (with recursive child fetching), and Google Drive files, including permissions and access control data. The aggregated data can be output in multiple formats including individual JSONL files per page, perfect for Vertex AI RAG ingestion and other AI/ML workflows.

## Features

*   **Multiple Platform Support:**
    *   **Jira:** Issues, subtasks, linked issues, epic children via issue key, JQL query, or entire project
    *   **Confluence:** Pages with recursive child fetching, including permissions/ACLs
    *   **Google Drive:** Files, folders, documents with metadata and content extraction
*   **Enterprise-Ready Security:**
    *   Captures permissions and access control lists (ACLs) for Confluence pages
    *   Identifies restricted content for proper access control in downstream systems
    *   Respects API rate limits with configurable concurrency controls
*   **RAG-Optimized Output Formats:**
    *   **Individual JSONL per page** - Perfect for Vertex AI RAG corpus loading
    *   **Single JSONL file** - All content in one file for batch processing  
    *   **Traditional JSON** - Complete hierarchical data with metadata
*   **Intelligent Content Processing:**
    *   HTML content cleaned and converted to plain text for RAG ingestion
    *   Preserves document hierarchy and relationships
    *   Includes rich metadata (authors, timestamps, versions, ancestors)
*   **High Performance:**
    *   Concurrent API calls with threading and semaphores
    *   Configurable rate limiting per service
    *   Efficient recursive processing with cycle detection
*   **Enterprise Configuration:** 
    *   Environment-based configuration via `.env` files
    *   Support for Google Cloud ADC for Drive integration
    *   Flexible authentication for corporate environments

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

CAKE is run via the `cake` command-line interface (if installed as a package) or by directly executing `cake.py` using `uv run`.

**General command structure:**

```bash
uv run cake.py --mode <mode> --query <query_string> [options]
```
Or, if installed as a package (e.g., via `uv pip install .`):
```bash
cake --mode <mode> --query <query_string> [options]
```

**Arguments:**

*   `--mode`: (Required) The mode for fetching data.
    *   `issue`: Fetch a single Jira issue and its related data.
    *   `jql`: Fetch Jira issues based on a JQL query.
    *   `project`: Fetch all issues for a specific Jira project.
    *   `confluence`: Fetch a Confluence page and all its children recursively.
*   `--query`: (Required) The identifier for the fetch operation.
    *   For `issue` mode: The Jira issue key (e.g., `DWDEV-123`).
    *   For `jql` mode: The JQL query string (e.g., `project = DWDEV AND status = "In Progress"`).
    *   For `project` mode: The Jira project key (e.g., `DWDEV`).
    *   For `confluence` mode: Confluence page ID or full URL.
*   `--output-format`: (Optional) Output format: `json` (default), `jsonl`, or `jsonl-per-page`.
*   `--include-permissions`: (Optional) Include permissions/ACL data for Confluence pages.
*   `--skip-remote-content`: (Optional) Skip fetching content from Confluence and Google Drive links.
*   `--debug`: (Optional) Enables detailed debug logging.

**Examples:**

1.  **Fetch Confluence pages with individual JSONL files (perfect for RAG):**
    ```bash
    uv run cake.py --mode confluence --query 3492511763 --output-format jsonl-per-page --include-permissions
    ```

2.  **Fetch a specific Jira issue:**
    ```bash
    uv run cake.py --mode issue --query DWDEV-6812
    ```

3.  **Fetch Jira issues using a JQL query:**
    ```bash
    uv run cake.py --mode jql --query "project = DWDEV AND issuetype = Epic AND status = Open ORDER BY created DESC"
    ```

4.  **Fetch Confluence page with single JSONL output:**
    ```bash
    uv run cake.py --mode confluence --query "https://simplifi.atlassian.net/wiki/spaces/DW/pages/3492511763" --output-format jsonl
    ```

5.  **Fetch all issues for a project with traditional JSON:**
    ```bash
    uv run cake.py --mode project --query DWDEV --skip-remote-content
    ```

6.  **Debug mode for troubleshooting:**
    ```bash
    uv run cake.py --mode confluence --query 3492511763 --debug
    ```

## Output Formats

CAKE supports multiple output formats optimized for different use cases:

### Individual JSONL Files (`--output-format jsonl-per-page`)
**Perfect for Vertex AI RAG corpus loading**
- Creates a directory with one JSONL file per page/issue
- Each file contains exactly one document in RAG-ready format
- Example: `cake_export_confluence_3492511763_TIMESTAMP_raw_jsonl_files/`
  - `confluence_3492511763.jsonl`
  - `confluence_4428169266.jsonl` 
  - ... (106 total files)

### Single JSONL File (`--output-format jsonl`)
**For batch processing and streaming ingestion**
- All documents in one JSONL file
- One document per line, easy to stream and process
- Example: `cake_export_confluence_3492511763_TIMESTAMP.jsonl`

### Traditional JSON (`--output-format json`, default)
**Complete hierarchical data with full metadata**
- Preserves original structure and relationships
- Includes comprehensive export metadata
- Example: `cake_export_confluence_3492511763_TIMESTAMP_raw.json`

### RAG Document Format
Each document (in JSONL formats) contains:
```json
{
  "id": "confluence_3492511763",
  "title": "Page Title",
  "content": "Clean text content without HTML",
  "url": "https://domain.atlassian.net/wiki/...",
  "metadata": {
    "source": "confluence|jira|gdrive",
    "permissions": { "is_restricted": false, ... },
    "space": "DW",
    "page_id": "3492511763",
    "ancestors": [...],
    "last_modified": "2025-06-12T15:15:45.573Z"
  }
}
```

## Development / Running Locally

Ensure Python 3.12+ and `uv` are installed.

1.  Clone the repository.
2.  Set up your `.env` file as described in the "Setup" section.
3.  You can run CAKE directly:
    ```bash
    uv run cake.py --mode confluence --query YOUR-PAGE-ID --output-format jsonl-per-page
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
