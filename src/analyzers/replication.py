"""
Master-Replica (async replication) analyzer.
"""

from datetime import datetime

from src.analyzers.base import BaseAnalyzer
from src.models.input import ClusterReviewRequest, TopologyType, NodeRole
from src.models.output import (
    Severity, Category, ArchitectureAssessment, NodeAnalysis, ClusterReviewResponse
)
from src.utils import metrics


class ReplicationAnalyzer(BaseAnalyzer):
    """Analyzer for master-replica async replication topology."""
    
    def analyze_node_performance(self, node) -> NodeAnalysis:
        """Extended analysis including replication status."""
        # Get base analysis
        analysis = super().analyze_node_performance(node)
        
        # Add replication-specific metrics for replicas
        if node.role == NodeRole.REPLICA and node.slave_status:
            io_running, sql_running = metrics.is_replication_running(node)
            lag = metrics.get_replication_lag(node)
            
            analysis.slave_io_running = io_running
            analysis.slave_sql_running = sql_running
            analysis.seconds_behind_master = lag
            
            # Check replication health
            if not io_running or not sql_running:
                analysis.status = Severity.CRITICAL
                analysis.findings.append(self._create_replication_stopped_finding(node, io_running, sql_running))
            elif lag is not None:
                lag_thresholds = self.thresholds.get("replication", {}).get("seconds_behind_master", {})
                if lag >= lag_thresholds.get("critical", 300):
                    analysis.status = Severity.CRITICAL
                    analysis.findings.append(self._create_lag_finding(node, lag, "critical"))
                elif lag >= lag_thresholds.get("warning", 30):
                    if analysis.status != Severity.CRITICAL:
                        analysis.status = Severity.WARNING
                    analysis.findings.append(self._create_lag_finding(node, lag, "warning"))
        
        return analysis
    
    def _create_replication_stopped_finding(self, node, io_running: bool, sql_running: bool):
        """Create finding for stopped replication."""
        from src.models.output import Finding
        issues = []
        if not io_running:
            issues.append("IO thread stopped")
        if not sql_running:
            issues.append("SQL thread stopped")
        
        return Finding(
            severity=Severity.CRITICAL,
            category=Category.REPLICATION,
            title="Replication stopped",
            description=f"Replication issues: {', '.join(issues)}",
            node=node.hostname
        )
    
    def _create_lag_finding(self, node, lag: int, level: str):
        """Create finding for replication lag."""
        from src.models.output import Finding
        return Finding(
            severity=Severity.CRITICAL if level == "critical" else Severity.WARNING,
            category=Category.REPLICATION,
            title=f"Replication lag {level}",
            description=f"Replica is {lag} seconds behind master",
            metric_name="Seconds_Behind_Master",
            metric_value=str(lag),
            node=node.hostname
        )
    
    def analyze_architecture(self, request: ClusterReviewRequest) -> ArchitectureAssessment:
        """Analyze master-replica architecture."""
        masters = [n for n in request.nodes if n.role == NodeRole.MASTER]
        replicas = [n for n in request.nodes if n.role == NodeRole.REPLICA]
        
        recommendations = []
        alternatives = []
        topology_valid = True
        status = Severity.INFO
        
        # Validate topology
        if len(masters) != 1:
            topology_valid = False
            recommendations.append(f"Expected 1 master, found {len(masters)}")
            status = Severity.CRITICAL
        
        if len(replicas) < 1:
            recommendations.append("No replicas found - no read scaling or failover capability")
            status = Severity.WARNING
        
        # Check replication health across replicas
        replication_healthy = True
        max_lag = 0
        for replica in replicas:
            if replica.slave_status:
                io_running, sql_running = metrics.is_replication_running(replica)
                if not io_running or not sql_running:
                    replication_healthy = False
                lag = metrics.get_replication_lag(replica)
                if lag is not None:
                    max_lag = max(max_lag, lag)
        
        if not replication_healthy:
            status = Severity.CRITICAL
            recommendations.append("One or more replicas have stopped replication")
        
        # HA assessment
        ha_capable = len(replicas) >= 1
        
        # Consider alternatives
        if max_lag > 30:
            alternatives.append("semi_sync - For guaranteed replication with minimal lag")
        if len(replicas) >= 2:
            alternatives.append("galera - For automatic failover without manual promotion")
        
        return ArchitectureAssessment(
            topology_type=TopologyType.MASTER_REPLICA.value,
            topology_valid=topology_valid,
            status=status,
            summary=f"Master-replica with {len(masters)} master(s) and {len(replicas)} replica(s)",
            node_count=len(request.nodes),
            expected_node_count=None,
            ha_capable=ha_capable,
            quorum_capable=False,
            replication_healthy=replication_healthy,
            replication_lag_seconds=max_lag if max_lag > 0 else None,
            maxscale_present=request.maxscale is not None and request.maxscale.enabled,
            architecture_recommendations=recommendations,
            consider_alternatives=alternatives
        )
    
    def analyze(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Perform full analysis for master-replica topology."""
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
        
        # Add recommendations based on findings
        if architecture.replication_lag_seconds and architecture.replication_lag_seconds > 30:
            self.add_recommendation(
                priority=1,
                category=Category.REPLICATION,
                title="Address replication lag",
                description=f"Replicas are {architecture.replication_lag_seconds}s behind master",
                action="Investigate slow queries on replicas, network issues, or consider semi-sync",
                impact="Reduced data loss risk and better read consistency",
                effort="medium"
            )
        
        if not architecture.replication_healthy:
            self.add_recommendation(
                priority=1,
                category=Category.REPLICATION,
                title="Fix stopped replication",
                description="One or more replicas have stopped replicating",
                action="Check SHOW SLAVE STATUS for errors and restart replication",
                impact="Restore HA capability and data consistency",
                effort="low"
            )
        
        # Generate key insights
        insights = self.generate_key_insights(request, architecture, capacity, load)
        insights["galera_required"] = False
        insights["replication_lag_seconds"] = architecture.replication_lag_seconds
        insights["replication_healthy"] = architecture.replication_healthy
        
        # Recommend semi-sync if lag is a concern
        if architecture.replication_lag_seconds and architecture.replication_lag_seconds > 10:
            insights["consider_semi_sync"] = True
        
        # Determine overall status
        critical_nodes = [n for n in node_analyses if n.status == Severity.CRITICAL]
        warning_nodes = [n for n in node_analyses if n.status == Severity.WARNING]
        
        if critical_nodes or architecture.status == Severity.CRITICAL or capacity.is_undersized:
            overall_status = Severity.CRITICAL
            overall_summary = "Master-replica cluster has critical issues"
        elif warning_nodes or architecture.status == Severity.WARNING or capacity.is_oversized:
            overall_status = Severity.WARNING
            overall_summary = "Master-replica cluster has warnings to address"
        else:
            overall_status = Severity.INFO
            overall_summary = "Master-replica cluster is healthy"
        
        return ClusterReviewResponse(
            cluster_name=request.cluster_name,
            topology_type=TopologyType.MASTER_REPLICA.value,
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
