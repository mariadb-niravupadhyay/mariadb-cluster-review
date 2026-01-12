---
marp: true
theme: default
paginate: true
backgroundColor: #fff
---

# MariaDB AI Based Architecture Review and Logs Analyzer Tool

**AI-Powered Architecture Review and Logs Analysis for MariaDB Databases**

![bg right:30% 80%](https://mariadb.com/wp-content/uploads/2019/11/mariadb-logo-vert_blue-transparent.png)

---

## What This Tool Does

An AI-powered tool that performs the following:

- **Reviews** MariaDB database topologies deployed in various Customer environments to answer critical architecture questions

- **Analyzes** MariaDB and MaxScale logs to identify critical issues and perform root cause analysis

- **Identifies** key issue patterns and prepares sequence of critical events by parsing log files

---

## Key Features

| Feature | Description |
|---------|-------------|
| **AI Based Architecture Review** | Comprehensive analysis with Workload & Capacity Assessment, HA/DR Assessment and Bottleneck Detection |
| **AI Based Per-Node Analysis** | Individual node diagnostics with CPU, memory, swap, and resource recommendations |
| **AI Based Logs Analysis** | Intelligent MariaDB and MaxScale log interpretation with issue detection |
| **AI Chat Assistant** | Interactive Q&A for report-specific follow-up questions |

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

![bg contain](./architecture.svg)

---

## Technology Stack

### AI/ML
- **Google Gemini 2.0 Flash** - Large language model
- **Sentence Transformers** - Text embeddings (all-MiniLM-L6-v2)
- **MariaDB VECTOR** - Native vector storage
- **VEC_DISTANCE** - Similarity search

### Backend & Frontend
- **Python 3.10+ / FastAPI** - Backend API
- **Vanilla JavaScript** - Frontend UI
- **MariaDB Cloud (SkySQL)** - Data & Vector Store

---

## RAG Pipeline

```
Query → Embed → Vector Search → Context → Augment Prompt → AI Response
```

1. User requests analysis
2. System builds search query from cluster metrics
3. Embeddings searched in MariaDB `doc_embeddings` table
4. Relevant MariaDB KB documentation retrieved
5. Cluster data + RAG context combined
6. Gemini 2.0 generates comprehensive review

---

## User Workflow

1. **Add Customer** - Create customer profiles to organize analyses
2. **Define Database Topology** - Configure Galera, Replication, or Standalone setups
3. **Add Nodes** - Input GLOBAL STATUS, GLOBAL VARIABLES, and system resources
4. **Run AI Analysis** - Get AI-powered architecture review with documentation context
5. **Ask Follow-up Questions** - Use the AI Chat Assistant for analysis-specific Q&A

---

## AI Based Analysis Types

| Type | Description | Access |
|------|-------------|--------|
| **Architecture Review** | Full cluster analysis | Topologies page → "Architecture Review" |
| **Node Analysis** | Individual node diagnostics | Nodes page → "Node Analysis" |
| **Logs Analyzer** | AI log interpretation | Topologies/Nodes page → "Logs Analyzer" |

---

## Future Enhancements

1. **Analysis History & Persistence**
   - Store AI analysis responses in database
   - Save chat Q&A history for all modules

2. **Reinforcement Learning from User Feedback**
   - 5-star rating system for analysis quality
   - Continuous improvement loop

3. **Prompt Optimization** - Better AI responses

4. **Knowledge Base Expansion** - More MariaDB documentation

---

## Acknowledgments

- **MariaDB Corporation** - Database technology and cloud platform
- **Google** - Gemini AI API
- **Hugging Face** - Sentence Transformers

---

# Thank You!

**MariaDB AI Based Architecture Review and Logs Analyzer Tool**

[![MariaDB](https://img.shields.io/badge/MariaDB-Cloud-003545)](https://mariadb.com/products/skysql/)
[![AI](https://img.shields.io/badge/AI-Gemini%202.0%20Flash-8b5cf6)](https://ai.google.dev/)
[![RAG](https://img.shields.io/badge/RAG-Enabled-f59e0b)](https://en.wikipedia.org/wiki/Retrieval-augmented_generation)
