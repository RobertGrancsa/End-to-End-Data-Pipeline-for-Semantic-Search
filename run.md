# 🚀 Running Guide - End-to-End Data Pipeline for Semantic Search

## 📋 Table of Contents

1. [General Overview](#general-overview)
2. [Team Contributions](#team-contributions)
3. [System Requirements](#system-requirements)
4. [Installation and Configuration](#installation-and-configuration)
5. [Starting Infrastructure](#starting-infrastructure)
6. [Running the Pipeline](#running-the-pipeline)
7. [Using the Frontend](#using-the-frontend)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## 📖 General Overview

This project implements an end-to-end data pipeline for semantic search that:

1. **Scrapes** data from the web
2. **Streams** data through Apache Kafka
3. **Processes** text (chunking + embedding)
4. **Indexes** in OpenSearch with k-NN support
5. **Enables** semantic, text, or hybrid search

### Architecture

```
[Web Scraper] → [Kafka] → [Processor] → [OpenSearch] → [Frontend]
     ↓              ↓           ↓              ↓            ↓
   HTML/Text    raw-web-data   Chunks      Vectors     Search UI
                   topic      + Embeddings   Index
```

---

## 👥 Team Contributions

### 🔧 Andrei-Daniel Anghelescu - Kafka Integration

**Essay:** "Building a Resilient Data Ingestion Layer with Apache Kafka"

**Developed files:**
- `src/kafka/__init__.py` - Package initialization
- `src/kafka/producer.py` - Kafka Producer with features:
  - Automatic reconnection with exponential retry
  - JSON serialization
  - Delivery confirmation callbacks
  - Statistics tracking (messages sent, failed, bytes)
  - Batch sending support
  - Graceful shutdown
  
- `src/kafka/consumer.py` - Kafka Consumer with features:
  - Automatic reconnection
  - JSON deserialization
  - Manual/auto offset commit
  - Graceful shutdown with signal handlers
  - Consumption statistics (messages, processing time, lag)
  - Generator pattern for continuous consumption

**Key components:**
```python
# Producer - sends scraped documents to Kafka
with KafkaProducerWrapper() as producer:
    producer.send(message=doc.to_dict(), key=doc.doc_id)

# Consumer - reads and processes messages
with KafkaConsumerWrapper() as consumer:
    for msg in consumer.consume(process_callback=my_processor):
        # Process each message
        pass
```

---

### 🕷️ Rares-Alexandru Constantin - Web Crawler

**Essay:** "Developing a Scalable Web Scraper for Data Aggregation"

**Developed files:**
- `src/scraper/__init__.py` - Package initialization
- `src/scraper/web_scraper.py` - Web Scraper with features:
  - Rate limiting with configurable delay
  - Retry logic with exponential backoff
  - Clean text extraction from HTML
  - Unique document ID generation
  - User-Agent rotation
  - Recursive crawling with depth control
  - Visited URL deduplication
  
- `src/scraper/content_extractor.py` - Content Extractor with features:
  - Automatic main content detection
  - Non-content element removal (nav, footer, scripts)
  - Headings, paragraphs, links, images extraction
  - Metadata extraction (og:tags, description, etc.)
  - Text density analysis

**Key components:**
```python
# Simple scraper
scraper = WebScraper(delay_seconds=1, max_pages=100)
for doc in scraper.scrape_urls(["https://example.com"]):
    print(doc.title, doc.content[:100])

# Recursive crawling
for doc in scraper.crawl_website("https://example.com", max_depth=2):
    process(doc)
```

---

### 🎯 Robert Grancsa - Orchestration and Visualization

**Essay:** "Orchestrating Services and Visualizing Data with OpenSearch"

**Developed files:**

**Docker Infrastructure:**
- `docker-compose.yml` - Service orchestration:
  - Zookeeper (Kafka coordination)
  - Apache Kafka (message broker)
  - Kafka UI (monitoring)
  - OpenSearch (vector database)
  - OpenSearch Dashboards (visualization)

**OpenSearch Integration:**
- `src/opensearch/__init__.py` - Package initialization
- `src/opensearch/client.py` - OpenSearch Client with features:
  - Connection management with retry
  - Bulk indexing for efficiency
  - k-NN (vector) search
  - Hybrid search (BM25 + semantic)
  - Classic text search
  - Cluster statistics

- `src/opensearch/index_manager.py` - Index Manager with features:
  - k-NN enabled index creation
  - Optimized mappings for semantic search
  - Multiple k-NN algorithms (HNSW, FAISS)
  - Performance/accuracy tuning
  - Index lifecycle management

**Pipeline Orchestration:**
- `src/pipeline/__init__.py` - Package initialization
- `src/pipeline/data_pipeline.py` - Integrated Data Pipeline
- `src/pipeline/pipeline_runner.py` - CLI for execution

**Frontend:**
- `src/frontend/app.py` - Streamlit UI for search

**Scripts:**
- `scripts/start.sh` - Start infrastructure
- `scripts/stop.sh` - Stop infrastructure
- `scripts/create_index.sh` - Create index

**Configuration:**
- `src/config.py` - Centralized settings
- `.env.example` - Environment variables template

---

### 🧠 Ana-Maria Toader - Semantic Processing Pipeline

**Essay:** "Implementing a Semantic Processing Pipeline for Text Embeddings"

**Developed files:**
- `src/processing/__init__.py` - Package initialization
- `src/processing/chunker.py` - Text Chunker with features:
  - Token-based chunking (sliding window)
  - Configurable chunk size and overlap
  - Sentence-aware boundaries
  - Advanced semantic chunker (detects headings)
  - Chunk statistics
  - Generator pattern for memory efficiency

- `src/processing/embedder.py` - Embedding Generator with features:
  - Sentence-transformers integration
  - Multiple model support (MiniLM, MPNet, etc.)
  - Batch processing for efficiency
  - CPU/GPU auto-detection
  - Caching for repeated queries
  - Similarity calculation (cosine)
  - Find most similar (local search)

**Key components:**
```python
# Chunking
chunker = TextChunker(chunk_size=500, chunk_overlap=50)
chunks = chunker.chunk_text(long_text, doc_id="doc1")

# Embedding
embedder = EmbeddingGenerator(model_name="all-MiniLM-L6-v2")
embedded_chunks = embedder.embed_chunks(chunks)

# Search
query_vector = embedder.embed_query("What is machine learning?")
similar = embedder.find_most_similar(query_vector, all_embeddings, top_k=5)
```

---

## 💻 System Requirements

### Required software:
- **Docker** & **Docker Compose** (v2.0+)
- **Python** 3.10+ (recommended 3.12)
- **pip** for package installation
- **8GB RAM** minimum (recommended 16GB)
- **20GB disk** free space

### Ports used:
| Port | Service |
|------|---------|
| 2181 | Zookeeper |
| 9092 | Kafka |
| 8080 | Kafka UI |
| 9200 | OpenSearch |
| 5601 | OpenSearch Dashboards |
| 8501 | Streamlit (frontend) |

---

## 🔧 Installation and Configuration

### 1. Clone project
```bash
cd /home/gemdekaise/from_0_to_hero
```

### 2. Create Python environment
```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
# Copy template
cp .env.example .env

# Edit if necessary
nano .env
```

**Important variables in `.env`:**
```bash
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_RAW_DATA=raw-web-data

# OpenSearch
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_INDEX=semantic-documents

# Embedding
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Chunking
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

---

## 🚀 Starting Infrastructure

### Option 1: Automatic script
```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

### Option 2: Manual
```bash
# Start containers
docker-compose up -d

# Check status
docker-compose ps

# Wait for services
# Kafka: curl localhost:9092 (will error, but port is open)
# OpenSearch: curl localhost:9200

# Create Kafka topic
docker-compose exec kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic raw-web-data \
    --partitions 3 \
    --replication-factor 1
```

### Verify services:
- **Kafka UI:** http://localhost:8080
- **OpenSearch:** http://localhost:9200
- **OpenSearch Dashboards:** http://localhost:5601

### Stop infrastructure:
```bash
./scripts/stop.sh
# or
docker-compose down
```

---

## ▶️ Running the Pipeline

### Mode 1: Direct (without Kafka) - Recommended for testing
```bash
# Scrape, process and index directly
python src/pipeline/pipeline_runner.py direct \
    --urls https://en.wikipedia.org/wiki/Machine_learning \
           https://en.wikipedia.org/wiki/Deep_learning \
    --batch-size 50
```

### Mode 2: With Kafka (production)

**Terminal 1 - Producer (scrape and send to Kafka):**
```bash
python src/pipeline/pipeline_runner.py producer \
    --urls https://en.wikipedia.org/wiki/Machine_learning \
    --crawl  # optional: crawl linked pages
```

**Terminal 2 - Consumer (read from Kafka and index):**
```bash
python src/pipeline/pipeline_runner.py consumer \
    --batch-size 50 \
    --max-messages 1000  # optional: message limit
```

### Mode 3: Search
```bash
# Hybrid search (recommended)
python src/pipeline/pipeline_runner.py search \
    --query "What is deep learning?" \
    --k 10 \
    --type hybrid

# Pure semantic search
python src/pipeline/pipeline_runner.py search \
    --query "neural networks" \
    --type semantic

# Text search (BM25)
python src/pipeline/pipeline_runner.py search \
    --query "machine learning algorithms" \
    --type text
```

### CLI Options:
```bash
python src/pipeline/pipeline_runner.py --help

# Logging
python src/pipeline/pipeline_runner.py \
    --log-level DEBUG \
    --log-file pipeline.log \
    direct --urls https://example.com
```

---

## 🖥️ Using the Frontend

### Start Streamlit:
```bash
streamlit run src/frontend/app.py
```

The application will be available at: **http://localhost:8501**

### Features:
- 🔍 **Search box** with auto-complete
- 📊 **Index statistics** in sidebar
- 🔄 **Three search types:** semantic, text, hybrid
- 🎯 **Results** with score, title, URL, text
- 🛠️ **Admin tools** for index management

---

## 🧪 Testing

### Run tests:
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test
pytest tests/test_pipeline.py::TestTextChunker -v
```

### Manual tests:

**1. Test Scraper:**
```python
from src.scraper import WebScraper

scraper = WebScraper()
doc = scraper.scrape_page("https://example.com")
print(f"Title: {doc.title}")
print(f"Content: {doc.content[:200]}")
```

**2. Test Chunking + Embedding:**
```python
from src.processing import TextChunker, EmbeddingGenerator

text = "Your long text here..."
chunker = TextChunker(chunk_size=100)
embedder = EmbeddingGenerator()

chunks = chunker.chunk_text(text, "test_doc")
embedded = embedder.embed_chunks(chunks)

print(f"Chunks: {len(embedded)}")
print(f"Vector dim: {len(embedded[0].embedding)}")
```

**3. Test OpenSearch:**
```python
from src.opensearch import OpenSearchClient

with OpenSearchClient() as client:
    count = client.count_documents()
    health = client.get_cluster_health()
    print(f"Docs: {count}, Status: {health['status']}")
```

---

## 🔧 Troubleshooting

### Common issues:

**1. "No brokers available"**
```bash
# Check Kafka
docker-compose logs kafka
docker-compose restart kafka
```

**2. "Connection refused" to OpenSearch**
```bash
# Check OpenSearch
docker-compose logs opensearch
curl http://localhost:9200

# Increase memory if necessary
# In docker-compose.yml: OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
```

**3. "Out of memory" during embedding**
```python
# Use smaller batch size
embedder.embed_texts(texts, batch_size=8)
```

**4. Slow indexing**
```python
# After bulk indexing, force merge:
index_manager.force_merge(index_name, max_num_segments=1)
```

**5. Module not found**
```bash
# Add src to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

## 📁 Project Structure

```
from_0_to_hero/
├── docker-compose.yml          # Docker orchestration
├── requirements.txt            # Python dependencies
├── .env.example               # Configuration template
├── .gitignore
├── README.md                  # Project documentation
├── run.md                     # This file
│
├── scripts/
│   ├── start.sh              # Start infrastructure
│   ├── stop.sh               # Stop infrastructure
│   └── create_index.sh       # Create OpenSearch index
│
├── src/
│   ├── __init__.py
│   ├── config.py             # Centralized settings
│   │
│   ├── scraper/              # [Rares-Alexandru Constantin]
│   │   ├── __init__.py
│   │   ├── web_scraper.py    # Web scraping
│   │   └── content_extractor.py
│   │
│   ├── kafka/                # [Andrei-Daniel Anghelescu]
│   │   ├── __init__.py
│   │   ├── producer.py       # Kafka producer
│   │   └── consumer.py       # Kafka consumer
│   │
│   ├── processing/           # [Ana-Maria Toader]
│   │   ├── __init__.py
│   │   ├── chunker.py        # Text chunking
│   │   └── embedder.py       # Vector embeddings
│   │
│   ├── opensearch/           # [Robert Grancsa]
│   │   ├── __init__.py
│   │   ├── client.py         # OpenSearch client
│   │   └── index_manager.py  # Index management
│   │
│   ├── pipeline/             # [All team members]
│   │   ├── __init__.py
│   │   ├── data_pipeline.py  # Main pipeline
│   │   └── pipeline_runner.py # CLI
│   │
│   └── frontend/             # [Robert Grancsa]
│       ├── __init__.py
│       └── app.py            # Streamlit UI
│
└── tests/
    ├── __init__.py
    └── test_pipeline.py      # Unit tests
```

---

## 📊 Metrics and Performance

### Typical benchmarks:

| Operation | Approximate time |
|-----------|------------------|
| Scrape 1 page | 1-3 seconds |
| Chunk 10KB text | <100ms |
| Embed 1 chunk | ~50ms (CPU) |
| Embed batch 100 | ~2s (CPU) |
| Index 1000 docs | ~5-10s |
| k-NN search | <100ms |

### Scaling recommendations:

- **More pages:** Increase `max_pages_per_site`
- **More parallelism:** Multiple producer/consumer instances
- **More data:** Increase OpenSearch heap and shards
- **Faster embedding:** Use GPU with PyTorch CUDA

---

## 📝 Final Notes

The project fully implements all requirements from the README:

✅ **Phase 1:** Infrastructure (Docker Compose, OpenSearch, Kafka)  
✅ **Phase 2:** Data Pipeline (Scraper, Producer, Consumer)  
✅ **Phase 3:** Semantic Processing (Chunking, Embedding, Indexing)  
✅ **Phase 4:** UI & Refinement (Streamlit frontend, k-NN tuning)

**Team:**
- **Andrei-Daniel Anghelescu** - Kafka integration
- **Rares-Alexandru Constantin** - Web crawler
- **Robert Grancsa** - Orchestration & Visualization
- **Ana-Maria Toader** - Semantic processing pipeline

---

*Auto-generated - January 2026*
