# MariaDB AI Based Architecture Review and Logs Analyzer Tool

[![MariaDB](https://img.shields.io/badge/MariaDB-Cloud-003545)](https://mariadb.com/products/skysql/)
[![AI](https://img.shields.io/badge/AI-Gemini%202.0%20Flash-8b5cf6)](https://ai.google.dev/)
[![Vector](https://img.shields.io/badge/Vector-VECTOR(768)-10b981)](https://mariadb.com/docs/)
[![RAG](https://img.shields.io/badge/RAG-Enabled-f59e0b)](https://en.wikipedia.org/wiki/Retrieval-augmented_generation)

An AI-powered tool that performs the following:
- Reviews MariaDB database topologies deployed in various Customer environments to answer critical architecture questions
- Analyzes MariaDB and MaxScale logs of various nodes in topology to help identify critical issues and perform root cause analysis.
- Identifies key issue patterns and prepares sequence of critical events occurred on the node by parsing it's log file.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **AI Based Architecture Review** | Comprehensive database architecture analysis with Workload & Capacity Assessment, HA/DR Assessment and Bottleneck Detection |
| **AI Based Per-Node Analysis** | Individual node diagnostics with CPU, memory, swap, and resource recommendations |
| **AI Based Logs Analysis** | Intelligent MariaDB and MaxScale log interpretation with issue detection |
| **AI Chat Assistant for Analysis Q&A** | Interactive Q&A for report-specific follow-up questions |

---

## Critical Questions Answered

- **Can it handle current workload?**
- **Should we scale up?**
- **Can we scale down (save cost)?**
- **Is HA/DR properly configured?**
- **What bottlenecks exist?**
- **What's the workload profile?**
- **What critical events occurred and what is the potential root cause?**

---

## Database Topologies Supported

| Topology | Description |
|----------|-------------|
| **Standalone** | Single MariaDB node |
| **Master-Replica** | Async replication (1 master, N replicas) |
| **Semi-Sync** | Semi-synchronous replication |
| **Galera** | Fully synchronous multi-master cluster |
| **MaxScale** | Any topology with MaxScale proxy |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                 │
│   Dashboard │ Customers │ Topologies │ Nodes │ Analysis │ Logs │ Chat   │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ REST API
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /api/v1/data/* (CRUD)  │  /api/v1/ai/* (Analysis)  │  /review/*  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                   │                                      │
│  ┌────────────────────────────────┴────────────────────────────────┐    │
│  │  RAG: Query → Embed → Vector Search → Context → Augment Prompt │    │
│  └────────────────────────────────┬────────────────────────────────┘    │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
┌─────────────────────────┐                   ┌─────────────────────────┐
│   MARIADB CLOUD         │                   │   GOOGLE GEMINI 2.0     │
│   - Data Storage        │                   │   - Architecture Review │
│   - Vector Store        │                   │   - Node Analysis       │
│   - VECTOR(768)         │                   │   - Logs Analysis       │
│   - VEC_DISTANCE()      │                   │   - AI Chat Assistant   │
└─────────────────────────┘                   └─────────────────────────┘
```

---

## Quick Start

### 1. Clone and Install Dependencies

```bash
git clone <repository-url>
cd mariadb-cluster-review
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
# Google Gemini API Key
echo "YOUR_GEMINI_API_KEY" > .gak

# MariaDB Cloud Connection
cat > .skysql << EOF
your-skysql-host.db2.skysql.com
4005
username: your-username
password: your-password
EOF
```

### 3. Start Backend Server

```bash
uvicorn src.main:app --reload --port 8000
```

### 4. Start Frontend Server

```bash
cd frontend
python3 -m http.server 5500
```

### 5. Access Application

- **Frontend UI**: http://localhost:5500
- **API Documentation**: http://localhost:8000/docs

### 6. Initialize AI System (First Time)

```bash
curl -X POST http://localhost:8000/api/v1/ai/init
```

This seeds the vector store with MariaDB documentation for RAG.

---

## User Workflow

1. **Add Customer** - Create customer profiles to organize analyses
2. **Define Database Topology** - Configure Galera, Replication, or Standalone setups
3. **Add Nodes** - Input GLOBAL STATUS, GLOBAL VARIABLES, and system resources
4. **Run AI Analysis** - Get AI-powered architecture review with documentation context
5. **Ask Follow-up Questions** - Use the AI Chat Assistant for analysis-specific Q&A

### AI Based Analysis Types

| Type | Description | Access |
|------|-------------|--------|
| **Architecture Review** | Full cluster analysis | Topologies page → "Architecture Review" |
| **Node Analysis** | Individual node diagnostics | Nodes page → "Node Analysis" |
| **Logs Analyzer** | AI log interpretation | Topologies/Nodes page → "Logs Analyzer" |

---

## Analysis Output

### Performance Metrics
- **Total QPS** - Queries per second across cluster
- **Reads/sec** - SELECT operations rate
- **Writes/sec** - INSERT/UPDATE/DELETE rate
- **Active Connections** - Current vs max connections
- **Peak Connections** - Historical maximum

### Node Details
- Hostname and role
- System resources (CPU, RAM, Storage)
- Key configuration values
- Status indicators

### AI Findings
- **Critical** - Issues requiring immediate attention
- **Warning** - Potential problems to address
- **Info** - Optimization opportunities

### Recommendations
- Actionable steps for optimization
- Configuration change suggestions
- Sizing recommendations

### Analysis Sources & References
- Links to relevant MariaDB documentation
- Knowledge base sources used in analysis
- Topology-specific documentation

---

## API Endpoints

| Category | Key Endpoints |
|----------|---------------|
| **Data** | `/api/v1/data/customers`, `/clusters`, `/nodes` - CRUD operations |
| **AI Analysis** | `/api/v1/ai/analyze/cluster`, `/capacity`, `/logs` - AI-powered analysis |
| **Chat** | `/api/v1/ai/chat` - Interactive Q&A assistant |
| **Review** | `/api/v1/review`, `/review/galera`, `/review/replication` - Topology reviews |
| **System** | `/api/v1/ai/init` - Initialize RAG, `/ai/stats` - Vector store stats |

Full API documentation available at `http://localhost:8000/docs`

---

## Technology Stack

### Backend
- **Python 3.10+**
- **FastAPI** - Modern async web framework
- **Pydantic** - Data validation
- **MariaDB Connector** - Database connectivity

### Frontend
- **Vanilla JavaScript** - No framework dependencies
- **Modern CSS** - CSS variables, flexbox, grid
- **Responsive Design** - Mobile-friendly

### AI/ML
- **Google Gemini 2.0 Flash** - Large language model
- **Sentence Transformers** - Text embeddings (all-MiniLM-L6-v2)
- **MariaDB VECTOR** - Native vector storage
- **VEC_DISTANCE** - Similarity search

### Database
- **MariaDB Cloud (SkySQL)** - Managed database
- **VECTOR(768)** - Vector column type
- **JSON** - Flexible data storage

---

## Future Enhancements

### Planned Features

#### 1. Analysis History & Persistence
- Store AI analysis responses in database
- Save chat Q&A history for all modules
- Track analysis trends over time
- Export analysis reports

#### 2. Reinforcement Learning from User Feedback
- **5-star rating system** for analysis quality
- User feedback on accuracy and usefulness
- **Continuous improvement loop**:
  - Collect ratings on Architecture Review, Node Analysis, Logs Analysis
  - Store feedback with analysis context
  - Use feedback to fine-tune recommendations
  - Learn from corrections to improve future output

#### 3. Prompt Optimization
- Refine how questions are structured for better AI responses
- Improve specificity and context in prompts

#### 4. Knowledge Base Expansion
- Adding more MariaDB documentation to the vector store
- Improved RAG context for more accurate recommendations
- Version-specific documentation for targeted advice

## Acknowledgments

- **MariaDB Corporation** - Database technology and cloud platform
- **Google** - Gemini AI API
- **Hugging Face** - Sentence Transformers
