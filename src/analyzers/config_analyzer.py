"""
Configuration analyzer for MariaDB/Galera settings.
"""

from typing import Optional
from src.models.input import NodeData, ClusterReviewRequest, TopologyType
from src.models.output import Severity, Category, Finding, Recommendation


class ConfigAnalyzer:
    """Analyzer for MariaDB configuration settings."""
    
    def __init__(self):
        self.findings: list[Finding] = []
        self.recommendations: list[Recommendation] = []
    
    def analyze(self, request: ClusterReviewRequest) -> dict:
        """Analyze configuration across all nodes."""
        self.findings = []
        self.recommendations = []
        
        result = {
            "config_issues": [],
            "galera_config": {},
            "innodb_config": {},
            "recommendations": []
        }
        
        for node in request.nodes:
            self._analyze_innodb_config(node)
            self._analyze_connection_config(node, request)
            
            if request.topology_type == TopologyType.GALERA:
                self._analyze_galera_config(node)
                self._analyze_gcache_config(node)
        
        result["findings"] = self.findings
        result["recommendations"] = self.recommendations
        
        return result
    
    def _analyze_innodb_config(self, node: NodeData):
        """Analyze InnoDB configuration."""
        # Buffer pool size
        buffer_pool_size = node.get_variable_int("innodb_buffer_pool_size", 0)
        if node.system_resources and node.system_resources.ram_gb:
            ram_bytes = node.system_resources.ram_gb * 1024 * 1024 * 1024
            buffer_pool_pct = (buffer_pool_size / ram_bytes) * 100 if ram_bytes > 0 else 0
            
            if buffer_pool_pct < 50:
                self.recommendations.append(Recommendation(
                    priority=3,
                    category=Category.PERFORMANCE,
                    title=f"Increase buffer pool on {node.hostname}",
                    description=f"Buffer pool is only {buffer_pool_pct:.1f}% of RAM ({buffer_pool_size / (1024**3):.1f}GB of {node.system_resources.ram_gb}GB)",
                    action="Consider setting innodb_buffer_pool_size to 60-70% of RAM for dedicated DB servers",
                    impact="Better cache hit ratio",
                    effort="low"
                ))
        
        # innodb_flush_log_at_trx_commit
        flush_setting = node.get_variable("innodb_flush_log_at_trx_commit", "1")
        if str(flush_setting) == "0":
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title=f"Durability risk on {node.hostname}",
                description="innodb_flush_log_at_trx_commit=0 can lose up to 1 second of transactions on crash",
                details="For Galera, this is often acceptable as other nodes have the data, but consider =2 for better durability"
            ))
        
        # innodb_autoinc_lock_mode
        autoinc_mode = node.get_variable("innodb_autoinc_lock_mode", "1")
        if str(autoinc_mode) != "2":
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title=f"Auto-increment lock mode on {node.hostname}",
                description=f"innodb_autoinc_lock_mode={autoinc_mode}, should be 2 for Galera",
                details="Mode 2 (interleaved) is required for Galera to avoid deadlocks"
            ))
    
    def _analyze_connection_config(self, node: NodeData, request: ClusterReviewRequest):
        """Analyze connection-related configuration."""
        max_connections = node.get_variable_int("max_connections", 151)
        max_used = node.get_status_int("Max_used_connections", 0)
        
        if max_used > 0:
            utilization = (max_used / max_connections) * 100
            
            if utilization > 80:
                self.findings.append(Finding(
                    severity=Severity.WARNING,
                    category=Category.CAPACITY,
                    title=f"High connection utilization on {node.hostname}",
                    description=f"Peak connections ({max_used}) is {utilization:.1f}% of max_connections ({max_connections})",
                    details="Consider increasing max_connections or implementing connection pooling"
                ))
            elif utilization < 20 and max_connections > 500:
                self.recommendations.append(Recommendation(
                    priority=4,
                    category=Category.CONFIGURATION,
                    title=f"Reduce max_connections on {node.hostname}",
                    description=f"max_connections={max_connections} but peak usage is only {max_used} ({utilization:.1f}%)",
                    action=f"Consider reducing to {max(max_used * 2, 200)} to free memory",
                    impact="Minor memory savings",
                    effort="low"
                ))
        
        # wait_timeout
        wait_timeout = node.get_variable_int("wait_timeout", 28800)
        if wait_timeout > 3600:
            self.recommendations.append(Recommendation(
                priority=4,
                category=Category.CONFIGURATION,
                title=f"Review wait_timeout on {node.hostname}",
                description=f"wait_timeout={wait_timeout}s ({wait_timeout/3600:.1f} hours) may keep idle connections too long",
                action="Consider reducing to 300-900 seconds for web applications",
                impact="Better connection management",
                effort="low"
            ))
    
    def _analyze_galera_config(self, node: NodeData):
        """Analyze Galera-specific configuration."""
        # wsrep_slave_threads
        slave_threads = node.get_variable_int("wsrep_slave_threads", 1)
        cert_deps_distance = node.get_status_float("wsrep_cert_deps_distance", 0)
        
        if cert_deps_distance > 0 and slave_threads < cert_deps_distance:
            self.recommendations.append(Recommendation(
                priority=3,
                category=Category.PERFORMANCE,
                title=f"Increase wsrep_slave_threads on {node.hostname}",
                description=f"wsrep_slave_threads={slave_threads} but cert_deps_distance={cert_deps_distance:.1f}",
                action=f"Consider setting wsrep_slave_threads to {min(int(cert_deps_distance), 16)}",
                impact="Better parallel apply performance",
                effort="low"
            ))
        
        # wsrep_sync_wait
        sync_wait = node.get_variable("wsrep_sync_wait", "0")
        if str(sync_wait) != "0":
            self.findings.append(Finding(
                severity=Severity.INFO,
                category=Category.CONFIGURATION,
                title=f"Causal reads enabled on {node.hostname}",
                description=f"wsrep_sync_wait={sync_wait} ensures read-your-writes consistency",
                details="This adds latency but guarantees consistency. Disable if not needed."
            ))
        
        # binlog_format
        binlog_format = node.get_variable("binlog_format", "STATEMENT")
        if str(binlog_format).upper() != "ROW":
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title=f"Wrong binlog format on {node.hostname}",
                description=f"binlog_format={binlog_format}, should be ROW for Galera",
                details="ROW-based replication is required for Galera certification"
            ))
    
    def _analyze_gcache_config(self, node: NodeData):
        """Analyze Galera gcache configuration."""
        # Try to extract from wsrep_provider_options
        provider_options = node.get_variable("wsrep_provider_options", "")
        
        gcache_size = "0"
        gcache_keep_pages = "0"
        
        if provider_options:
            # Parse gcache.size from provider options
            if "gcache.size" in str(provider_options):
                import re
                match = re.search(r'gcache\.size\s*=\s*(\d+[GMK]?)', str(provider_options))
                if match:
                    gcache_size = match.group(1)
            
            if "gcache.keep_pages_size" in str(provider_options):
                match = re.search(r'gcache\.keep_pages_size\s*=\s*(\d+[GMK]?)', str(provider_options))
                if match:
                    gcache_keep_pages = match.group(1)
        
        # Check if gcache is effectively disabled
        if gcache_size == "0":
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title=f"gcache disabled on {node.hostname}",
                description="gcache.size=0 means IST (Incremental State Transfer) is not possible",
                details="Node recovery will always require full SST which is much slower"
            ))
            self.recommendations.append(Recommendation(
                priority=2,
                category=Category.AVAILABILITY,
                title=f"Enable gcache on {node.hostname}",
                description="gcache.size=0 disables IST recovery",
                action="Set gcache.size=1G or larger based on write volume",
                impact="Faster node recovery after short outages",
                effort="medium"
            ))
        
        # Check gcache.keep_pages_size as backup
        if gcache_keep_pages != "0":
            self.findings.append(Finding(
                severity=Severity.INFO,
                category=Category.CONFIGURATION,
                title=f"gcache.keep_pages_size on {node.hostname}",
                description=f"gcache.keep_pages_size={gcache_keep_pages} provides IST capability via page files",
                details="This is a fallback mechanism when gcache.size=0"
            ))


