"""
Standalone MariaDB node analyzer.
"""

from datetime import datetime

from src.analyzers.base import BaseAnalyzer
from src.models.input import ClusterReviewRequest, TopologyType
from src.models.output import (
    Severity, Category, ArchitectureAssessment, ClusterReviewResponse
)


class StandaloneAnalyzer(BaseAnalyzer):
    """Analyzer for standalone MariaDB nodes."""
    
    def analyze_architecture(self, request: ClusterReviewRequest) -> ArchitectureAssessment:
        """Analyze standalone architecture."""
        node_count = len(request.nodes)
        topology_valid = node_count == 1
        
        recommendations = []
        alternatives = []
        
        if not topology_valid:
            recommendations.append(
                f"Standalone topology expects 1 node, but {node_count} were provided"
            )
        
        # Standalone has no HA
        recommendations.append(
            "Standalone node has no high availability. Consider adding replicas for redundancy."
        )
        alternatives.append("master_replica - Add replica(s) for read scaling and failover capability")
        alternatives.append("galera - For automatic failover and multi-master writes")
        
        return ArchitectureAssessment(
            topology_type=TopologyType.STANDALONE.value,
            topology_valid=topology_valid,
            status=Severity.WARNING if not topology_valid else Severity.INFO,
            summary="Standalone node - no high availability",
            node_count=node_count,
            expected_node_count=1,
            ha_capable=False,
            quorum_capable=False,
            maxscale_present=request.maxscale is not None and request.maxscale.enabled,
            architecture_recommendations=recommendations,
            consider_alternatives=alternatives
        )
    
    def analyze(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Perform full analysis for standalone node."""
        # Reset findings and recommendations
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
        
        # Add architecture-related finding
        self.add_finding(
            severity=Severity.WARNING,
            category=Category.AVAILABILITY,
            title="No high availability",
            description="Standalone node has single point of failure",
            node=request.nodes[0].hostname if request.nodes else None
        )
        
        # Add recommendation for HA
        self.add_recommendation(
            priority=2,
            category=Category.AVAILABILITY,
            title="Consider adding high availability",
            description="Standalone node lacks redundancy",
            action="Add at least one replica for failover capability",
            impact="Improved availability and disaster recovery",
            effort="medium"
        )
        
        # Generate key insights
        insights = self.generate_key_insights(request, architecture, capacity, load)
        insights["galera_required"] = False
        insights["semi_sync_sufficient"] = True
        
        # Determine overall status
        if capacity.is_undersized or any(n.status == Severity.CRITICAL for n in node_analyses):
            overall_status = Severity.CRITICAL
            overall_summary = "Standalone node has critical issues requiring attention"
        elif capacity.is_oversized or any(n.status == Severity.WARNING for n in node_analyses):
            overall_status = Severity.WARNING
            overall_summary = "Standalone node is functional but has optimization opportunities"
        else:
            overall_status = Severity.INFO
            overall_summary = "Standalone node is operating normally"
        
        return ClusterReviewResponse(
            cluster_name=request.cluster_name,
            topology_type=TopologyType.STANDALONE.value,
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
