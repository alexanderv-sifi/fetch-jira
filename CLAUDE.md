# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CAKE - Corporate Aggregation & Knowledge Extraction** is a powerful Python utility for comprehensively extracting and aggregating corporate knowledge from multiple platforms including Jira, Confluence, and Google Drive. It supports multiple output formats including individual JSONL files per page (perfect for Vertex AI RAG ingestion) and includes enterprise-grade features like permissions/ACL capture.

## Key Commands

### Running CAKE
```bash
# Run with uv (recommended)
uv run cake.py --mode <mode> --query <query> [options]

# If installed as package
cake --mode <mode> --query <query> [options]
```

### Common Usage Patterns
```bash
# Confluence pages with individual JSONL files (perfect for RAG)
uv run cake.py --mode confluence --query 3492511763 --output-format jsonl-per-page --include-permissions

# Fetch specific Jira issue
uv run cake.py --mode issue --query DWDEV-6812

# Fetch with JQL query and JSONL output
uv run cake.py --mode jql --query "project = DWDEV AND status = 'In Progress'" --output-format jsonl

# Fetch entire project (traditional JSON)
uv run cake.py --mode project --query DWDEV --skip-remote-content

# Debug mode
uv run cake.py --mode confluence --query 3492511763 --debug
```

### Development Setup
```bash
# Install dependencies
uv pip install -r requirements.txt

# For Google Drive integration
uv pip install google-api-python-client google-auth
```

## Architecture

### Current State
- **Main Script**: `cake.py` containing core orchestration and multi-platform logic
- **Confluence Module**: `confluence_client.py` - Modular Confluence API client (✅ **Completed**)
- **Enhanced Confluence**: `enhanced_confluence_client.py` - Permissions-aware client (✅ **Completed**)
- **Multi-format Output**: JSON, JSONL, and individual JSONL per page
- Uses threading with semaphores for concurrent API calls
- Configurable via `.env` file
- RAG-optimized output with cleaned content and metadata

### Modular Architecture Progress
**✅ Completed Modules:**
- `confluence_client.py` - Confluence API interactions with ConfluenceClient class

**🔄 Planned Modules (from PROJECT_DEVELOPMENT_PLAN.md):**
- `main.py` - CLI parsing and orchestration
- `config.py` - Configuration management  
- `jira_client.py` - Jira API interactions
- `gdrive_client.py` - Google Drive API interactions
- `data_processor.py` - Issue processing and enrichment logic
- `output_manager.py` - Data output handling
- `utils.py` - Common utilities

### Key Components
- **API Clients**: 
  - ✅ **ConfluenceClient**: Separate class with methods for page content, child pages, recursive fetching, URL parsing
  - 🔄 **Planned**: Separate clients for Jira and Google Drive with built-in retry logic
- **Data Processing**: Processes issues and fetches related content (subtasks, linked issues, epic children)
- **Concurrency**: Uses ThreadPoolExecutor with semaphores to respect API rate limits
- **Output**: Generates timestamped JSON files with export metadata and processed issue data

### Confluence Client Usage
```python
from confluence_client import ConfluenceClient

# Initialize client
client = ConfluenceClient(
    base_url="https://domain.atlassian.net/wiki",
    username="user@example.com", 
    api_token="api_token",
    max_concurrent_calls=5
)

# Check if URL is Confluence
is_confluence = client.is_confluence_url(url)

# Extract page ID from URL
page_id = client.extract_page_id_from_url(url)

# Fetch page content recursively
content = client.fetch_content_recursive(page_id)
```

## Configuration

### Required Environment Variables (.env file)
```env
JIRA_BASE_URL="https://your-domain.atlassian.net"
JIRA_USERNAME="your-jira-email@example.com"
JIRA_API_TOKEN="your-jira-api-token"
CONFLUENCE_BASE_URL="https://your-domain.atlassian.net/wiki"

# Optional for Google Drive
GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
```

## Important Development Standards

This project follows extensive development guidelines defined in `.cursor/rules/DEVELOPMENT_GUIDELINES.md`. Key areas include:

### Code Quality Standards
- **Modularity**: Separation of concerns with clear interfaces
- **Error Handling**: Robust retry mechanisms with exponential backoff
- **Logging**: Structured logging throughout the application
- **Security**: Proper secrets management and input validation

### API Integration Patterns
- Consistent retry strategies across different services (Jira, Confluence, Google Drive)
- Rate limiting and semaphore usage to respect API constraints
- Structured error responses and timeout handling

### Planned Improvements
- Enhanced retry logic using `tenacity` library
- Structured logging with `structlog`
- Comprehensive test coverage with `pytest`
- Checkpointing for resumable large exports
- Containerization with Docker

## Output Format

The tool generates JSON files with this structure:
- `export_metadata`: Information about the fetch operation
- `processed_issues_data`: Array of processed Jira issues with:
  - Standard Jira fields
  - `remote_links_data`: Linked Confluence/Google Drive content
  - `epic_children_data`: Child issues if Epic
  - `subtasks_data`: Associated subtasks
  - `linked_issues_data`: Related linked issues

## Dependencies

- **Python**: 3.12+
- **Core**: `requests`, `python-dotenv`
- **Optional**: `google-api-python-client`, `google-auth` (for Google Drive integration)
- **Package Manager**: `uv` (recommended)