class TopologyComparisonAnalyzer:
    """Analyzer for comparing topology options (Galera vs Semi-Sync).
    
    IMPORTANT CORRECTIONS (based on technical review):
    1. Semi-sync CAN be configured for same-DC ACK only (faster than Galera)
    2. Galera DOES have cross-DC latency on every commit (certification)
    3. Semi-sync HAS automatic failover options (MaxScale, Orchestrator, MHA)
    4. Multi-DC deployments need proper quorum consideration (2n+1 rule)
    """
    
    # Failover options for semi-sync
    SEMI_SYNC_FAILOVER_OPTIONS = [
        "MaxScale with mariadbmon (auto_failover=true)",
        "Orchestrator (topology management + auto-failover)",
        "MHA (Master High Availability Manager)",
        "MariaDB Replication Manager",
        "ProxySQL + custom scripts"
    ]
    
    def analyze(self, request: ClusterReviewRequest) -> dict:
        """Analyze whether current topology is optimal or alternatives should be considered."""
        result = {
            "current_topology": request.topology_type.value,
            "workload_characteristics": {},
            "topology_comparison": [],
            "latency_comparison": {},
            "multi_dc_considerations": {},
            "recommendation": "",
            "galera_suitable": True,
            "semi_sync_suitable": False,
            "async_suitable": False,
            "semi_sync_failover_options": self.SEMI_SYNC_FAILOVER_OPTIONS
        }
        
        # Calculate workload characteristics
        total_writes = 0
        total_reads = 0
        total_qps = 0
        cert_failures = 0
        flow_control_issues = False
        
        for node in request.nodes:
            uptime = node.get_status_int("Uptime", 1)
            if uptime == 0:
                uptime = 1
            
            # Writes
            inserts = node.get_status_int("Com_insert", 0)
            updates = node.get_status_int("Com_update", 0)
            deletes = node.get_status_int("Com_delete", 0)
            total_writes += (inserts + updates + deletes) / uptime
            
            # Reads
            selects = node.get_status_int("Com_select", 0)
            total_reads += selects / uptime
            
            # QPS
            questions = node.get_status_int("Questions", 0)
            total_qps += questions / uptime
            
            # Galera-specific
            cert_failures += node.get_status_int("wsrep_local_cert_failures", 0)
            fc_paused = node.get_status_float("wsrep_flow_control_paused", 0)
            if fc_paused > 0.01:
                flow_control_issues = True
        
        # Avoid double-counting for cluster-wide metrics
        # For Galera, writes are replicated, so don't sum across nodes
        if request.topology_type == TopologyType.GALERA and len(request.nodes) > 1:
            # Use the highest write rate (likely the primary writer)
            max_writes = 0
            for node in request.nodes:
                uptime = node.get_status_int("Uptime", 1) or 1
                local_commits = node.get_status_int("wsrep_local_commits", 0)
                if local_commits / uptime > max_writes:
                    max_writes = local_commits / uptime
            total_writes = max_writes if max_writes > 0 else total_writes / len(request.nodes)
        
        read_write_ratio = total_reads / total_writes if total_writes > 0 else float('inf')
        
        result["workload_characteristics"] = {
            "total_qps": round(total_qps, 2),
            "writes_per_second": round(total_writes, 2),
            "reads_per_second": round(total_reads, 2),
            "read_write_ratio": round(read_write_ratio, 2) if read_write_ratio != float('inf') else "read-only",
            "certification_failures": cert_failures,
            "flow_control_issues": flow_control_issues
        }
        
        # Analyze suitability
        comparison = []
        
        # Galera analysis (CORRECTED understanding)
        galera_score = 90  # Reduced from 100 - Galera has tradeoffs
        galera_notes = []
        galera_advantages = []
        galera_disadvantages = []
        
        # Advantages
        galera_advantages.append("Multi-master writes supported")
        galera_advantages.append("Automatic failover with MaxScale")
        galera_advantages.append("All nodes always consistent (synchronous)")
        galera_advantages.append("Automatic node recovery (IST/SST)")
        galera_advantages.append("Built-in quorum and split-brain prevention")
        
        # CORRECTION: Galera HAS cross-DC latency on every commit
        galera_disadvantages.append("Cross-DC latency on EVERY commit (certification)")
        galera_disadvantages.append("Requires more nodes (2n+1 for quorum)")
        galera_disadvantages.append("More complex operations (SST/IST/gcache tuning)")
        galera_disadvantages.append("Write conflicts cause transaction rollback")
        
        if total_writes > 500:
            galera_score -= 10
            galera_notes.append("High write volume may cause flow control")
        if cert_failures > 100:
            galera_score -= 20
            galera_notes.append(f"Certification failures ({cert_failures}) indicate write conflicts")
        if flow_control_issues:
            galera_score -= 15
            galera_notes.append("Flow control indicates nodes struggling to keep up")
        if len(request.nodes) >= 3:
            galera_score += 5
            galera_notes.append("Quorum-capable with current node count")
        if total_writes < 50 and read_write_ratio > 10:
            galera_score -= 5
            galera_notes.append("Very low writes - Galera overhead may not be justified")
        
        # Multi-DC consideration
        galera_notes.append("NOTE: Galera certification requires cross-DC round-trip on every commit")
        
        comparison.append({
            "topology": "galera",
            "score": min(100, galera_score),
            "suitable": galera_score >= 60,
            "notes": galera_notes,
            "advantages": galera_advantages,
            "disadvantages": galera_disadvantages
        })
        
        # Semi-sync analysis (CORRECTED understanding)
        semi_sync_score = 75  # Base score - semi-sync is often underrated
        semi_sync_notes = []
        semi_sync_advantages = []
        semi_sync_disadvantages = []
        
        # CORRECTION: Semi-sync with local-DC ACK is FASTER than Galera for writes
        semi_sync_advantages.append("Faster writes with local-DC ACK (no cross-DC wait)")
        semi_sync_advantages.append("Simpler operations - standard replication")
        semi_sync_advantages.append("Fewer nodes required (2-3 vs 5-7 for Galera)")
        semi_sync_advantages.append("Better tooling ecosystem (pt-tools, standard backup)")
        
        # CORRECTION: Semi-sync HAS automatic failover options
        semi_sync_notes.append("Automatic failover available via MaxScale/Orchestrator/MHA")
        
        if total_writes < 100:
            semi_sync_score += 10
            semi_sync_notes.append("Low write volume - easily handled by single master")
        elif total_writes < 500:
            semi_sync_notes.append(f"Write rate ({total_writes:.0f}/sec) manageable by single master")
        else:
            semi_sync_notes.append(f"High write rate ({total_writes:.0f}/sec) - still viable for single master")
        
        if read_write_ratio > 5:
            semi_sync_score += 10
            semi_sync_notes.append("Read-heavy workload benefits from read replicas")
        
        if cert_failures == 0:
            semi_sync_score += 5
            semi_sync_notes.append("No write conflicts - single-writer model would work")
        
        # Disadvantages
        semi_sync_disadvantages.append("Single writer only - no multi-master capability")
        semi_sync_disadvantages.append("Remote DC may lag (RPO > 0 for DR site)")
        semi_sync_disadvantages.append("Node recovery requires manual/scripted rebuild")
        semi_sync_disadvantages.append("Need to configure split-brain prevention")
        
        comparison.append({
            "topology": "semi_sync",
            "score": min(100, semi_sync_score),
            "suitable": semi_sync_score >= 60,
            "notes": semi_sync_notes,
            "advantages": semi_sync_advantages,
            "disadvantages": semi_sync_disadvantages,
            "configuration_options": [
                "Local-DC ACK only (fastest - remote DC uses async)",
                "Any replica ACK (semi-sync from any node)",
                "Hybrid (semi-sync local + async remote)"
            ],
            "failover_options": self.SEMI_SYNC_FAILOVER_OPTIONS
        })
        
        # Async analysis
        async_score = 60
        async_notes = ["Lowest latency for writes", "Risk of data loss on master failure"]
        
        if total_writes > 500:
            async_score += 10
            async_notes.append("High writes benefit from async's lower latency")
        else:
            async_notes.append("Low write volume doesn't need async performance")
        
        comparison.append({
            "topology": "async_replication",
            "score": min(100, async_score),
            "suitable": async_score >= 60,
            "notes": async_notes
        })
        
        result["topology_comparison"] = comparison
        result["galera_suitable"] = galera_score >= 60
        result["semi_sync_suitable"] = semi_sync_score >= 60
        result["async_suitable"] = async_score >= 60
        
        # Add latency comparison (CORRECTED understanding)
        result["latency_comparison"] = {
            "galera": {
                "same_dc_write_latency": "2-5ms (certification overhead)",
                "cross_dc_write_latency": "10-50ms+ (certification requires ALL nodes)",
                "note": "Every commit waits for cross-DC certification"
            },
            "semi_sync_local_ack": {
                "same_dc_write_latency": "1-2ms (local replica ACK)",
                "cross_dc_write_latency": "N/A (remote DC uses async)",
                "note": "Fastest writes - only wait for local DC ACK"
            },
            "semi_sync_any_ack": {
                "same_dc_write_latency": "1-2ms (if local ACKs first)",
                "cross_dc_write_latency": "10-50ms+ (if remote ACKs first)",
                "note": "Latency depends on which replica ACKs first"
            },
            "async": {
                "same_dc_write_latency": "<1ms (no wait)",
                "cross_dc_write_latency": "N/A",
                "note": "Fastest but risk of data loss"
            }
        }
        
        # Add multi-DC considerations
        result["multi_dc_considerations"] = {
            "galera_quorum_rules": {
                "description": "Galera requires >50% of nodes for quorum",
                "safe_configurations": [
                    {"nodes": "3+3+arbitrator (7 total)", "dc1_loss": "4/7=57% ✓", "dc2_loss": "4/7=57% ✓"},
                    {"nodes": "2+2+arbitrator (5 total)", "dc1_loss": "3/5=60% ✓", "dc2_loss": "3/5=60% ✓"},
                    {"nodes": "3+2 (5 total, no arb)", "dc1_loss": "2/5=40% ✗", "dc2_loss": "3/5=60% ✓"}
                ],
                "warning": "2 nodes per DC without arbitrator = CLUSTER FREEZE on DC failure (50% = no quorum)"
            },
            "semi_sync_considerations": {
                "description": "Semi-sync with local ACK has no cross-DC latency for writes",
                "configuration": "Enable semi-sync on local DC replicas only, use async for remote DC",
                "dr_note": "Remote DC will lag behind (RPO > 0)"
            }
        }
        
        # Generate recommendation (CORRECTED - more balanced)
        if request.topology_type == TopologyType.GALERA:
            recommendations = []
            
            if galera_score >= semi_sync_score:
                recommendations.append(f"Galera score: {galera_score}, Semi-sync score: {semi_sync_score}")
                recommendations.append("Current Galera topology is working. Migration has risk.")
            
            # Check if using multi-master
            # If all writes go through MaxScale to single master, semi-sync is viable
            if cert_failures == 0:
                recommendations.append("No certification conflicts detected - single-writer pattern.")
                recommendations.append("Semi-sync with local-DC ACK would provide FASTER writes.")
            
            # Honest assessment
            recommendations.append("KEEP GALERA if: Need multi-master writes, zero RPO for DR, already working.")
            recommendations.append("CONSIDER SEMI-SYNC if: Want faster writes, simpler operations, cost reduction.")
            
            result["recommendation"] = " | ".join(recommendations)
        
        return result


