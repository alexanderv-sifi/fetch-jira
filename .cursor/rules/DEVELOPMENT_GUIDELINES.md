# Enhanced Development Rulesets - Complete Alignment

## Implementation Strategy

**Automated Rules**: Can be enforced via static analysis and IDE tooling
**Review Guidelines**: Best implemented as code review checklists and team standards
**Hybrid**: Partial automation possible, human judgment needed for edge cases

---

## Core Development Principles

Even with the evolution away from a formal plugin system, the following core principles guide our development approach to ensure a robust, maintainable, and scalable application:

*   **Modularity and Separation of Concerns:**
    *   Organize code into distinct modules or components, each with a well-defined purpose and responsibility (e.g., API routing, business logic/services, data access, external service integrations).
    *   This promotes easier understanding, testing, and modification of individual parts of the system without unintended side effects.

*   **Clear Interfaces:**
    *   Modules and components should interact through clearly defined interfaces.
    *   Primarily, this involves precise function/method signatures and the consistent use of Pydantic models for data structures and API contracts, as detailed in these guidelines.

*   **Maintainability and Readability:**
    *   Prioritize writing code that is straightforward to understand, debug, and enhance by any member of the team.
    *   Adherence to the specific coding (Rulesets 1-4), testing (Ruleset 5), documentation (Ruleset 6), operational (Ruleset 7), and version control (Ruleset 8) standards herein is key to achieving this.

*   **Consistency:**
    *   Following these established guidelines consistently across the codebase is crucial for reducing complexity and improving collaboration.

These principles underpin the specific rulesets that follow.

---

## Ruleset 1: FastAPI Development Standards

**Goal:** Ensure consistency, robustness, and adherence to best practices in FastAPI endpoint development.

**Key Rules:**

1.  **AUTOMATED** - Pydantic for All I/O: All API request and response bodies must be strictly defined using Pydantic models.
2.  **AUTOMATED** - Pydantic Field Descriptions: For Pydantic models used in API I/O, require the use of `Field(description="...")` for model attributes.
3.  **REVIEW** - Digital Workplace Response Models: Enforce standardized response structures matching the design document:
    *   Bot Response Structure: All bot responses should include `text: str`, `actions: List[str]` fields
    *   Query Response Structure: Message processing responses should include `query_id: str`, `intent: str`, `text: str`, `actions: List[str]`
    *   RAG Response Structure: RAG responses should include `status: str`, `query_id: str`, `text: str`, and conditionally `sources: List[str]`, `processing_time_ms: int`
    *   Slack Integration: Responses to Slack endpoints should include `blocks` field when UI components are needed
4.  **AUTOMATED** - Async Handlers: All FastAPI route handlers must be defined with `async def`.
5.  **HYBRID** - Standard HTTP Status Codes: Enforce standard RESTful HTTP status codes matching the design:
    *   `201 Created` for successful POST operations (access-requests, tickets)
    *   `200 OK` for successful GET operations and event processing
    *   `404 Not Found` for cache misses (qna-cache)
6.  **AUTOMATED** - Versioned & Snake_case Endpoints:
    *   API routes must be versioned in the path (e.g., `/v1/...`)
    *   Path and query parameters must use `snake_case`
    *   Flag endpoints that don't match documented paths (`/v1/integrations/slack/events`, `/v1/access-requests`, etc.)
7.  **AUTOMATED** - Typed Parameters: All path and query parameters in route handlers must have type hints.
8.  **HYBRID** - Streaming Response Implementation:
    *   The `/v1/rag` endpoint should return a `fastapi.responses.StreamingResponse`
    *   Streaming content should be an async generator yielding JSON objects
    *   Include `query_id` in streaming responses for client-side correlation
    *   Review Guidelines: Verify multi-stage streaming sequence (initial → success/timeout/error)
9.  **HYBRID** - Request/Response Headers:
    *   Detect missing `Authorization` header validation on RAG endpoint
    *   Flag missing `Content-Type` header setting

---

## Ruleset 2: Data Handling & External Service Integration

**Goal:** Promote consistent data modeling for Firestore and robust integration with external services following the design document specifications.

**Key Rules:**

1.  **AUTOMATED** - Firestore Model Conventions (Pydantic):
    *   Field names must be `snake_case`
    *   A `created_at: datetime` field is required for all new models
    *   An `updated_at: datetime` field is required for models intended to be mutable
    *   An `expires_at: datetime` field is required for models with TTL policies
2.  **HYBRID** - TTL Policy Alignment:
    *   Flag models missing TTL fields when they match documented collections:
        *   `ticket_threads`, `conversation_sessions`: 14 days TTL
        *   `llm_query_logs`: 365 days TTL
        *   `interaction_outcomes`: 90 days TTL
        *   `qna_cache`: 24 hours TTL
