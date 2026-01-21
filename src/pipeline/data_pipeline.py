"""
Data Pipeline Module

Integrates all components of the semantic search pipeline.

Authors: All Team Members
- Rares-Alexandru Constantin: Web Scraping
- Andrei-Daniel Anghelescu: Kafka Integration
- Ana-Maria Toader: Semantic Processing
- Robert Grancsa: Orchestration
"""

from typing import List, Dict, Optional, Generator, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
from tqdm import tqdm

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config
from src.scraper import WebScraper, ContentExtractor
from src.scraper.web_scraper import ScrapedDocument
from src.kafka import KafkaProducerWrapper, KafkaConsumerWrapper
from src.kafka.consumer import ConsumedMessage
from src.processing import TextChunker, Chunk, EmbeddingGenerator
from src.processing.embedder import EmbeddedChunk
from src.opensearch import OpenSearchClient, IndexManager


@dataclass
class PipelineStats:
    """Statistics for pipeline execution"""
    documents_scraped: int = 0
    documents_sent_to_kafka: int = 0
    documents_consumed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    documents_indexed: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        duration = (self.end_time or datetime.now()) - self.start_time
        return {
            "documents_scraped": self.documents_scraped,
            "documents_sent_to_kafka": self.documents_sent_to_kafka,
            "documents_consumed": self.documents_consumed,
            "chunks_created": self.chunks_created,
            "embeddings_generated": self.embeddings_generated,
            "documents_indexed": self.documents_indexed,
            "errors": self.errors,
            "duration_seconds": duration.total_seconds()
        }


