# Changelog

All notable changes to CAKE will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-06-23

### 🏗️ Architecture Overhaul
- **BREAKING:** Complete rewrite with modular architecture
- **NEW:** Clean separation of concerns across clients, processors, and core logic
- **NEW:** Modern CLI interface with `cake_cli.py` command
- **IMPROVED:** Legacy `cake.py` interface preserved for backward compatibility

### 🚀 Performance Improvements
- **FIXED:** Critical pagination bug - now captures all 44 pages instead of 25 (76% more content)
- **NEW:** Automatic pagination handling across all API clients
- **NEW:** Concurrent processing with intelligent rate limiting
- **NEW:** Connection pooling and reuse for better throughput
- **IMPROVED:** Memory-efficient streaming JSONL generation

### 🤖 RAG/AI Optimization
- **NEW:** Simplified JSONL format option (`--simplified`) with minimal metadata for better RAG performance  
- **IMPROVED:** Enhanced HTML cleaning and Confluence macro processing
- **IMPROVED:** Better content enhancement with child page navigation and labels
- **NEW:** RAG-specific document formatting optimized for Vertex AI ingestion

### 🔧 Enhanced Confluence Support
- **NEW:** Unified Confluence client consolidating duplicate implementations
- **IMPROVED:** Comprehensive field extraction including labels, permissions, ancestors
- **FIXED:** Label extraction now working correctly across all pages
- **NEW:** Enhanced macro processing for info, warning, expand, and layout macros
- **IMPROVED:** Better HTML-to-text conversion for cleaner content

### 📦 New Modular Components
- `cake/core/config.py` - Centralized configuration management
- `cake/core/processor.py` - Main orchestration logic  
- `cake/clients/base.py` - Shared client functionality with pagination
- `cake/clients/confluence_client.py` - Unified Confluence client
- `cake/processors/content.py` - HTML cleaning and content enhancement
- `cake/processors/rag.py` - RAG-specific formatting
- `cake/cli.py` - Modern command-line interface

### 🔒 Security & Enterprise Features
- **NEW:** Enhanced permission extraction and ACL handling
- **IMPROVED:** Better error handling and retry logic
- **NEW:** Configurable concurrency limits and rate limiting
- **IMPROVED:** Comprehensive audit trail and export metadata

### 🛠️ Developer Experience
- **NEW:** Clean package structure with proper imports
- **NEW:** Comprehensive documentation updates
- **NEW:** Migration guide for v1.x to v2.0 transition
- **IMPROVED:** Better CLI help and usage examples
- **NEW:** Development tooling configuration (black, pytest, mypy)

### 📊 Output Format Improvements
- **NEW:** Individual JSONL files per page (perfect for RAG corpus loading)
- **NEW:** Simplified metadata format option
- **IMPROVED:** Better structured document hierarchy preservation
- **NEW:** Enhanced content with child page navigation context

### 🔄 Migration Notes
- Legacy `cake.py` interface remains fully functional
- New `cake_cli.py` provides cleaner, more performant interface
- Configuration format unchanged (existing `.env` files work)
- Output formats enhanced but backward compatible

## [1.x] - Previous Versions

### Legacy Monolithic Architecture
- Single `cake.py` script with embedded logic
- Basic Confluence and Jira extraction
- Manual pagination handling
- Duplicate client implementations

---

**Full Changelog**: https://github.com/alexanderv-sifi/cake/compare/v1.0...v2.0.0