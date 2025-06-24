"""Command-line interface for CAKE."""

import argparse
import logging
import sys
from typing import List

from .core.config import CakeConfig
from .core.processor import CakeProcessor


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="CAKE - Corporate Aggregation & Knowledge Extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cake confluence 3492511763                           # Export page with defaults
  cake confluence 3492511763 --format jsonl           # Single JSONL file  
  cake confluence 3492511763 --simplified             # Minimal metadata
  cake confluence 3492511763 --no-permissions         # Skip permissions
        """
    )
    
    parser.add_argument("--debug", action="store_true", 
                       help="Enable debug logging")
    parser.add_argument("--env-file", default=".env",
                       help="Environment file path (default: .env)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Confluence command
    confluence_parser = subparsers.add_parser("confluence", help="Process Confluence content")
    confluence_parser.add_argument("page_id", help="Confluence page ID to process")
    confluence_parser.add_argument("--format", choices=["json", "jsonl", "jsonl-per-page"],
                                  default="jsonl-per-page", 
                                  help="Output format (default: jsonl-per-page)")
    confluence_parser.add_argument("--simplified", action="store_true",
                                  help="Use simplified output with minimal metadata")
    confluence_parser.add_argument("--no-permissions", action="store_true",
                                  help="Skip permission extraction")
    confluence_parser.add_argument("--max-concurrent", type=int, default=5,
                                  help="Maximum concurrent API calls (default: 5)")
    confluence_parser.add_argument("--delay", type=float, default=0.1,
                                  help="Delay between API calls in seconds (default: 0.1)")
    
    return parser


def handle_confluence_command(args: argparse.Namespace) -> int:
    """Handle confluence command."""
    try:
        # Load configuration
        config = CakeConfig.from_env(args.env_file)
        
        # Apply command-line overrides
        config.simplified_output = args.simplified
        config.include_permissions = not args.no_permissions
        config.max_concurrent_calls = args.max_concurrent
        config.api_call_delay = args.delay
        
        # Create processor and run
        processor = CakeProcessor(config)
        results = processor.process_confluence_page(args.page_id, args.format)
        
        if results["success"]:
            print(f"✅ Processing completed successfully")
            print(f"📄 Page ID: {results['page_id']}")
            if "document_count" in results:
                print(f"📊 Documents processed: {results['document_count']}")
            if "file_count" in results:
                print(f"📁 Files created: {results['file_count']}")
            print(f"⏱️  Processing time: {results['processing_time']}")
            print(f"📂 Files created:")
            for file in results["files_created"]:
                print(f"   • {file}")
            return 0
        else:
            print(f"❌ Processing failed: {results['error']}")
            return 1
            
    except Exception as e:
        logging.error(f"Command failed: {e}")
        return 1


def main(argv: List[str] = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Setup logging
    setup_logging(args.debug)
    
    # Handle commands
    if args.command == "confluence":
        return handle_confluence_command(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())