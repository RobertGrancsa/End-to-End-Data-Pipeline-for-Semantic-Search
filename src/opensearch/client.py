"""
OpenSearch Client Module

Client wrapper for OpenSearch operations including k-NN search.

Author: Robert Grancsa
Essay: "Orchestrating Services and Visualizing Data with OpenSearch"
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import NotFoundError, RequestError
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config
from src.processing.chunker import Chunk
from src.processing.embedder import EmbeddedChunk


@dataclass
class SearchResult:
    """Represents a search result"""
    doc_id: str
    chunk_id: str
    text: str
    score: float
    metadata: dict


class OpenSearchClient:
    """
    OpenSearch client wrapper for vector search operations.
    
    Features:
    - Connection management with retry
    - Bulk indexing for efficiency
    - k-NN (vector) search
    - Hybrid search (lexical + semantic)
    - Index management
    
    This client is optimized for semantic search use cases with
    support for dense vector embeddings.
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        index: str = None,
        user: str = None,
        password: str = None,
        use_ssl: bool = False,
        verify_certs: bool = False
    ):
        """
        Initialize the OpenSearch client.
        
        Args:
            host: OpenSearch host
            port: OpenSearch port
            index: Default index name
            user: Username (optional)
            password: Password (optional)
            use_ssl: Whether to use SSL
            verify_certs: Whether to verify SSL certificates
        """
        self.host = host or config.opensearch.host
        self.port = port or config.opensearch.port
        self.index = index or config.opensearch.index
        self.user = user or config.opensearch.user
        self.password = password or config.opensearch.password
        self.use_ssl = use_ssl
        self.verify_certs = verify_certs
        
        self.client: Optional[OpenSearch] = None
        self._is_connected = False
        
        logger.info(f"OpenSearchClient initialized for {self.host}:{self.port}")
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30)
    )
    def connect(self) -> bool:
        """
        Connect to OpenSearch cluster.
        
        Returns:
            True if connection successful
        """
        try:
            auth = (self.user, self.password) if self.user and self.password else None
            
            self.client = OpenSearch(
                hosts=[{"host": self.host, "port": self.port}],
                http_auth=auth,
                use_ssl=self.use_ssl,
                verify_certs=self.verify_certs,
                ssl_show_warn=False,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            
            # Verify connection
            info = self.client.info()
            
            self._is_connected = True
            logger.info(
                f"Connected to OpenSearch cluster: {info['cluster_name']} "
                f"(version: {info['version']['number']})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            raise
    
    def ensure_connected(self) -> None:
        """Ensure client is connected"""
        if not self._is_connected or not self.client:
            self.connect()
    
    def index_document(
        self,
        document: Dict[str, Any],
        doc_id: str = None,
        index: str = None,
        refresh: bool = False
    ) -> bool:
        """
        Index a single document.
        
        Args:
            document: Document to index
            doc_id: Document ID (optional)
            index: Target index (defaults to configured index)
            refresh: Whether to refresh index after indexing
            
        Returns:
            True if successful
        """
        self.ensure_connected()
        target_index = index or self.index
        
        try:
            response = self.client.index(
                index=target_index,
                body=document,
                id=doc_id,
                refresh=refresh
            )
            
            logger.debug(f"Indexed document {doc_id} to {target_index}")
            return response.get('result') in ['created', 'updated']
            
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return False
    
    def bulk_index(
        self,
        documents: List[Dict[str, Any]],
        index: str = None,
        chunk_size: int = 500,
        refresh: bool = False
    ) -> Dict[str, int]:
        """
        Bulk index multiple documents.
        
        Args:
            documents: List of documents to index
            index: Target index
            chunk_size: Number of documents per bulk request
            refresh: Whether to refresh after indexing
            
        Returns:
            Dictionary with success and failure counts
        """
        self.ensure_connected()
        target_index = index or self.index
        
        if not documents:
            return {"success": 0, "failed": 0}
        
        # Prepare bulk actions
        actions = []
        for doc in documents:
            doc_id = doc.get('chunk_id') or doc.get('doc_id')
            action = {
                "_index": target_index,
                "_id": doc_id,
                "_source": doc
            }
            actions.append(action)
        
        try:
            logger.info(f"Bulk indexing {len(actions)} documents to {target_index}...")
            
            success, failed = helpers.bulk(
                self.client,
                actions,
                chunk_size=chunk_size,
                refresh=refresh,
                raise_on_error=False
            )
            
            logger.info(f"Bulk index complete: {success} success, {len(failed)} failed")
            
            return {
                "success": success,
                "failed": len(failed) if isinstance(failed, list) else failed
            }
            
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return {"success": 0, "failed": len(documents)}
    
    def index_embedded_chunks(
        self,
        embedded_chunks: List[EmbeddedChunk],
        index: str = None,
        refresh: bool = False
    ) -> Dict[str, int]:
        """
        Index embedded chunks (convenience method).
        
        Args:
            embedded_chunks: List of EmbeddedChunk objects
            index: Target index
            refresh: Whether to refresh after indexing
            
        Returns:
            Success/failure counts
        """
        documents = [ec.to_dict() for ec in embedded_chunks]
        return self.bulk_index(documents, index, refresh=refresh)
    
    def search_knn(
        self,
        query_vector: List[float],
        k: int = 10,
        index: str = None,
        filter_query: Dict = None,
        min_score: float = None
    ) -> List[SearchResult]:
        """
        Perform k-NN (vector) search.
        
        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            index: Target index
            filter_query: Optional filter to apply
            min_score: Minimum score threshold
            
        Returns:
            List of SearchResult objects
        """
        self.ensure_connected()
        target_index = index or self.index
        
        # Build k-NN query
        knn_query = {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_vector,
                        "k": k
                    }
                }
            }
        }
        
        # Add filter if provided
        if filter_query:
            knn_query["query"] = {
                "bool": {
                    "must": [knn_query["query"]],
                    "filter": filter_query
                }
            }
        
        # Add min_score if provided
        if min_score:
            knn_query["min_score"] = min_score
        
        try:
            response = self.client.search(
                index=target_index,
                body=knn_query
            )
            
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                result = SearchResult(
                    doc_id=source.get('doc_id', ''),
                    chunk_id=source.get('chunk_id', hit['_id']),
                    text=source.get('text', ''),
                    score=hit['_score'],
                    metadata=source.get('metadata', {})
                )
                results.append(result)
            
            logger.debug(f"k-NN search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"k-NN search failed: {e}")
            return []
    
    def search_hybrid(
        self,
        query_text: str,
        query_vector: List[float],
        k: int = 10,
        index: str = None,
        lexical_weight: float = 0.3,
        semantic_weight: float = 0.7
    ) -> List[SearchResult]:
        """
        Perform hybrid search (lexical + semantic).
        
        Args:
            query_text: Text query for lexical search
            query_vector: Query embedding for semantic search
            k: Number of results
            index: Target index
            lexical_weight: Weight for lexical (BM25) score
            semantic_weight: Weight for semantic (k-NN) score
            
        Returns:
            List of SearchResult objects
        """
        self.ensure_connected()
        target_index = index or self.index
        
        # Hybrid query using function_score
        hybrid_query = {
            "size": k,
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["text", "metadata.title"],
                                "boost": lexical_weight
                            }
                        },
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_vector,
                                    "k": k * 2  # Get more candidates for reranking
                                }
                            }
                        }
                    ]
                }
            }
        }
        
        try:
            response = self.client.search(
                index=target_index,
                body=hybrid_query
            )
            
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                result = SearchResult(
                    doc_id=source.get('doc_id', ''),
                    chunk_id=source.get('chunk_id', hit['_id']),
                    text=source.get('text', ''),
                    score=hit['_score'],
                    metadata=source.get('metadata', {})
                )
                results.append(result)
            
            logger.debug(f"Hybrid search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    def search_text(
        self,
        query: str,
        fields: List[str] = None,
        k: int = 10,
        index: str = None
    ) -> List[SearchResult]:
        """
        Perform traditional text search.
        
        Args:
            query: Search query
            fields: Fields to search in
            k: Number of results
            index: Target index
            
        Returns:
            List of SearchResult objects
        """
        self.ensure_connected()
        target_index = index or self.index
        fields = fields or ["text", "metadata.title"]
        
        text_query = {
            "size": k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": fields,
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
        }
        
        try:
            response = self.client.search(
                index=target_index,
                body=text_query
            )
            
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                result = SearchResult(
                    doc_id=source.get('doc_id', ''),
                    chunk_id=source.get('chunk_id', hit['_id']),
                    text=source.get('text', ''),
                    score=hit['_score'],
                    metadata=source.get('metadata', {})
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return []
    
    def get_document(self, doc_id: str, index: str = None) -> Optional[Dict]:
        """Get a document by ID"""
        self.ensure_connected()
        target_index = index or self.index
        
        try:
            response = self.client.get(index=target_index, id=doc_id)
            return response['_source']
        except NotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to get document: {e}")
            return None
    
    def delete_document(self, doc_id: str, index: str = None) -> bool:
        """Delete a document by ID"""
        self.ensure_connected()
        target_index = index or self.index
        
        try:
            self.client.delete(index=target_index, id=doc_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def count_documents(self, index: str = None) -> int:
        """Count documents in index"""
        self.ensure_connected()
        target_index = index or self.index
        
        try:
            response = self.client.count(index=target_index)
            return response['count']
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            return 0
    
    def get_cluster_health(self) -> Dict[str, Any]:
        """Get cluster health status"""
        self.ensure_connected()
        
        try:
            return self.client.cluster.health()
        except Exception as e:
            logger.error(f"Failed to get cluster health: {e}")
            return {}
    
    def close(self) -> None:
        """Close the client connection"""
        if self.client:
            self.client.close()
            self._is_connected = False
            logger.info("OpenSearch client closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Example usage
if __name__ == "__main__":
    # Create client
    with OpenSearchClient() as client:
        # Check cluster health
        health = client.get_cluster_health()
        print(f"Cluster health: {health.get('status', 'unknown')}")
        
        # Count documents
        count = client.count_documents()
        print(f"Document count: {count}")
