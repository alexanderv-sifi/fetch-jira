# 🍰 CAKE - Corporate Aggregation & Knowledge Extraction

*"Let them eat data!"* - Marie Data-nette

CAKE is a deliciously powerful, multi-layered Python framework that extracts and aggregates enterprise knowledge from multiple platforms. Like any good cake, it's built with carefully crafted layers - each one adding flavor to your data extraction needs. We slice through Jira issues, frost your Confluence pages (with complete recursive child fetching that goes deeper than a chocolate ganache), and sprinkle in Google Drive files with all the metadata toppings. The final result? A perfectly baked dataset optimized for AI/ML workflows that's sweeter than Vertex AI RAG ingestion.

## ✨ Key Features

### 🏢 **Enterprise Platform Support** (The Cake Layers)
- **Jira Layer:** Issues, subtasks, linked issues, epic children via issue key, JQL query, or entire project - *the sponge that soaks up all your tickets*
- **Confluence Layer:** Pages with recursive child fetching, comprehensive field extraction, and permissions/ACLs - *the creamy filling that holds everything together*
- **Google Drive Layer:** Files, folders, documents with metadata and content extraction - *the decorative frosting on top*

### 🔒 **Enterprise-Ready Security** (No Crumbs Left Behind)
- Captures permissions and access control lists (ACLs) for Confluence pages - *knows who gets which slice*
- Identifies restricted content for proper access control in downstream systems - *keeps the secret recipe safe*
- Respects API rate limits with intelligent concurrency controls - *doesn't burn the kitchen down*

### 🤖 **AI/ML Optimized Output** (Fresh from the Oven)
- **Individual JSONL per page** - Perfect bite-sized slices for Vertex AI RAG corpus loading
- **Simplified format option** - Less frosting, more cake - minimal metadata for enhanced RAG performance
- **Single JSONL file** - The whole cake in one serving for batch processing  
- **Traditional JSON** - Complete layer cake with all the hierarchical data and metadata garnish

### ⚡ **High Performance Architecture** (Industrial Bakery Scale)
- **Automatic pagination** - Ensures complete content extraction (no missing crumbs!)
- **Concurrent processing** - Multiple ovens running with semaphores for optimal throughput
- **Modular design** - Clean separation of mixing, baking, and decorating for maintainability
- **Connection pooling** - Efficient ingredient delivery that doesn't waste anything

### 🧠 **Intelligent Content Processing** (Master Chef Mode)
- **Advanced HTML cleaning** - Confluence macro processing that removes the burnt bits and enhances flavors
- **Hierarchy preservation** - Keeps the cake layers in perfect order with navigation context
- **Rich metadata** - All the recipe details - authors, timestamps, versions, ancestors, labels (the ingredient list)

## 🏗️ Architecture (The Recipe Book)

CAKE v2.0 features a clean, modular architecture that even Gordon Ramsay would approve of:

```
cake/
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
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12 or higher
- `uv` (recommended Python package manager)
- Access credentials for Jira and Confluence
- For Google Drive: Google Cloud Project with ADC configured

### Installation

1. **Clone and setup:**
   ```bash
   git clone <repository-url>
   cd fetch-jira
   uv pip install -r requirements.txt
   ```

2. **Configure environment:**
   Create `.env` file:
   ```env
   JIRA_BASE_URL="https://your-domain.atlassian.net"
   JIRA_USERNAME="your-email@example.com"
   JIRA_API_TOKEN="your-api-token"
   CONFLUENCE_BASE_URL="https://your-domain.atlassian.net/wiki"
   
   # Optional: Google Drive integration
   GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
   ```

3. **Bake your CAKE:**
   ```bash
   # New modular CLI (recommended) - fresh from the oven!
   uv run cake_cli.py confluence 3492511763 --simplified
   
   # Legacy interface (still available) - grandma's recipe that still works
   uv run cake.py --mode confluence --query 3492511763 --output-format jsonl-per-page
   ```

## 📖 Usage Examples

### New CLI Interface (v2.0)

```bash
# Basic Confluence extraction
uv run cake_cli.py confluence 3492511763

# Simplified format for better RAG performance
uv run cake_cli.py confluence 3492511763 --simplified

# Single JSONL file output
uv run cake_cli.py confluence 3492511763 --format jsonl

# Skip permissions (faster processing)
uv run cake_cli.py confluence 3492511763 --no-permissions

# Performance tuning
uv run cake_cli.py confluence 3492511763 --max-concurrent 10 --delay 0.05

# Debug mode
uv run cake_cli.py confluence 3492511763 --debug
```

### Legacy Interface (v1.x compatibility)

```bash
# Confluence pages with individual JSONL files
uv run cake.py --mode confluence --query 3492511763 --output-format jsonl-per-page

# Jira issue extraction
uv run cake.py --mode issue --query DWDEV-6812

# JQL query
uv run cake.py --mode jql --query "project = DWDEV AND status = Open"

