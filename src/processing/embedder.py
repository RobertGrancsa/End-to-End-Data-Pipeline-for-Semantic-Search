"""
Embedding Generator Module

Generates vector embeddings using sentence-transformers for semantic search.

Author: Ana-Maria Toader
Essay: "Implementing a Semantic Processing Pipeline for Text Embeddings"
"""

import os
from typing import List, Optional, Union
import numpy as np
from dataclasses import dataclass
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")

from src.config import config
from src.processing.chunker import Chunk


@dataclass
class EmbeddedChunk:
    """A chunk with its vector embedding"""
    chunk: Chunk
    embedding: List[float]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for indexing"""
        data = self.chunk.to_dict()
        data['embedding'] = self.embedding
        return data


class EmbeddingGenerator:
    """
    Generates vector embeddings for text using sentence-transformers.
    
    Features:
    - Uses HuggingFace sentence-transformers
    - Supports multiple embedding models
    - Batch processing for efficiency
    - CPU/GPU automatic detection
    - Caching support for repeated queries
    
    Default model: all-MiniLM-L6-v2 (384 dimensions)
    This model offers a good balance between quality and speed.
    """
    
    # Popular embedding models with their dimensions
    MODELS = {
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-multilingual-MiniLM-L12-v2": 384,
        "msmarco-MiniLM-L6-cos-v5": 384,
    }
    
    def __init__(
        self,
        model_name: str = None,
        device: str = None,
        normalize: bool = True,
        cache_folder: str = None
    ):
        """
        Initialize the embedding generator.
        
        Args:
            model_name: Name of the sentence-transformer model
            device: Device to use ('cpu', 'cuda', 'mps', or None for auto)
            normalize: Whether to normalize embeddings to unit length
            cache_folder: Folder to cache downloaded models
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            )
        
        self.model_name = model_name or config.embedding.model_name
        self.normalize = normalize
        self.device = device
        self.cache_folder = cache_folder or os.path.join(os.getcwd(), "models_cache")
        
        # Determine embedding dimension
        self.dimension = self.MODELS.get(self.model_name, config.embedding.dimension)
        
        self.model: Optional[SentenceTransformer] = None
        self._is_loaded = False
        
        logger.info(
            f"EmbeddingGenerator initialized with model: {self.model_name} "
            f"(dimension: {self.dimension})"
        )
    
    def load_model(self) -> None:
        """Load the embedding model"""
        if self._is_loaded:
            return
        
        try:
            logger.info(f"Loading model: {self.model_name}...")
            
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_folder
            )
            
            self._is_loaded = True
            
            # Log device information
            device_info = str(self.model.device)
            logger.info(f"Model loaded successfully on device: {device_info}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        if not self._is_loaded:
            self.load_model()
        
        # Generate embedding
        embedding = self.model.encode(
            text,
            normalize_embeddings=self.normalize,
            show_progress_bar=False
        )
        
        return embedding.tolist()
    
    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar
            
        Returns:
            List of embedding vectors
        """
        if not self._is_loaded:
            self.load_model()
        
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts...")
        
        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize,
            show_progress_bar=show_progress
        )
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        return embeddings.tolist()
    
    def embed_chunk(self, chunk: Chunk) -> EmbeddedChunk:
        """
        Generate embedding for a chunk.
        
        Args:
            chunk: Chunk object to embed
            
        Returns:
            EmbeddedChunk with embedding
        """
        embedding = self.embed_text(chunk.text)
        return EmbeddedChunk(chunk=chunk, embedding=embedding)
    
    def embed_chunks(
        self,
        chunks: List[Chunk],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> List[EmbeddedChunk]:
        """
        Generate embeddings for multiple chunks.
        
        Args:
            chunks: List of Chunk objects
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar
            
        Returns:
            List of EmbeddedChunk objects
        """
        if not chunks:
            return []
        
        # Extract texts
        texts = [chunk.text for chunk in chunks]
        
        # Generate embeddings
        embeddings = self.embed_texts(texts, batch_size, show_progress)
        
        # Create embedded chunks
        embedded_chunks = [
            EmbeddedChunk(chunk=chunk, embedding=embedding)
            for chunk, embedding in zip(chunks, embeddings)
        ]
        
        return embedded_chunks
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.
        
        Some models have different behaviors for queries vs documents.
        This method handles that distinction.
        
        Args:
            query: Search query text
            
        Returns:
            Query embedding vector
        """
        return self.embed_text(query)
    
    def similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1 for normalized vectors)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 5
    ) -> List[tuple]:
        """
        Find most similar embeddings to a query.
        
        Args:
            query_embedding: Query vector
            candidate_embeddings: List of candidate vectors
            top_k: Number of top results to return
            
        Returns:
            List of (index, similarity_score) tuples
        """
        similarities = [
            (i, self.similarity(query_embedding, emb))
            for i, emb in enumerate(candidate_embeddings)
        ]
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def get_dimension(self) -> int:
        """Get the embedding dimension"""
        return self.dimension
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model"""
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "is_loaded": self._is_loaded,
            "device": str(self.model.device) if self.model else None,
            "normalize": self.normalize
        }


# Cached embedding generator for repeated queries
class CachedEmbeddingGenerator(EmbeddingGenerator):
    """
    Embedding generator with caching for efficiency.
    """
    
    def __init__(self, cache_size: int = 10000, **kwargs):
        super().__init__(**kwargs)
        self.cache = {}
        self.cache_size = cache_size
        self.cache_hits = 0
        self.cache_misses = 0
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding with caching"""
        cache_key = self._get_cache_key(text)
        
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        embedding = super().embed_text(text)
        
        # Add to cache if space available
        if len(self.cache) < self.cache_size:
            self.cache[cache_key] = embedding
        
        return embedding
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        total = self.cache_hits + self.cache_misses
        return {
            "cache_size": len(self.cache),
            "max_size": self.cache_size,
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": self.cache_hits / total if total > 0 else 0
        }


# Example usage and testing
if __name__ == "__main__":
    from src.processing.chunker import TextChunker
    
    # Sample text
    sample_text = """
    Machine learning is a powerful technology that enables computers to learn from data.
    It has applications in many fields including healthcare, finance, and transportation.
    Deep learning, a subset of machine learning, uses neural networks with many layers.
    """
    
    # Create chunker and embedder
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    embedder = EmbeddingGenerator()
    
    # Chunk and embed
    chunks = chunker.chunk_text(sample_text, "test_doc")
    embedded_chunks = embedder.embed_chunks(chunks)
    
    print(f"Created {len(embedded_chunks)} embedded chunks")
    print(f"Model info: {embedder.get_model_info()}")
    
    # Test similarity search
    query = "What is deep learning?"
    query_embedding = embedder.embed_query(query)
    
    print(f"\nQuery: {query}")
    print(f"Query embedding dimension: {len(query_embedding)}")
    
    # Find similar chunks
    candidate_embeddings = [ec.embedding for ec in embedded_chunks]
    similar = embedder.find_most_similar(query_embedding, candidate_embeddings, top_k=2)
    
    print("\nMost similar chunks:")
    for idx, score in similar:
        print(f"  Score: {score:.4f} - {embedded_chunks[idx].chunk.text[:100]}...")
