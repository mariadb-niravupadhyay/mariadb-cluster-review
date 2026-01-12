"""
Gemini Client - Google Gemini API Integration for AI Analysis
"""

import json
from typing import List, Dict, Any, Optional
import google.generativeai as genai

from .config import AIConfig


class GeminiClient:
    """
    Google Gemini API client for cluster analysis
    
    Provides AI-powered analysis with RAG context integration.
    """
    
    def __init__(self, config: AIConfig):
        self.config = config
        genai.configure(api_key=config.gemini.api_key)
        self.model = genai.GenerativeModel(config.gemini.model)
    
    def analyze_cluster(
        self,
        cluster_data: Dict[str, Any],
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze cluster configuration and metrics
        
        Args:
            cluster_data: Cluster information (nodes, status, variables, etc.)
            rag_context: Relevant documentation context from RAG
        
        Returns:
            AI analysis with recommendations
        """
        
        # Build the prompt with explicit critical questions
        system_context = """You are an expert MariaDB database administrator and architect.
Analyze the provided cluster data and answer these CRITICAL ARCHITECTURE QUESTIONS:

## Question 1: Can this architecture handle the current workload?
Analyze: QPS (queries per second), connection utilization, buffer pool hit ratios, thread activity.
Look at: Com_select, Com_insert, Com_update, Com_delete, Questions, Threads_connected, Threads_running,
Innodb_buffer_pool_reads, Innodb_buffer_pool_read_requests, Max_used_connections.

## Question 2: Should we scale UP or can we scale DOWN (cost savings)?
Analyze: CPU utilization (if available), RAM usage vs buffer pool size, connection headroom.
- Under-provisioned: resources maxed out, high thread counts, buffer pool thrashing
- Over-provisioned: low utilization (<30%), excess RAM, excess connections
- Right-sized: balanced utilization (50-70%)

## Question 3: Are HA/DR requirements properly met?
Analyze based on topology:
- Galera: wsrep_cluster_size (need 3+ for quorum), wsrep_ready, wsrep_connected, wsrep_local_state
- Replication: Slave_IO_Running, Slave_SQL_Running, Seconds_Behind_Master, semi-sync status
- Standalone: No HA - flag this as a risk

## Question 4: What bottlenecks exist? (Be specific and actionable)
Identify WHICH NODES and WHICH RESOURCES are under stress or could become bottlenecks affecting the entire database service:
- **Per-node resource stress**: Compare each node's metrics - identify the weakest node dragging down cluster performance
- **Buffer pool bottleneck**: Which node(s) have hit ratio < 99%? What's the actual impact on read latency?
- **Connection bottleneck**: Which node(s) are running out of connections? What happens when max is reached?
- **Flow control (Galera)**: Which node(s) are causing cluster-wide slowdowns via flow control?
- **Replication lag**: Which replica(s) are falling behind and by how much? Impact on read consistency?
- **Lock contention**: Where is row locking causing query waits?
- **CPU/Thread saturation**: Which node(s) have high Threads_running causing query queuing?
Explain the IMPACT on end-users (e.g., "Node X's buffer pool is 85% utilized, causing 15% of reads to hit disk, adding ~5ms latency")

## Question 5: Data Loss Risk Analysis
Based on the current topology and configuration, identify scenarios that could cause DATA LOSS:
- **Galera**: What happens if 2+ nodes fail simultaneously? Is arbitrator configured for split-brain prevention?
- **Async Replication**: If primary crashes, how much data could be lost based on replication lag?
- **Semi-Sync**: Is it configured with AFTER_SYNC (crash-safe) or AFTER_COMMIT? What's the timeout fallback risk?
- **Network Partition**: What happens during DC split? Is there proper fencing?
- **Configuration risks**: Is sync_binlog=1? Is innodb_flush_log_at_trx_commit=1?
Rate the data loss risk: low|medium|high with specific scenarios.

## Question 6: What does the current workload look like?
Calculate and report:
- Total QPS across cluster
- Read/Write ratio
- Writes per second (Com_insert + Com_update + Com_delete)
- Peak vs current connections
- Query patterns

Provide your response in JSON format with the following structure:
{
    "summary": "Brief overall assessment answering if architecture is adequate",
    "health_score": 0-100,
    "workload_assessment": {
        "total_qps": "calculated or N/A",
        "reads_per_sec": "calculated or N/A",
        "writes_per_sec": "calculated or N/A",
        "read_write_ratio": "e.g., 70:30",
        "connection_utilization": "percentage",
        "workload_type": "read-heavy|write-heavy|balanced|oltp|olap"
    },
    "capacity_assessment": {
        "status": "under-provisioned|right-sized|over-provisioned",
        "can_handle_current_workload": true/false,
        "scale_recommendation": "scale_up|maintain|scale_down",
        "cost_optimization_possible": true/false,
        "details": "explanation"
    },
    "ha_dr_assessment": {
        "ha_configured": true/false,
        "ha_status": "healthy|degraded|at_risk|none",
        "quorum_status": "ok|warning|critical|n/a",
        "replication_health": "ok|warning|critical|n/a",
        "failover_ready": true/false,
        "details": "explanation of HA/DR status"
    },
    "bottlenecks": [
        {"node": "hostname or 'cluster-wide'", "resource": "buffer_pool|connections|cpu|disk|replication|flow_control", "severity": "critical|warning|info", "current_value": "...", "threshold": "...", "impact": "User-friendly explanation of how this affects database performance"}
    ],
    "data_loss_risk": {
        "risk_level": "low|medium|high",
        "scenarios": [
            {"scenario": "Description of what could cause data loss", "likelihood": "low|medium|high", "data_at_risk": "Estimated amount/duration of data that could be lost", "mitigation": "How to prevent this"}
        ],
        "configuration_concerns": ["List of config settings that increase data loss risk"],
        "recommendations": ["Actions to reduce data loss risk"]
    },
    "findings": [
        {"category": "workload|capacity|ha_dr|bottleneck|config|data_loss", "severity": "critical|warning|info", "title": "...", "description": "...", "recommendation": "..."}
    ],
    "recommendations": ["prioritized list of actions with rationale"],
    "risks": ["potential risks identified"]
}
"""
        
        prompt_parts = [system_context]
        
        if rag_context:
            prompt_parts.append(f"""
Relevant MariaDB Documentation Context:
---
{rag_context}
---
Use this documentation to support your analysis and recommendations.
""")
        
        prompt_parts.append(f"""
Cluster Data to Analyze:
```json
{json.dumps(cluster_data, indent=2, default=str)}
```

Provide your analysis:
""")
        
        full_prompt = "\n".join(prompt_parts)
        
        # Generate response
        response = self.model.generate_content(full_prompt)
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, return structured response
            result = {
                "summary": response.text,
                "health_score": None,
                "findings": [],
                "recommendations": [],
                "risks": [],
                "raw_response": response.text
            }
        
        return result
    
    def analyze_workload(
        self,
        cluster_data: Dict[str, Any],
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze workload and resource utilization for right-sizing"""
        
        prompt = f"""You are an expert MariaDB database administrator and capacity planner.
Analyze the provided cluster data including status variables and statistics.

{f"Documentation Context:{chr(10)}{rag_context}{chr(10)}---" if rag_context else ""}

Cluster Data:
```json
{json.dumps(cluster_data, indent=2, default=str)}
```

Answer the following questions in your analysis:
1. Based on status variable values and other statistics, is the current architecture good enough to serve the current workload?
2. Is it under-provisioned (needs more resources)?
3. Is it over-provisioned (wasting resources)?
4. Can it run with fewer CPU cores or less RAM?
5. How is storage looking? Is there a need to increase storage capacity?

Provide response as JSON:
{{
    "summary": "Brief overall assessment of workload fit",
    "provisioning_status": "under-provisioned|right-sized|over-provisioned",
    "cpu_assessment": {{
        "status": "adequate|needs_more|over_allocated",
        "analysis": "Detailed analysis based on Threads_running, thread activity, etc.",
        "recommendation": "Specific recommendation"
    }},
    "memory_assessment": {{
        "status": "adequate|needs_more|over_allocated",
        "analysis": "Analysis based on buffer pool size, hit ratio, memory usage patterns",
        "recommendation": "Specific recommendation"
    }},
    "storage_assessment": {{
        "status": "adequate|needs_attention|critical",
        "analysis": "Analysis based on available metrics",
        "recommendation": "Specific recommendation"
    }},
    "connection_assessment": {{
        "status": "adequate|needs_more|over_allocated",
        "analysis": "Analysis based on connection usage patterns",
        "recommendation": "Specific recommendation"
    }},
    "overall_recommendations": ["List of prioritized recommendations"],
    "cost_optimization": "Suggestions for cost optimization if over-provisioned"
}}
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            result = {"summary": response.text, "raw_response": response.text}
        
        return result
    
    def analyze_capacity(
        self,
        node_data: Dict[str, Any],
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze node capacity and sizing"""
        
        prompt = f"""You are an expert MariaDB database administrator.
Analyze the following node metrics and provide a detailed capacity and bottleneck assessment.

{f"Documentation Context:{chr(10)}{rag_context}{chr(10)}---" if rag_context else ""}

Node Data:
```json
{json.dumps(node_data, indent=2, default=str)}
```

Perform a thorough analysis covering:

## 1. Resource Bottleneck Analysis
Identify which resources are currently stressed or could become bottlenecks that slow down database throughput:
- **CPU/Threads**: Is Threads_running high relative to CPU cores? Are queries queuing?
- **Buffer Pool**: What's the hit ratio? Are disk reads causing latency?
- **Connections**: How close to max_connections? What happens when exhausted?
- **Disk I/O**: Any signs of I/O wait or slow queries due to disk?
- **Lock Contention**: Innodb_row_lock_waits, Innodb_row_lock_time - is locking a problem?

## 2. Memory & Swap Analysis (IMPORTANT)
- **Swap Usage**: Is the system using swap? Any swap activity indicates memory pressure!
- **Swappiness Setting**: What is vm.swappiness? For databases, should be 1-10, NOT default 60
- **Buffer Pool vs Available RAM**: Is buffer pool sized appropriately (70-80% of RAM)?
- **Memory Pressure Signs**: Look for OOM risks, buffer pool resizing issues

## 3. Capacity Assessment
- CPU utilization and headroom
- Memory utilization and buffer pool efficiency  
- Connection utilization and patterns
- Storage capacity and growth

## 4. Query Throughput Analysis
- Current QPS and query patterns
- Slow query indicators
- Read vs write distribution

Provide response as JSON:
{{
    "node_name": "...",
    "capacity_score": 0-100,
    "bottlenecks": [
        {{"resource": "cpu|memory|buffer_pool|connections|disk|locks|swap", "severity": "critical|warning|info", "current_state": "...", "impact": "User-friendly explanation of how this slows down the database", "recommendation": "..."}}
    ],
    "swap_analysis": {{
        "swap_usage": "amount if available, or 'unknown'",
        "swappiness": "value if available, or 'unknown'",
        "is_swapping": true/false/"unknown",
        "risk_level": "ok|warning|critical",
        "analysis": "Explanation of swap impact on database performance",
        "recommendation": "Specific action to take"
    }},
    "metrics": {{
        "cpu": {{"status": "ok|warning|critical", "utilization": "...", "threads_running": "...", "recommendation": "..."}},
        "memory": {{"status": "...", "total_ram": "...", "buffer_pool_size": "...", "buffer_pool_hit_ratio": "...", "recommendation": "..."}},
        "connections": {{"status": "...", "current": "...", "max": "...", "utilization_pct": "...", "recommendation": "..."}},
        "disk": {{"status": "...", "assessment": "...", "recommendation": "..."}}
    }},
    "sizing_recommendation": "scale_up|right_sized|scale_down",
    "performance_impact": "Summary of how current bottlenecks are affecting query performance for end users",
    "recommendations": ["Prioritized list of specific actions to improve this node's performance"]
}}
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            result = {"raw_response": response.text}
        
        return result
    
    def analyze_logs_timeline(
        self,
        cluster_name: str,
        topology_type: str,
        node_logs: Dict[str, Any],
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze logs from multiple nodes and extract important events timeline"""
        
        # Build logs content
        logs_content = ""
        for node_id, node_data in node_logs.items():
            logs_content += f"\n=== Node: {node_data.get('hostname', 'Unknown')} ({node_data.get('role', 'Unknown')}) ===\n"
            if node_data.get('mariadb_log'):
                logs_content += f"--- MariaDB Log ---\n{node_data['mariadb_log'][:5000]}\n"
            if node_data.get('maxscale_log'):
                logs_content += f"--- MaxScale Log ---\n{node_data['maxscale_log'][:3000]}\n"
        
        prompt = f"""You are an expert at analyzing MariaDB and MaxScale logs.
Analyze the following logs from a {topology_type} cluster named "{cluster_name}".

{f"Documentation Context:{chr(10)}{rag_context}{chr(10)}---" if rag_context else ""}

Logs from cluster nodes:
{logs_content}

Extract and analyze the important events. Provide your response as JSON:
{{
    "summary": "Brief overall summary of what happened in these logs",
    "critical_findings": ["List of critical issues found"],
    "warnings": ["List of warnings and concerns"],
    "events": [
        {{
            "timestamp": "extracted or estimated timestamp",
            "node": "hostname or node identifier",
            "severity": "critical|error|warning|info",
            "description": "What happened"
        }}
    ],
    "recommendations": ["Prioritized list of recommended actions"],
    "root_cause_analysis": "If issues found, what appears to be the root cause"
}}

Focus on:
1. Error patterns and their sequence
2. Cluster state changes (for Galera: node joins/parts, state transfers)
3. Replication issues
4. Connection problems
5. Performance-related warnings
6. Any correlation between events across nodes
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            result = {"summary": response.text, "raw_response": response.text}
        
        return result
    
    def analyze_logs_with_local_context(
        self,
        cluster_name: str,
        topology_type: str,
        node_logs: Dict[str, Any],
        local_analysis: Dict[str, Any],
        findings: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze logs with pre-processed local analysis for AI enhancement"""
        
        # Build summary of local analysis
        local_summary = f"""
Pre-analyzed findings from pattern matching:
- Total findings: {len(findings)}
- Total events extracted: {len(events)}

Key findings detected:
"""
        for f in findings[:15]:  # Top 15 findings
            severity = f.get('severity', 'info')
            title = f.get('title', 'Unknown')
            local_summary += f"- [{severity}] {title}\n"
        
        local_summary += f"\nExtracted events timeline:\n"
        for e in events[:20]:  # Top 20 events
            local_summary += f"- [{e.get('timestamp', '?')}] {e.get('node', '?')}: {e.get('type', '?')} - {e.get('message', '')[:80]}\n"
        
        # Include some raw log snippets for context
        log_snippets = ""
        for node_id, node_data in list(node_logs.items())[:3]:
            hostname = node_data.get('hostname', 'Unknown')
            if node_data.get('mariadb_log'):
                log_snippets += f"\n=== {hostname} MariaDB Log (excerpt) ===\n"
                log_snippets += node_data['mariadb_log'][:2000] + "\n"
        
        prompt = f"""You are an expert MariaDB DBA analyzing logs from a {topology_type} cluster named "{cluster_name}".

{f"Documentation Context:{chr(10)}{rag_context}{chr(10)}---" if rag_context else ""}

A local pattern-based analyzer has already processed these logs. Here is its analysis:
{local_summary}

Raw log excerpts for additional context:
{log_snippets}

Based on this pre-analysis and raw logs, provide an enhanced AI interpretation:

1. Validate and expand on the findings - are there any false positives or missed issues?
2. Identify the root cause if there are related errors
3. Determine the sequence of events that led to any issues
4. Provide actionable recommendations

Return JSON:
{{
    "summary": "Overall interpretation of what happened",
    "critical_findings": ["Critical issues that need immediate attention"],
    "warnings": ["Warning-level concerns"],
    "events": [
        {{"timestamp": "...", "node": "...", "severity": "critical|error|warning|info", "description": "What happened"}}
    ],
    "root_cause_analysis": "If issues found, what's the likely root cause",
    "recommendations": ["Prioritized action items"],
    "correlation_insights": "Any patterns or correlations found across nodes"
}}
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            result = json.loads(response_text.strip())
            
            # Merge local events if AI didn't provide enough
            if not result.get("events") and events:
                result["events"] = [
                    {
                        "timestamp": e.get("timestamp", "Unknown"),
                        "node": e.get("node", "Unknown"),
                        "severity": "warning" if "error" in e.get("type", "").lower() else "info",
                        "description": f"{e.get('type', '')}: {e.get('message', '')}"
                    }
                    for e in events[:15]
                ]
        except json.JSONDecodeError:
            result = {
                "summary": response.text,
                "events": [
                    {
                        "timestamp": e.get("timestamp", "Unknown"),
                        "node": e.get("node", "Unknown"),
                        "severity": "info",
                        "description": f"{e.get('type', '')}: {e.get('message', '')}"
                    }
                    for e in events[:15]
                ],
                "raw_response": response.text
            }
        
        return result
    
    def interpret_log_entry(
        self,
        log_entry: str,
        log_type: str,  # "mariadb", "maxscale", "galera"
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Interpret a log entry using AI and documentation"""
        
        prompt = f"""You are an expert at analyzing MariaDB, MaxScale, and Galera logs.

{f"Documentation Context:{chr(10)}{rag_context}{chr(10)}---" if rag_context else ""}

Log Type: {log_type}
Log Entry:
```
{log_entry}
```

Analyze this log entry and provide:
{{
    "severity": "critical|error|warning|info|debug",
    "category": "e.g., replication, connection, query, authentication, etc.",
    "summary": "brief explanation of what happened",
    "root_cause": "likely cause of this event",
    "impact": "potential impact on the system",
    "recommended_action": "what to do about it",
    "related_metrics": ["metrics to check"],
    "documentation_reference": "relevant doc section if known"
}}
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            result = {"raw_response": response.text}
        
        return result
    
    def compare_topologies(
        self,
        current_topology: str,
        cluster_data: Dict[str, Any],
        rag_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare current topology with alternatives"""
        
        prompt = f"""You are an expert MariaDB architect.

{f"Documentation Context:{chr(10)}{rag_context}{chr(10)}---" if rag_context else ""}

Current Topology: {current_topology}
Cluster Data:
```json
{json.dumps(cluster_data, indent=2, default=str)}
```

Compare the current topology with alternatives (Galera, Semi-Sync, Async) and provide:
{{
    "current_topology": {{
        "name": "...",
        "pros": ["..."],
        "cons": ["..."],
        "suitability_score": 0-100
    }},
    "alternatives": [
        {{
            "name": "...",
            "pros": ["..."],
            "cons": ["..."],
            "suitability_score": 0-100,
            "migration_complexity": "low|medium|high",
            "recommendation": "..."
        }}
    ],
    "recommendation": "overall recommendation based on workload"
}}
"""
        
        response = self.model.generate_content(prompt)
        
        try:
            response_text = response.text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            result = {"raw_response": response.text}
        
        return result
    
    def chat(
        self,
        question: str,
        cluster_context: Optional[Dict[str, Any]] = None,
        rag_context: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        General chat interface for asking questions about the cluster
        """
        
        system_prompt = """You are an expert MariaDB database administrator assistant.
Answer questions about MariaDB, MaxScale, Galera, and database cluster management.
Be concise but thorough. Cite documentation when available."""
        
        prompt_parts = [system_prompt]
        
        if rag_context:
            prompt_parts.append(f"\nRelevant Documentation:\n{rag_context}\n---")
        
        if cluster_context:
            prompt_parts.append(f"\nCurrent Cluster Context:\n{json.dumps(cluster_context, indent=2, default=str)}\n---")
        
        if chat_history:
            prompt_parts.append("\nConversation History:")
            for msg in chat_history[-5:]:  # Last 5 messages
                prompt_parts.append(f"{msg['role'].upper()}: {msg['content']}")
            prompt_parts.append("---")
        
        prompt_parts.append(f"\nUser Question: {question}\n\nYour Response:")
        
        full_prompt = "\n".join(prompt_parts)
        response = self.model.generate_content(full_prompt)
        
        return response.text
