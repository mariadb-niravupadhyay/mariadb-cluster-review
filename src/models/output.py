"""
Output models for MariaDB Cluster Review Service.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Severity(str, Enum):
    """Severity level for findings and recommendations."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Category(str, Enum):
    """Category of finding or recommendation."""
    PERFORMANCE = "performance"
    CAPACITY = "capacity"
    AVAILABILITY = "availability"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    REPLICATION = "replication"
    RESOURCE = "resource"
    STORAGE = "storage"
    GALERA = "galera"
    NETWORK = "network"
    GENERAL = "general"


class Finding(BaseModel):
    """A single finding from the analysis."""
    severity: Severity
    category: Category
    title: str
    description: str
    details: Optional[str] = Field(None, description="Additional details or evidence")
    metric_name: Optional[str] = None
    metric_value: Optional[str] = None
    threshold: Optional[str] = None
    node: Optional[str] = Field(None, description="Affected node hostname")


class Recommendation(BaseModel):
    """A recommendation based on findings."""
    priority: int = Field(..., ge=1, le=5, description="1=highest, 5=lowest")
    category: Category
    title: str
    description: str
    action: str = Field(..., description="Specific action to take")
    impact: str = Field(..., description="Expected impact of this change")
    effort: str = Field(..., description="Estimated effort (low/medium/high)")
    related_findings: list[str] = Field(default_factory=list)


class MetricAnalysis(BaseModel):
    """Analysis of a specific metric."""
    name: str
    value: float
    unit: Optional[str] = None
    status: Severity
    description: str
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None


class NodeAnalysis(BaseModel):
    """Analysis results for a single node."""
    hostname: str
    role: str
    status: Severity
    
    # Key metrics
    metrics: list[MetricAnalysis] = Field(default_factory=list)
    
    # Findings for this node
    findings: list[Finding] = Field(default_factory=list)
    
    # Summary stats
    queries_per_second: Optional[float] = None
    connections_current: Optional[int] = None
    connections_max_used: Optional[int] = None
    buffer_pool_hit_ratio: Optional[float] = None
    
    # Galera-specific
    wsrep_ready: Optional[bool] = None
    wsrep_cluster_status: Optional[str] = None
    wsrep_flow_control_paused: Optional[float] = None
    
    # Replication-specific
    seconds_behind_master: Optional[int] = None
    slave_io_running: Optional[bool] = None
    slave_sql_running: Optional[bool] = None


class CapacityAssessment(BaseModel):
    """Overall capacity assessment."""
    status: Severity
    summary: str
    
    # Resource utilization
    cpu_assessment: str
    memory_assessment: str
    disk_assessment: str
    connection_assessment: str
    
    # Sizing recommendations
    is_oversized: bool = False
    is_undersized: bool = False
    rightsizing_recommendations: list[str] = Field(default_factory=list)
    
    # Capacity headroom
    estimated_capacity_headroom_pct: Optional[float] = Field(
        None, description="Estimated % capacity remaining before issues"
    )


class ArchitectureAssessment(BaseModel):
    """Overall architecture assessment."""
    topology_type: str
    topology_valid: bool
    status: Severity
    summary: str
    
    # Topology specifics
    node_count: int
    expected_node_count: Optional[int] = None
    
    # High availability
    ha_capable: bool
    quorum_capable: bool = Field(False, description="For Galera: has 3+ nodes")
    
    # Replication health (for applicable topologies)
    replication_healthy: Optional[bool] = None
    replication_lag_seconds: Optional[int] = None
    
    # Galera-specific
    galera_cluster_size: Optional[int] = None
    galera_cluster_status: Optional[str] = None
    galera_flow_control_issues: Optional[bool] = None
    
    # MaxScale
    maxscale_present: bool = False
    maxscale_healthy: Optional[bool] = None
    
    # Architecture recommendations
    architecture_recommendations: list[str] = Field(default_factory=list)
    
    # Topology alternatives to consider
    consider_alternatives: list[str] = Field(default_factory=list)


class LoadAnalysis(BaseModel):
    """Analysis of current workload."""
    status: Severity
    summary: str
    
    # Aggregate metrics
    total_queries_per_second: float
    total_writes_per_second: float
    total_reads_per_second: float
    read_write_ratio: float
    
    # Connection metrics
    total_current_connections: int
    total_max_connections: int
    peak_connections_used: int
    
    # Performance indicators
    slow_queries_per_hour: Optional[float] = None
    avg_query_time_ms: Optional[float] = None
    
    # Assessment
    can_handle_current_load: bool
    estimated_max_load_multiplier: Optional[float] = Field(
        None, description="Estimated multiplier of current load the cluster can handle"
    )


class ClusterReviewResponse(BaseModel):
    """
    Complete response from cluster review analysis.
    """
    # Metadata
    cluster_name: str
    topology_type: str
    review_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Overall status
    overall_status: Severity
    overall_summary: str
    
    # Detailed assessments
    architecture: ArchitectureAssessment
    capacity: CapacityAssessment
    load_analysis: LoadAnalysis
    
    # Per-node analysis
    node_analyses: list[NodeAnalysis] = Field(default_factory=list)
    
    # Consolidated findings and recommendations
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    
    # Quick answers to key questions
    key_insights: dict = Field(default_factory=dict, description="Answers to common questions")

    class Config:
        json_schema_extra = {
            "example": {
                "cluster_name": "production-galera",
                "topology_type": "galera",
                "overall_status": "warning",
                "overall_summary": "Cluster is functional but has capacity concerns",
                "key_insights": {
                    "handling_current_load": True,
                    "resources_sufficient": True,
                    "is_oversized": False,
                    "galera_required": True,
                    "consider_downsizing": False
                }
            }
        }
