"""
Test Suite for Semantic Search Pipeline

Run with: pytest tests/ -v
"""

import pytest
import sys
sys.path.insert(0, '..')


class TestTextChunker:
    """Tests for the text chunking module"""
    
    def test_basic_chunking(self):
        """Test basic text chunking"""
        from src.processing.chunker import TextChunker
        
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        
        text = """
        This is a test document with multiple sentences.
        It contains enough text to be split into multiple chunks.
        Each chunk should have some overlap with the next one.
        This helps maintain context across chunk boundaries.
        """
        
        chunks = chunker.chunk_text(text, "test_doc")
        
        assert len(chunks) > 0
        assert all(c.doc_id == "test_doc" for c in chunks)
        assert all(c.text for c in chunks)
    
    def test_empty_text(self):
        """Test handling of empty text"""
        from src.processing.chunker import TextChunker
        
        chunker = TextChunker()
        chunks = chunker.chunk_text("", "empty_doc")
        
        assert len(chunks) == 0
    
    def test_chunk_metadata(self):
        """Test that metadata is preserved"""
        from src.processing.chunker import TextChunker
        
        chunker = TextChunker(chunk_size=100)
        
        metadata = {"source": "test", "category": "demo"}
        text = "This is a test document with some content."
        
        chunks = chunker.chunk_text(text, "meta_doc", metadata)
        
        if chunks:
            assert chunks[0].metadata == metadata


class TestContentExtractor:
    """Tests for content extraction"""
    
    def test_html_extraction(self):
        """Test HTML content extraction"""
        from src.scraper.content_extractor import ContentExtractor
        
        extractor = ContentExtractor()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Page</title></head>
        <body>
            <script>console.log('removed');</script>
            <main>
                <h1>Main Heading</h1>
                <p>This is the main content paragraph.</p>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract(html)
        
        assert result.title == "Test Page"
        assert "Main Heading" in result.main_content
        assert "console.log" not in result.main_content  # Script removed
    
    def test_heading_extraction(self):
        """Test heading extraction"""
        from src.scraper.content_extractor import ContentExtractor
        
        extractor = ContentExtractor()
        
        html = """
        <html>
        <body>
            <h1>First Heading</h1>
            <h2>Second Heading</h2>
            <h3>Third Heading</h3>
        </body>
        </html>
        """
        
        result = extractor.extract(html)
        
        assert len(result.headings) == 3


class TestWebScraper:
    """Tests for web scraper"""
    
    def test_url_validation(self):
        """Test URL domain extraction"""
        from src.scraper.web_scraper import WebScraper
        
        scraper = WebScraper()
        
        domain = scraper._extract_domain("https://example.com/path/page")
        assert domain == "example.com"
    
    def test_doc_id_generation(self):
        """Test unique document ID generation"""
        from src.scraper.web_scraper import WebScraper
        
        scraper = WebScraper()
        
        id1 = scraper._generate_doc_id("http://example.com", "content1")
        id2 = scraper._generate_doc_id("http://example.com", "content2")
        
        assert id1 != id2  # Different content = different ID
        assert len(id1) == 16  # Expected length


class TestKafkaProducer:
    """Tests for Kafka producer (mocked)"""
    
    def test_producer_initialization(self):
        """Test producer configuration"""
        from src.kafka.producer import KafkaProducerWrapper
        
        producer = KafkaProducerWrapper(
            bootstrap_servers="localhost:9092",
            topic="test-topic"
        )
        
        assert producer.topic == "test-topic"
        assert producer.bootstrap_servers == "localhost:9092"
    
    def test_producer_stats(self):
        """Test producer statistics tracking"""
        from src.kafka.producer import KafkaProducerWrapper, ProducerStats
        
        producer = KafkaProducerWrapper()
        
        stats = producer.get_stats()
        
        assert "messages_sent" in stats
        assert "messages_failed" in stats
        assert "success_rate" in stats


class TestKafkaConsumer:
    """Tests for Kafka consumer (mocked)"""
    
    def test_consumer_initialization(self):
        """Test consumer configuration"""
        from src.kafka.consumer import KafkaConsumerWrapper
        
        consumer = KafkaConsumerWrapper(
            bootstrap_servers="localhost:9092",
            topic="test-topic",
            group_id="test-group"
        )
        
        assert consumer.topic == "test-topic"
        assert consumer.group_id == "test-group"
    
    def test_consumed_message_structure(self):
        """Test consumed message dataclass"""
        from src.kafka.consumer import ConsumedMessage
        
        msg = ConsumedMessage(
            topic="test",
            partition=0,
            offset=100,
            key="doc1",
            value={"content": "test"},
            timestamp=1234567890
        )
        
        assert msg.topic == "test"
        assert msg.key == "doc1"


class TestOpenSearchClient:
    """Tests for OpenSearch client"""
    
    def test_client_initialization(self):
        """Test client configuration"""
        from src.opensearch.client import OpenSearchClient
        
        client = OpenSearchClient(
            host="localhost",
            port=9200,
            index="test-index"
        )
        
        assert client.host == "localhost"
        assert client.port == 9200
        assert client.index == "test-index"
    
    def test_search_result_structure(self):
        """Test search result dataclass"""
        from src.opensearch.client import SearchResult
        
        result = SearchResult(
            doc_id="doc1",
            chunk_id="chunk1",
            text="Test content",
            score=0.95,
            metadata={"title": "Test"}
        )
        
        assert result.score == 0.95
        assert result.metadata["title"] == "Test"


class TestDataPipeline:
    """Tests for the main data pipeline"""
    
    def test_pipeline_initialization(self):
        """Test pipeline configuration"""
        from src.pipeline.data_pipeline import DataPipeline
        
        pipeline = DataPipeline(use_kafka=False)
        
        assert pipeline.use_kafka == False
        assert pipeline.stats is not None
    
    def test_pipeline_stats(self):
        """Test pipeline statistics"""
        from src.pipeline.data_pipeline import PipelineStats
        
        stats = PipelineStats()
        
        result = stats.to_dict()
        
        assert "documents_scraped" in result
        assert "chunks_created" in result
        assert "duration_seconds" in result


class TestConfiguration:
    """Tests for configuration module"""
    
    def test_config_loading(self):
        """Test configuration loading"""
        from src.config import Config
        
        config = Config.load()
        
        assert config.kafka is not None
        assert config.opensearch is not None
        assert config.embedding is not None
        assert config.chunking is not None
    
    def test_default_values(self):
        """Test default configuration values"""
        from src.config import config
        
        assert config.embedding.dimension == 384
        assert config.chunking.chunk_size == 500


# Integration test (requires running services)
class TestIntegration:
    """Integration tests (skipped by default)"""
    
    @pytest.mark.skip(reason="Requires running infrastructure")
    def test_full_pipeline(self):
        """Test full pipeline flow"""
        from src.pipeline.data_pipeline import DataPipeline
        
        with DataPipeline(use_kafka=False) as pipeline:
            # Would test actual scraping, processing, and indexing
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
