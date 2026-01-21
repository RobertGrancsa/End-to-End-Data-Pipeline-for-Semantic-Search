#!/bin/bash
# Create OpenSearch index with k-NN mappings

OPENSEARCH_URL="${OPENSEARCH_URL:-http://localhost:9200}"
INDEX_NAME="${INDEX_NAME:-semantic-documents}"

echo "Creating k-NN enabled index: $INDEX_NAME"

curl -X PUT "$OPENSEARCH_URL/$INDEX_NAME" \
    -H "Content-Type: application/json" \
    -d '{
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "knn": true,
                "knn.algo_param.ef_search": 256
            }
        },
        "mappings": {
            "properties": {
                "chunk_id": { "type": "keyword" },
                "doc_id": { "type": "keyword" },
                "chunk_index": { "type": "integer" },
                "text": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": { "type": "keyword", "ignore_above": 256 }
                    }
                },
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 384,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 256,
                            "m": 16
                        }
                    }
                },
                "start_char": { "type": "integer" },
                "end_char": { "type": "integer" },
                "token_count": { "type": "integer" },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "title": { "type": "text" },
                        "url": { "type": "keyword" },
                        "domain": { "type": "keyword" },
                        "timestamp": { "type": "date" }
                    }
                }
            }
        }
    }'

echo ""
echo "Index created successfully!"
