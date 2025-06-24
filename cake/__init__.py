"""
CAKE - Corporate Aggregation & Knowledge Extraction

A modular framework for extracting content from enterprise platforms
(Jira, Confluence, Google Drive) with permissions for RAG ingestion.
"""

__version__ = "2.0.0"
__author__ = "Digital Workplace Solutions"

from .core.processor import CakeProcessor
from .core.config import CakeConfig

__all__ = ["CakeProcessor", "CakeConfig"]