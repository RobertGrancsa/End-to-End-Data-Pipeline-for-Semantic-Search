"""
Processing Package

Implementing a Semantic Processing Pipeline for Text Embeddings

Developed by: Ana-Maria Toader
"""

from .chunker import TextChunker, Chunk
from .embedder import EmbeddingGenerator

__all__ = ["TextChunker", "Chunk", "EmbeddingGenerator"]