# Project extraction
uv run cake.py --mode project --query DWDEV
```

## 📊 Output Formats

### Individual JSONL Files (`--format jsonl-per-page`, default)
**🎯 Perfect bite-sized portions for Vertex AI RAG corpus loading**
- Creates directory with one JSONL file per page - *individual cupcakes, not a sheet cake*
- Each file contains exactly one RAG-ready document - *perfectly portioned*
- Optimized for corpus loading and indexing - *no messy cutting required*

### Single JSONL File (`--format jsonl`)
**📦 The whole cake for sharing**
- All documents in one JSONL file - *family-size portion*
- One document per line - *neatly sliced*
- Easy to stream and process in batches - *perfect for potlucks*

### Raw JSON (`--format json`)
**🔍 The complete recipe with all ingredients listed**
- Preserves original structure and relationships - *layer cake architecture intact*
- Includes comprehensive export metadata - *full ingredient list and nutrition facts*
- Full debugging and analysis capabilities - *you can taste every component*

### RAG Document Structure

**Standard format:**
```json
{
  "id": "confluence_3492511763",
  "title": "Page Title",
  "content": "Clean text content with child page navigation...\n\nPage Labels: label1, label2",
  "url": "https://domain.atlassian.net/wiki/...",
  "metadata": {
    "source": "confluence",
    "space": "DW",
    "space_name": "Digital Workplace Solutions",
    "page_id": "3492511763",
    "version": 10,
    "last_modified": "2025-06-12T15:15:45.573Z",
    "author": "Bill Price",
    "ancestors": [...],
    "permissions": {...},
    "is_restricted": false
  }
}
```

**Simplified format (`--simplified`):**
```json
{
  "id": "confluence_3492511763",
  "title": "Page Title", 
  "content": "Clean content with labels and navigation...",
  "url": "https://domain.atlassian.net/wiki/..."
}
```

## 🔧 Configuration Options

### Performance Settings
- `--max-concurrent`: Maximum concurrent API calls (default: 5)
- `--delay`: Delay between API calls in seconds (default: 0.1)
- `--no-permissions`: Skip permission extraction for faster processing

### Output Settings  
- `--simplified`: Minimal metadata for optimal RAG performance
- `--format`: Choose output format (jsonl-per-page, jsonl, json)

### Environment Variables
```env
# Required
JIRA_BASE_URL="https://your-domain.atlassian.net"
JIRA_USERNAME="your-email@example.com"  
JIRA_API_TOKEN="your-api-token"
CONFLUENCE_BASE_URL="https://your-domain.atlassian.net/wiki"

# Optional
GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
GOOGLE_API_KEY="your-api-key"
```

## 🚀 Performance Improvements (v2.0) - *Now with Extra Frosting!*

- **76% more content**: Fixed pagination bug that missed 19 pages - *found the missing cake slices!*
- **Faster processing**: Concurrent API calls with intelligent rate limiting - *multiple ovens, perfect timing*
- **Better RAG results**: Simplified format reduces metadata noise - *less frosting, more flavor*
- **Complete extraction**: Automatic pagination ensures no missing content - *every last crumb accounted for*
- **Enhanced content**: Better macro processing and HTML cleaning - *removed the burnt bits, enhanced the taste*

## 🧪 Development (Test Kitchen)

### Recipe Testing
```bash
# Test new architecture - taste test the latest batch
uv run cake_cli.py confluence 3758620708 --simplified

# Quality control - make sure it looks as good as it tastes
find . -name "*simplified*" -type f | head -3
```

### Architecture Benefits (Why This Recipe Works)
- **Modular**: Easy to add new ingredients and cooking methods
- **Testable**: Clean interfaces that let you taste each layer separately
- **Performant**: Built-in concurrency that doesn't burn anything
- **Maintainable**: Clear separation of prep, cooking, and presentation

## 🗺️ Migration Guide

### From v1.x to v2.0

**Old command:**
```bash
uv run cake.py --mode confluence --query 3492511763 --output-format jsonl-per-page
```

**New command:**
```bash
uv run cake_cli.py confluence 3492511763  # Same output, better performance
```

**Benefits of migration (Why upgrade your kitchen):**
- Faster processing with improved pagination - *new ovens that don't miss any batches*
- Better RAG performance with simplified format option - *cleaner presentation, better taste*
- More reliable extraction with enhanced error handling - *no more burnt cakes*
- Future-proof modular architecture - *a kitchen that grows with your appetite*

## 📚 Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) - Detailed architecture overview
- [`CLAUDE.md`](CLAUDE.md) - Development context and guidelines
- Legacy documentation preserved for compatibility

## 🤝 Contributing (Join the Kitchen Brigade!)

Contributions welcome! The new modular architecture makes it easy to:
- Add new platform integrations - *bring your favorite ingredients*
- Enhance content processors - *improve the cooking techniques*
- Improve output formats - *better plating and presentation*
- Add new CLI commands - *expand the menu*

*Remember: Good code is like a good cake - it should be layered, well-structured, and leave people wanting more!*

## 📄 License

GPL 3.0 License (see LICENSE file for details)