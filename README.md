# Project Plan: End-to-End Data Pipeline for Semantic Search

## Summary

**Project Title:** End-to-End Data Pipeline with OpenSearch and Semantic Search
**Objective:** Build a scalable Big Data pipeline that scrapes web data, processes it via message queues, generates vector embeddings, and indexes it into OpenSearch for hybrid (lexical + semantic) search retrieval.
**Scope:** Data acquisition (scraping), ingestion (Kafka), processing (chunking/embedding), storage (OpenSearch), and visualization (OpenSearch Dashboards).
**Team:**
- Andrei-Daniel Anghelescu
- Rares-Alexandru Constantin
- Robert Grancsa
- Ana-Maria Toader


## 2. Technology Stack

| Component | Technology | Role in Pipeline |
| :-- | :-- | :-- |
| **Orchestration** | Docker Compose | Container management for all services |
| **Ingestion** | Apache Kafka | Message queue for buffering scraped raw text |
| **Database** | OpenSearch | Vector database \& search engine (hybrid search) |
| **Processing** | Python 3.12+ | Custom scrapers and middleware consumers |
| **Embeddings** | HuggingFace / ONNX | Sentence-transformers (e.g., `all-MiniLM-L6-v2`) |
| **Visualization** | OpenSearch Dashboards | UI for querying and visualizing data |

## 3. Architecture Overview

The pipeline follows a standard ETL (Extract, Transform, Load) pattern enhanced for vector search:

1. **Data Acquisition (Source):** Python scrapers fetch HTML, clean it, and extract raw text.
2. **Buffering (Queue):** Raw documents are pushed to a Kafka topic (`raw-web-data`).
3. **Transformation (Processor):**
    * Consumer reads from Kafka.
    * **Chunking:** Splits long text into manageable overlapping segments (e.g., 500 tokens).
    * **Embedding:** Generates vector representations (384 dimensions) for each chunk.
4. **Storage (Sink):** Chunks + Vectors are indexed into OpenSearch.
5. **Retrieval:** User queries are embedded and matched using k-NN (k-Nearest Neighbors).
```mermaid
graph LR
    subgraph "Data Acquisition"
        A[Web Scraper] -->|JSON| B(Kafka Topic: raw-web-data)
    end

    subgraph "Ingestion Layer"
        B --> C[Kafka Connect / Data Prepper]
        C -->|Bulk Request| D(OpenSearch Ingest Node)
    end

    subgraph "OpenSearch Cluster"
        D --> P{Ingest Pipeline}
        
        subgraph "Native Processors"
            P -->|Split| E[Text Chunking Processor]
            E -->|Vectorize| F[Text Embedding Processor]
        end

        F <-->|Inference| G[ML Commons Node]
        F -->|Indexed Documents| H[(Target Index)]
    end

    style B fill:#f9f,stroke:#333,stroke-width:2px
    style D fill:#bbf,stroke:#333,stroke-width:2px
    style G fill:#bfb,stroke:#333,stroke-width:2px
```


## 5. Development Roadmap (7 Weeks)

### Phase 1: Infrastructure (Weeks 1-2)

- [ ] Set up Docker Compose for OpenSearch, Dashboards, and Kafka.
- [ ] Verify connectivity between containers.
- [ ] Create initial index mappings with k-NN enabled.


### Phase 2: Data Pipeline (Weeks 3-4)

- [ ] Develop Python scraper for target websites.
- [ ] Implement Kafka Producer to stream raw data.
- [ ] Implement Kafka Consumer to read and print data (test).


### Phase 3: Semantic Processing (Weeks 5-6)

- [ ] Integrate `sentence-transformers` for local embedding generation.
- [ ] Implement chunking logic (sliding window).
- [ ] Connect Consumer output to OpenSearch bulk indexing API.


### Phase 4: UI \& Refinement (Week 7)

- [ ] Build a simple Streamlit or Flask frontend for user queries.
- [ ] Visualize document ingest rates in OpenSearch Dashboards.
- [ ] Tune k-NN parameters (ef_search, m) for performance.
