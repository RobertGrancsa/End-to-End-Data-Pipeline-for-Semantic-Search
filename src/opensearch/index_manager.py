"""
OpenSearch Index Manager Module

Manages index creation, mappings, and settings for k-NN enabled indices.

Author: Robert Grancsa
Essay: "Orchestrating Services and Visualizing Data with OpenSearch"
"""

from typing import Dict, Optional, Any
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, RequestError
from loguru import logger

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config


class IndexManager:
    """
    Manages OpenSearch indices with k-NN support.
    
    Features:
    - Create k-NN enabled indices
    - Configure optimal mappings for semantic search
    - Manage index settings and lifecycle
    - Support for multiple vector similarity algorithms
    
    Optimized for storing document chunks with embeddings
    for semantic similarity search.
    """
    
    # k-NN algorithm options
    KNN_ALGORITHMS = {
        "hnsw": {
            "name": "hnsw",
            "space_type": "l2",
            "engine": "nmslib",
            "parameters": {
                "ef_construction": 256,
                "m": 16
            }
        },
        "hnsw_cosine": {
            "name": "hnsw",
            "space_type": "cosinesimil",
            "engine": "nmslib",
            "parameters": {
                "ef_construction": 256,
                "m": 16
            }
        },
        "faiss": {
            "name": "hnsw",
            "space_type": "l2",
            "engine": "faiss",
            "parameters": {
                "ef_construction": 256,
                "m": 16,
                "ef_search": 256
            }
        }
    }
    
    def __init__(self, client: OpenSearch):
        """
        Initialize the index manager.
        
        Args:
            client: OpenSearch client instance
        """
        self.client = client
        self.dimension = config.embedding.dimension
        
        logger.info(f"IndexManager initialized with dimension: {self.dimension}")
    
    def create_semantic_index(
        self,
        index_name: str,
        dimension: int = None,
        algorithm: str = "hnsw_cosine",
        shards: int = 1,
        replicas: int = 0,
        refresh_interval: str = "1s"
    ) -> bool:
        """
        Create an index optimized for semantic search with k-NN.
        
        Args:
            index_name: Name of the index to create
            dimension: Vector dimension (default from config)
            algorithm: k-NN algorithm to use
            shards: Number of primary shards
            replicas: Number of replica shards
            refresh_interval: Index refresh interval
            
        Returns:
            True if index created successfully
        """
        dimension = dimension or self.dimension
        knn_config = self.KNN_ALGORITHMS.get(algorithm, self.KNN_ALGORITHMS["hnsw_cosine"])
        
        # Index settings
        settings = {
            "index": {
                "number_of_shards": shards,
                "number_of_replicas": replicas,
                "refresh_interval": refresh_interval,
                "knn": True,
                "knn.algo_param.ef_search": 256
            }
        }
        
        # Index mappings
        mappings = {
            "properties": {
                # Chunk identification
                "chunk_id": {
                    "type": "keyword"
                },
                "doc_id": {
                    "type": "keyword"
                },
                "chunk_index": {
                    "type": "integer"
                },
                
                # Text content
                "text": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                },
                
                # Vector embedding
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dimension,
                    "method": {
                        "name": knn_config["name"],
                        "space_type": knn_config["space_type"],
                        "engine": knn_config["engine"],
                        "parameters": knn_config["parameters"]
                    }
                },
                
                # Character positions
                "start_char": {
                    "type": "integer"
                },
                "end_char": {
                    "type": "integer"
                },
                "token_count": {
                    "type": "integer"
                },
                
                # Metadata (nested for flexibility)
                "metadata": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "text",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "url": {
                            "type": "keyword"
                        },
                        "domain": {
                            "type": "keyword"
                        },
                        "timestamp": {
                            "type": "date"
                        },
                        "section_heading": {
                            "type": "text"
                        },
                        "content_length": {
                            "type": "integer"
                        },
                        "word_count": {
                            "type": "integer"
                        }
                    }
                }
            }
        }
        
        # Create index
        body = {
            "settings": settings,
            "mappings": mappings
        }
        
        try:
            # Check if index exists
            if self.client.indices.exists(index=index_name):
                logger.warning(f"Index {index_name} already exists")
                return True
            
            # Create the index
            response = self.client.indices.create(
                index=index_name,
                body=body
            )
            
            logger.info(f"Created index: {index_name}")
            logger.debug(f"Index settings: shards={shards}, replicas={replicas}, algorithm={algorithm}")
            
            return response.get('acknowledged', False)
            
        except RequestError as e:
            logger.error(f"Failed to create index: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error creating index: {e}")
            return False
    
    def delete_index(self, index_name: str) -> bool:
        """
        Delete an index.
        
        Args:
            index_name: Name of the index to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            if self.client.indices.exists(index=index_name):
                self.client.indices.delete(index=index_name)
                logger.info(f"Deleted index: {index_name}")
                return True
            else:
                logger.warning(f"Index {index_name} does not exist")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            return False
    
    def recreate_index(
        self,
        index_name: str,
        **kwargs
    ) -> bool:
        """
        Delete and recreate an index.
        
        Args:
            index_name: Name of the index
            **kwargs: Arguments to pass to create_semantic_index
            
        Returns:
            True if successful
        """
        self.delete_index(index_name)
        return self.create_semantic_index(index_name, **kwargs)
    
    def get_index_info(self, index_name: str) -> Optional[Dict]:
        """
        Get information about an index.
        
        Args:
            index_name: Name of the index
            
        Returns:
            Index information dictionary
        """
        try:
            if not self.client.indices.exists(index=index_name):
                return None
            
            settings = self.client.indices.get_settings(index=index_name)
            mappings = self.client.indices.get_mapping(index=index_name)
            stats = self.client.indices.stats(index=index_name)
            
            return {
                "exists": True,
                "settings": settings.get(index_name, {}).get('settings', {}),
                "mappings": mappings.get(index_name, {}).get('mappings', {}),
                "docs_count": stats['indices'][index_name]['primaries']['docs']['count'],
                "store_size": stats['indices'][index_name]['primaries']['store']['size_in_bytes']
            }
            
        except Exception as e:
            logger.error(f"Failed to get index info: {e}")
            return None
    
    def update_settings(
        self,
        index_name: str,
        settings: Dict[str, Any]
    ) -> bool:
        """
        Update index settings.
        
        Args:
            index_name: Name of the index
            settings: Settings to update
            
        Returns:
            True if successful
        """
        try:
            # Close index to update certain settings
            self.client.indices.close(index=index_name)
            
            # Update settings
            self.client.indices.put_settings(
                index=index_name,
                body=settings
            )
            
            # Reopen index
            self.client.indices.open(index=index_name)
            
            logger.info(f"Updated settings for index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update settings: {e}")
            # Try to reopen index
            try:
                self.client.indices.open(index=index_name)
            except:
                pass
            return False
    
    def tune_for_performance(self, index_name: str) -> bool:
        """
        Apply performance tuning settings to an index.
        
        Args:
            index_name: Name of the index
            
        Returns:
            True if successful
        """
        performance_settings = {
            "index": {
                "refresh_interval": "30s",
                "number_of_replicas": 0,
                "knn.algo_param.ef_search": 512
            }
        }
        
        return self.update_settings(index_name, performance_settings)
    
    def tune_for_accuracy(self, index_name: str) -> bool:
        """
        Apply accuracy-focused settings to an index.
        
        Args:
            index_name: Name of the index
            
        Returns:
            True if successful
        """
        accuracy_settings = {
            "index": {
                "refresh_interval": "1s",
                "knn.algo_param.ef_search": 1024
            }
        }
        
        return self.update_settings(index_name, accuracy_settings)
    
    def create_alias(
        self,
        index_name: str,
        alias_name: str
    ) -> bool:
        """
        Create an alias for an index.
        
        Args:
            index_name: Name of the index
            alias_name: Name of the alias
            
        Returns:
            True if successful
        """
        try:
            self.client.indices.put_alias(
                index=index_name,
                name=alias_name
            )
            logger.info(f"Created alias {alias_name} for index {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create alias: {e}")
            return False
    
    def refresh_index(self, index_name: str) -> bool:
        """
        Refresh an index to make recent changes searchable.
        
        Args:
            index_name: Name of the index
            
        Returns:
            True if successful
        """
        try:
            self.client.indices.refresh(index=index_name)
            logger.debug(f"Refreshed index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to refresh index: {e}")
            return False
    
    def force_merge(
        self,
        index_name: str,
        max_num_segments: int = 1
    ) -> bool:
        """
        Force merge an index for better performance (after bulk indexing).
        
        Args:
            index_name: Name of the index
            max_num_segments: Maximum number of segments
            
        Returns:
            True if successful
        """
        try:
            self.client.indices.forcemerge(
                index=index_name,
                max_num_segments=max_num_segments
            )
            logger.info(f"Force merged index {index_name} to {max_num_segments} segments")
            return True
            
        except Exception as e:
            logger.error(f"Failed to force merge: {e}")
            return False


# Example usage
if __name__ == "__main__":
    from src.opensearch.client import OpenSearchClient
    
    # Create client and manager
    with OpenSearchClient() as client:
        manager = IndexManager(client.client)
        
        # Create semantic search index
        index_name = "semantic-test"
        success = manager.create_semantic_index(
            index_name,
            dimension=384,
            algorithm="hnsw_cosine"
        )
        
        if success:
            print(f"Created index: {index_name}")
            
            # Get index info
            info = manager.get_index_info(index_name)
            print(f"Index info: {info}")
            
            # Clean up
            manager.delete_index(index_name)
            print(f"Deleted index: {index_name}")
