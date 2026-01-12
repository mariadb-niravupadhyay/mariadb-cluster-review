# MariaDB AI Architecture Review Tool - Demo Script

## Demo Duration: 5-6 minutes

---

## Scene 1: Dashboard & Problem Statement (0:00 - 0:45)

> "Welcome to the MariaDB AI Architecture Review Tool.
>
> Database architects face critical questions daily that take hours to answer manually:
> - Can my architecture handle this workload?
> - Should I scale up or can I save costs by scaling down?
> - Are my HA and disaster recovery requirements actually met?
> - Where are the performance bottlenecks?
>
> This tool answers these questions in seconds using Google Gemini AI with MariaDB Cloud's native vector store for Retrieval Augmented Generation.
>
> Let me show you how it works."

**Action:** Show dashboard briefly

---

## Scene 2: Add Customer (0:45 - 1:15)

> "First, we add a customer. Click Customers, then Add Customer. I'll enter a company name and their environment type.
>
> In production, this would be your client or internal team whose database you're reviewing."

**Action:** Customers → Add Customer → Fill: "Acme Corp" / "Production" → Save

---

## Scene 3: Add Topology (1:15 - 1:45)

> "Next, we define the database topology. Click Topologies, Add Topology. Select the customer, give it a name, and choose the topology type - I'll select Galera Cluster.
>
> The tool supports Galera, Async Replication, Semi-Sync, and standalone configurations."

**Action:** Topologies → Add Topology → Select customer, name: "Primary Cluster", type: "Galera" → Save

---

## Scene 4: Add Nodes with Metrics (1:45 - 2:30)

> "Now the important part - adding nodes with their metrics. Click on the cluster, then Add Node.
>
> Here I enter the hostname, role, and paste the actual database metrics - Global Status from SHOW GLOBAL STATUS, Global Variables, and system resources.
>
> This is data you'd collect from your MariaDB servers - connection counts, buffer pool stats, replication status, everything the AI needs for analysis.
>
> For this demo, I'll load a pre-configured dataset with 6 nodes to show the full analysis."

**Action:** Show Add Node dialog briefly, explain the metrics fields, then click "Load Demo Data" → Galera Balanced

---

## Scene 5: Architecture Review - The Core Innovation (2:30 - 4:00)

> "Here's our Galera cluster with 6 nodes. Now let's see the AI in action - click Architecture Review.
>
> *(During loading spinner)*
> The system is now:
> - Querying MariaDB Cloud's vector store for relevant documentation using native VECTOR columns
> - Retrieving context about Galera best practices, buffer pool tuning, replication settings
> - Sending this context plus your cluster data to Gemini 2.0 Flash
>
> This is RAG - Retrieval Augmented Generation - ensuring recommendations are backed by actual MariaDB documentation.
>
> *(When results appear)*
> Here's our Architecture Analysis Report. The Summary shows cluster health - total QPS across all nodes, read-write ratio, active connections.
>
> The Architecture Assessment answers our five critical questions with specific findings. Each finding has a severity level - Critical, Warning, or Info - with actionable recommendations.
>
> Scroll down to see Per Node Details and the documentation references from our knowledge base. The AI isn't guessing - it's citing real MariaDB documentation."

**Action:** Click "Architecture Review", narrate during loading, walk through results

---

## Scene 6: Node Analysis (4:00 - 4:30)

> "For deeper investigation, run Node Analysis on individual servers. This focuses on single-node metrics - buffer pool efficiency, connection utilization, specific to that server."

**Action:** Nodes → Node Analysis on one node → Brief results overview

---

## Scene 7: AI Chat Follow-up (4:30 - 5:00)

> "Users can ask follow-up questions. The AI maintains context from the analysis.
>
> 'What buffer pool size do you recommend?'
>
> The response is specific to THIS cluster's actual metrics and configuration - not generic advice."

**Action:** Type question, show response

---

## Scene 8: AI Quality & Future Improvements (5:00 - 5:30)

> "The AI analysis you've seen is a starting point. The system is designed to improve over time:
>
> - **Prompt Optimization** - Refining how questions are structured for better AI responses
> - **Knowledge Base Expansion** - Adding more MariaDB documentation to the vector store improves RAG context
> - **User Feedback** - Ratings and corrections are stored to refine prompts and improve future recommendations through few-shot learning
>
> As the prompts and knowledge base improve, the analysis quality improves - without changing the core architecture."

**Action:** Stay on results page or return to dashboard

---

## Scene 9: Closing (5:30 - 5:50)

> "MariaDB AI Architecture Review - combining MariaDB Cloud's native vector store, RAG for accuracy, and Gemini AI intelligence.
>
> The key innovation: MariaDB Cloud serves as BOTH the operational database AND the AI knowledge store - no external vector database needed.
>
> Thank you for watching."

**Action:** Return to dashboard

---

## Demo Checklist

Before the demo:
- [ ] Docker MariaDB running: `docker ps | grep mariadb-demo`
- [ ] Backend running: `USE_DOCKER_DB=true uvicorn src.main:app --reload --port 8000`
- [ ] Frontend running: `python3 -m http.server 5500` in frontend/
- [ ] Database initialized: `curl -X POST http://localhost:8000/api/v1/data/init`
- [ ] Vector store seeded: `curl -X POST http://localhost:8000/api/v1/ai/init`
- [ ] Test demo data loads correctly
- [ ] Test analysis returns results
- [ ] Test chat interface responds

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend not starting | Check Python venv: `source venv/bin/activate` |
| "Cannot connect to backend" | Ensure uvicorn is running on port 8000 |
| Analysis timeout | Check Gemini API key in `.gak` file |
| Vector search empty | Run `curl -X POST http://localhost:8000/api/v1/ai/init` |
| Database connection error | Verify `.skysql_docker` credentials for local Docker |
| CORS errors | Backend should allow localhost:5500 |

---

## Key Talking Points

1. **MariaDB-Native Vector Store** - No external vector DB needed
2. **RAG for Accuracy** - Documentation-backed, not hallucinated
3. **Real Workflow** - Customer → Topology → Nodes → Analysis
4. **Multi-Level Analysis** - Cluster, Node, and Log analysis
5. **Interactive** - Chat follow-ups maintain context
6. **Continuous Improvement** - Few-shot learning from user feedback

---

## Recording Tips

- **Tool:** QuickTime Player (File → New Screen Recording)
- **Audio:** Select microphone in dropdown before recording
- **Format:** Export as 1080p .mov (Google Drive compatible)
- **Prep:** Close notifications, hide dock, use full-screen browser
