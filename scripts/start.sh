#!/bin/bash
# Startup script for the semantic search pipeline

set -e

echo "🚀 Starting Semantic Search Pipeline Infrastructure..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Navigate to project directory
cd "$(dirname "$0")"

# Start infrastructure
echo "📦 Starting Docker containers..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."

# Wait for Kafka
echo "  - Waiting for Kafka..."
until docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; do
    sleep 2
done
echo "  ✅ Kafka is ready"

# Wait for OpenSearch
echo "  - Waiting for OpenSearch..."
until curl -s http://localhost:9200 | grep -q "opensearch"; do
    sleep 2
done
echo "  ✅ OpenSearch is ready"

# Create Kafka topic
echo "📝 Creating Kafka topic..."
docker-compose exec -T kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic raw-web-data \
    --partitions 3 \
    --replication-factor 1 \
    --if-not-exists

echo ""
echo "✅ Infrastructure is ready!"
echo ""
echo "📊 Service URLs:"
echo "  - Kafka:                localhost:9092"
echo "  - Kafka UI:             http://localhost:8080"
echo "  - OpenSearch:           http://localhost:9200"
echo "  - OpenSearch Dashboards: http://localhost:5601"
echo ""
echo "🔧 Next steps:"
echo "  1. Install Python dependencies: pip install -r requirements.txt"
echo "  2. Copy .env.example to .env and configure"
echo "  3. Run the pipeline: python src/pipeline/pipeline_runner.py --help"
echo "  4. Start the frontend: streamlit run src/frontend/app.py"
