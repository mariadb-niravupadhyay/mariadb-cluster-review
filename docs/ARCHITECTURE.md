# MariaDB AI Architecture Review Tool - Architecture Documentation

## System Architecture Diagram

![System Architecture](./architecture.svg)

---

## Architecture Overview

The MariaDB AI Architecture Review Tool is a full-stack application that combines:

1. **Modern Web Frontend** - Vanilla JavaScript with responsive CSS
2. **FastAPI Backend** - Python REST API with modular service architecture
3. **MariaDB Cloud** - Unified storage for structured data AND vector embeddings
4. **MariaDB Vector & RAG** - Native VECTOR(768) type with VEC_DISTANCE() for similarity search, enabling Retrieval Augmented Generation
5. **Google Gemini 2.0 Flash** - AI-powered analysis with RAG enhancement

---

## Core Components

### Frontend Layer (Port 5500)

| Component | File | Purpose |
|-----------|------|---------|
| Dashboard | `index.html` | Home page with Getting Started guide |
| Customers | `customers.html` | Customer CRUD operations |
| Topologies | `clusters.html` | Database topology management (Galera/Replication) |
| Nodes | `nodes.html` | Node configuration and metrics input |
| Analysis | `analysis.html` | AI analysis results + interactive chat |
| Logs | `logs.html` | Log file analysis and interpretation |

### Backend Layer (Port 8000)

| Route Module | Prefix | Purpose |
|--------------|--------|---------|
| Data Routes | `/api/v1/data/*` | Customer/Cluster/Node CRUD |
| AI Routes | `/api/v1/ai/*` | AI analysis endpoints |
| Review Routes | `/api/v1/review/*` | Architecture review endpoints |
| Log Routes | `/api/v1/logs/*` | Log analysis endpoints |

### Services Layer

| Service | File | Purpose |
|---------|------|---------|
| Database Service | `src/services/database.py` | MariaDB Cloud CRUD operations |
| RAG Service | `src/ai/rag.py` | Vector search + context retrieval |
| Gemini Client | `src/ai/gemini.py` | AI analysis generation |
| Vector Store | `src/ai/vector.py` | Embedding storage + semantic search |
| Log Analyzer | `src/analyzers/log_analyzer.py` | Log pattern detection |

---

## Data Flow

```
User Input → Frontend → REST API → Backend Services
                                        ↓
                              ┌─────────┴─────────┐
                              ↓                   ↓
                       MariaDB Cloud       Google Gemini
                       (Data + RAG)          (AI Analysis)
                              ↓                   ↓
                              └─────────┬─────────┘
                                        ↓
                              Analysis Results → Frontend → User
```

---

## RAG Pipeline

The Retrieval Augmented Generation (RAG) pipeline enhances AI accuracy:

1. **Query Building** - Extract topics from cluster data (topology, issues, configs)
2. **Embedding** - Convert query to vector using `all-MiniLM-L6-v2`
3. **Vector Search** - Find relevant docs using `VEC_DISTANCE()` in MariaDB
4. **Context Assembly** - Combine retrieved docs with cluster data
5. **AI Generation** - Gemini analyzes with documentation context
6. **Response** - Structured JSON with findings, recommendations, and sources

---

## Database Schema

### Structured Data Tables

```sql
-- Customer management
CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_customer (name, email)
);

-- Cluster/Topology management  
CREATE TABLE clusters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    topology VARCHAR(50) NOT NULL,  -- galera, semi-sync, async
    environment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cluster (customer_id, name),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- Node configuration
CREATE TABLE nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cluster_id INT NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    role VARCHAR(50),
    global_status JSON,
    global_variables JSON,
    system_resources JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_node (cluster_id, hostname),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);
```

### Vector Store Table

```sql
-- Knowledge base with vector embeddings
CREATE TABLE kb_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content TEXT NOT NULL,
    source VARCHAR(512),
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity search index
CREATE INDEX vec_idx ON kb_documents (embedding) USING VECTOR;
```

---

## Critical Questions Answered

The AI is specifically prompted to answer these architecture questions:

| Question | Metrics Analyzed |
|----------|------------------|
| **Can it handle current workload?** | QPS, connections, buffer pool hit ratio |
| **Scale UP or scale DOWN?** | CPU, RAM utilization, connection headroom |
| **HA/DR requirements met?** | Cluster size, quorum, replication health |
| **What bottlenecks exist?** | Flow control, buffer pool, slow queries |
| **Workload profile?** | Read/write ratio, QPS, connection patterns |

---

## Security Considerations

1. **API Keys** - Stored in local files (`.gak`, `.skysql`), not in code
2. **CORS** - Configured for local development
3. **Input Validation** - Pydantic models for request validation
4. **No Hardcoded Credentials** - All secrets externalized

---

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Frontend | Vanilla JS + CSS | ES6+ |
| Backend | FastAPI (Python) | 3.10+ |
| AI Model | Google Gemini | 2.0 Flash |
| Embeddings | Sentence Transformers | all-MiniLM-L6-v2 |
| Database | MariaDB Cloud | SkySQL |
| Vector Store | MariaDB VECTOR | 768 dimensions |