3.  **HYBRID** - Service-Specific Retry Logic with `tenacity`:
    *   Detect external service calls without retry decorators
    *   Suggest service-specific configurations (implementation should reference project retry documentation):
        *   Slack API calls: 2 retries, 0.5s fixed backoff
        *   Jira API calls: 5 retries, exponential backoff
        *   GenAI Service calls: 2 retries, 1s fixed backoff
        *   Vertex AI calls: 4 retries, exponential backoff
4.  **AUTOMATED** - Enforce `await`: Within `async def` functions, any call to an awaitable object/method must be `await`ed.
5.  **AUTOMATED** - External Service Client Detection: Flag calls to `httpx.AsyncClient`, Slack SDK methods, or Vertex AI clients without retry decorators.

---

## Ruleset 3: Logging & Observability with `structlog`

**Goal:** Ensure all logging is structured, consistent, and provides rich contextual information.

**Key Rules:**

1.  **Exclusive `structlog` Usage:** All application logging within the `src/` directory must use `structlog.get_logger()`.
2.  **Discourage `print()`:** Flag `print()` statements within `src/` as a strong warning, encouraging replacement with `structlog` calls.
3.  **Digital Workplace Contextual Logging:**
    *   At the beginning of API route handlers, bind key contextual variables using `structlog.contextvars.bind_contextvars()`:
        *   `user_id` (from Slack user ID)
        *   `query_id` (for message processing and RAG queries)
        *   `channel_id` and `thread_ts` (for Slack integration)
        *   `session_id` (for conversation continuity)
4.  **Appropriate Log Levels:**
    *   `log.info()` for request flow and successful operations
    *   `log.debug()` for detailed diagnostic info and processing steps
    *   `log.warning()` for expected, non-blocking errors (cache misses, timeouts)
    *   In `except` blocks, use `log.error(..., exc_info=True)` or `log.exception(...)`
5.  **Entry/Exit Logging:**
    *   `DEBUG` level log entries for start and completion of API endpoint handlers
    *   `INFO` level logging for external service calls and their outcomes
    *   Include processing time metrics for performance monitoring

---

## Ruleset 4: Security Best Practices

**Goal:** Implement the specific security patterns documented in the design.

**Key Rules:**

1.  **HYBRID** - Digital Workplace Authentication Patterns:
    *   Slack Integration: Flag endpoints `/v1/integrations/slack/*` missing Slack signature verification imports/calls
    *   RAG System: Detect missing Bearer token validation on `/v1/rag` endpoint
    *   Review Guidelines: Verify correct GCP Service Account auth implementation
2.  **AUTOMATED** - API Key Management:
    *   Flag hardcoded high-entropy strings (potential API keys) in source code
    *   Suggest GCP Secret Manager usage when detecting secret-like patterns
    *   Exclude test files and configuration examples from secret detection
3.  **HYBRID** - Standardized Error Responses:
    *   Error responses should use Pydantic models
    *   Flag custom exception handlers that don't use structured response models
    *   Review Guidelines: Verify error responses include required fields (`error`, `text`, conditional `retry_after_seconds`, `fallback_options`)
4.  **AUTOMATED** - Input Validation:
    *   All Pydantic models must include validation for required fields
    *   Flag missing type hints on request/response models

---

## Ruleset 5: Testing Conventions (`pytest`)

**Goal:** Promote comprehensive, consistent, and discoverable tests.

**Key Rules:**

1.  **Test File Naming & Existence:**
    *   Enforce standard `pytest` naming for test files (`test_*.py` or `*_test.py`)
    *   When new service files are added to `src/`, suggest corresponding test files
2.  **Test Function Naming:** Enforce standard `pytest` naming for test functions (`def test_...():`)
3.  **Assertions Required:** Test functions must contain one or more `assert` statements
4.  **No `print()` in Tests:** Flag `print()` statements in test files, encourage pytest capturing or logging
5.  **🔧 Mock External Services:**
    *   Flag tests calling external services (Slack, Jira, GenAI, Vertex AI) without apparent mocking
    *   Suggest `unittest.mock.patch` or `mocker` fixture usage
    *   *Review Guidelines: Verify mocks match actual service interfaces*
6.  **👀 Digital Workplace Test Patterns:**
    *   *Review Guidelines: Tests for streaming endpoints should validate response sequence*
    *   *Review Guidelines: Authentication tests should cover documented auth patterns*
    *   *Review Guidelines: Integration tests should verify request/response formats from design*
7.  **HYBRID - Test Organization:**
    *   Tests should generally be organized within a top-level `tests/` directory.
    *   The structure within `tests/` should mirror the `src/` directory structure to maintain clarity and ease of navigation (e.g., tests for `src/module_a/feature_b.py` might reside in `tests/module_a/test_feature_b.py`).

---

## Ruleset 6: Code Documentation Standards

**Goal:** Improve code understanding, maintainability, and the quality of auto-generated documentation.

**Key Rules:**

