"""
Semi-synchronous replication analyzer.
"""

from datetime import datetime

from src.analyzers.replication import ReplicationAnalyzer
from src.models.input import ClusterReviewRequest, TopologyType, NodeRole
from src.models.output import (
    Severity, Category, ArchitectureAssessment, ClusterReviewResponse
)
from src.utils import metrics


class SemiSyncAnalyzer(ReplicationAnalyzer):
    """
    Analyzer for semi-synchronous replication topology.
    Extends ReplicationAnalyzer with semi-sync specific checks.
    """
    
    def analyze_architecture(self, request: ClusterReviewRequest) -> ArchitectureAssessment:
        """Analyze semi-sync architecture."""
        # Get base replication analysis
        base_arch = super().analyze_architecture(request)
        
        masters = [n for n in request.nodes if n.role == NodeRole.MASTER]
        replicas = [n for n in request.nodes if n.role == NodeRole.REPLICA]
        
        recommendations = list(base_arch.architecture_recommendations)
        alternatives = []
        status = base_arch.status
        
        # Check semi-sync specific settings
        semi_sync_enabled = False
        semi_sync_healthy = True
        
        for master in masters:
            # Check if semi-sync is enabled on master
            semi_sync_master = master.get_variable("rpl_semi_sync_master_enabled", "OFF")
            if str(semi_sync_master).upper() in ("ON", "1", "TRUE"):
                semi_sync_enabled = True
                
                # Check semi-sync status
                semi_sync_status = master.get_status("Rpl_semi_sync_master_status", "OFF")
                if str(semi_sync_status).upper() != "ON":
                    semi_sync_healthy = False
                    recommendations.append("Semi-sync master status is OFF - may have fallen back to async")
                
                # Check wait timeout
                wait_timeout = master.get_variable_int("rpl_semi_sync_master_timeout", 10000)
                if wait_timeout < 1000:
                    recommendations.append(
                        f"Semi-sync timeout is low ({wait_timeout}ms) - may cause frequent async fallback"
                    )
                
                # Check semi-sync clients
                semi_sync_clients = master.get_status_int("Rpl_semi_sync_master_clients", 0)
                if semi_sync_clients < len(replicas):
                    recommendations.append(
                        f"Only {semi_sync_clients} of {len(replicas)} replicas connected with semi-sync"
                    )
        
        if not semi_sync_enabled:
            status = Severity.WARNING
            recommendations.append("Semi-sync does not appear to be enabled on master")
        
        # Check replicas for semi-sync
        for replica in replicas:
            semi_sync_replica = replica.get_variable("rpl_semi_sync_slave_enabled", "OFF")
            if str(semi_sync_replica).upper() not in ("ON", "1", "TRUE"):
                recommendations.append(f"Replica {replica.hostname} does not have semi-sync enabled")
        
        # Consider Galera as alternative if high write consistency is needed
        if len(replicas) >= 2:
            alternatives.append("galera - For fully synchronous replication and automatic failover")
        
        return ArchitectureAssessment(
            topology_type=TopologyType.SEMI_SYNC.value,
            topology_valid=base_arch.topology_valid and semi_sync_enabled,
            status=status,
            summary=f"Semi-sync replication with {len(masters)} master(s) and {len(replicas)} replica(s)",
            node_count=len(request.nodes),
            expected_node_count=None,
            ha_capable=len(replicas) >= 1 and semi_sync_healthy,
            quorum_capable=False,
            replication_healthy=base_arch.replication_healthy and semi_sync_healthy,
            replication_lag_seconds=base_arch.replication_lag_seconds,
            maxscale_present=request.maxscale is not None and request.maxscale.enabled,
            architecture_recommendations=recommendations,
            consider_alternatives=alternatives
        )
    
    def analyze(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Perform full analysis for semi-sync topology."""
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
        
        # Semi-sync specific recommendations
        if not architecture.topology_valid:
            self.add_recommendation(
                priority=1,
                category=Category.REPLICATION,
                title="Enable semi-synchronous replication",
                description="Semi-sync configuration appears incomplete",
                action="Enable rpl_semi_sync_master_enabled on master and rpl_semi_sync_slave_enabled on replicas",
                impact="Guaranteed replication before commit acknowledgment",
                effort="low"
            )
        
        # Check if Galera might be more appropriate
        masters = [n for n in request.nodes if n.role == NodeRole.MASTER]
        if masters:
            master = masters[0]
            write_rate = metrics.calculate_writes_per_second(master)
            if write_rate > 1000:
                self.add_recommendation(
                    priority=3,
                    category=Category.AVAILABILITY,
                    title="Consider Galera for high write workloads",
                    description=f"High write rate ({write_rate:.1f}/sec) may benefit from Galera's parallel apply",
                    action="Evaluate Galera cluster for multi-master capability",
                    impact="Better write distribution and automatic failover",
                    effort="high"
                )
        
        # Generate key insights
        insights = self.generate_key_insights(request, architecture, capacity, load)
        insights["semi_sync_enabled"] = architecture.topology_valid
        insights["galera_required"] = False
        insights["consider_galera"] = load.total_writes_per_second > 500
        
        # Determine overall status
        critical_nodes = [n for n in node_analyses if n.status == Severity.CRITICAL]
        warning_nodes = [n for n in node_analyses if n.status == Severity.WARNING]
        
        if critical_nodes or architecture.status == Severity.CRITICAL or capacity.is_undersized:
            overall_status = Severity.CRITICAL
            overall_summary = "Semi-sync cluster has critical issues"
        elif warning_nodes or architecture.status == Severity.WARNING or capacity.is_oversized:
            overall_status = Severity.WARNING
            overall_summary = "Semi-sync cluster has warnings to address"
        else:
            overall_status = Severity.INFO
            overall_summary = "Semi-sync cluster is healthy"
        
        return ClusterReviewResponse(
            cluster_name=request.cluster_name,
            topology_type=TopologyType.SEMI_SYNC.value,
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
