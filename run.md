# 🚀 Ghid de Rulare - End-to-End Data Pipeline pentru Semantic Search

## 📋 Cuprins

1. [Prezentare Generală](#prezentare-generală)
2. [Contribuții pe Membri](#contribuții-pe-membri)
3. [Cerințe Sistem](#cerințe-sistem)
4. [Instalare și Configurare](#instalare-și-configurare)
5. [Pornire Infrastructură](#pornire-infrastructură)
6. [Rulare Pipeline](#rulare-pipeline)
7. [Utilizare Frontend](#utilizare-frontend)
8. [Testare](#testare)
9. [Troubleshooting](#troubleshooting)

---

## 📖 Prezentare Generală

Acest proiect implementează o pipeline de date end-to-end pentru căutare semantică, care:

1. **Scrapează** date de pe web
2. **Streamează** datele prin Apache Kafka
3. **Procesează** textul (chunking + embedding)
4. **Indexează** în OpenSearch cu suport k-NN
5. **Permite căutare** semantică, text sau hibridă

### Arhitectura

```
[Web Scraper] → [Kafka] → [Processor] → [OpenSearch] → [Frontend]
     ↓              ↓           ↓              ↓            ↓
   HTML/Text    raw-web-data   Chunks      Vectors     Search UI
                   topic      + Embeddings   Index
```

---

## 👥 Contribuții pe Membri

### 🔧 Andrei-Daniel Anghelescu - Kafka Integration

**Essay:** "Building a Resilient Data Ingestion Layer with Apache Kafka"

**Fișiere dezvoltate:**
- `src/kafka/__init__.py` - Package initialization
- `src/kafka/producer.py` - Kafka Producer cu features:
  - Reconectare automată cu retry exponential
  - Serializare JSON
  - Callback-uri pentru confirmare delivery
  - Tracking statistici (mesaje trimise, eșuate, bytes)
  - Suport batch sending
  - Graceful shutdown
  
- `src/kafka/consumer.py` - Kafka Consumer cu features:
  - Reconnection automată
  - Deserializare JSON
  - Manual/auto offset commit
  - Graceful shutdown cu signal handlers
  - Statistici consum (mesaje, timp procesare, lag)
  - Generator pattern pentru consum continuu

**Componente cheie:**
```python
# Producer - trimite documente scrapate la Kafka
with KafkaProducerWrapper() as producer:
    producer.send(message=doc.to_dict(), key=doc.doc_id)

# Consumer - citește și procesează mesaje
with KafkaConsumerWrapper() as consumer:
    for msg in consumer.consume(process_callback=my_processor):
        # Process each message
        pass
```

---

### 🕷️ Rares-Alexandru Constantin - Web Crawler

**Essay:** "Developing a Scalable Web Scraper for Data Aggregation"

**Fișiere dezvoltate:**
- `src/scraper/__init__.py` - Package initialization
- `src/scraper/web_scraper.py` - Web Scraper cu features:
  - Rate limiting cu delay configurabil
  - Retry logic cu exponential backoff
  - Extracție text curat din HTML
  - Generare ID-uri unice pentru documente
  - Rotație User-Agent
  - Crawling recursiv cu control depth
  - Deduplicare URL-uri vizitate
  
- `src/scraper/content_extractor.py` - Content Extractor cu features:
  - Detectare automată main content
  - Eliminare elemente non-content (nav, footer, scripts)
  - Extracție headings, paragraphs, links, images
  - Extracție metadata (og:tags, description, etc.)
  - Text density analysis

**Componente cheie:**
```python
# Scraper simplu
scraper = WebScraper(delay_seconds=1, max_pages=100)
for doc in scraper.scrape_urls(["https://example.com"]):
    print(doc.title, doc.content[:100])

# Crawling recursiv
for doc in scraper.crawl_website("https://example.com", max_depth=2):
    process(doc)
```

---

### 🎯 Robert Grancsa - Orchestration și Visualization

**Essay:** "Orchestrating Services and Visualizing Data with OpenSearch"

**Fișiere dezvoltate:**

**Infrastructură Docker:**
- `docker-compose.yml` - Orchestrare servicii:
  - Zookeeper (Kafka coordination)
  - Apache Kafka (message broker)
  - Kafka UI (monitoring)
  - OpenSearch (vector database)
  - OpenSearch Dashboards (visualization)

**OpenSearch Integration:**
- `src/opensearch/__init__.py` - Package initialization
- `src/opensearch/client.py` - OpenSearch Client cu features:
  - Connection management cu retry
  - Bulk indexing pentru eficiență
  - k-NN (vector) search
  - Hybrid search (BM25 + semantic)
  - Text search clasic
  - Statistici cluster

- `src/opensearch/index_manager.py` - Index Manager cu features:
  - Creare index k-NN enabled
  - Mappings optimizate pentru semantic search
  - Multiple algoritmi k-NN (HNSW, FAISS)
  - Tuning performance/accuracy
  - Index lifecycle management

**Pipeline Orchestration:**
- `src/pipeline/__init__.py` - Package initialization
- `src/pipeline/data_pipeline.py` - Data Pipeline integrat
- `src/pipeline/pipeline_runner.py` - CLI pentru rulare

**Frontend:**
- `src/frontend/app.py` - Streamlit UI pentru căutare

**Scripturi:**
- `scripts/start.sh` - Pornire infrastructură
- `scripts/stop.sh` - Oprire infrastructură
- `scripts/create_index.sh` - Creare index

**Configurare:**
- `src/config.py` - Centralizare configurări
- `.env.example` - Template variabile environment

---

### 🧠 Ana-Maria Toader - Semantic Processing Pipeline

**Essay:** "Implementing a Semantic Processing Pipeline for Text Embeddings"

**Fișiere dezvoltate:**
- `src/processing/__init__.py` - Package initialization
- `src/processing/chunker.py` - Text Chunker cu features:
  - Token-based chunking (sliding window)
  - Configurable chunk size și overlap
  - Sentence-aware boundaries
  - Semantic chunker avansat (detectează headings)
  - Statistici chunk-uri
  - Generator pattern pentru memory efficiency

- `src/processing/embedder.py` - Embedding Generator cu features:
  - Sentence-transformers integration
  - Multiple model support (MiniLM, MPNet, etc.)
  - Batch processing pentru eficiență
  - CPU/GPU auto-detection
  - Caching pentru queries repetate
  - Similarity calculation (cosine)
  - Find most similar (local search)

**Componente cheie:**
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

## 💻 Cerințe Sistem

### Software necesar:
- **Docker** & **Docker Compose** (v2.0+)
- **Python** 3.10+ (recomandat 3.12)
- **pip** pentru instalare pachete
- **8GB RAM** minim (recomandat 16GB)
- **20GB disk** spațiu liber

### Porturi utilizate:
| Port | Serviciu |
|------|----------|
| 2181 | Zookeeper |
| 9092 | Kafka |
| 8080 | Kafka UI |
| 9200 | OpenSearch |
| 5601 | OpenSearch Dashboards |
| 8501 | Streamlit (frontend) |

---

## 🔧 Instalare și Configurare

### 1. Clonare proiect
```bash
cd /home/gemdekaise/from_0_to_hero
```

### 2. Creare environment Python
```bash
# Creare virtual environment
python -m venv venv

# Activare (Linux/Mac)
source venv/bin/activate

# Activare (Windows)
.\venv\Scripts\activate
```

### 3. Instalare dependențe
```bash
pip install -r requirements.txt
```

### 4. Configurare environment
```bash
# Copiere template
cp .env.example .env

# Editare dacă e necesar
nano .env
```

**Variabile importante în `.env`:**
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

## 🚀 Pornire Infrastructură

### Opțiunea 1: Script automat
```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

### Opțiunea 2: Manual
```bash
# Pornire containere
docker-compose up -d

# Verificare status
docker-compose ps

# Așteptare servicii
# Kafka: curl localhost:9092 (va da eroare, dar portul e deschis)
# OpenSearch: curl localhost:9200

# Creare topic Kafka
docker-compose exec kafka kafka-topics --create \
    --bootstrap-server localhost:9092 \
    --topic raw-web-data \
    --partitions 3 \
    --replication-factor 1
```

### Verificare servicii:
- **Kafka UI:** http://localhost:8080
- **OpenSearch:** http://localhost:9200
- **OpenSearch Dashboards:** http://localhost:5601

### Oprire infrastructură:
```bash
./scripts/stop.sh
# sau
docker-compose down
```

---

## ▶️ Rulare Pipeline

### Mod 1: Direct (fără Kafka) - Recomandat pentru teste
```bash
# Scrape, procesează și indexează direct
python src/pipeline/pipeline_runner.py direct \
    --urls https://en.wikipedia.org/wiki/Machine_learning \
           https://en.wikipedia.org/wiki/Deep_learning \
    --batch-size 50
```

### Mod 2: Cu Kafka (producție)

**Terminal 1 - Producer (scrape și trimite la Kafka):**
```bash
python src/pipeline/pipeline_runner.py producer \
    --urls https://en.wikipedia.org/wiki/Machine_learning \
    --crawl  # opțional: crawl linked pages
```

**Terminal 2 - Consumer (citește din Kafka și indexează):**
```bash
python src/pipeline/pipeline_runner.py consumer \
    --batch-size 50 \
    --max-messages 1000  # opțional: limită mesaje
```

### Mod 3: Căutare
```bash
# Căutare hibridă (recomandat)
python src/pipeline/pipeline_runner.py search \
    --query "What is deep learning?" \
    --k 10 \
    --type hybrid

# Căutare semantică pură
python src/pipeline/pipeline_runner.py search \
    --query "neural networks" \
    --type semantic

# Căutare text (BM25)
python src/pipeline/pipeline_runner.py search \
    --query "machine learning algorithms" \
    --type text
```

### Opțiuni CLI:
```bash
python src/pipeline/pipeline_runner.py --help

# Logging
python src/pipeline/pipeline_runner.py \
    --log-level DEBUG \
    --log-file pipeline.log \
    direct --urls https://example.com
```

---

## 🖥️ Utilizare Frontend

### Pornire Streamlit:
```bash
streamlit run src/frontend/app.py
```

Aplicația va fi disponibilă la: **http://localhost:8501**

### Features:
- 🔍 **Search box** cu auto-complete
- 📊 **Statistici index** în sidebar
- 🔄 **Trei tipuri căutare:** semantic, text, hybrid
- 🎯 **Rezultate** cu score, titlu, URL, text
- 🛠️ **Admin tools** pentru management index

---

## 🧪 Testare

### Rulare teste:
```bash
# Toate testele
pytest tests/ -v

# Cu coverage
pytest tests/ --cov=src --cov-report=html

# Test specific
pytest tests/test_pipeline.py::TestTextChunker -v
```

### Teste manuale:

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

### Probleme comune:

**1. "No brokers available"**
```bash
# Verificare Kafka
docker-compose logs kafka
docker-compose restart kafka
```

**2. "Connection refused" la OpenSearch**
```bash
# Verificare OpenSearch
docker-compose logs opensearch
curl http://localhost:9200

# Increase memory dacă e necesar
# În docker-compose.yml: OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
```

**3. "Out of memory" la embedding**
```python
# Folosește batch size mai mic
embedder.embed_texts(texts, batch_size=8)
```

**4. Slow indexing**
```python
# După bulk indexing, force merge:
index_manager.force_merge(index_name, max_num_segments=1)
```

**5. Module not found**
```bash
# Adaugă src la PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

## 📁 Structura Proiect

```
from_0_to_hero/
├── docker-compose.yml          # Orchestrare Docker
├── requirements.txt            # Dependențe Python
├── .env.example               # Template configurare
├── .gitignore
├── README.md                  # Documentație proiect
├── run.md                     # Acest fișier
│
├── scripts/
│   ├── start.sh              # Pornire infrastructură
│   ├── stop.sh               # Oprire infrastructură
│   └── create_index.sh       # Creare index OpenSearch
│
├── src/
│   ├── __init__.py
│   ├── config.py             # Configurări centralizate
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
│   ├── pipeline/             # [Toți]
│   │   ├── __init__.py
│   │   ├── data_pipeline.py  # Pipeline principal
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

## 📊 Metrici și Performanță

### Benchmarks tipice:

| Operație | Timp aproximativ |
|----------|------------------|
| Scrape 1 pagină | 1-3 secunde |
| Chunk 10KB text | <100ms |
| Embed 1 chunk | ~50ms (CPU) |
| Embed batch 100 | ~2s (CPU) |
| Index 1000 docs | ~5-10s |
| k-NN search | <100ms |

### Recomandări scaling:

- **Mai multe pagini:** Crește `max_pages_per_site`
- **Mai mult paralelism:** Multiple producer/consumer instances
- **Mai multe date:** Increase OpenSearch heap și shards
- **Mai rapid embedding:** Folosește GPU cu PyTorch CUDA

---

## 📝 Note Finale

Proiectul implementează complet toate cerințele din README:

✅ **Faza 1:** Infrastructure (Docker Compose, OpenSearch, Kafka)  
✅ **Faza 2:** Data Pipeline (Scraper, Producer, Consumer)  
✅ **Faza 3:** Semantic Processing (Chunking, Embedding, Indexing)  
✅ **Faza 4:** UI & Refinement (Streamlit frontend, k-NN tuning)

**Echipa:**
- **Andrei-Daniel Anghelescu** - Kafka integration
- **Rares-Alexandru Constantin** - Web crawler
- **Robert Grancsa** - Orchestration & Visualization
- **Ana-Maria Toader** - Semantic processing pipeline

---

*Generat automat - Ianuarie 2026*
