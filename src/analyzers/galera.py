"""
Galera Cluster analyzer.
"""

from datetime import datetime

from src.analyzers.base import BaseAnalyzer
from src.models.input import ClusterReviewRequest, TopologyType, NodeRole
from src.models.output import (
    Severity, Category, ArchitectureAssessment, NodeAnalysis,
    MetricAnalysis, ClusterReviewResponse
)
from src.utils import metrics


class GaleraAnalyzer(BaseAnalyzer):
    """Analyzer for Galera Cluster (synchronous multi-master replication)."""
    
    def analyze_node_performance(self, node) -> NodeAnalysis:
        """Extended analysis including Galera-specific metrics."""
        # Get base analysis
        analysis = super().analyze_node_performance(node)
        
        # Add Galera-specific metrics
        wsrep_ready = metrics.get_wsrep_status(node, "wsrep_ready", "OFF")
        wsrep_connected = metrics.get_wsrep_status(node, "wsrep_connected", "OFF")
        wsrep_cluster_status = metrics.get_wsrep_status(node, "wsrep_cluster_status", "")
        wsrep_local_state = metrics.get_wsrep_status(node, "wsrep_local_state_comment", "")
        
        analysis.wsrep_ready = str(wsrep_ready).upper() == "ON"
        analysis.wsrep_cluster_status = wsrep_cluster_status
        
        # Check node health
        if not analysis.wsrep_ready:
            analysis.status = Severity.CRITICAL
            analysis.findings.append(self._create_wsrep_finding(
                node, "wsrep_ready is OFF", Severity.CRITICAL
            ))
        
        if wsrep_cluster_status != "Primary":
            analysis.status = Severity.CRITICAL
            analysis.findings.append(self._create_wsrep_finding(
                node, f"Node not in Primary component (status: {wsrep_cluster_status})", 
                Severity.CRITICAL
            ))
        
        if wsrep_local_state not in ("Synced", "Donor/Desynced"):
            if analysis.status != Severity.CRITICAL:
                analysis.status = Severity.WARNING
            analysis.findings.append(self._create_wsrep_finding(
                node, f"Node state is {wsrep_local_state}", Severity.WARNING
            ))
        
        # Flow control analysis
        flow_control_paused = metrics.calculate_galera_flow_control_paused(node)
        analysis.wsrep_flow_control_paused = flow_control_paused
        
        fc_thresholds = self.thresholds.get("galera", {}).get("flow_control_paused", {})
        fc_status = Severity.INFO
        
        if flow_control_paused >= fc_thresholds.get("critical", 0.2):
            fc_status = Severity.CRITICAL
            analysis.status = Severity.CRITICAL
            analysis.findings.append(self._create_flow_control_finding(
                node, flow_control_paused, "critical"
            ))
        elif flow_control_paused >= fc_thresholds.get("warning", 0.01):
            fc_status = Severity.WARNING
            if analysis.status != Severity.CRITICAL:
                analysis.status = Severity.WARNING
            analysis.findings.append(self._create_flow_control_finding(
                node, flow_control_paused, "warning"
            ))
        
        analysis.metrics.append(MetricAnalysis(
            name="wsrep_flow_control_paused",
            value=flow_control_paused * 100,
            unit="%",
            status=fc_status,
            description=f"Time paused for flow control: {flow_control_paused*100:.2f}%",
            threshold_warning=fc_thresholds.get("warning", 0.01) * 100,
            threshold_critical=fc_thresholds.get("critical", 0.2) * 100
        ))
        
        # Receive queue analysis
        recv_queue_avg = metrics.calculate_galera_recv_queue_avg(node)
        rq_thresholds = self.thresholds.get("galera", {}).get("local_recv_queue_avg", {})
        rq_status = Severity.INFO
        
        if recv_queue_avg >= rq_thresholds.get("critical", 1.0):
            rq_status = Severity.CRITICAL
        elif recv_queue_avg >= rq_thresholds.get("warning", 0.5):
            rq_status = Severity.WARNING
        
        analysis.metrics.append(MetricAnalysis(
            name="wsrep_local_recv_queue_avg",
            value=recv_queue_avg,
            unit="writesets",
            status=rq_status,
            description=f"Average receive queue: {recv_queue_avg:.2f}",
            threshold_warning=rq_thresholds.get("warning", 0.5),
            threshold_critical=rq_thresholds.get("critical", 1.0)
        ))
        
        # Send queue analysis
        send_queue_avg = metrics.calculate_galera_send_queue_avg(node)
        sq_thresholds = self.thresholds.get("galera", {}).get("local_send_queue_avg", {})
        sq_status = Severity.INFO
        
        if send_queue_avg >= sq_thresholds.get("critical", 1.0):
            sq_status = Severity.CRITICAL
        elif send_queue_avg >= sq_thresholds.get("warning", 0.5):
            sq_status = Severity.WARNING
        
        analysis.metrics.append(MetricAnalysis(
            name="wsrep_local_send_queue_avg",
            value=send_queue_avg,
            unit="writesets",
            status=sq_status,
            description=f"Average send queue: {send_queue_avg:.2f}",
            threshold_warning=sq_thresholds.get("warning", 0.5),
            threshold_critical=sq_thresholds.get("critical", 1.0)
        ))
        
        # Certification conflicts
        cert_conflicts = metrics.calculate_galera_cert_conflicts_per_hour(node)
        analysis.metrics.append(MetricAnalysis(
            name="cert_conflicts_per_hour",
            value=cert_conflicts,
            unit="conflicts/hour",
            status=Severity.INFO if cert_conflicts < 10 else Severity.WARNING,
            description=f"Certification conflicts: {cert_conflicts:.1f}/hour"
        ))
        
        return analysis
    
    def _create_wsrep_finding(self, node, message: str, severity: Severity):
        """Create a WSREP-related finding."""
        from src.models.output import Finding
        return Finding(
            severity=severity,
            category=Category.REPLICATION,
            title="Galera node issue",
            description=message,
            node=node.hostname
        )
    
    def _create_flow_control_finding(self, node, value: float, level: str):
        """Create a flow control finding."""
        from src.models.output import Finding
        return Finding(
            severity=Severity.CRITICAL if level == "critical" else Severity.WARNING,
            category=Category.PERFORMANCE,
            title=f"Flow control {level}",
            description=f"Node paused {value*100:.2f}% of time due to flow control",
            metric_name="wsrep_flow_control_paused",
            metric_value=f"{value*100:.2f}%",
            node=node.hostname
        )
    
    def analyze_architecture(self, request: ClusterReviewRequest) -> ArchitectureAssessment:
        """Analyze Galera cluster architecture."""
        galera_nodes = [n for n in request.nodes if n.role == NodeRole.GALERA_NODE]
        node_count = len(galera_nodes) if galera_nodes else len(request.nodes)
        
        recommendations = []
        alternatives = []
        status = Severity.INFO
        topology_valid = True
        
        # Check cluster size
        if node_count < 3:
            topology_valid = False
            status = Severity.WARNING
            recommendations.append(
                f"Galera cluster has {node_count} nodes. Minimum 3 recommended for quorum."
            )
        
        if node_count % 2 == 0:
            recommendations.append(
                f"Even number of nodes ({node_count}) - consider odd number to avoid split-brain"
            )
        
        # Check cluster state consistency
        cluster_sizes = set()
        cluster_statuses = set()
        cluster_uuids = set()
        flow_control_issues = False
        
        nodes_to_check = galera_nodes if galera_nodes else request.nodes
        
        for node in nodes_to_check:
            cluster_size = metrics.get_wsrep_status_int(node, "wsrep_cluster_size", 0)
            cluster_status = metrics.get_wsrep_status(node, "wsrep_cluster_status", "")
            cluster_uuid = metrics.get_wsrep_status(node, "wsrep_cluster_state_uuid", "")
            
            if cluster_size > 0:
                cluster_sizes.add(cluster_size)
            if cluster_status:
                cluster_statuses.add(cluster_status)
            if cluster_uuid:
                cluster_uuids.add(cluster_uuid)
            
            # Check flow control
            fc = metrics.calculate_galera_flow_control_paused(node)
            if fc > 0.01:
                flow_control_issues = True
        
        # Validate consistency
        if len(cluster_sizes) > 1:
            status = Severity.CRITICAL
            topology_valid = False
            recommendations.append(
                f"Inconsistent cluster sizes detected: {cluster_sizes}. Cluster may be partitioned."
            )
        
        if len(cluster_uuids) > 1:
            status = Severity.CRITICAL
            topology_valid = False
            recommendations.append(
                f"Multiple cluster UUIDs detected. Nodes may not be in the same cluster."
            )
        
        if "Primary" not in cluster_statuses and cluster_statuses:
            status = Severity.CRITICAL
            recommendations.append("No nodes in Primary component - cluster is non-operational")
        
        # Galera-specific recommendations
        if flow_control_issues:
            recommendations.append(
                "Flow control detected - some nodes may be slower than others"
            )
        
        # Check if cluster might be oversized
        if node_count > 5:
            alternatives.append(
                "Consider if 5+ node cluster is necessary - may add replication overhead"
            )
        
        # Consider alternatives if workload is read-heavy
        actual_cluster_size = list(cluster_sizes)[0] if cluster_sizes else node_count
        
        return ArchitectureAssessment(
            topology_type=TopologyType.GALERA.value,
            topology_valid=topology_valid,
            status=status,
            summary=f"Galera cluster with {node_count} nodes",
            node_count=node_count,
            expected_node_count=None,
            ha_capable=node_count >= 2,
            quorum_capable=node_count >= 3,
            galera_cluster_size=actual_cluster_size,
            galera_cluster_status=list(cluster_statuses)[0] if cluster_statuses else None,
            galera_flow_control_issues=flow_control_issues,
            maxscale_present=request.maxscale is not None and request.maxscale.enabled,
            architecture_recommendations=recommendations,
            consider_alternatives=alternatives
        )
    
    def analyze(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Perform full analysis for Galera cluster."""
        self.findings = []
        self.recommendations = []
        
        # Analyze each node
        node_analyses = []
        for node in request.nodes:
            analysis = self.analyze_node_performance(node)
            node_analyses.append(analysis)
            self.findings.extend(analysis.findings)
        
        # Architecture analysis
        architecture = self.analyze_architecture(request)
        
        # Capacity analysis
        capacity = self.analyze_capacity(request)
        
        # Load analysis
        load = self.analyze_load(request)
        
        # Galera-specific recommendations
        if architecture.galera_flow_control_issues:
            self.add_recommendation(
                priority=2,
                category=Category.PERFORMANCE,
                title="Address flow control issues",
                description="Flow control indicates performance bottleneck",
                action="Investigate slow nodes, tune wsrep_slave_threads, check disk I/O",
                impact="Improved cluster throughput and reduced latency",
                effort="medium"
            )
        
        if not architecture.quorum_capable:
            self.add_recommendation(
                priority=1,
                category=Category.AVAILABILITY,
                title="Add nodes for quorum",
                description=f"Cluster has {architecture.node_count} nodes, need 3+ for proper quorum",
                action="Add at least one more node to achieve quorum capability",
                impact="Prevent split-brain and improve availability",
                effort="high"
            )
        
        # Check if Galera is overkill
        read_write_ratio = load.read_write_ratio
        if read_write_ratio > 20 and load.total_writes_per_second < 100:
            self.add_recommendation(
                priority=4,
                category=Category.CONFIGURATION,
                title="Consider simpler topology",
                description=f"Read/write ratio is {read_write_ratio:.1f}:1 with low write rate",
                action="Evaluate if async replication with read replicas would suffice",
                impact="Reduced complexity and potentially better read performance",
                effort="high",
                related_findings=["low_write_rate"]
            )
        
        # Generate key insights
        insights = self.generate_key_insights(request, architecture, capacity, load)
        insights["galera_required"] = load.total_writes_per_second > 100 or read_write_ratio < 10
        insights["galera_healthy"] = all(
            n.wsrep_ready and n.wsrep_cluster_status == "Primary"
            for n in node_analyses if hasattr(n, 'wsrep_ready')
        )
        insights["flow_control_issues"] = architecture.galera_flow_control_issues
        insights["quorum_capable"] = architecture.quorum_capable
        
        # Check if can downsize
        if architecture.node_count > 3 and capacity.is_oversized:
            insights["consider_downsizing"] = True
            insights["recommended_node_count"] = 3
        
        # Determine overall status
        critical_nodes = [n for n in node_analyses if n.status == Severity.CRITICAL]
        warning_nodes = [n for n in node_analyses if n.status == Severity.WARNING]
        
        if critical_nodes or architecture.status == Severity.CRITICAL or capacity.is_undersized:
            overall_status = Severity.CRITICAL
            overall_summary = "Galera cluster has critical issues requiring immediate attention"
        elif warning_nodes or architecture.status == Severity.WARNING or capacity.is_oversized:
            overall_status = Severity.WARNING
            overall_summary = "Galera cluster is functional but has issues to address"
        else:
            overall_status = Severity.INFO
            overall_summary = "Galera cluster is healthy and operating normally"
        
        return ClusterReviewResponse(
            cluster_name=request.cluster_name,
            topology_type=TopologyType.GALERA.value,
            review_timestamp=datetime.utcnow(),
            overall_status=overall_status,
            overall_summary=overall_summary,
            architecture=architecture,
            capacity=capacity,
            load_analysis=load,
            node_analyses=node_analyses,
            findings=self.findings,
            recommendations=self.recommendations,
            key_insights=insights
        )
