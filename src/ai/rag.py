"""
RAG Service - Retrieval Augmented Generation for Cluster Analysis

Combines vector search with LLM to provide context-aware analysis.
"""

from typing import List, Dict, Any, Optional
import json

from .config import AIConfig
from .vector import VectorStore, DocumentChunk
from .gemini import GeminiClient


class RAGService:
    """
    RAG Pipeline for MariaDB Cluster Analysis
    
    Retrieves relevant documentation and combines with AI analysis.
    """
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.vector_store = VectorStore(config)
        self.gemini = GeminiClient(config)
    
    def init(self):
        """Initialize the RAG service (create schema, etc.)"""
        self.vector_store.init_schema()
    
    def close(self):
        """Clean up resources"""
        self.vector_store.close()
    
    def _get_relevant_context(
        self,
        query: str,
        source_filter: Optional[str] = None,
        top_k: int = 5
    ) -> str:
        """Retrieve relevant documentation context for a query"""
        
        results = self.vector_store.search(query, top_k=top_k, source_filter=source_filter)
        
        if not results:
            return ""
        
        context_parts = []
        for doc, score in results:
            context_parts.append(f"""
### {doc.title} (Source: {doc.source}, Relevance: {score:.2f})
{doc.content}
{f"Reference: {doc.url}" if doc.url else ""}
""")
        
        return "\n---\n".join(context_parts)
    
    def analyze_cluster_with_rag(
        self,
        cluster_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze cluster with RAG-enhanced context
        
        1. Extract key topics from cluster data
        2. Retrieve relevant documentation
        3. Generate AI analysis with context
        """
        
        # Build query from cluster data to find relevant docs
        topology = cluster_data.get("topology_type", "unknown")
        node_count = len(cluster_data.get("nodes", []))
        
        # Build search queries based on critical architecture questions
        queries = [
            f"MariaDB {topology} best practices and configuration",
        ]
        
        # Add topology-specific queries for HA/DR
        if topology == "galera":
            queries.append("Galera cluster quorum and high availability requirements")
        elif topology in ["semi-sync", "replication", "async"]:
            queries.append("MariaDB replication high availability and failover")
        
        # Add capacity/sizing query
        queries.append("MariaDB capacity planning and resource sizing")
        
        # Check for specific issues to query (bottlenecks)
        if cluster_data.get("nodes"):
            for node in cluster_data["nodes"]:
                status = node.get("global_status", {})
                try:
                    # Flow control bottleneck
                    if float(status.get("wsrep_flow_control_paused", 0)) > 0.1:
                        queries.append("Galera flow control troubleshooting and tuning")
                    # High thread count - potential CPU bottleneck
                    if float(status.get("Threads_running", 0)) > 50:
                        queries.append("MariaDB high thread count CPU optimization")
                    # Buffer pool issues
                    reads = float(status.get("Innodb_buffer_pool_reads", 0))
                    read_requests = float(status.get("Innodb_buffer_pool_read_requests", 1))
                    if read_requests > 0 and (reads / read_requests) > 0.01:
                        queries.append("InnoDB buffer pool sizing and tuning")
                    # Connection bottleneck
                    max_used = float(status.get("Max_used_connections", 0))
                    max_conn = float(node.get("global_variables", {}).get("max_connections", 151))
                    if max_conn > 0 and (max_used / max_conn) > 0.8:
                        queries.append("MariaDB connection pooling and max_connections tuning")
                except (ValueError, TypeError):
                    pass  # Skip if values can't be converted
        
        # Retrieve context for all queries
        all_context = []
        for query in queries[:3]:  # Limit to top 3 queries
            context = self._get_relevant_context(query, top_k=2)
            if context:
                all_context.append(context)
        
        combined_context = "\n\n".join(all_context) if all_context else None
        
        # Run AI analysis with context
        analysis = self.gemini.analyze_cluster(cluster_data, rag_context=combined_context)
        
        # Add metadata about RAG usage
        analysis["rag_metadata"] = {
            "queries_used": queries[:3],
            "context_retrieved": len(all_context) > 0,
            "context_sources": [doc.source for doc, _ in self.vector_store.search(queries[0], top_k=3)] if all_context else []
        }
        
        return analysis
    
    def analyze_workload_sizing(
        self,
        cluster_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze workload to determine if current architecture is right-sized
        """
        # Get relevant context
        queries = [
            "MariaDB capacity planning best practices",
            "MariaDB resource sizing recommendations"
        ]
        
        all_context = []
        for query in queries:
            context = self._get_relevant_context(query, top_k=2)
            if context:
                all_context.append(context)
        
        combined_context = "\n\n".join(all_context) if all_context else None
        
        # Run workload analysis
        analysis = self.gemini.analyze_workload(cluster_data, rag_context=combined_context)
        
        return analysis
    
    def analyze_node_capacity_with_rag(
        self,
        node_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze individual node capacity with RAG context"""
        
        # Build query based on node metrics
        queries = ["MariaDB buffer pool sizing best practices"]
        
        status = node_data.get("global_status", {})
        variables = node_data.get("global_variables", {})
        
        # Check buffer pool configuration
        if variables.get("innodb_buffer_pool_size"):
            queries.append("InnoDB buffer pool configuration")
        
        # Check connection usage
        try:
            max_conn = int(variables.get("max_connections", 1000))
            threads_connected = int(status.get("Threads_connected", 0))
            if max_conn > 0 and threads_connected / max_conn > 0.7:
                queries.append("MariaDB connection pooling high utilization")
        except (ValueError, TypeError):
            pass
        
        # Retrieve context
        all_context = []
        for query in queries[:2]:
            context = self._get_relevant_context(query, top_k=2)
            if context:
                all_context.append(context)
        
        combined_context = "\n\n".join(all_context) if all_context else None
        
        return self.gemini.analyze_capacity(node_data, rag_context=combined_context)
    
    def interpret_logs_with_rag(
        self,
        log_entries: List[str],
        log_type: str
    ) -> List[Dict[str, Any]]:
        """Interpret log entries with documentation context"""
        
        results = []
        for entry in log_entries:
            # Search for similar errors in knowledge base
            error_matches = self.vector_store.lookup_error(entry, top_k=2)
            
            # Also search documentation
            doc_context = self._get_relevant_context(
                f"{log_type} log error: {entry[:200]}",
                source_filter=f"{log_type}-docs" if log_type in ["mariadb", "maxscale", "galera"] else None,
                top_k=2
            )
            
            # Combine error KB and doc context
            rag_context = ""
            if error_matches:
                rag_context += "Known Similar Errors:\n"
                for match in error_matches:
                    rag_context += f"- {match['error_code']}: {match['message']}\n"
                    if match.get('explanation'):
                        rag_context += f"  Explanation: {match['explanation']}\n"
                    if match.get('solution'):
                        rag_context += f"  Solution: {match['solution']}\n"
                rag_context += "\n"
            
            if doc_context:
                rag_context += f"Documentation Context:\n{doc_context}"
            
            # Get AI interpretation
            interpretation = self.gemini.interpret_log_entry(
                entry,
                log_type,
                rag_context=rag_context if rag_context else None
            )
            
            interpretation["original_entry"] = entry
            interpretation["matched_errors"] = error_matches
            results.append(interpretation)
        
        return results
    
    def analyze_logs_timeline(
        self,
        cluster_name: str,
        topology_type: str,
        node_logs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze logs from multiple nodes and extract timeline of events"""
        
        # Import log analyzers
        from src.analyzers.log_analyzer import MariaDBLogAnalyzer, MaxScaleLogAnalyzer
        
        mariadb_analyzer = MariaDBLogAnalyzer()
        maxscale_analyzer = MaxScaleLogAnalyzer()
        
        # First, run local pattern-based analysis
        local_analysis = {}
        all_findings = []
        all_events = []
        
        for node_id, node_data in node_logs.items():
            hostname = node_data.get('hostname', 'Unknown')
            node_analysis = {"hostname": hostname, "mariadb": None, "maxscale": None}
            
            # Analyze MariaDB logs
            if node_data.get('mariadb_log'):
                result = mariadb_analyzer.analyze_log_content(
                    node_data['mariadb_log'], 
                    f"{hostname}_mariadb.log"
                )
                node_analysis["mariadb"] = result
                
                # Extract events for timeline
                summary = result.get("summary", {})
                for event_type in ["critical_events", "sst_events", "state_changes", 
                                   "crash_events", "replication_errors", "inconsistency_events"]:
                    events = summary.get(event_type, [])
                    for e in events[:10]:  # Limit events per type
                        all_events.append({
                            "node": hostname,
                            "timestamp": e.get("timestamp", "Unknown"),
                            "type": event_type,
                            "message": e.get("message", "")[:150]
                        })
                
                # Collect findings
                for f in result.get("findings", []):
                    if hasattr(f, 'model_dump'):
                        all_findings.append(f.model_dump())
                    elif isinstance(f, dict):
                        all_findings.append(f)
            
            # Analyze MaxScale logs
            if node_data.get('maxscale_log'):
                result = maxscale_analyzer.analyze_log_content(
                    node_data['maxscale_log'],
                    f"{hostname}_maxscale.log"
                )
                node_analysis["maxscale"] = result
                
                # Extract events
                summary = result.get("summary", {})
                for event_type in ["server_down_events", "master_changes", "cluster_issues"]:
                    events = summary.get(event_type, [])
                    for e in events[:10]:
                        all_events.append({
                            "node": hostname,
                            "timestamp": e.get("timestamp", "Unknown"),
                            "type": event_type,
                            "message": e.get("message", "")[:150]
                        })
                
                for f in result.get("findings", []):
                    if hasattr(f, 'model_dump'):
                        all_findings.append(f.model_dump())
                    elif isinstance(f, dict):
                        all_findings.append(f)
            
            local_analysis[node_id] = node_analysis
        
        # Sort events by timestamp if available
        all_events.sort(key=lambda x: x.get("timestamp") or "")
        
        # Get RAG context
        queries = [
            f"MariaDB {topology_type} troubleshooting logs",
            "MariaDB error log common issues"
        ]
        
        all_context = []
        for query in queries:
            context = self._get_relevant_context(query, top_k=2)
            if context:
                all_context.append(context)
        
        combined_context = "\n\n".join(all_context) if all_context else None
        
        # Call Gemini for AI-enhanced analysis with local analysis as input
        ai_analysis = self.gemini.analyze_logs_with_local_context(
            cluster_name,
            topology_type,
            node_logs,
            local_analysis,
            all_findings,
            all_events,
            rag_context=combined_context
        )
        
        # Merge local and AI analysis
        return {
            **ai_analysis,
            "local_analysis": {
                "findings_count": len(all_findings),
                "events_extracted": len(all_events),
                "nodes_analyzed": list(local_analysis.keys())
            }
        }
    
    def compare_topologies_with_rag(
        self,
        current_topology: str,
        cluster_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare topologies with documentation context"""
        
        # Get context for each topology type
        contexts = []
        for topology in ["galera", "semi-sync", "async"]:
            ctx = self._get_relevant_context(
                f"MariaDB {topology} replication advantages disadvantages",
                top_k=2
            )
            if ctx:
                contexts.append(f"=== {topology.upper()} ===\n{ctx}")
        
        combined_context = "\n\n".join(contexts) if contexts else None
        
        return self.gemini.compare_topologies(
            current_topology,
            cluster_data,
            rag_context=combined_context
        )
    
    def chat_with_rag(
        self,
        question: str,
        cluster_context: Optional[Dict[str, Any]] = None,
        log_entries: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, str]:
        """Chat interface with RAG context, including log analysis"""
        
        # Retrieve relevant documentation for the question
        rag_context = self._get_relevant_context(question, top_k=3)
        
        # If question seems log-related, add log context to the question
        enhanced_question = question
        if log_entries:
            log_keywords = ['log', 'error', 'warning', 'issue', 'problem', 'message', 'wsrep', 'innodb']
            if any(kw in question.lower() for kw in log_keywords):
                log_context = "\n".join(log_entries[:5])
                enhanced_question = f"{question}\n\nRelevant log entries:\n{log_context}"
        
        response = self.gemini.chat(
            enhanced_question,
            cluster_context=cluster_context,
            rag_context=rag_context if rag_context else None,
            chat_history=chat_history
        )
        
        return {
            "question": question,
            "answer": response,
            "context_used": bool(rag_context),
            "logs_included": bool(log_entries and enhanced_question != question)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG service statistics"""
        return {
            "vector_store": self.vector_store.get_stats(),
            "model": self.config.gemini.model
        }


# Sample documentation to seed the vector store
SAMPLE_DOCS = [
    DocumentChunk(
        id=None,
        source="mariadb-docs",
        title="InnoDB Buffer Pool Sizing",
        content="""The InnoDB buffer pool is the memory area where InnoDB caches table and index data.
For dedicated database servers, set innodb_buffer_pool_size to 70-80% of available RAM.
Monitor Innodb_buffer_pool_read_requests vs Innodb_buffer_pool_reads to check hit ratio.
A hit ratio below 99% may indicate the buffer pool is too small.""",
        url="https://mariadb.com/kb/en/innodb-buffer-pool/"
    ),
    DocumentChunk(
        id=None,
        source="galera-docs",
        title="Galera Cluster Quorum and Node Count",
        content="""Galera requires a quorum (more than 50% of nodes) to operate.
For multi-datacenter deployments, use 2n+1 nodes per DC or use an arbitrator.
Common configurations:
- 3 nodes in single DC: Can tolerate 1 failure
- 3+3+arbitrator (7 nodes): Can tolerate entire DC failure
- Avoid 2+2 without arbitrator: 50/50 split causes cluster freeze""",
        url="https://mariadb.com/kb/en/galera-cluster-system-variables/"
    ),
    DocumentChunk(
        id=None,
        source="galera-docs",
        title="Galera Flow Control",
        content="""Flow control pauses replication when a node falls behind.
Monitor wsrep_flow_control_paused - should be near 0.
High values indicate slow nodes causing cluster-wide slowdown.
Tune gcs.fc_limit and gcs.fc_factor to adjust sensitivity.
Consider increasing wsrep_slave_threads for parallel apply.""",
        url="https://mariadb.com/kb/en/galera-cluster-status-variables/"
    ),
    DocumentChunk(
        id=None,
        source="maxscale-docs",
        title="MaxScale ReadWriteSplit Router",
        content="""The readwritesplit router separates read and write queries.
Writes go to master, reads distributed to slaves.
Enable transaction_replay for automatic retry on failures.
Use master_accept_reads=true if slaves may have lag.
causal_reads ensures read-your-writes consistency.""",
        url="https://mariadb.com/kb/en/mariadb-maxscale-6-readwritesplit/"
    ),
    DocumentChunk(
        id=None,
        source="mariadb-docs",
        title="Semi-Synchronous Replication",
        content="""Semi-sync replication waits for at least one replica to acknowledge.
Provides better durability than async with lower latency than Galera.
Configure rpl_semi_sync_master_wait_point=AFTER_SYNC for crash safety.
For multi-DC, configure local replicas as semi-sync, remote as async.
Use MaxScale or Orchestrator for automatic failover.""",
        url="https://mariadb.com/kb/en/semisynchronous-replication/"
    ),
    DocumentChunk(
        id=None,
        source="mariadb-docs",
        title="Connection Thread Management",
        content="""max_connections limits concurrent client connections.
Monitor Max_used_connections vs max_connections for utilization.
Threads_running shows actively executing queries.
High Threads_running with low CPU may indicate lock contention.
Consider connection pooling (ProxySQL, MaxScale) for many short connections.""",
        url="https://mariadb.com/kb/en/server-system-variables/"
    ),
    # Architecture Review Documents
    DocumentChunk(
        id=None,
        source="mariadb-docs",
        title="High Availability Strategies Overview",
        content="""MariaDB offers multiple high availability strategies:
1. Galera Cluster: Synchronous multi-master with automatic node provisioning
2. Semi-Synchronous Replication: Balance between performance and durability
3. Asynchronous Replication: Best performance, eventual consistency
4. MaxScale with auto-failover: Proxy-based HA for replication setups
Key considerations: RPO (data loss tolerance), RTO (downtime tolerance), 
geographic distribution, and workload type (read-heavy vs write-heavy).
For zero data loss, use Galera or semi-sync with AFTER_SYNC.""",
        url="https://mariadb.com/kb/en/high-availability-performance-tuning/"
    ),
    DocumentChunk(
        id=None,
        source="galera-docs",
        title="Galera Cluster Technical Architecture",
        content="""Galera uses certification-based replication with group communication.
Write sets are broadcast to all nodes and certified for conflicts.
Certification happens at commit time - conflicts cause transaction rollback.
Key components: wsrep API, Group Communication System (GCS), certification layer.
All nodes are equal masters - writes can occur on any node.
State transfers: IST (incremental) for small gaps, SST (full) for new nodes.
Flow control prevents fast nodes from overwhelming slow ones.
Optimal for read-heavy workloads; write scaling limited by certification.""",
        url="https://galeracluster.com/library/documentation/tech-description-introduction.html"
    ),
    # Data Loss Risk Documents
    DocumentChunk(
        id=None,
        source="best-practices",
        title="Data Loss Prevention in MariaDB Replication",
        content="""Potential data loss scenarios and mitigations:
1. Async replication: Master crash before replica receives binlog - use semi-sync
2. Semi-sync timeout fallback: Set rpl_semi_sync_master_timeout appropriately
3. Galera network partition: Ensure odd node count or arbitrator for quorum
4. GTID gaps: Monitor gtid_slave_pos vs gtid_binlog_pos
5. Disk failures: Use sync_binlog=1 and innodb_flush_log_at_trx_commit=1
6. Split-brain: Configure proper fencing and use single-writer mode
Prevention: Enable binary log checksums, monitor replication lag, 
regular backup verification, test failover procedures.""",
        url="https://mariadb.com/kb/en/replication-and-binary-log-system-variables/"
    ),
    # MaxScale Documents
    DocumentChunk(
        id=None,
        source="maxscale-docs",
        title="MaxScale Filters and Query Processing",
        content="""MaxScale filters process queries in the routing pipeline:
- Query Log Filter (qlafilter): Log all queries for auditing
- Regex Filter: Rewrite queries using regular expressions
- Top Filter: Track and report slow/frequent queries
- Cache Filter: Query result caching for read scalability
- Tee Filter: Duplicate queries to multiple targets
- Binlog Filter: Filter replication events
Configuration: filters=MyFilter in service definition.
Filter order matters - processed in definition order.
Use for query analysis, security auditing, and performance optimization.""",
        url="https://mariadb.com/kb/en/mariadb-maxscale-6-filters/"
    ),
    # Scaling Documents
    DocumentChunk(
        id=None,
        source="mariadb-docs",
        title="Performance Schema for Bottleneck Analysis",
        content="""Performance Schema identifies bottlenecks without external tools:
Key tables for analysis:
- events_waits_summary_global_by_event_name: Wait event hotspots
- events_statements_summary_by_digest: Slow query patterns
- file_summary_by_instance: I/O bottlenecks per file
- table_io_waits_summary_by_table: Hot tables
- memory_summary_global_by_event_name: Memory consumers
Enable selectively: UPDATE performance_schema.setup_instruments SET ENABLED='YES'
Low overhead when configured properly. Essential for capacity planning.""",
        url="https://mariadb.com/kb/en/performance-schema-overview/"
    ),
    DocumentChunk(
        id=None,
        source="best-practices",
        title="Capacity Planning and Scaling Decisions",
        content="""Scale up vs scale out decision framework:
Scale UP (vertical) when:
- Single query performance is bottleneck
- Buffer pool hit ratio < 99%
- CPU bound with low thread count
- Storage IOPS maxed on single server
Scale OUT (horizontal) when:
- Read throughput exceeds single server capacity
- Geographic distribution needed
- Write availability (multi-master) required
- Dataset exceeds single server storage
Key metrics: QPS trends, connection growth, storage growth rate,
replication lag trends. Plan for 6-12 month growth.
Consider: More RAM before more nodes. SSD before more replicas.""",
        url="https://mariadb.com/kb/en/optimization-and-tuning/"
    ),
    DocumentChunk(
        id=None,
        source="best-practices",
        title="Memory and Swap Configuration for MariaDB",
        content="""Swap usage is critical for database performance:
- **Swappiness**: Set vm.swappiness=1-10 for databases (default 60 is too high)
- **Swap impact**: Any swap activity causes severe latency spikes (disk vs RAM speed)
- **Detection**: Check 'free -m' for swap usage, 'vmstat 1' for si/so activity
- **OOM risks**: If buffer pool + OS needs > RAM, OOM killer may terminate MariaDB
Best practices:
1. Size RAM so buffer pool (70-80%) + OS needs fit without swap
2. Keep small swap (1-2GB) for emergency, but it should never be used actively
3. Monitor with: cat /proc/meminfo | grep -i swap
4. Set innodb_buffer_pool_size based on AVAILABLE RAM, not total
5. Leave 20-25% RAM for OS, connections, temp tables
Warning signs: Swap used > 0, high si/so in vmstat, sudden query latency spikes.""",
        url="https://mariadb.com/kb/en/configuring-swappiness/"
    ),
]


def seed_sample_docs(rag_service: RAGService):
    """Seed the vector store with sample documentation"""
    print("Seeding vector store with sample documentation...")
    for doc in SAMPLE_DOCS:
        rag_service.vector_store.add_document(doc)
        print(f"  Added: {doc.title}")
    print(f"✅ Seeded {len(SAMPLE_DOCS)} documents")
