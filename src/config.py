"""
Configuration Module for the Semantic Search Pipeline

This module handles all configuration settings loaded from environment variables.
Author: Robert Grancsa (Orchestration)
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class KafkaConfig:
    """Kafka configuration settings"""
    bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic_raw_data: str = os.getenv("KAFKA_TOPIC_RAW_DATA", "raw-web-data")
    consumer_group: str = os.getenv("KAFKA_CONSUMER_GROUP", "semantic-pipeline-group")


@dataclass
class OpenSearchConfig:
    """OpenSearch configuration settings"""
    host: str = os.getenv("OPENSEARCH_HOST", "localhost")
    port: int = int(os.getenv("OPENSEARCH_PORT", "9200"))
    index: str = os.getenv("OPENSEARCH_INDEX", "semantic-documents")
    user: Optional[str] = os.getenv("OPENSEARCH_USER")
    password: Optional[str] = os.getenv("OPENSEARCH_PASSWORD")
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class EmbeddingConfig:
    """Embedding model configuration"""
    model_name: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))


@dataclass
class ChunkingConfig:
    """Text chunking configuration"""
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "50"))


@dataclass
class ScraperConfig:
    """Web scraper configuration"""
    user_agent: str = os.getenv(
        "SCRAPER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    delay_seconds: float = float(os.getenv("SCRAPER_DELAY_SECONDS", "1"))
    max_pages_per_site: int = int(os.getenv("MAX_PAGES_PER_SITE", "100"))


@dataclass
class Config:
    """Main configuration class aggregating all configs"""
    kafka: KafkaConfig
    opensearch: OpenSearchConfig
    embedding: EmbeddingConfig
    chunking: ChunkingConfig
    scraper: ScraperConfig
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment"""
        return cls(
            kafka=KafkaConfig(),
            opensearch=OpenSearchConfig(),
            embedding=EmbeddingConfig(),
            chunking=ChunkingConfig(),
            scraper=ScraperConfig()
        )


# Global configuration instance
config = Config.load()