class DataPipeline:
    """
    End-to-end data pipeline for semantic search.
    
    This pipeline orchestrates:
    1. Web scraping (data acquisition)
    2. Kafka streaming (data ingestion)
    3. Text chunking and embedding (data processing)
    4. OpenSearch indexing (data storage)
    
    The pipeline can run in different modes:
    - Full pipeline: Scrape -> Kafka -> Process -> Index
    - Producer mode: Scrape -> Kafka
    - Consumer mode: Kafka -> Process -> Index
    - Direct mode: Scrape -> Process -> Index (no Kafka)
    """
    
    def __init__(
        self,
        use_kafka: bool = True,
        index_name: str = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
        embedding_model: str = None
    ):
        """
        Initialize the data pipeline.
        
        Args:
            use_kafka: Whether to use Kafka for message queuing
            index_name: OpenSearch index name
            chunk_size: Text chunk size in tokens
            chunk_overlap: Overlap between chunks
            embedding_model: Name of the embedding model
        """
        self.use_kafka = use_kafka
        self.index_name = index_name or config.opensearch.index
        self.chunk_size = chunk_size or config.chunking.chunk_size
        self.chunk_overlap = chunk_overlap or config.chunking.chunk_overlap
        self.embedding_model = embedding_model or config.embedding.model_name
        
        # Initialize components
        self.scraper: Optional[WebScraper] = None
        self.producer: Optional[KafkaProducerWrapper] = None
        self.consumer: Optional[KafkaConsumerWrapper] = None
        self.chunker: Optional[TextChunker] = None
        self.embedder: Optional[EmbeddingGenerator] = None
        self.os_client: Optional[OpenSearchClient] = None
        self.index_manager: Optional[IndexManager] = None
        
        self.stats = PipelineStats()
        
        logger.info(f"DataPipeline initialized (use_kafka={use_kafka})")
    
    def initialize_components(self, components: List[str] = None) -> None:
        """
        Initialize pipeline components.
        
        Args:
            components: List of components to initialize
                       ['scraper', 'kafka', 'processing', 'opensearch']
        """
        components = components or ['scraper', 'processing', 'opensearch']
        
        if 'scraper' in components:
            logger.info("Initializing web scraper...")
            self.scraper = WebScraper()
            self.content_extractor = ContentExtractor()
        
        if 'kafka' in components or self.use_kafka:
            logger.info("Initializing Kafka producer and consumer...")
            self.producer = KafkaProducerWrapper()
            self.consumer = KafkaConsumerWrapper()
        
        if 'processing' in components:
            logger.info("Initializing text chunker and embedder...")
            self.chunker = TextChunker(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            self.embedder = EmbeddingGenerator(model_name=self.embedding_model)
            # Pre-load the model
            self.embedder.load_model()
        
        if 'opensearch' in components:
            logger.info("Initializing OpenSearch client...")
            self.os_client = OpenSearchClient(index=self.index_name)
            self.os_client.connect()
            self.index_manager = IndexManager(self.os_client.client)
    
    def setup_index(self, recreate: bool = False) -> bool:
        """
        Setup the OpenSearch index.
        
        Args:
            recreate: Whether to recreate if exists
            
        Returns:
            True if successful
        """
        if not self.index_manager:
            self.initialize_components(['opensearch'])
        
        if recreate:
            return self.index_manager.recreate_index(
                self.index_name,
                dimension=self.embedder.dimension if self.embedder else 384
            )
        else:
            return self.index_manager.create_semantic_index(
                self.index_name,
                dimension=self.embedder.dimension if self.embedder else 384
            )
    
    def scrape_and_produce(
        self,
        urls: List[str],
        crawl: bool = False,
        max_depth: int = 2
    ) -> int:
        """
        Scrape URLs and send to Kafka.
        
        Args:
            urls: List of URLs to scrape
            crawl: Whether to crawl linked pages
            max_depth: Maximum crawl depth
            
        Returns:
            Number of documents produced
        """
        if not self.scraper:
            self.initialize_components(['scraper'])
        
        if self.use_kafka and not self.producer:
            self.initialize_components(['kafka'])
            self.producer.connect()
        
        produced_count = 0
        
        for url in urls:
            if crawl:
                documents = self.scraper.crawl_website(url, max_depth=max_depth)
            else:
                documents = self.scraper.scrape_urls([url])
            
            for doc in documents:
                self.stats.documents_scraped += 1
                
                if self.use_kafka:
                    success = self.producer.send(
                        message=doc.to_dict(),
                        key=doc.doc_id
                    )
                    if success:
                        produced_count += 1
                        self.stats.documents_sent_to_kafka += 1
                else:
                    # Direct processing without Kafka
                    self._process_document(doc.to_dict())
                    produced_count += 1
        
        if self.use_kafka:
            self.producer.flush()
        
        return produced_count
    
    def _process_document(self, doc_dict: Dict) -> List[EmbeddedChunk]:
        """
        Process a single document: chunk, embed, and optionally index.
        
        Args:
            doc_dict: Document dictionary
            
        Returns:
            List of embedded chunks
        """
        if not self.chunker or not self.embedder:
            self.initialize_components(['processing'])
        
        # Extract content
        doc_id = doc_dict.get('doc_id', 'unknown')
        content = doc_dict.get('content', '')
        metadata = {
            'title': doc_dict.get('title', ''),
            'url': doc_dict.get('url', ''),
            'domain': doc_dict.get('domain', ''),
            'timestamp': doc_dict.get('timestamp', '')
        }
        
        # Chunk the text
        chunks = self.chunker.chunk_text(content, doc_id, metadata)
        self.stats.chunks_created += len(chunks)
        
        # Generate embeddings
        embedded_chunks = self.embedder.embed_chunks(chunks, show_progress=False)
        self.stats.embeddings_generated += len(embedded_chunks)
        
        return embedded_chunks
    
    def consume_and_index(
        self,
        batch_size: int = 50,
        max_messages: int = None
    ) -> int:
        """
        Consume from Kafka, process, and index to OpenSearch.
        
        Args:
            batch_size: Number of messages to process before indexing
            max_messages: Maximum messages to consume (None for continuous)
            
        Returns:
            Number of indexed chunks
        """
        if not self.consumer:
            self.initialize_components(['kafka'])
            self.consumer.connect()
        
        if not self.os_client:
            self.initialize_components(['processing', 'opensearch'])
            self.setup_index()
        
        batch = []
        total_indexed = 0
        message_count = 0
        
        logger.info(f"Starting consumer (batch_size={batch_size}, max={max_messages})")
        
        for msg in self.consumer.consume():
            self.stats.documents_consumed += 1
            message_count += 1
            
            try:
                # Process document
                embedded_chunks = self._process_document(msg.value)
                batch.extend(embedded_chunks)
                
                # Index batch when full
                if len(batch) >= batch_size:
                    result = self.os_client.index_embedded_chunks(batch)
                    total_indexed += result['success']
                    self.stats.documents_indexed += result['success']
                    batch = []
                    logger.info(f"Indexed batch: {result['success']} chunks")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                self.stats.errors += 1
            
            # Check if we should stop
            if max_messages and message_count >= max_messages:
                break
        
        # Index remaining batch
        if batch:
            result = self.os_client.index_embedded_chunks(batch)
            total_indexed += result['success']
            self.stats.documents_indexed += result['success']
        
        return total_indexed
    
    def process_urls_direct(
        self,
        urls: List[str],
        batch_size: int = 50,
        show_progress: bool = True
    ) -> int:
        """
        Process URLs directly without Kafka (simplified mode).
        
        Args:
            urls: URLs to scrape and process
            batch_size: Indexing batch size
            show_progress: Show progress bar
            
        Returns:
            Number of indexed chunks
        """
        self.use_kafka = False
        self.initialize_components(['scraper', 'processing', 'opensearch'])
        self.setup_index()
        
        all_embedded = []
        
        # Scrape and process
        url_iter = tqdm(urls, desc="Processing URLs") if show_progress else urls
        
        for url in url_iter:
            doc = self.scraper.scrape_page(url)
            
            if doc:
                self.stats.documents_scraped += 1
                embedded = self._process_document(doc.to_dict())
                all_embedded.extend(embedded)
        
        # Index all chunks
        logger.info(f"Indexing {len(all_embedded)} chunks...")
        
        total_indexed = 0
        for i in range(0, len(all_embedded), batch_size):
            batch = all_embedded[i:i + batch_size]
            result = self.os_client.index_embedded_chunks(batch)
            total_indexed += result['success']
            self.stats.documents_indexed += result['success']
        
        self.stats.end_time = datetime.now()
        
        return total_indexed
    
    def search(
        self,
        query: str,
        k: int = 10,
        search_type: str = "hybrid"
    ) -> List[Dict]:
        """
        Search the indexed documents.
        
        Args:
            query: Search query
            k: Number of results
            search_type: 'semantic', 'text', or 'hybrid'
            
        Returns:
            List of search results
        """
        if not self.os_client:
            self.initialize_components(['opensearch'])
        
        if not self.embedder:
            self.initialize_components(['processing'])
        
        if search_type == "semantic":
            # Pure k-NN search
            query_vector = self.embedder.embed_query(query)
            results = self.os_client.search_knn(query_vector, k=k)
        
        elif search_type == "text":
            # Pure text search
            results = self.os_client.search_text(query, k=k)
        
        else:
            # Hybrid search
            query_vector = self.embedder.embed_query(query)
            results = self.os_client.search_hybrid(query, query_vector, k=k)
        
        return [
            {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "text": r.text,
                "score": r.score,
                "title": r.metadata.get('title', ''),
                "url": r.metadata.get('url', '')
            }
            for r in results
        ]
    
    def get_stats(self) -> Dict:
        """Get pipeline statistics"""
        return self.stats.to_dict()
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()
        if self.os_client:
            self.os_client.close()
        
        logger.info("Pipeline cleanup complete")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


# Example usage
if __name__ == "__main__":
    # Direct mode (without Kafka)
    urls = [
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://en.wikipedia.org/wiki/Natural_language_processing"
    ]
    
    with DataPipeline(use_kafka=False) as pipeline:
        # Process URLs
        indexed = pipeline.process_urls_direct(urls)
        print(f"Indexed {indexed} chunks")
        
        # Search
        results = pipeline.search("What is deep learning?", k=5)
        
        print("\nSearch Results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. Score: {result['score']:.4f}")
            print(f"   Title: {result['title'][:50]}...")
            print(f"   Text: {result['text'][:100]}...")
            print()
        
        # Stats
        print(f"Pipeline stats: {pipeline.get_stats()}")
