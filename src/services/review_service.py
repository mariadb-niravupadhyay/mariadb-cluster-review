"""
Review service - main business logic for cluster review.
"""

from src.models.input import ClusterReviewRequest, TopologyType
from src.models.output import ClusterReviewResponse, Severity
from src.analyzers.standalone import StandaloneAnalyzer
from src.analyzers.replication import ReplicationAnalyzer
from src.analyzers.semi_sync import SemiSyncAnalyzer
from src.analyzers.galera import GaleraAnalyzer
from src.analyzers.maxscale import MaxScaleAnalyzer
from src.analyzers.config_analyzer import ConfigAnalyzer, TopologyComparisonAnalyzer, SizingAnalyzer


class ReviewService:
    """
    Main service for performing cluster architecture and capacity reviews.
    """
    
    def __init__(self):
        self.analyzers = {
            TopologyType.STANDALONE: StandaloneAnalyzer(),
            TopologyType.MASTER_REPLICA: ReplicationAnalyzer(),
            TopologyType.SEMI_SYNC: SemiSyncAnalyzer(),
            TopologyType.GALERA: GaleraAnalyzer(),
        }
        self.maxscale_analyzer = MaxScaleAnalyzer()
        self.config_analyzer = ConfigAnalyzer()
        self.topology_comparison = TopologyComparisonAnalyzer()
        self.sizing_analyzer = SizingAnalyzer()
    
    def review(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """
        Perform a complete cluster review.
        
        Args:
            request: The cluster review request with all node data
            
        Returns:
            Complete review response with findings and recommendations
        """
        # Get appropriate analyzer for topology
        analyzer = self.analyzers.get(request.topology_type)
        
        if not analyzer:
            raise ValueError(f"Unsupported topology type: {request.topology_type}")
        
        # Perform main analysis
        response = analyzer.analyze(request)
        
        # Add MaxScale analysis if present
        if request.maxscale and request.maxscale.enabled:
            maxscale_result = self.maxscale_analyzer.analyze(request.maxscale, request)
            
            # Merge MaxScale findings
            response.findings.extend(maxscale_result["findings"])
            response.recommendations.extend(maxscale_result["recommendations"])
            
            # Update key insights
            response.key_insights["maxscale_healthy"] = maxscale_result["healthy"]
            
            # Potentially update overall status
            if maxscale_result["status"] == Severity.CRITICAL:
                if response.overall_status != Severity.CRITICAL:
                    response.overall_status = Severity.CRITICAL
                    response.overall_summary += " (MaxScale issues detected)"
        
        # Add configuration analysis
        config_result = self.config_analyzer.analyze(request)
        response.findings.extend(config_result["findings"])
        response.recommendations.extend(config_result["recommendations"])
        
        # Add topology comparison analysis
        topology_result = self.topology_comparison.analyze(request)
        response.key_insights["topology_comparison"] = topology_result["topology_comparison"]
        response.key_insights["workload_characteristics"] = topology_result["workload_characteristics"]
        response.key_insights["topology_recommendation"] = topology_result["recommendation"]
        response.key_insights["semi_sync_suitable"] = topology_result["semi_sync_suitable"]
        
        # Add sizing analysis
        sizing_result = self.sizing_analyzer.analyze(request)
        response.key_insights["current_sizing"] = sizing_result["current_sizing"]
        response.key_insights["utilization"] = sizing_result["utilization"]
        response.key_insights["rightsizing_options"] = sizing_result["rightsizing_options"]
        response.key_insights["cost_impact"] = sizing_result["cost_impact"]
        
        # Sort recommendations by priority
        response.recommendations.sort(key=lambda r: r.priority)
        
        # Add summary key insights
        response.key_insights["total_findings"] = len(response.findings)
        response.key_insights["critical_findings"] = len([
            f for f in response.findings if f.severity == Severity.CRITICAL
        ])
        response.key_insights["total_recommendations"] = len(response.recommendations)
        
        return response
    
    def review_standalone(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Review a standalone node."""
        request.topology_type = TopologyType.STANDALONE
        return self.review(request)
    
    def review_replication(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Review a master-replica setup."""
        request.topology_type = TopologyType.MASTER_REPLICA
        return self.review(request)
    
    def review_semi_sync(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Review a semi-sync replication setup."""
        request.topology_type = TopologyType.SEMI_SYNC
        return self.review(request)
    
    def review_galera(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Review a Galera cluster."""
        request.topology_type = TopologyType.GALERA
        return self.review(request)
    
    def detect_topology(self, request: ClusterReviewRequest) -> TopologyType:
        """
        Attempt to auto-detect the topology type from the provided data.
        
        Returns:
            Detected TopologyType
        """
        # Check for Galera indicators
        for node in request.nodes:
            wsrep_on = node.get_variable("wsrep_on", "OFF")
            if str(wsrep_on).upper() == "ON":
                return TopologyType.GALERA
            
            # Check for wsrep status variables
            if node.get_status("wsrep_cluster_size"):
                return TopologyType.GALERA
        
        # Check for replication
        has_master = False
        has_replica = False
        has_semi_sync = False
        
        for node in request.nodes:
            # Check for master status
            if node.master_status:
                has_master = True
            
            # Check for slave status
            if node.slave_status:
                has_replica = True
            
            # Check for semi-sync
            semi_sync_master = node.get_variable("rpl_semi_sync_master_enabled", "OFF")
            semi_sync_slave = node.get_variable("rpl_semi_sync_slave_enabled", "OFF")
            if str(semi_sync_master).upper() == "ON" or str(semi_sync_slave).upper() == "ON":
                has_semi_sync = True
        
        if has_replica:
            if has_semi_sync:
                return TopologyType.SEMI_SYNC
            return TopologyType.MASTER_REPLICA
        
        return TopologyType.STANDALONE
    
    def auto_review(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """
        Auto-detect topology and perform review.
        """
        detected_topology = self.detect_topology(request)
        request.topology_type = detected_topology
        
        response = self.review(request)
        response.key_insights["topology_auto_detected"] = True
        response.key_insights["detected_topology"] = detected_topology.value
        
        return response
