# MariaDB Cluster Analyzer - Technical Design Document

## Project Overview

**MariaDB Cluster Analyzer** is an AI-powered tool for analyzing MariaDB database clusters, providing intelligent recommendations for architecture, capacity, and performance optimization.

### Key Features

1. **AI-Powered Cluster Analysis** - Uses Google Gemini to analyze cluster configuration and metrics
2. **Vector Search (RAG)** - Retrieves relevant documentation from MariaDB knowledge base
3. **Log Interpretation** - AI-driven interpretation of MariaDB and MaxScale logs
4. **Topology Comparison** - Compare Galera vs Semi-Sync vs Async replication
5. **Capacity Assessment** - Per-node resource utilization and sizing recommendations

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (HTML/JS/CSS)                    │
│  • Data Input Forms    • Analysis Dashboard    • AI Chat    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (Python FastAPI)                   │
│  • AI Analysis Engine  • RAG Service  • Vector Store Client │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ MariaDB Cloud   │ │ Google Gemini    │ │ MCP Server       │
│ (Vector Store)   │ │ (AI Model)       │ │ (Documentation)  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | HTML5 + CSS3 + Vanilla JS | User interface |
| Backend | Python 3.11+ / FastAPI | REST API server |
| AI Model | Google Gemini 2.0 Flash | Analysis & generation |
| Embeddings | Google embedding-001 | Text vectorization |
| Vector DB | MariaDB Cloud | Store & search embeddings |
| Knowledge | MCP (remote-mdb-docs) | MariaDB documentation |

---

## MariaDB Vector Implementation

### Schema Design

```sql
-- Document embeddings for RAG
CREATE TABLE doc_embeddings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source VARCHAR(100) NOT NULL,       -- 'mariadb-docs', 'galera-docs', etc.
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    url VARCHAR(1000),
    embedding VECTOR(768) NOT NULL,     -- Google embedding dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_source (source),
    VECTOR INDEX idx_embedding (embedding)
);

-- Error code knowledge base
CREATE TABLE error_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    error_code VARCHAR(50) NOT NULL UNIQUE,
    component VARCHAR(50) NOT NULL,      -- 'mariadb', 'galera', 'maxscale'
    severity VARCHAR(20),
    message TEXT NOT NULL,
    explanation TEXT,
    solution TEXT,
    embedding VECTOR(768),
    
    INDEX idx_error_code (error_code),
    INDEX idx_component (component)
);

-- Analysis cache for performance
CREATE TABLE analysis_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    input_hash VARCHAR(64) NOT NULL UNIQUE,
    analysis_type VARCHAR(50) NOT NULL,
    result JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_hash (input_hash)
);
```

### Vector Operations

```python
# Embedding generation
embedding = genai.embed_content(
    model="models/embedding-001",
    content=text,
    task_type="retrieval_document"
)

# Vector similarity search
SELECT id, source, title, content,
       VEC_DISTANCE(embedding, VEC_FromText(?)) as distance
FROM doc_embeddings
ORDER BY distance ASC
LIMIT 5;
```

---

## RAG Pipeline

### Flow

1. **User Query** → Extract key topics from cluster data
2. **Vector Search** → Find relevant documentation chunks
3. **Context Assembly** → Combine retrieved docs into context
4. **AI Prompt** → Send cluster data + context to Gemini
5. **Response** → Parse and display AI analysis

### Example RAG Query

```python
# Step 1: Generate query embedding
query = "galera cluster best practices buffer pool"
query_embedding = get_query_embedding(query)

# Step 2: Vector search in MariaDB
results = vector_store.search(query, top_k=5)

# Step 3: Build context
context = "\n".join([
    f"### {doc.title}\n{doc.content}"
    for doc, score in results
])

# Step 4: AI analysis with context
analysis = gemini.analyze_cluster(
    cluster_data=cluster_data,
    rag_context=context
)
```

---

## API Endpoints

### AI Analysis Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ai/init` | POST | Initialize vector store and seed docs |
| `/api/v1/ai/stats` | GET | Get vector store statistics |
| `/api/v1/ai/analyze/cluster` | POST | Analyze full cluster |
| `/api/v1/ai/analyze/capacity` | POST | Analyze node capacity |
| `/api/v1/ai/analyze/logs` | POST | Interpret log entries |
| `/api/v1/ai/compare/topologies` | POST | Compare replication types |
| `/api/v1/ai/chat` | POST | Chat with AI assistant |
| `/api/v1/ai/search` | GET | Search vector store |

### Request/Response Example

**Request: Cluster Analysis**
```json
POST /api/v1/ai/analyze/cluster
{
    "cluster_name": "production-galera",
    "topology_type": "galera",
    "nodes": [
        {
            "hostname": "db-node-01",
            "global_status": { ... },
            "global_variables": { ... },
            "system_resources": { "cpu_cores": 8, "ram_gb": 32 }
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "summary": "The Galera cluster appears healthy...",
        "health_score": 85,
        "findings": [
            {
                "category": "InnoDB Buffer Pool",
                "severity": "warning",
                "finding": "Buffer pool undersized at 22% of RAM",
                "recommendation": "Increase to 70-75% of RAM"
            }
        ],
        "recommendations": [
            "Increase innodb_buffer_pool_size to 22-24GB",
            "Enable gcache for faster IST recovery"
        ],
        "rag_metadata": {
            "context_retrieved": true,
            "queries_used": ["galera cluster best practices"]
        }
    }
}
```

---

## AI Prompts

### Cluster Analysis Prompt

```
You are an expert MariaDB database administrator.
Analyze the provided cluster data and provide actionable recommendations.

Focus on:
1. Cluster health and status
2. Configuration best practices
3. Resource utilization and sizing
4. Replication health
5. Potential issues and risks

Relevant Documentation Context:
{rag_context}

Cluster Data:
{cluster_data}

Provide response as JSON with: summary, health_score, findings, recommendations
```

### Log Interpretation Prompt

```
You are an expert at analyzing MariaDB logs.

Documentation Context:
{rag_context}

Log Entry:
{log_entry}

Provide:
- severity (critical/error/warning/info)
- category
- summary
- root_cause
- recommended_action
```

---

## Security Considerations

1. **API Keys** - Stored in `.gak` and `.skysql` files, excluded from git
2. **SSL/TLS** - All SkySQL connections use SSL
3. **Input Validation** - Pydantic models validate all API inputs
4. **No PII** - Sample data uses sanitized hostnames

---

## Performance Optimizations

1. **Embedding Cache** - Reuse embeddings for repeated queries
2. **Analysis Cache** - Cache results by input hash
3. **Batch Embeddings** - Generate embeddings in batches
4. **Limited Context** - Cap RAG context to prevent token overflow

---

## Future Enhancements

- [ ] Real-time cluster monitoring integration
- [ ] Automated remediation suggestions
- [ ] Historical trend analysis
- [ ] Multi-cluster comparison
- [ ] Custom knowledge base ingestion
- [ ] Export reports to PDF

---

## Running the Demo

### Prerequisites

- Python 3.11+
- MariaDB Cloud account with Vector support
- Google Gemini API key

### Setup

```bash
# Clone and install
cd mariadb-cluster-review
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add credentials
echo "YOUR_GEMINI_API_KEY" > .gak
echo "your-skysql-host
4005
username: your-user
password: your-pass" > .skysql

# Start backend
uvicorn src.main:app --port 8000

# Start frontend (new terminal)
cd frontend && python -m http.server 5500

# Open http://localhost:5500
```

---

*MariaDB AI Competition 2025*
