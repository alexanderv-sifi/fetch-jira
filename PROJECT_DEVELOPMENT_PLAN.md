# Project Development Plan: Fetch-Jira Utility

This document outlines the plan for restructuring the `fetch-jira` utility for better modularity and long-term maintainability, along with considerations for evolving it into a production-grade application.

## 1. Code Restructuring and Modularization

**Status Update:** ✅ **Confluence Module Completed** - The Confluence functionality has been successfully extracted into `confluence_client.py` as a standalone module with proper class structure and clean interfaces.

The current `jira-fetcher.py` script, while functional and optimized for API efficiency, is being modularized to improve readability, maintainability, testability, and scalability.

**Proposed Module Structure:**

The single `jira-fetcher.py` script will be broken down into the following Python files/modules:

*   **`main.py` (or `fetch_jira_cli.py`)**:
    *   Responsibilities: Handles command-line argument parsing (`argparse`). Orchestrates the overall fetching process by calling functions from other modules. Manages the `ThreadPoolExecutor` and the main processing loop. This will be the primary entry point of the application.
*   **`config.py`**:
    *   Responsibilities: Loads and manages configuration from the `.env` file (Jira/Confluence URLs, API tokens, Google Cloud Project ID). Stores global constants (e.g., `MAX_RESULTS_PER_JIRA_PAGE`, API call delays, semaphore limits).
*   **`jira_client.py`**:
    *   Responsibilities: Contains all low-level functions for direct interaction with the Jira API.
        *   Handles authentication, request headers, and base URL construction.
        *   Manages Jira-specific API call delays and semaphore usage.
        *   Provides functions for core Jira operations:
            *   `fetch_issue(issue_key, expand_fields=None)`: Fetches a single issue, optionally expanding fields.
            *   `search_jql(jql_query, expand_fields=None, start_at=0, max_results=100)`: Executes a JQL query with pagination and optional expansion.
            *   `fetch_remote_links_for_issue(issue_key)`: (To be used as a fallback if not expanded).
    *   This module will encapsulate all direct `requests.get` calls to Jira.
*   **`confluence_client.py`**: ✅ **COMPLETED**
    *   Responsibilities: Manages all interactions with the Confluence API.
        *   ✅ `ConfluenceClient` class with proper initialization and configuration
        *   ✅ Authentication, base URL, API call delays, and semaphore management
        *   ✅ Methods: `fetch_page_content(page_id)`, `fetch_child_pages(page_id)`, `fetch_content_recursive(page_id)`
        *   ✅ Utility methods: `is_confluence_url(url)`, `extract_page_id_from_url(url)`
        *   ✅ Proper error handling and type hints
*   **`gdrive_client.py`**:
    *   Responsibilities: Handles all Google Drive API interactions.
        *   Google Drive service initialization (`get_google_drive_service`).
        *   Functions for `fetch_drive_item_metadata(item_id)`, `download_drive_file_content(file_id, mime_type, file_name)`, `fetch_drive_item_recursive(service, item_id)`.
        *   Manages GDrive-specific API call delays and semaphore usage.
*   **`data_processor.py` (or `issue_enricher.py`)**:
    *   Responsibilities: Contains the higher-level logic for processing and enriching Jira issues.
        *   `process_issue_and_related_data(issue_json, skip_remote_content=False)`: This function would be the core worker function. It takes a raw Jira issue (potentially with expanded links).
            *   Orchestrates fetching of subtasks, linked issues, and epic children (by calling `jira_client.py` batch methods).
            *   Handles the processing of remote links, calling `confluence_client.py` or `gdrive_client.py` as needed.
            *   Aggregates all fetched data for a given issue into a comprehensive structure.
*   **`output_manager.py`**:
    *   Responsibilities: Handles saving the processed data.
        *   Current: `save_to_json(data, filename)`.
        *   Future: Could be extended for streaming output (e.g., JSON Lines), checkpointing progress, and managing output file naming conventions.
*   **`utils.py` (Optional)**:
    *   For common utility functions that don't fit neatly into other modules (e.g., specific date formatting, complex string manipulations if any).

**Benefits of this Structure:**

*   **Separation of Concerns:** Each module has a well-defined responsibility.
*   **Testability:** Individual modules (especially clients and processors) can be unit-tested more easily by mocking dependencies.
*   **Maintainability:** Easier to locate and modify specific functionality.
*   **Scalability:** Simpler to add new features (e.g., fetching other types of Jira data, different output formats) by adding or modifying modules.

## 1.1 Implementation Progress

### ✅ Confluence Client Module (Completed)

**What was accomplished:**
*   **Extracted all Confluence functionality** from `jira-fetcher.py` into standalone `confluence_client.py`
*   **Created ConfluenceClient class** with clean initialization and configuration
*   **Implemented all core methods:**
    *   `fetch_page_content(page_id)` - Fetches individual page content with metadata
    *   `fetch_child_pages(page_id)` - Retrieves child page summaries
    *   `fetch_content_recursive(page_id, visited_pages=None)` - Recursive content fetching with cycle detection
*   **Added utility methods:**
    *   `is_confluence_url(url)` - URL detection for Confluence links
    *   `extract_page_id_from_url(url)` - Page ID extraction from various URL formats
