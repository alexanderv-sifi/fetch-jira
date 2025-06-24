# CAKE Architecture Design

## Proposed Modular Structure

```
cake/
├── __init__.py
├── cli.py                 # CLI interface and argument parsing
├── core/
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── processor.py      # Main orchestration logic
│   └── output.py         # Output format handling (JSONL, JSON)
├── clients/
│   ├── __init__.py
│   ├── base.py           # Base client with common functionality
│   ├── jira_client.py    # Jira API client
│   ├── confluence_client.py  # Unified Confluence client
│   └── gdrive_client.py  # Google Drive client
├── processors/
│   ├── __init__.py
│   ├── content.py        # HTML cleaning, macro processing
│   ├── permissions.py    # Permission extraction
│   └── rag.py           # RAG-specific formatting
└── utils/
    ├── __init__.py
    ├── pagination.py     # Generic pagination handling
    ├── concurrency.py    # Thread pool management
    └── auth.py          # Authentication utilities
```

## Key Principles

### 1. **Single Responsibility**
- Each client handles one API
- Processors focus on content transformation
- Clear separation of concerns

### 2. **Performance Focus**
- Async/await for I/O operations
- Connection pooling
- Intelligent caching
- Batch processing

### 3. **Flexibility**
- Plugin architecture for new sources
- Configurable output formats
- Extensible content processors

### 4. **Testability**
- Dependency injection
- Mock-friendly interfaces
- Clear contracts

## Implementation Plan

1. **Phase 1**: Create base architecture
2. **Phase 2**: Migrate Confluence client (consolidate both)
3. **Phase 3**: Extract Jira client from cake.py
4. **Phase 4**: Add async support for performance
5. **Phase 5**: Clean up old files