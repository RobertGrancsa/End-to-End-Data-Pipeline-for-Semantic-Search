"""
OpenSearch Package

Orchestrating Services and Visualizing Data with OpenSearch

Developed by: Robert Grancsa
"""

from .client import OpenSearchClient
from .index_manager import IndexManager

__all__ = ["OpenSearchClient", "IndexManager"]