1.  **Require Module Docstrings:** All `.py` files within `src/` should have a module-level docstring.
2.  **Require Public Function/Method/Class Docstrings:** All public functions, methods, and classes must have docstrings.
3.  **Basic Docstring Presence:** Check that docstrings exist and are not empty or just whitespace.
4.  **Pydantic Field Descriptions:** For Pydantic models used in API I/O, require `Field(description="...")` for documentation generation.
5.  **👀 Digital Workplace Documentation Requirements:**
    *   *Review Guidelines: Service integration modules should document retry strategies and rate limits*
    *   *Review Guidelines: Authentication handlers should document the specific auth flow being implemented*
    *   *Review Guidelines: Streaming response generators should document expected response sequence*
6.  **REVIEW - Component/Module READMEs:**
    *   Major internal components or modules within `src/` that have a distinct purpose or complex internal logic may benefit from their own `README.md` file located within their respective directory.
    *   These READMEs should detail the component's responsibilities, how it interacts with other parts of the system, and any specific setup or usage notes relevant to that component.

---

## Ruleset 7: Operational Constraints & Performance

**Goal:** Enforce operational requirements and performance constraints from the design document.

**Key Rules:**

1.  **HYBRID** - Timeout Implementation:
    *   Flag missing timeout parameters on external service calls
    *   RAG endpoint should implement processing timeout mechanism
    *   Review Guidelines: Verify 5-second timeout implementation and graceful fallback
2.  **HYBRID** - Rate Limiting Enforcement:
    *   Flag missing rate limiting decorators/middleware on public endpoints
    *   Suggest Firestore-based rate limiting implementation
    *   Review Guidelines: Verify rate limits match design document (e.g., 5,100 queries/day for RAG)
3.  **AUTOMATED** - Data Lifecycle Management:
    *   Flag Firestore models missing `expires_at` when TTL is documented
    *   Ensure `expires_at` field is properly calculated (created_at + TTL period)
    *   Flag cache implementations without TTL logic
4.  **HYBRID** - Performance Monitoring:
    *   Suggest including `processing_time_ms` in documented response models
    *   Flag missing performance logging for external service calls
    *   Review Guidelines: Verify cancellation support for long-running operations
5.  **REVIEW** - Resource Management:
    *   Review Guidelines: Async generators should handle client disconnection gracefully
    *   Review Guidelines: Database connections should use connection pooling
    *   Review Guidelines: External service clients should be reused, not created per request
6.  **HYBRID** - Fallback Behavior:
    *   RAG timeout responses should include structured fallback fields
    *   Service unavailable errors should include `fallback_options` field
    *   Review Guidelines: Verify all error scenarios provide user-actionable next steps

---

## Ruleset 8: Version Control & Commit Hygiene

**Goal:** Ensure a clear, traceable, and manageable development history, facilitating collaboration and easier troubleshooting.

**Key Rules:**

1.  **REVIEW - Frequent, Atomic, and Detailed Commits:**
    *   **Commit Frequently:** Make small, incremental commits as you complete logical units of work. Avoid large, monolithic commits that bundle unrelated changes.
    *   **Atomic Commits:** Each commit should represent a single, complete thought or change. If a change addresses multiple issues or features, break it into separate commits where possible.
    *   **Detailed Commit Messages:**
        *   **Imperative Mood:** Start the subject line with an imperative verb (e.g., "Fix: ...", "Add: ...", "Refactor: ...", "Update: ...", "Docs: ...").
        *   **Concise Subject Line:** Keep the subject line to 50-72 characters.
        *   **Descriptive Body (if needed):** For more complex changes, provide a detailed body explaining the "what" and "why" of the change, not just the "how" (the code shows the how).
        *   **Reference Issues:** If the commit relates to a specific issue or task, reference its ID (e.g., "Closes #42", "Addresses TSK-101").
    *   **Rationale:** This practice leads to:
        *   Easier progress tracking and understanding of project evolution.
        *   Simpler code reviews, as changes are smaller and more focused.
        *   More straightforward rollbacks or debugging if issues arise.
        *   Improved collaboration as changes are integrated more often.

---

## Implementation Priority

**Phase 1 - Immediate Automation (AUTOMATED):**
*   Basic structure rules (async handlers, type hints, naming conventions)
*   Import and dependency detection
*   Secret detection and basic validation

**Phase 2 - Enhanced Detection (HYBRID):**
*   Pattern matching for service integrations
*   Endpoint-specific validations
*   Missing component detection

**Phase 3 - Review Integration (REVIEW):**
*   Complex behavioral validation
*   Architecture compliance
*   Performance and resource management

---

## Automation Strategy

**Static Analysis Tools**: Perfect for AUTOMATED rules
**IDE Extensions**: Great for HYBRID rules with contextual hints
**Code Review Templates**: Essential for REVIEW guidelines
**CI/CD Integration**: Combine automated checks with review gate requirements

These enhanced rulesets balance comprehensive coverage with practical implementation, ensuring immediate value while building toward more sophisticated development assistance.
