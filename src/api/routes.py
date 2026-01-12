"""
API routes for MariaDB Cluster Review Service.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.models.input import ClusterReviewRequest, TopologyType
from src.models.output import ClusterReviewResponse, Severity
from src.services.review_service import ReviewService

router = APIRouter()
review_service = ReviewService()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str


class TopologyDetectionRequest(BaseModel):
    """Request for topology auto-detection."""
    cluster_name: str
    nodes: list[dict]
    maxscale: Optional[dict] = None


class TopologyDetectionResponse(BaseModel):
    """Response for topology detection."""
    detected_topology: str
    confidence: str
    indicators: list[str]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="MariaDB Cluster Review Service",
        version="1.0.0"
    )


@router.post("/review", response_model=ClusterReviewResponse)
async def review_cluster(request: ClusterReviewRequest):
    """
    Perform a complete cluster architecture and capacity review.
    
    This endpoint analyzes the provided cluster data and returns:
    - Architecture assessment
    - Capacity assessment
    - Load analysis
    - Per-node analysis
    - Findings and recommendations
    - Key insights answering common questions
    """
    try:
        response = review_service.review(request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/review/auto", response_model=ClusterReviewResponse)
async def auto_review_cluster(request: ClusterReviewRequest):
    """
    Auto-detect topology type and perform review.
    
    Use this endpoint when you're not sure of the topology type.
    The service will attempt to detect it from the provided data.
    """
    try:
        response = review_service.auto_review(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/review/standalone", response_model=ClusterReviewResponse)
async def review_standalone(request: ClusterReviewRequest):
    """
    Review a standalone MariaDB node.
    
    Analyzes a single-node deployment for:
    - Performance metrics
    - Capacity utilization
    - Configuration issues
    - HA recommendations
    """
    try:
        response = review_service.review_standalone(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/review/replication", response_model=ClusterReviewResponse)
async def review_replication(request: ClusterReviewRequest):
    """
    Review a master-replica (async replication) setup.
    
    Analyzes:
    - Master and replica health
    - Replication status and lag
    - Performance metrics
    - Capacity and scaling recommendations
    """
    try:
        response = review_service.review_replication(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/review/semi-sync", response_model=ClusterReviewResponse)
async def review_semi_sync(request: ClusterReviewRequest):
    """
    Review a semi-synchronous replication setup.
    
    Analyzes:
    - Semi-sync configuration validity
    - Replication health
    - Fallback to async detection
    - Performance impact
    """
    try:
        response = review_service.review_semi_sync(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/review/galera", response_model=ClusterReviewResponse)
async def review_galera(request: ClusterReviewRequest):
    """
    Review a Galera Cluster.
    
    Analyzes:
    - Cluster health and quorum
    - Node synchronization status
    - Flow control issues
    - Certification conflicts
    - Performance metrics
    - Capacity assessment
    - Recommendations for optimization
    """
    try:
        response = review_service.review_galera(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/detect-topology", response_model=TopologyDetectionResponse)
async def detect_topology(request: ClusterReviewRequest):
    """
    Detect the topology type from the provided cluster data.
    
    Returns the detected topology and the indicators used for detection.
    """
    try:
        detected = review_service.detect_topology(request)
        
        # Determine indicators
        indicators = []
        for node in request.nodes:
            wsrep_on = node.get_variable("wsrep_on", "OFF")
            if str(wsrep_on).upper() == "ON":
                indicators.append(f"Node {node.hostname}: wsrep_on=ON")
            if node.slave_status:
                indicators.append(f"Node {node.hostname}: has slave status")
            if node.master_status:
                indicators.append(f"Node {node.hostname}: has master status")
            semi_sync = node.get_variable("rpl_semi_sync_master_enabled", "OFF")
            if str(semi_sync).upper() == "ON":
                indicators.append(f"Node {node.hostname}: semi-sync enabled")
        
        confidence = "high" if indicators else "low"
        
        return TopologyDetectionResponse(
            detected_topology=detected.value,
            confidence=confidence,
            indicators=indicators
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/topology-types")
async def list_topology_types():
    """List all supported topology types."""
    return {
        "topology_types": [
            {
                "type": TopologyType.STANDALONE.value,
                "description": "Single MariaDB node",
                "ha_capable": False,
                "multi_master": False
            },
            {
                "type": TopologyType.MASTER_REPLICA.value,
                "description": "Async replication with master and replica(s)",
                "ha_capable": True,
                "multi_master": False
            },
            {
                "type": TopologyType.SEMI_SYNC.value,
                "description": "Semi-synchronous replication",
                "ha_capable": True,
                "multi_master": False
            },
            {
                "type": TopologyType.GALERA.value,
                "description": "Galera Cluster - synchronous multi-master",
                "ha_capable": True,
                "multi_master": True
            }
        ]
    }


@router.post("/compare-topologies")
async def compare_topologies(request: ClusterReviewRequest):
    """
    Compare topology options (Galera vs Semi-Sync vs Async) for the workload.
    
    Returns analysis of whether current topology is optimal and
    recommendations for alternatives if applicable.
    """
    from src.analyzers.config_analyzer import TopologyComparisonAnalyzer
    try:
        analyzer = TopologyComparisonAnalyzer()
        result = analyzer.analyze(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@router.post("/analyze-sizing")
async def analyze_sizing(request: ClusterReviewRequest):
    """
    Analyze cluster sizing and provide rightsizing recommendations.
    
    Returns current resource utilization and cost optimization options.
    """
    from src.analyzers.config_analyzer import SizingAnalyzer
    try:
        analyzer = SizingAnalyzer()
        result = analyzer.analyze(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sizing analysis failed: {str(e)}")


@router.post("/analyze-config")
async def analyze_config(request: ClusterReviewRequest):
    """
    Analyze MariaDB/Galera configuration settings.
    
    Reviews innodb settings, Galera configuration, gcache settings,
    and provides recommendations for optimization.
    """
    from src.analyzers.config_analyzer import ConfigAnalyzer
    try:
        analyzer = ConfigAnalyzer()
        result = analyzer.analyze(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config analysis failed: {str(e)}")


@router.post("/analyze-logs")
async def analyze_logs(
    mariadb_logs: dict[str, str] = None,
    maxscale_logs: dict[str, str] = None,
    slow_query_logs: dict[str, str] = None
):
    """
    Analyze MariaDB, MaxScale, and slow query logs.
    
    Detects:
    - Disk/table full errors
    - Galera inconsistency events
    - SST/IST events
    - Flow control issues
    - Connection errors
    - Server state changes
    - Slow queries
    
    Request body should contain:
    - mariadb_logs: Map of node name to MariaDB error log content
    - maxscale_logs: Map of node name to MaxScale log content
    - slow_query_logs: Map of node name to slow query log content
    """
    from src.analyzers.log_analyzer import CombinedLogAnalyzer, LogAnalysisInput
    try:
        analyzer = CombinedLogAnalyzer()
        logs = LogAnalysisInput(
            mariadb_logs=mariadb_logs,
            maxscale_logs=maxscale_logs,
            slow_query_logs=slow_query_logs
        )
        result = analyzer.analyze(logs)
        
        # Convert findings to dict for JSON serialization
        result["combined_findings"] = [f.model_dump() for f in result["combined_findings"]]
        result["combined_recommendations"] = [r.model_dump() for r in result["combined_recommendations"]]
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}")


@router.post("/analyze-logs-from-request")
async def analyze_logs_from_request(request: ClusterReviewRequest):
    """
    Analyze logs included in the cluster review request.
    
    Extracts error_log and slow_query_log from each node,
    and maxscale logs if provided, then performs analysis.
    """
    from src.analyzers.log_analyzer import CombinedLogAnalyzer, LogAnalysisInput
    try:
        # Extract logs from nodes
        mariadb_logs = {}
        slow_query_logs = {}
        
        for node in request.nodes:
            if node.error_log:
                mariadb_logs[node.hostname] = node.error_log
            if node.slow_query_log:
                slow_query_logs[node.hostname] = node.slow_query_log
        
        # Extract MaxScale logs
        maxscale_logs = None
        if request.maxscale and request.maxscale.logs:
            maxscale_logs = request.maxscale.logs
        
        analyzer = CombinedLogAnalyzer()
        logs = LogAnalysisInput(
            mariadb_logs=mariadb_logs if mariadb_logs else None,
            maxscale_logs=maxscale_logs,
            slow_query_logs=slow_query_logs if slow_query_logs else None
        )
        result = analyzer.analyze(logs)
        
        # Convert findings to dict for JSON serialization
        result["combined_findings"] = [f.model_dump() for f in result["combined_findings"]]
        result["combined_recommendations"] = [r.model_dump() for r in result["combined_recommendations"]]
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}")


@router.get("/metrics-reference")
async def metrics_reference():
    """Get reference information about analyzed metrics."""
    return {
        "server_metrics": [
            {
                "name": "queries_per_second",
                "description": "Total queries executed per second",
                "source": "SHOW GLOBAL STATUS LIKE 'Questions'"
            },
            {
                "name": "connection_utilization",
                "description": "Peak connections used vs max_connections",
                "source": "Max_used_connections / max_connections"
            },
            {
                "name": "buffer_pool_hit_ratio",
                "description": "InnoDB buffer pool cache hit percentage",
                "source": "1 - (Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests)"
            },
            {
                "name": "buffer_pool_usage",
                "description": "Buffer pool pages in use percentage",
                "source": "Innodb_buffer_pool_pages_data / Innodb_buffer_pool_pages_total"
            },
            {
                "name": "slow_queries_per_hour",
                "description": "Rate of slow queries",
                "source": "Slow_queries / (Uptime / 3600)"
            }
        ],
        "galera_metrics": [
            {
                "name": "wsrep_cluster_status",
                "description": "Cluster component status (should be 'Primary')",
                "healthy_value": "Primary"
            },
            {
                "name": "wsrep_ready",
                "description": "Node ready to accept queries",
                "healthy_value": "ON"
            },
            {
                "name": "wsrep_flow_control_paused",
                "description": "Fraction of time paused for flow control",
                "healthy_value": "< 0.01"
            },
            {
                "name": "wsrep_local_recv_queue_avg",
                "description": "Average receive queue size",
                "healthy_value": "< 0.5"
            },
            {
                "name": "wsrep_local_send_queue_avg",
                "description": "Average send queue size",
                "healthy_value": "< 0.5"
            },
            {
                "name": "wsrep_cert_deps_distance",
                "description": "Potential for parallel transaction apply",
                "note": "Use to tune wsrep_slave_threads"
            }
        ],
        "replication_metrics": [
            {
                "name": "Seconds_Behind_Master",
                "description": "Replication lag in seconds",
                "healthy_value": "< 30"
            },
            {
                "name": "Slave_IO_Running",
                "description": "IO thread status",
                "healthy_value": "Yes"
            },
            {
                "name": "Slave_SQL_Running",
                "description": "SQL thread status",
                "healthy_value": "Yes"
            }
        ]
    }