*   **Proper error handling** with structured error responses
*   **Type hints and documentation** for all methods
*   **Semaphore management** for concurrent API call limiting
*   **Updated main script** to use the new client with minimal changes to existing logic

**Key Design Improvements:**
*   **Dependency injection:** Client accepts configuration parameters instead of relying on global variables
*   **Stateless operations:** All state is managed within method calls, making testing easier
*   **Clean interfaces:** Methods have clear inputs/outputs and handle errors gracefully
*   **Reusability:** Client can be instantiated independently of the main script

**Integration verified:** ✅ All tests pass, URL detection works correctly, main script imports and uses the client successfully.

## 2. Considerations for Productionization

Moving beyond a one-off tool to a reliable, long-term application requires addressing several aspects:

1.  **Enhanced Configuration Management:**
    *   **Environment-Specific Configs:** Support for sourcing configurations from system environment variables (common in CI/CD and containerized deployments) in addition to/preference over `.env` files for production.
    *   **Secrets Management:** Integrate with a secrets management system (e.g., HashiCorp Vault, AWS/Azure/Google Cloud secret managers) for API tokens in production environments, rather than plain text.

2.  **Robust Error Handling & Retry Mechanisms:**
    *   **Granular Error Handling:** Differentiate handling for various HTTP error codes (401, 403, 404, 429, 5xx) from Jira, Confluence, and GDrive.
    *   **Configurable Retries:** Implement robust retry logic (e.g., using the `tenacity` library) with exponential backoff and jitter for transient API errors.
    *   **Dead Letter/Error Reporting:** Mechanism to log persistent errors comprehensively, potentially integrate with an error tracking service (e.g., Sentry).

3.  **Comprehensive Logging and Monitoring:**
    *   **Structured Logging:** Transition to structured logging (e.g., JSON format) for easier parsing by log management systems (ELK, Splunk, Datadog). Include contextual information like issue keys or JQL queries in log entries.
    *   **Key Metrics:** Instrument the application to emit metrics (e.g., using Prometheus client library or similar):
        *   Number and latency of API calls (per service).
        *   Success/failure rates of API calls.
        *   Issues processed per minute.
        *   Queue sizes and thread activity.
        *   Duration of major operations.
    *   **Monitoring & Alerting:** Integrate metrics with a monitoring dashboard (e.g., Grafana) and set up alerts for critical conditions (job failures, high error rates).

4.  **Thorough Testing Strategy:**
    *   **Unit Tests:** For each module, mocking external API calls and dependencies.
    *   **Integration Tests:** Testing interactions between key modules (e.g., `jira_client` -> `data_processor` -> `output_manager`).
    *   **End-to-End Tests (Optional):** If feasible, tests against a dedicated test Jira instance for critical user flows.

5.  **Checkpointing and Resumability:**
    *   **Stateful Processing:** For very large exports (e.g., entire Jira instance or very large projects), implement a checkpointing mechanism.
    *   Periodically save the progress (e.g., last project processed, last issue key in a project, last page of JQL results).
    *   Enable the script to resume from the last known good checkpoint to avoid starting from scratch on failure.

6.  **Idempotency:**
    *   Ensure that re-running the script with the same parameters (e.g., after a failure and resumption) produces consistent results without unintended side effects. For file outputs, this typically means a strategy for overwriting or versioning output files.

7.  **Data Validation:**
    *   Implement basic validation for expected fields in API responses to catch unexpected changes or malformed data, preventing crashes or incorrect processing.
    *   Consider defining an output schema and validating the final JSON against it.

8.  **Packaging and Deployment:**
    *   **Containerization:** Package the application using Docker for consistent deployments.
    *   **Dependency Management:** Maintain clear `pyproject.toml` and `uv.lock` (or `requirements.txt`) and regularly audit/update dependencies.
    *   **CI/CD Pipeline:** Implement a CI/CD pipeline (e.g., GitHub Actions, GitLab CI) for automated testing, building, and potentially deploying the application.

9.  **Operational Documentation:**
    *   **README:** Keep `README.md` updated with setup, usage, and basic troubleshooting.
    *   **Runbook (for production):** Detailed instructions for operators on how to run, monitor, troubleshoot, and recover the application in a production setting.

10. **Scalability and Performance (Beyond current optimizations):**
    *   **Streaming Output:** For "pull everything" scenarios, change `output_manager.py` to stream processed issues to disk (e.g., JSON Lines format) instead of accumulating all in memory.
    *   **Dynamic Rate Limiting:** Potentially adapt API call rates based on `Retry-After` headers or observed error patterns.
    *   **Resource Management:** Monitor and optimize memory and CPU usage, especially for very large datasets.

**Next Steps:**

1.  Begin the modularization process as outlined in Section 1. This will provide a cleaner codebase to implement further productionization features.
2.  Incrementally introduce elements from Section 2, prioritizing based on the tool's usage context and criticality. For example, enhanced logging and error handling are often good early improvements.

This plan provides a roadmap for enhancing the `fetch-jira` utility, making it more robust, maintainable, and ready for more demanding use cases. 