"""
Pipeline Runner Module

Command-line interface for running the data pipeline.

Author: Robert Grancsa
"""

import argparse
import sys
import os
from typing import List
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.pipeline.data_pipeline import DataPipeline


def setup_logging(level: str = "INFO", log_file: str = None):
    """Configure logging"""
    logger.remove()
    logger.add(sys.stderr, level=level)
    
    if log_file:
        logger.add(log_file, rotation="10 MB", level=level)


def run_producer(urls: List[str], crawl: bool = False):
    """Run the producer (scrape and send to Kafka)"""
    with DataPipeline(use_kafka=True) as pipeline:
        pipeline.initialize_components(['scraper', 'kafka'])
        pipeline.producer.connect()
        
        count = pipeline.scrape_and_produce(urls, crawl=crawl)
        logger.info(f"Produced {count} documents to Kafka")
        logger.info(f"Stats: {pipeline.get_stats()}")


def run_consumer(batch_size: int = 50, max_messages: int = None):
    """Run the consumer (read from Kafka, process, index)"""
    with DataPipeline(use_kafka=True) as pipeline:
        pipeline.initialize_components(['kafka', 'processing', 'opensearch'])
        pipeline.setup_index()
        pipeline.consumer.connect()
        
        indexed = pipeline.consume_and_index(
            batch_size=batch_size,
            max_messages=max_messages
        )
        logger.info(f"Indexed {indexed} chunks")
        logger.info(f"Stats: {pipeline.get_stats()}")


def run_direct(urls: List[str], batch_size: int = 50):
    """Run in direct mode (no Kafka)"""
    with DataPipeline(use_kafka=False) as pipeline:
        indexed = pipeline.process_urls_direct(urls, batch_size=batch_size)
        logger.info(f"Indexed {indexed} chunks")
        logger.info(f"Stats: {pipeline.get_stats()}")


def run_search(query: str, k: int = 10, search_type: str = "hybrid"):
    """Run a search query"""
    with DataPipeline(use_kafka=False) as pipeline:
        pipeline.initialize_components(['processing', 'opensearch'])
        
        results = pipeline.search(query, k=k, search_type=search_type)
        
        print(f"\nSearch Results for: '{query}'\n")
        print("=" * 60)
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Score: {result['score']:.4f}")
            print(f"   Title: {result['title'][:60]}")
            print(f"   URL: {result['url']}")
            print(f"   Text: {result['text'][:200]}...")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Semantic Search Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape URLs and send to Kafka
  python pipeline_runner.py producer --urls https://example.com https://example2.com

  # Start consumer to process Kafka messages
  python pipeline_runner.py consumer --batch-size 100

  # Direct mode (no Kafka)
  python pipeline_runner.py direct --urls https://example.com

  # Search indexed documents
  python pipeline_runner.py search --query "machine learning" --type hybrid
        """
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    parser.add_argument(
        "--log-file",
        help="Log file path"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Producer command
    producer_parser = subparsers.add_parser("producer", help="Run producer mode")
    producer_parser.add_argument(
        "--urls",
        nargs="+",
        required=True,
        help="URLs to scrape"
    )
    producer_parser.add_argument(
        "--crawl",
        action="store_true",
        help="Crawl linked pages"
    )
    
    # Consumer command
    consumer_parser = subparsers.add_parser("consumer", help="Run consumer mode")
    consumer_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for indexing"
    )
    consumer_parser.add_argument(
        "--max-messages",
        type=int,
        help="Maximum messages to consume"
    )
    
    # Direct command
    direct_parser = subparsers.add_parser("direct", help="Run in direct mode (no Kafka)")
    direct_parser.add_argument(
        "--urls",
        nargs="+",
        required=True,
        help="URLs to process"
    )
    direct_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for indexing"
    )
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search indexed documents")
    search_parser.add_argument(
        "--query",
        required=True,
        help="Search query"
    )
    search_parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Number of results"
    )
    search_parser.add_argument(
        "--type",
        choices=["semantic", "text", "hybrid"],
        default="hybrid",
        help="Search type"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file)
    
    # Run command
    if args.command == "producer":
        run_producer(args.urls, args.crawl)
    elif args.command == "consumer":
        run_consumer(args.batch_size, args.max_messages)
    elif args.command == "direct":
        run_direct(args.urls, args.batch_size)
    elif args.command == "search":
        run_search(args.query, args.k, args.type)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
