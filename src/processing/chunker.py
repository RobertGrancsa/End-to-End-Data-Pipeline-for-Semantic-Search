"""
Text Chunker Module

Implements text chunking with sliding window for optimal embedding generation.

Author: Ana-Maria Toader
Essay: "Implementing a Semantic Processing Pipeline for Text Embeddings"
"""

import re
from typing import List, Optional, Generator
from dataclasses import dataclass, field
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config


@dataclass
class Chunk:
    """Represents a text chunk with metadata"""
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    token_count: int
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "token_count": self.token_count,
            "metadata": self.metadata
        }


class TextChunker:
    """
    Text chunking implementation using sliding window approach.
    
    Features:
    - Token-based chunking (approximation using words)
    - Configurable chunk size and overlap
    - Sentence-aware boundaries
    - Maintains document context
    - Generates unique chunk IDs
    
    The sliding window approach ensures that semantic context is preserved
    across chunk boundaries by overlapping adjacent chunks.
    """
    
    # Sentence ending patterns
    SENTENCE_ENDINGS = re.compile(r'[.!?]\s+')
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        respect_sentences: bool = True,
        min_chunk_size: int = 50
    ):
        """
        Initialize the text chunker.
        
        Args:
            chunk_size: Target number of tokens per chunk (default from config)
            chunk_overlap: Number of overlapping tokens between chunks
            respect_sentences: Try to break at sentence boundaries
            min_chunk_size: Minimum chunk size in tokens
        """
        self.chunk_size = chunk_size or config.chunking.chunk_size
        self.chunk_overlap = chunk_overlap or config.chunking.chunk_overlap
        self.respect_sentences = respect_sentences
        self.min_chunk_size = min_chunk_size
        
        logger.info(
            f"TextChunker initialized: chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, respect_sentences={self.respect_sentences}"
        )
    
    def _count_tokens(self, text: str) -> int:
        """
        Approximate token count using word count.
        Most tokenizers produce ~1.3 tokens per word for English.
        """
        words = text.split()
        return int(len(words) * 1.3)
    
    def _word_count(self, text: str) -> int:
        """Count words in text"""
        return len(text.split())
    
    def _find_sentence_boundary(self, text: str, target_pos: int, search_range: int = 100) -> int:
        """
        Find the nearest sentence boundary to the target position.
        
        Args:
            text: The text to search in
            target_pos: Target character position
            search_range: Range to search for boundaries
            
        Returns:
            Character position of nearest sentence boundary
        """
        # Search backwards from target
        search_start = max(0, target_pos - search_range)
        search_text = text[search_start:target_pos]
        
        # Find all sentence endings in search range
        matches = list(self.SENTENCE_ENDINGS.finditer(search_text))
        
        if matches:
            # Return position after the last sentence ending
            last_match = matches[-1]
            return search_start + last_match.end()
        
        # If no sentence boundary found, look for other natural breaks
        # Try to break at paragraph or newline
        newline_pos = search_text.rfind('\n')
        if newline_pos != -1:
            return search_start + newline_pos + 1
        
        # Fall back to target position
        return target_pos
    
    def _split_into_words(self, text: str) -> List[tuple]:
        """
        Split text into words with their character positions.
        
        Returns:
            List of (word, start_pos, end_pos) tuples
        """
        words = []
        for match in re.finditer(r'\S+', text):
            words.append((match.group(), match.start(), match.end()))
        return words
    
    def chunk_text(
        self,
        text: str,
        doc_id: str,
        metadata: dict = None
    ) -> List[Chunk]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: The text to chunk
            doc_id: Document ID for reference
            metadata: Optional metadata to include in chunks
            
        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            logger.warning(f"Empty text provided for doc_id: {doc_id}")
            return []
        
        # Clean text
        text = ' '.join(text.split())
        
        # Get words with positions
        words = self._split_into_words(text)
        
        if not words:
            return []
        
        # Calculate word-based sizes (tokens ≈ words * 1.3)
        words_per_chunk = int(self.chunk_size / 1.3)
        words_overlap = int(self.chunk_overlap / 1.3)
        
        chunks = []
        chunk_index = 0
        start_word_idx = 0
        
        while start_word_idx < len(words):
            # Determine end word index
            end_word_idx = min(start_word_idx + words_per_chunk, len(words))
            
            # Get character positions
            start_char = words[start_word_idx][1]
            end_char = words[end_word_idx - 1][2]
            
            # Try to respect sentence boundaries
            if self.respect_sentences and end_word_idx < len(words):
                boundary = self._find_sentence_boundary(text, end_char)
                
                # Find the word at or after the boundary
                for idx in range(start_word_idx, min(end_word_idx + 20, len(words))):
                    if words[idx][1] >= boundary:
                        # Only adjust if it doesn't make chunk too small
                        if idx - start_word_idx >= int(self.min_chunk_size / 1.3):
                            end_word_idx = idx
                            end_char = boundary
                        break
            
            # Extract chunk text
            chunk_text = text[start_char:end_char].strip()
            
            # Skip if chunk is too small
            if len(chunk_text.split()) < int(self.min_chunk_size / 2):
                start_word_idx = end_word_idx
                continue
            
            # Create chunk
            chunk = Chunk(
                chunk_id=f"{doc_id}_chunk_{chunk_index}",
                doc_id=doc_id,
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=end_char,
                token_count=self._count_tokens(chunk_text),
                metadata=metadata or {}
            )
            
            chunks.append(chunk)
            chunk_index += 1
            
            # Move to next chunk with overlap
            if end_word_idx >= len(words):
                break
            
            start_word_idx = max(start_word_idx + 1, end_word_idx - words_overlap)
        
        logger.info(f"Created {len(chunks)} chunks from document {doc_id}")
        return chunks
    
    def chunk_generator(
        self,
        text: str,
        doc_id: str,
        metadata: dict = None
    ) -> Generator[Chunk, None, None]:
        """
        Generator version of chunk_text for memory efficiency.
        
        Args:
            text: The text to chunk
            doc_id: Document ID
            metadata: Optional metadata
            
        Yields:
            Chunk objects
        """
        for chunk in self.chunk_text(text, doc_id, metadata):
            yield chunk
    
    def chunk_documents(
        self,
        documents: List[dict]
    ) -> Generator[Chunk, None, None]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of dicts with 'doc_id', 'content', and optional 'metadata'
            
        Yields:
            Chunk objects from all documents
        """
        for doc in documents:
            doc_id = doc.get('doc_id', 'unknown')
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            # Add document-level metadata
            metadata['title'] = doc.get('title', '')
            metadata['url'] = doc.get('url', '')
            
            for chunk in self.chunk_generator(content, doc_id, metadata):
                yield chunk
    
    def get_chunk_stats(self, chunks: List[Chunk]) -> dict:
        """
        Get statistics about a list of chunks.
        
        Args:
            chunks: List of Chunk objects
            
        Returns:
            Dictionary with chunk statistics
        """
        if not chunks:
            return {"count": 0}
        
        token_counts = [c.token_count for c in chunks]
        
        return {
            "count": len(chunks),
            "total_tokens": sum(token_counts),
            "avg_tokens": sum(token_counts) / len(token_counts),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts)
        }


# Semantic chunker with additional intelligence
class SemanticChunker(TextChunker):
    """
    Enhanced chunker that considers semantic structure.
    
    Improvements over basic chunker:
    - Detects headings and keeps them with content
    - Preserves paragraph structure
    - Handles lists and code blocks
    """
    
    # Heading patterns
    HEADING_PATTERN = re.compile(r'^(#{1,6}\s+.+|[A-Z][^.!?]*:)$', re.MULTILINE)
    
    def _detect_sections(self, text: str) -> List[tuple]:
        """Detect text sections based on headings"""
        sections = []
        current_start = 0
        current_heading = ""
        
        for match in self.HEADING_PATTERN.finditer(text):
            if current_start < match.start():
                sections.append((current_heading, text[current_start:match.start()]))
            current_heading = match.group().strip()
            current_start = match.end()
        
        # Add final section
        if current_start < len(text):
            sections.append((current_heading, text[current_start:]))
        
        return sections if sections else [("", text)]
    
    def chunk_text(
        self,
        text: str,
        doc_id: str,
        metadata: dict = None
    ) -> List[Chunk]:
        """
        Chunk text with semantic awareness.
        """
        sections = self._detect_sections(text)
        all_chunks = []
        global_chunk_index = 0
        
        for heading, section_text in sections:
            # Prepend heading to each chunk for context
            prefix = f"{heading}\n\n" if heading else ""
            
            # Get base chunks
            base_chunks = super().chunk_text(section_text, doc_id, metadata)
            
            for chunk in base_chunks:
                # Add heading context
                if prefix:
                    chunk.text = prefix + chunk.text
                    chunk.token_count = self._count_tokens(chunk.text)
                    chunk.metadata['section_heading'] = heading
                
                # Update global chunk index
                chunk.chunk_index = global_chunk_index
                chunk.chunk_id = f"{doc_id}_chunk_{global_chunk_index}"
                
                all_chunks.append(chunk)
                global_chunk_index += 1
        
        return all_chunks


# Example usage and testing
if __name__ == "__main__":
    sample_text = """
    Introduction to Machine Learning
    
    Machine learning is a subset of artificial intelligence that enables systems to learn 
    and improve from experience without being explicitly programmed. It focuses on developing 
    computer programs that can access data and use it to learn for themselves.
    
    Types of Machine Learning
    
    There are three main types of machine learning: supervised learning, unsupervised learning, 
    and reinforcement learning. Supervised learning involves training a model on labeled data. 
    Unsupervised learning finds hidden patterns in unlabeled data. Reinforcement learning 
    trains agents through rewards and penalties.
    
    Applications
    
    Machine learning has numerous applications including image recognition, natural language 
    processing, recommendation systems, fraud detection, and autonomous vehicles. These 
    applications are transforming industries from healthcare to finance to transportation.
    
    Deep Learning
    
    Deep learning is a subset of machine learning that uses neural networks with many layers.
    These deep neural networks can learn complex patterns and representations from large 
    amounts of data. Popular architectures include CNNs for images and RNNs for sequences.
    """
    
    # Test basic chunker
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_text(sample_text, "doc_001")
    
    print("Basic Chunker Results:")
    print(f"Created {len(chunks)} chunks\n")
    
    for chunk in chunks:
        print(f"Chunk {chunk.chunk_index}:")
        print(f"  Tokens: {chunk.token_count}")
        print(f"  Text: {chunk.text[:100]}...")
        print()
    
    # Test semantic chunker
    semantic_chunker = SemanticChunker(chunk_size=100, chunk_overlap=20)
    semantic_chunks = semantic_chunker.chunk_text(sample_text, "doc_001")
    
    print("\nSemantic Chunker Results:")
    print(f"Created {len(semantic_chunks)} chunks")
    print(f"Stats: {chunker.get_chunk_stats(semantic_chunks)}")