class SizingAnalyzer:
    """Analyzer for cluster sizing and cost optimization.
    
    Provides both cluster-wide and per-node analysis including:
    - Per-node load metrics (QPS, writes/sec, connections)
    - Per-node resource utilization (CPU, memory, buffer pool)
    - Per-node sizing recommendations (scale up/down)
    """
    
    def analyze(self, request: ClusterReviewRequest) -> dict:
        """Analyze if cluster is right-sized."""
        result = {
            "current_sizing": {},
            "utilization": {},
            "per_node_analysis": [],  # NEW: Per-node detailed analysis
            "per_node_sizing_recommendations": [],  # NEW: Per-node sizing recommendations
            "cluster_summary": {},  # NEW: Aggregated cluster metrics
            "rightsizing_options": [],
            "cost_impact": ""
        }
        
        # Current sizing
        total_vcpus = 0
        total_ram_gb = 0
        total_disk_gb = 0
        
        for node in request.nodes:
            if node.system_resources:
                total_vcpus += node.system_resources.cpu_cores
                total_ram_gb += node.system_resources.ram_gb
                total_disk_gb += node.system_resources.disk_total_gb
        
        result["current_sizing"] = {
            "node_count": len(request.nodes),
            "total_vcpus": total_vcpus,
            "total_ram_gb": total_ram_gb,
            "total_disk_gb": total_disk_gb,
            "vcpus_per_node": total_vcpus / len(request.nodes) if request.nodes else 0,
            "ram_per_node_gb": total_ram_gb / len(request.nodes) if request.nodes else 0
        }
        
        # Calculate utilization
        avg_connection_util = 0
        avg_cpu_util = 0
        peak_connections = 0
        total_qps = 0
        
        for node in request.nodes:
            max_conn = node.get_variable_int("max_connections", 1000)
            max_used = node.get_status_int("Max_used_connections", 0)
            if max_conn > 0:
                avg_connection_util += (max_used / max_conn) * 100
            peak_connections = max(peak_connections, max_used)
            
            if node.system_resources and node.system_resources.cpu_utilization_pct:
                avg_cpu_util += node.system_resources.cpu_utilization_pct
            
            uptime = node.get_status_int("Uptime", 1) or 1
            questions = node.get_status_int("Questions", 0)
            total_qps += questions / uptime
        
        if request.nodes:
            avg_connection_util /= len(request.nodes)
            avg_cpu_util /= len(request.nodes)
        
        result["utilization"] = {
            "avg_connection_utilization_pct": round(avg_connection_util, 1),
            "avg_cpu_utilization_pct": round(avg_cpu_util, 1) if avg_cpu_util > 0 else "N/A",
            "peak_connections_cluster": peak_connections,
            "total_qps_cluster": round(total_qps, 1)
        }
        
        # =====================================================
        # PER-NODE ANALYSIS (NEW)
        # =====================================================
        per_node_analysis = []
        per_node_recommendations = []
        
        # Collect per-node metrics for avg/max calculations
        all_qps = []
        all_writes_per_sec = []
        all_connection_util = []
        all_bp_hit_ratio = []
        all_cpu_util = []
        all_memory_util = []
        
        for node in request.nodes:
            uptime = node.get_status_int("Uptime", 1) or 1
            
            # Load metrics
            questions = node.get_status_int("Questions", 0)
            qps = questions / uptime
            
            inserts = node.get_status_int("Com_insert", 0)
            updates = node.get_status_int("Com_update", 0)
            deletes = node.get_status_int("Com_delete", 0)
            writes_per_sec = (inserts + updates + deletes) / uptime
            
            selects = node.get_status_int("Com_select", 0)
            reads_per_sec = selects / uptime
            
            commits = node.get_status_int("Com_commit", 0)
            commits_per_sec = commits / uptime
            
            # Connection metrics
            max_conn = node.get_variable_int("max_connections", 1000)
            max_used = node.get_status_int("Max_used_connections", 0)
            threads_connected = node.get_status_int("Threads_connected", 0)
            threads_running = node.get_status_int("Threads_running", 0)
            conn_util = (max_used / max_conn * 100) if max_conn > 0 else 0
            
            # Buffer pool metrics
            bp_read_requests = node.get_status_int("Innodb_buffer_pool_read_requests", 0)
            bp_reads = node.get_status_int("Innodb_buffer_pool_reads", 0)
            bp_hit_ratio = ((bp_read_requests - bp_reads) / bp_read_requests * 100) if bp_read_requests > 0 else 0
            
            bp_pages_total = node.get_status_int("Innodb_buffer_pool_pages_total", 0)
            bp_pages_data = node.get_status_int("Innodb_buffer_pool_pages_data", 0)
            bp_pages_free = node.get_status_int("Innodb_buffer_pool_pages_free", 0)
            bp_pages_dirty = node.get_status_int("Innodb_buffer_pool_pages_dirty", 0)
            bp_usage_pct = (bp_pages_data / bp_pages_total * 100) if bp_pages_total > 0 else 0
            
            # Resource metrics from system_resources (if available)
            cpu_cores = 0
            ram_gb = 0
            cpu_util_pct = None
            memory_util_pct = None
            
            if node.system_resources:
                cpu_cores = node.system_resources.cpu_cores
                ram_gb = node.system_resources.ram_gb
                cpu_util_pct = getattr(node.system_resources, 'cpu_utilization_pct', None)
                memory_util_pct = getattr(node.system_resources, 'ram_utilization_pct', None)
            
            # Estimate CPU utilization from QPS if not provided
            estimated_cpu_util = None
            if cpu_util_pct is None and cpu_cores > 0:
                # Rough estimate: assume 100 QPS per core at 10% utilization
                estimated_cpu_util = min(100, (qps / (cpu_cores * 100)) * 10)
            
            # Collect for avg/max calculations
            all_qps.append(qps)
            all_writes_per_sec.append(writes_per_sec)
            all_connection_util.append(conn_util)
            if bp_hit_ratio > 0:
                all_bp_hit_ratio.append(bp_hit_ratio)
            if cpu_util_pct is not None:
                all_cpu_util.append(cpu_util_pct)
            if memory_util_pct is not None:
                all_memory_util.append(memory_util_pct)
            
            # Build per-node analysis
            node_analysis = {
                "hostname": node.hostname,
                "uptime_hours": round(uptime / 3600, 1),
                "load_metrics": {
                    "qps": round(qps, 1),
                    "writes_per_sec": round(writes_per_sec, 1),
                    "reads_per_sec": round(reads_per_sec, 1),
                    "commits_per_sec": round(commits_per_sec, 1),
                },
                "connection_metrics": {
                    "max_connections": max_conn,
                    "max_used_connections": max_used,
                    "threads_connected": threads_connected,
                    "threads_running": threads_running,
                    "connection_utilization_pct": round(conn_util, 1),
                },
                "buffer_pool_metrics": {
                    "hit_ratio_pct": round(bp_hit_ratio, 2),
                    "pages_total": bp_pages_total,
                    "pages_data": bp_pages_data,
                    "pages_free": bp_pages_free,
                    "pages_dirty": bp_pages_dirty,
                    "usage_pct": round(bp_usage_pct, 1),
                },
                "resource_metrics": {
                    "vcpus": cpu_cores,
                    "ram_gb": ram_gb,
                    "cpu_utilization_pct": cpu_util_pct if cpu_util_pct is not None else "N/A",
                    "memory_utilization_pct": memory_util_pct if memory_util_pct is not None else "N/A",
                    "estimated_cpu_utilization_pct": round(estimated_cpu_util, 1) if estimated_cpu_util else "N/A",
                }
            }
            per_node_analysis.append(node_analysis)
            
            # Generate per-node sizing recommendation
            node_recommendation = {
                "hostname": node.hostname,
                "current_vcpus": cpu_cores,
                "current_ram_gb": ram_gb,
                "recommended_vcpus": cpu_cores,
                "recommended_ram_gb": ram_gb,
                "action": "keep",
                "rationale": []
            }
            
            # Analyze if node is over/under provisioned
            effective_cpu_util = cpu_util_pct if cpu_util_pct is not None else estimated_cpu_util
            
            if effective_cpu_util is not None:
                if effective_cpu_util < 20 and cpu_cores >= 8:
                    node_recommendation["recommended_vcpus"] = max(4, cpu_cores // 2)
                    node_recommendation["action"] = "scale_down"
                    node_recommendation["rationale"].append(f"Low CPU utilization ({effective_cpu_util:.1f}%) - can reduce vCPUs")
                elif effective_cpu_util > 80:
                    node_recommendation["recommended_vcpus"] = min(32, cpu_cores * 2)
                    node_recommendation["action"] = "scale_up"
                    node_recommendation["rationale"].append(f"High CPU utilization ({effective_cpu_util:.1f}%) - consider adding vCPUs")
            
            if conn_util < 20 and max_conn >= 500:
                node_recommendation["rationale"].append(f"Connection utilization low ({conn_util:.1f}%) - max_connections can be reduced")
            elif conn_util > 80:
                node_recommendation["rationale"].append(f"High connection utilization ({conn_util:.1f}%) - consider increasing max_connections")
            
            if bp_hit_ratio > 0 and bp_hit_ratio < 95:
                node_recommendation["rationale"].append(f"Buffer pool hit ratio low ({bp_hit_ratio:.1f}%) - consider increasing innodb_buffer_pool_size")
            
            if bp_pages_free < 100 and bp_pages_total > 0:
                free_pct = bp_pages_free / bp_pages_total * 100
                if free_pct < 5:
                    node_recommendation["rationale"].append(f"Buffer pool nearly full ({free_pct:.1f}% free) - may need more RAM")
            
            # Check InnoDB buffer pool sizing (thumb rule: 70-75% of RAM for dedicated DB servers)
            if ram_gb > 0:
                # Get buffer pool size from variables
                bp_size_bytes = node.get_variable_int("innodb_buffer_pool_size", 0)
                bp_size_gb = bp_size_bytes / (1024 * 1024 * 1024) if bp_size_bytes > 0 else 0
                
                if bp_size_gb > 0:
                    bp_ram_pct = (bp_size_gb / ram_gb) * 100
                    node_analysis["buffer_pool_metrics"]["configured_size_gb"] = round(bp_size_gb, 2)
                    node_analysis["buffer_pool_metrics"]["ram_percentage"] = round(bp_ram_pct, 1)
                    
                    # Thumb rule: 70-75% of RAM for dedicated database servers
                    if bp_ram_pct < 50:
                        recommended_bp_gb = round(ram_gb * 0.70, 1)
                        node_recommendation["rationale"].append(
                            f"Buffer pool undersized: {bp_size_gb:.1f}GB = {bp_ram_pct:.0f}% of RAM. "
                            f"Thumb rule: 70-75% for dedicated DB servers. Recommend: {recommended_bp_gb}GB"
                        )
                        node_recommendation["recommended_buffer_pool_gb"] = recommended_bp_gb
                    elif bp_ram_pct > 85:
                        node_recommendation["rationale"].append(
                            f"Buffer pool may be oversized: {bp_size_gb:.1f}GB = {bp_ram_pct:.0f}% of RAM. "
                            f"Leave 15-25% for OS and connections. Consider reducing to {round(ram_gb * 0.75, 1)}GB"
                        )
                    elif 70 <= bp_ram_pct <= 80:
                        node_recommendation["rationale"].append(
                            f"Buffer pool well-sized: {bp_size_gb:.1f}GB = {bp_ram_pct:.0f}% of RAM (optimal: 70-75%)"
                        )
            
            if not node_recommendation["rationale"]:
                node_recommendation["rationale"].append("Node is appropriately sized for current workload")
            
            per_node_recommendations.append(node_recommendation)
        
        result["per_node_analysis"] = per_node_analysis
        result["per_node_sizing_recommendations"] = per_node_recommendations
        
        # =====================================================
        # RESOURCE CONSISTENCY CHECK (NEW)
        # =====================================================
        # Best practice: All nodes in Galera/Semi-Sync/Async clusters should have
        # equivalent RAM, CPU, and storage to ensure consistent performance
        
        resource_consistency = {
            "is_consistent": True,
            "inconsistencies": [],
            "node_resources": [],
            "recommendation": ""
        }
        
        # Collect resources from all nodes
        node_resources_list = []
        for node in request.nodes:
            if node.system_resources:
                node_resources_list.append({
                    "hostname": node.hostname,
                    "cpu_cores": node.system_resources.cpu_cores,
                    "ram_gb": node.system_resources.ram_gb,
                    "disk_total_gb": node.system_resources.disk_total_gb,
                    "disk_type": getattr(node.system_resources, 'disk_type', None)
                })
            else:
                node_resources_list.append({
                    "hostname": node.hostname,
                    "cpu_cores": None,
                    "ram_gb": None,
                    "disk_total_gb": None,
                    "disk_type": None
                })
        
        resource_consistency["node_resources"] = node_resources_list
        
        # Check for inconsistencies if we have resource data
        nodes_with_resources = [n for n in node_resources_list if n["cpu_cores"] is not None]
        
        if len(nodes_with_resources) >= 2:
            # Get unique values for each resource type
            cpu_values = set(n["cpu_cores"] for n in nodes_with_resources)
            ram_values = set(n["ram_gb"] for n in nodes_with_resources)
            disk_values = set(n["disk_total_gb"] for n in nodes_with_resources if n["disk_total_gb"])
            disk_types = set(n["disk_type"] for n in nodes_with_resources if n["disk_type"])
            
            inconsistencies = []
            
            # Check CPU consistency
            if len(cpu_values) > 1:
                resource_consistency["is_consistent"] = False
                min_cpu = min(cpu_values)
                max_cpu = max(cpu_values)
                nodes_by_cpu = {}
                for n in nodes_with_resources:
                    cpu = n["cpu_cores"]
                    if cpu not in nodes_by_cpu:
                        nodes_by_cpu[cpu] = []
                    nodes_by_cpu[cpu].append(n["hostname"])
                
                inconsistencies.append({
                    "resource": "cpu_cores",
                    "severity": "warning",
                    "message": f"CPU cores vary across nodes: {min_cpu} to {max_cpu} vCPUs",
                    "details": {str(k) + " vCPUs": v for k, v in nodes_by_cpu.items()},
                    "recommendation": f"Standardize all nodes to {max_cpu} vCPUs for consistent performance"
                })
            
            # Check RAM consistency
            if len(ram_values) > 1:
                resource_consistency["is_consistent"] = False
                min_ram = min(ram_values)
                max_ram = max(ram_values)
                nodes_by_ram = {}
                for n in nodes_with_resources:
                    ram = n["ram_gb"]
                    if ram not in nodes_by_ram:
                        nodes_by_ram[ram] = []
                    nodes_by_ram[ram].append(n["hostname"])
                
                inconsistencies.append({
                    "resource": "ram_gb",
                    "severity": "warning",
                    "message": f"RAM varies across nodes: {min_ram}GB to {max_ram}GB",
                    "details": {str(k) + " GB": v for k, v in nodes_by_ram.items()},
                    "recommendation": f"Standardize all nodes to {max_ram}GB RAM for consistent performance"
                })
            
            # Check disk capacity consistency
            if len(disk_values) > 1:
                resource_consistency["is_consistent"] = False
                min_disk = min(disk_values)
                max_disk = max(disk_values)
                # Only flag if difference is significant (>10%)
                if (max_disk - min_disk) / max_disk > 0.10:
                    nodes_by_disk = {}
                    for n in nodes_with_resources:
                        disk = n["disk_total_gb"]
                        if disk:
                            if disk not in nodes_by_disk:
                                nodes_by_disk[disk] = []
                            nodes_by_disk[disk].append(n["hostname"])
                    
                    inconsistencies.append({
                        "resource": "disk_total_gb",
                        "severity": "warning",
                        "message": f"Disk capacity varies across nodes: {min_disk}GB to {max_disk}GB",
                        "details": {str(k) + " GB": v for k, v in nodes_by_disk.items()},
                        "recommendation": f"Ensure all nodes have sufficient and consistent disk capacity"
                    })
            
            # Check disk type consistency
            if len(disk_types) > 1:
                resource_consistency["is_consistent"] = False
                nodes_by_type = {}
                for n in nodes_with_resources:
                    dtype = n["disk_type"]
                    if dtype:
                        if dtype not in nodes_by_type:
                            nodes_by_type[dtype] = []
                        nodes_by_type[dtype].append(n["hostname"])
                
                inconsistencies.append({
                    "resource": "disk_type",
                    "severity": "critical",
                    "message": f"Disk types vary across nodes: {', '.join(disk_types)}",
                    "details": nodes_by_type,
                    "recommendation": "CRITICAL: All nodes should use same storage type (SSD/NVMe recommended). Mixed storage causes performance inconsistencies and replication lag."
                })
            
            resource_consistency["inconsistencies"] = inconsistencies
            
            if inconsistencies:
                resource_consistency["recommendation"] = (
                    "⚠️ Resource inconsistencies detected across cluster nodes. "
                    "For Galera/Semi-Sync/Async replication, all nodes should have equivalent "
                    "CPU, RAM, and storage resources to ensure consistent performance and prevent "
                    "replication lag or flow control issues."
                )
            else:
                resource_consistency["recommendation"] = (
                    "✅ All nodes have consistent resource allocation (CPU, RAM, storage). "
                    "This is optimal for cluster performance."
                )
        
        result["resource_consistency"] = resource_consistency
        
        # =====================================================
        # END RESOURCE CONSISTENCY CHECK
        # =====================================================
        
        # Cluster summary with avg/max
        result["cluster_summary"] = {
            "qps": {
                "total": round(sum(all_qps), 1),
                "avg_per_node": round(sum(all_qps) / len(all_qps), 1) if all_qps else 0,
                "max_node": round(max(all_qps), 1) if all_qps else 0,
                "min_node": round(min(all_qps), 1) if all_qps else 0,
            },
            "writes_per_sec": {
                "total": round(sum(all_writes_per_sec), 1),
                "avg_per_node": round(sum(all_writes_per_sec) / len(all_writes_per_sec), 1) if all_writes_per_sec else 0,
                "max_node": round(max(all_writes_per_sec), 1) if all_writes_per_sec else 0,
            },
            "connection_utilization_pct": {
                "avg": round(sum(all_connection_util) / len(all_connection_util), 1) if all_connection_util else 0,
                "max": round(max(all_connection_util), 1) if all_connection_util else 0,
            },
            "buffer_pool_hit_ratio_pct": {
                "avg": round(sum(all_bp_hit_ratio) / len(all_bp_hit_ratio), 2) if all_bp_hit_ratio else 0,
                "min": round(min(all_bp_hit_ratio), 2) if all_bp_hit_ratio else 0,
            },
            "cpu_utilization_pct": {
                "avg": round(sum(all_cpu_util) / len(all_cpu_util), 1) if all_cpu_util else "N/A",
                "max": round(max(all_cpu_util), 1) if all_cpu_util else "N/A",
            },
            "memory_utilization_pct": {
                "avg": round(sum(all_memory_util) / len(all_memory_util), 1) if all_memory_util else "N/A",
                "max": round(max(all_memory_util), 1) if all_memory_util else "N/A",
            },
        }
        
        # =====================================================
        # END PER-NODE ANALYSIS
        # =====================================================
        
        # Generate rightsizing options
        options = []
        
        # Option 1: Current (baseline)
        options.append({
            "option": "current",
            "node_count": len(request.nodes),
            "vcpus_per_node": result["current_sizing"]["vcpus_per_node"],
            "ram_per_node_gb": result["current_sizing"]["ram_per_node_gb"],
            "cost_factor": 1.0,
            "risk_level": "low",
            "notes": "Current configuration - maximum redundancy"
        })
        
        # For Galera with 6 nodes, suggest alternatives (CORRECTED for multi-DC quorum)
        if request.topology_type == TopologyType.GALERA and len(request.nodes) >= 6:
            # Option 2: 5 nodes (2+2+arbitrator) - SAFE configuration
            options.append({
                "option": "reduced_5_node_with_arbitrator",
                "node_count": 5,
                "configuration": "2 nodes per DC + 1 arbitrator (cloud)",
                "vcpus_per_node": result["current_sizing"]["vcpus_per_node"],
                "ram_per_node_gb": result["current_sizing"]["ram_per_node_gb"],
                "cost_factor": 0.72,  # 4 DB nodes + 1 small arbitrator
                "risk_level": "low",
                "notes": "SAFE: 2+2+arb maintains quorum on DC failure (3/5=60%)",
                "dc_failure_behavior": "Cluster continues with 3/5 nodes (quorum maintained)"
            })
            
            # WARNING: 4 nodes (2+2) WITHOUT arbitrator is UNSAFE
            options.append({
                "option": "reduced_4_node_WARNING",
                "node_count": 4,
                "configuration": "2 nodes per DC, NO arbitrator",
                "vcpus_per_node": result["current_sizing"]["vcpus_per_node"],
                "ram_per_node_gb": result["current_sizing"]["ram_per_node_gb"],
                "cost_factor": 0.67,
                "risk_level": "CRITICAL",
                "notes": "⚠️ UNSAFE: 2+2 = CLUSTER FREEZE on DC failure (2/4=50% = NO quorum)",
                "dc_failure_behavior": "CLUSTER FREEZES - no reads or writes possible",
                "recommendation": "DO NOT USE without arbitrator or asymmetric node distribution"
            })
            
            # Option 3: 3 nodes (single DC only)
            options.append({
                "option": "minimum_3_node_single_dc",
                "node_count": 3,
                "configuration": "3 nodes in single DC (no DR)",
                "vcpus_per_node": result["current_sizing"]["vcpus_per_node"],
                "ram_per_node_gb": result["current_sizing"]["ram_per_node_gb"],
                "cost_factor": 0.5,
                "risk_level": "high",
                "notes": "Minimum for quorum - ~50% cost savings but NO disaster recovery",
                "dc_failure_behavior": "Complete outage if DC fails"
            })
        
        # If utilization is very low, suggest smaller nodes
        if avg_connection_util < 30 and (avg_cpu_util == 0 or avg_cpu_util < 30):
            current_vcpus = result["current_sizing"]["vcpus_per_node"]
            if current_vcpus >= 8:
                options.append({
                    "option": "smaller_nodes",
                    "node_count": len(request.nodes),
                    "vcpus_per_node": current_vcpus // 2,
                    "ram_per_node_gb": result["current_sizing"]["ram_per_node_gb"] // 2,
                    "cost_factor": 0.5,
                    "risk_level": "medium",
                    "notes": f"Half-sized nodes - utilization suggests {current_vcpus} vCPUs may be excessive"
                })
        
        result["rightsizing_options"] = options
        
        # Cost impact summary
        if avg_connection_util < 25:
            result["cost_impact"] = "Cluster appears over-provisioned. 30-50% cost reduction possible with minimal risk."
        elif avg_connection_util < 50:
            result["cost_impact"] = "Cluster has good headroom. Minor rightsizing possible if needed."
        else:
            result["cost_impact"] = "Cluster is well-utilized. Current sizing is appropriate."
        
        return result
