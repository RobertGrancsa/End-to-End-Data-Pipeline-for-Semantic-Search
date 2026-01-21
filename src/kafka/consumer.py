"""
Kafka Consumer Module

A resilient Kafka consumer for reading scraped web data from the ingestion layer.

Author: Andrei-Daniel Anghelescu
Essay: "Building a Resilient Data Ingestion Layer with Apache Kafka"
"""

import json
import signal
import time
from typing import Dict, Optional, Callable, Any, Generator
from dataclasses import dataclass, field
from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable
from kafka import TopicPartition, OffsetAndMetadata
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config


@dataclass
class ConsumerStats:
    """Statistics for the consumer"""
    messages_received: int = 0
    messages_processed: int = 0
    messages_failed: int = 0
    bytes_received: int = 0
    processing_time_total: float = 0


@dataclass
class ConsumedMessage:
    """Wrapper for consumed Kafka message"""
    topic: str
    partition: int
    offset: int
    key: Optional[str]
    value: Dict[str, Any]
    timestamp: int
    headers: list = field(default_factory=list)


class KafkaConsumerWrapper:
    """
    A resilient Kafka consumer wrapper with the following features:
    
    - Automatic reconnection on failure
    - Message deserialization (JSON)
    - Manual/automatic offset commit
    - Graceful shutdown handling
    - Statistics tracking
    - Message processing callbacks
    
    This consumer is designed for reliable consumption of scraped
    web documents from the 'raw-web-data' topic.
    """
    
    def __init__(
        self,
        bootstrap_servers: str = None,
        topic: str = None,
        group_id: str = None,
        auto_offset_reset: str = 'earliest',
        enable_auto_commit: bool = False,
        max_poll_records: int = 100,
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 10000
    ):
        """
        Initialize the Kafka consumer.
        
        Args:
            bootstrap_servers: Kafka broker addresses
            topic: Topic to consume from
            group_id: Consumer group ID
            auto_offset_reset: Where to start reading ('earliest', 'latest')
            enable_auto_commit: Whether to auto-commit offsets
            max_poll_records: Maximum records per poll
            session_timeout_ms: Session timeout
            heartbeat_interval_ms: Heartbeat interval
        """
        self.bootstrap_servers = bootstrap_servers or config.kafka.bootstrap_servers
        self.topic = topic or config.kafka.topic_raw_data
        self.group_id = group_id or config.kafka.consumer_group
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.max_poll_records = max_poll_records
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        
        self.consumer: Optional[KafkaConsumer] = None
        self.stats = ConsumerStats()
        self._is_connected = False
        self._should_stop = False
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Initializing Kafka Consumer for topic: {self.topic}, group: {self.group_id}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._should_stop = True
    
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
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                max_poll_records=self.max_poll_records,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms
            )
            
            self._is_connected = True
            logger.info(f"Successfully connected to Kafka at {self.bootstrap_servers}")
            logger.info(f"Subscribed to topic: {self.topic}")
            
            return True
            
        except NoBrokersAvailable as e:
            logger.error(f"No Kafka brokers available: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def consume_one(self, timeout_ms: int = 1000) -> Optional[ConsumedMessage]:
        """
        Consume a single message.
        
        Args:
            timeout_ms: Timeout for polling
            
        Returns:
            ConsumedMessage or None if no message available
        """
        if not self._is_connected or not self.consumer:
            self.connect()
        
        try:
            records = self.consumer.poll(timeout_ms=timeout_ms)
            
            for topic_partition, messages in records.items():
                for msg in messages:
                    self.stats.messages_received += 1
                    self.stats.bytes_received += len(str(msg.value))
                    
                    return ConsumedMessage(
                        topic=msg.topic,
                        partition=msg.partition,
                        offset=msg.offset,
                        key=msg.key,
                        value=msg.value,
                        timestamp=msg.timestamp,
                        headers=list(msg.headers) if msg.headers else []
                    )
            
            return None
            
        except KafkaError as e:
            logger.error(f"Error consuming message: {e}")
            return None
    
    def consume(
        self,
        process_callback: Callable[[ConsumedMessage], bool] = None,
        batch_size: int = 1,
        poll_timeout_ms: int = 1000
    ) -> Generator[ConsumedMessage, None, None]:
        """
        Consume messages continuously.
        
        Args:
            process_callback: Function to call for each message
            batch_size: Number of messages before committing (if not auto-commit)
            poll_timeout_ms: Timeout for each poll
            
        Yields:
            ConsumedMessage objects
        """
        if not self._is_connected or not self.consumer:
            self.connect()
        
        messages_since_commit = 0
        logger.info("Starting message consumption loop...")
        
        while not self._should_stop:
            try:
                records = self.consumer.poll(timeout_ms=poll_timeout_ms)
                
                for topic_partition, messages in records.items():
                    for msg in messages:
                        start_time = time.time()
                        
                        self.stats.messages_received += 1
                        self.stats.bytes_received += len(str(msg.value))
                        
                        consumed = ConsumedMessage(
                            topic=msg.topic,
                            partition=msg.partition,
                            offset=msg.offset,
                            key=msg.key,
                            value=msg.value,
                            timestamp=msg.timestamp,
                            headers=list(msg.headers) if msg.headers else []
                        )
                        
                        # Process message
                        if process_callback:
                            try:
                                success = process_callback(consumed)
                                if success:
                                    self.stats.messages_processed += 1
                                else:
                                    self.stats.messages_failed += 1
                            except Exception as e:
                                logger.error(f"Error in process callback: {e}")
                                self.stats.messages_failed += 1
                        else:
                            self.stats.messages_processed += 1
                        
                        # Track processing time
                        self.stats.processing_time_total += time.time() - start_time
                        
                        yield consumed
                        
                        messages_since_commit += 1
                        
                        # Commit if needed
                        if not self.enable_auto_commit and messages_since_commit >= batch_size:
                            self.commit()
                            messages_since_commit = 0
                
            except KafkaError as e:
                logger.error(f"Kafka error during consumption: {e}")
                time.sleep(1)
        
        logger.info("Consumption loop stopped")
    
    def commit(self, async_commit: bool = False) -> None:
        """
        Commit current offsets.
        
        Args:
            async_commit: Whether to commit asynchronously
        """
        if self.consumer and not self.enable_auto_commit:
            try:
                if async_commit:
                    self.consumer.commit_async()
                else:
                    self.consumer.commit()
                logger.debug("Offsets committed")
            except KafkaError as e:
                logger.error(f"Failed to commit offsets: {e}")
    
    def seek_to_beginning(self) -> None:
        """Seek to beginning of all partitions"""
        if self.consumer:
            partitions = self.consumer.assignment()
            self.consumer.seek_to_beginning(*partitions)
            logger.info("Seeked to beginning of all partitions")
    
    def seek_to_end(self) -> None:
        """Seek to end of all partitions"""
        if self.consumer:
            partitions = self.consumer.assignment()
            self.consumer.seek_to_end(*partitions)
            logger.info("Seeked to end of all partitions")
    
    def get_lag(self) -> Dict[str, int]:
        """
        Get consumer lag for all partitions.
        
        Returns:
            Dictionary mapping partition to lag
        """
        lag = {}
        if self.consumer:
            partitions = self.consumer.assignment()
            end_offsets = self.consumer.end_offsets(partitions)
            
            for partition in partitions:
                current = self.consumer.position(partition)
                end = end_offsets[partition]
                lag[f"{partition.topic}-{partition.partition}"] = end - current
        
        return lag
    
    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics"""
        avg_processing_time = (
            self.stats.processing_time_total / self.stats.messages_processed
            if self.stats.messages_processed > 0 else 0
        )
        
        return {
            "messages_received": self.stats.messages_received,
            "messages_processed": self.stats.messages_processed,
            "messages_failed": self.stats.messages_failed,
            "bytes_received": self.stats.bytes_received,
            "avg_processing_time_ms": avg_processing_time * 1000,
            "success_rate": (
                self.stats.messages_processed /
                (self.stats.messages_processed + self.stats.messages_failed)
                if (self.stats.messages_processed + self.stats.messages_failed) > 0
                else 0
            ) * 100
        }
    
    def stop(self) -> None:
        """Signal the consumer to stop"""
        self._should_stop = True
        logger.info("Stop signal sent to consumer")
    
    def close(self) -> None:
        """Gracefully close the consumer"""
        if self.consumer:
            logger.info("Closing Kafka consumer...")
            # Commit any remaining offsets
            if not self.enable_auto_commit:
                self.commit()
            self.consumer.close()
            self._is_connected = False
            logger.info(f"Consumer closed. Final stats: {self.get_stats()}")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Example usage and testing
if __name__ == "__main__":
    logger.add("consumer.log", rotation="10 MB")
    
    def process_message(msg: ConsumedMessage) -> bool:
        """Example message processor"""
        print(f"Received: {msg.value.get('title', 'No title')[:50]}...")
        print(f"  Key: {msg.key}")
        print(f"  Partition: {msg.partition}, Offset: {msg.offset}")
        print(f"  Content length: {len(msg.value.get('content', ''))}")
        print("---")
        return True
    
    # Create consumer
    with KafkaConsumerWrapper() as consumer:
        print("Waiting for messages... (Ctrl+C to stop)")
        
        # Consume messages
        message_count = 0
        for msg in consumer.consume(process_callback=process_message, batch_size=10):
            message_count += 1
            
            # Stop after 100 messages for testing
            if message_count >= 100:
                consumer.stop()
        
        # Print stats
        print(f"\nConsumer Stats: {consumer.get_stats()}")
        print(f"Consumer Lag: {consumer.get_lag()}")
