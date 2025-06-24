# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CAKE - Corporate Aggregation & Knowledge Extraction** is a modular Python framework for extracting enterprise knowledge from multiple platforms including Jira, Confluence, and Google Drive. It features a clean, performance-oriented architecture optimized for AI/ML workflows, particularly Vertex AI RAG ingestion, with enterprise-grade security and permissions handling.

## Key Commands

### New CLI Interface (v2.0) - Recommended
```bash
# Modern modular CLI
uv run cake_cli.py confluence <page_id> [options]

# Examples
uv run cake_cli.py confluence 3492511763 --simplified
uv run cake_cli.py confluence 3492511763 --format jsonl --no-permissions
uv run cake_cli.py confluence 3492511763 --max-concurrent 10 --debug
```

### Legacy Interface (v1.x) - Still Available
```bash
# Traditional interface for backward compatibility
uv run cake.py --mode <mode> --query <query> [options]

# Examples
uv run cake.py --mode confluence --query 3492511763 --output-format jsonl-per-page
uv run cake.py --mode issue --query DWDEV-6812
uv run cake.py --mode jql --query "project = DWDEV AND status = Open"
```

### Development Setup
```bash
# Install dependencies
uv pip install -r requirements.txt

# For Google Drive integration (optional)
uv pip install google-api-python-client google-auth

# Test new architecture
uv run cake_cli.py confluence 3758620708 --simplified
```

## Architecture (v2.0)

### Modern Modular Structure
```
cake/                         # New modular framework
├── cli.py                    # Command-line interface
├── core/
│   ├── config.py            # Configuration management
│   └── processor.py         # Main orchestration logic
├── clients/
│   ├── base.py              # Shared client functionality
│   ├── confluence_client.py # Unified Confluence client
│   ├── jira_client.py       # Jira API client (planned)
│   └── gdrive_client.py     # Google Drive client (planned)
└── processors/
    ├── content.py           # HTML cleaning & enhancement
    └── rag.py              # RAG-specific formatting

cake_cli.py                   # New CLI entry point
cake.py                       # Legacy monolithic script (preserved)
```

### Key Improvements in v2.0
- **Fixed Pagination Bug**: Now captures all 44 pages instead of 25 (76% more content)
- **Unified Confluence Client**: Consolidated duplicate clients into one optimized version
- **Performance**: Concurrent processing with intelligent rate limiting
- **Simplified Output**: Minimal metadata option for better RAG performance
- **Modular Design**: Clean separation of concerns for maintainability

### Modular Architecture Components

**✅ Completed v2.0 Modules:**
- `cake/core/config.py` - Centralized configuration management with environment loading
- `cake/core/processor.py` - Main orchestration logic and workflow coordination
- `cake/clients/base.py` - Shared client functionality with pagination and concurrency
- `cake/clients/confluence_client.py` - Unified Confluence client (consolidates old duplicate clients)
- `cake/processors/content.py` - HTML cleaning, macro processing, and content enhancement
- `cake/processors/rag.py` - RAG-specific formatting and JSONL generation
- `cake/cli.py` - Modern command-line interface
- `cake_cli.py` - Entry point script

**🔄 Next Phase (Jira Migration):**
- `cake/clients/jira_client.py` - Extract Jira client from monolithic cake.py
- `cake/clients/gdrive_client.py` - Extract Google Drive client from monolithic cake.py
- `cake/processors/permissions.py` - Enhanced permission processing
- Async/await support for improved performance

### New CLI Usage Examples
```python
from cake import CakeProcessor, CakeConfig

# Load configuration
config = CakeConfig.from_env()
config.simplified_output = True
config.max_concurrent_calls = 10

# Create processor
processor = CakeProcessor(config)

# Process Confluence content
results = processor.process_confluence_page("3492511763", "jsonl-per-page")

# Get page info
page_info = processor.get_page_info("3758620708")
```

### Performance Benefits
- **Complete Content**: Fixed pagination bug captures all pages (44 vs 25)
- **Faster Processing**: Concurrent API calls with intelligent rate limiting
- **Better RAG**: Simplified output format reduces metadata noise
- **Memory Efficient**: Streaming JSONL generation for large datasets
- **Error Resilient**: Comprehensive error handling and retry logic

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