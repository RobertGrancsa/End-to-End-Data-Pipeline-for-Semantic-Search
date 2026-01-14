#!/bin/bash
# Stop script for the semantic search pipeline

echo "🛑 Stopping Semantic Search Pipeline Infrastructure..."

cd "$(dirname "$0")/.."

# Stop containers
docker-compose down

echo "✅ All services stopped"
