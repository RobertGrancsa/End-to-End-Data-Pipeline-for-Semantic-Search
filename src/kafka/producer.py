"""
Kafka Producer Module

A resilient Kafka producer for streaming scraped web data to the ingestion layer.

Author: Andrei-Daniel Anghelescu
Essay: "Building a Resilient Data Ingestion Layer with Apache Kafka"
"""

import json
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config


@dataclass
class ProducerStats:
    """Statistics for the producer"""
    messages_sent: int = 0
    messages_failed: int = 0
    bytes_sent: int = 0
    last_send_time: float = 0


class KafkaProducerWrapper:
    """
    A resilient Kafka producer wrapper with the following features:
    
    - Automatic reconnection on failure
    - Message serialization (JSON)
    - Delivery confirmation callbacks
    - Statistics tracking
    - Graceful shutdown
    
    This producer is designed for high-throughput streaming of scraped
    web documents to the 'raw-web-data' topic.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = None,
        topic: str = None,
        batch_size: int = 16384,
        linger_ms: int = 10,
        compression_type: str = 'gzip',
        acks: str = 'all',
        retries: int = 3
    ):
        """
        Initialize the Kafka producer.
        
        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Default topic to produce to
            batch_size: Size of batches in bytes
            linger_ms: Time to wait for batch to fill
            compression_type: Compression algorithm (gzip, snappy, lz4)
            acks: Acknowledgment level ('0', '1', 'all')
            retries: Number of retries on failure
        """
        self.bootstrap_servers = bootstrap_servers or config.kafka.bootstrap_servers
        self.topic = topic or config.kafka.topic_raw_data
        self.batch_size = batch_size
        self.linger_ms = linger_ms
        self.compression_type = compression_type
        self.acks = acks
        self.retries = retries
        
        self.producer: Optional[KafkaProducer] = None
        self.stats = ProducerStats()
        self._is_connected = False
        
        logger.info(f"Initializing Kafka Producer for topic: {self.topic}")
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(NoBrokersAvailable)
    )
    def connect(self) -> bool:
        """
        Connect to Kafka brokers with retry logic.
        
        Returns:
            True if connection successful
        """
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                batch_size=self.batch_size,
                linger_ms=self.linger_ms,
                compression_type=self.compression_type,
                acks=self.acks,
                retries=self.retries,
                max_block_ms=30000,
                request_timeout_ms=30000
            )
            
            # Verify connection by getting metadata
            self.producer.bootstrap_connected()
            
            self._is_connected = True
            logger.info(f"Successfully connected to Kafka at {self.bootstrap_servers}")
            return True
            
        except NoBrokersAvailable as e:
            logger.error(f"No Kafka brokers available: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def _on_send_success(self, record_metadata):
        """Callback for successful message delivery"""
        self.stats.messages_sent += 1
        self.stats.last_send_time = time.time()
        logger.debug(
            f"Message delivered to {record_metadata.topic}[{record_metadata.partition}] "
            f"at offset {record_metadata.offset}"
        )
    
    def _on_send_error(self, exception: Exception):
        """Callback for failed message delivery"""
        self.stats.messages_failed += 1
        logger.error(f"Message delivery failed: {exception}")
    
    def send(
        self,
        message: Dict[str, Any],
        key: str = None,
        topic: str = None,
        callback_success: Callable = None,
        callback_error: Callable = None
    ) -> bool:
        """
        Send a message to Kafka.
        
        Args:
            message: Dictionary to send (will be JSON serialized)
            key: Message key for partitioning (optional)
            topic: Target topic (defaults to configured topic)
            callback_success: Custom success callback
            callback_error: Custom error callback
            
        Returns:
            True if message was queued successfully
        """
        if not self._is_connected or not self.producer:
            logger.warning("Producer not connected, attempting to connect...")
            self.connect()
        
        target_topic = topic or self.topic
        
        try:
            # Calculate message size for stats
            message_bytes = len(json.dumps(message).encode('utf-8'))
            
            # Send message
            future = self.producer.send(
                target_topic,
                value=message,
                key=key
            )
            
            # Add callbacks
            future.add_callback(callback_success or self._on_send_success)
            future.add_errback(callback_error or self._on_send_error)
            
            self.stats.bytes_sent += message_bytes
            
            logger.debug(f"Message queued for topic {target_topic}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send message: {e}")
            self.stats.messages_failed += 1
            return False
    
    def send_batch(
        self,
        messages: list[Dict[str, Any]],
        topic: str = None
    ) -> int:
        """
        Send multiple messages in a batch.
        
        Args:
            messages: List of dictionaries to send
            topic: Target topic
            
        Returns:
            Number of successfully queued messages
        """
        success_count = 0
        
        for message in messages:
            key = message.get('doc_id') or message.get('id')
            if self.send(message, key=key, topic=topic):
                success_count += 1
        
        # Flush to ensure batch is sent
        self.flush()
        
        logger.info(f"Batch sent: {success_count}/{len(messages)} messages")
        return success_count
    
    def flush(self, timeout: float = 30) -> None:
        """
        Flush all buffered messages.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        if self.producer:
            self.producer.flush(timeout)
            logger.debug("Producer buffer flushed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get producer statistics"""
        return {
            "messages_sent": self.stats.messages_sent,
            "messages_failed": self.stats.messages_failed,
            "bytes_sent": self.stats.bytes_sent,
            "success_rate": (
                self.stats.messages_sent / 
                (self.stats.messages_sent + self.stats.messages_failed)
                if (self.stats.messages_sent + self.stats.messages_failed) > 0
                else 0
            ) * 100
        }
    
    def close(self) -> None:
        """Gracefully close the producer"""
        if self.producer:
            logger.info("Closing Kafka producer...")
            self.flush()
            self.producer.close(timeout=10)
            self._is_connected = False
            logger.info(f"Producer closed. Final stats: {self.get_stats()}")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Example usage and testing
if __name__ == "__main__":
    from src.scraper import WebScraper
    
    logger.add("producer.log", rotation="10 MB")
    
    # Create producer
    with KafkaProducerWrapper() as producer:
        # Create scraper
        scraper = WebScraper(max_pages=5)
        
        # Scrape and send to Kafka
        test_urls = [
            "https://en.wikipedia.org/wiki/Apache_Kafka",
            "https://en.wikipedia.org/wiki/Message_queue"
        ]
        
        for doc in scraper.scrape_urls(test_urls):
            # Send document to Kafka
            success = producer.send(
                message=doc.to_dict(),
                key=doc.doc_id
            )
            
            if success:
                print(f"Sent: {doc.title[:50]}...")
        
        # Print stats
        print(f"\nProducer Stats: {producer.get_stats()}")
