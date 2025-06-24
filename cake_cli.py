#!/usr/bin/env python3
"""
CAKE CLI entry point.

Usage: uv run cake_cli.py confluence <page_id> [options]
"""

import sys
from cake.cli import main

if __name__ == "__main__":
    sys.exit(main())