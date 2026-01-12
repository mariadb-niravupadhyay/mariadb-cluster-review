"""
Input models for MariaDB Cluster Review Service.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TopologyType(str, Enum):
    """Supported MariaDB topology types."""
    STANDALONE = "standalone"
    MASTER_REPLICA = "master_replica"
    SEMI_SYNC = "semi_sync"
    GALERA = "galera"


class NodeRole(str, Enum):
    """Role of a node in the topology."""
    STANDALONE = "standalone"
    MASTER = "master"
    REPLICA = "replica"
    GALERA_NODE = "galera_node"


class SystemResources(BaseModel):
    """System resource information for a node."""
    cpu_cores: int = Field(..., description="Number of CPU cores", ge=1)
    ram_gb: float = Field(..., description="RAM in GB", gt=0)
    disk_total_gb: float = Field(..., description="Total disk space in GB", gt=0)
    disk_used_gb: Optional[float] = Field(None, description="Used disk space in GB")
    disk_mount_point: str = Field("/data01", description="Primary data mount point")
    
    # Optional detailed metrics
    cpu_utilization_pct: Optional[float] = Field(None, description="Current CPU %", ge=0, le=100)
    ram_utilization_pct: Optional[float] = Field(None, description="Current RAM %", ge=0, le=100)
    iops_read: Optional[float] = Field(None, description="Read IOPS")
    iops_write: Optional[float] = Field(None, description="Write IOPS")


class NodeData(BaseModel):
    """Data collected from a single MariaDB node."""
    hostname: str = Field(..., description="Node hostname or identifier")
    role: NodeRole = Field(..., description="Role of this node")
    
    # MariaDB version info
    version: Optional[str] = Field(None, description="MariaDB version string")
    
    # Status and variables as dictionaries
    global_status: dict = Field(default_factory=dict, description="Output of SHOW GLOBAL STATUS")
    global_variables: dict = Field(default_factory=dict, description="Output of SHOW GLOBAL VARIABLES")
    
    # Replication status (for master-replica setups)
    slave_status: Optional[dict] = Field(None, description="Output of SHOW SLAVE STATUS")
    master_status: Optional[dict] = Field(None, description="Output of SHOW MASTER STATUS")
    
    # Galera-specific (extracted from global_status but can be provided separately)
    wsrep_status: Optional[dict] = Field(None, description="WSREP status variables")
    
    # System resources
    system_resources: Optional[SystemResources] = Field(None, description="OS-level resource info")
    
    # Uptime for rate calculations
    uptime_seconds: Optional[int] = Field(None, description="Server uptime in seconds")
    
    # Log content for analysis
    error_log: Optional[str] = Field(None, description="MariaDB error log content")
    slow_query_log: Optional[str] = Field(None, description="Slow query log content")

    def get_status(self, key: str, default=None):
        """Get a status variable value."""
        return self.global_status.get(key, default)
    
    def get_status_int(self, key: str, default: int = 0) -> int:
        """Get a status variable as integer."""
        try:
            return int(self.global_status.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def get_status_float(self, key: str, default: float = 0.0) -> float:
        """Get a status variable as float."""
        try:
            return float(self.global_status.get(key, default))
        except (ValueError, TypeError):
            return default
    
    def get_variable(self, key: str, default=None):
        """Get a system variable value."""
        return self.global_variables.get(key, default)
    
    def get_variable_int(self, key: str, default: int = 0) -> int:
        """Get a system variable as integer."""
        try:
            val = self.global_variables.get(key, default)
            # Handle values like "128M" or "1G"
            if isinstance(val, str):
                val = val.upper().strip()
                if val.endswith('G'):
                    return int(float(val[:-1]) * 1024 * 1024 * 1024)
                elif val.endswith('M'):
                    return int(float(val[:-1]) * 1024 * 1024)
                elif val.endswith('K'):
                    return int(float(val[:-1]) * 1024)
            return int(val)
        except (ValueError, TypeError):
            return default


class MaxScaleServer(BaseModel):
    """MaxScale server configuration and statistics."""
    name: str
    address: str
    port: int = 3306
    state: Optional[str] = None
    
    # Connection statistics
    connections: Optional[int] = Field(None, description="Current connections to this server")
    total_connections: Optional[int] = Field(None, description="Total connections since MaxScale start")
    
    # Query statistics
    queries: Optional[int] = Field(None, description="Total queries routed to this server")
    read_queries: Optional[int] = Field(None, description="Read queries to this server")
    write_queries: Optional[int] = Field(None, description="Write queries to this server")


class MaxScaleService(BaseModel):
    """MaxScale service configuration and statistics."""
    name: str
    router: str = Field(..., description="Router type (readwritesplit, readconnroute, etc.)")
    servers: list[str] = Field(default_factory=list)
    
    # Connection statistics
    connections: Optional[int] = Field(None, description="Current client connections")
    total_connections: Optional[int] = Field(None, description="Total client connections since start")
    
    # Router statistics (readwritesplit)
    route_master: Optional[int] = Field(None, description="Queries routed to master")
    route_slave: Optional[int] = Field(None, description="Queries routed to slaves")
    route_all: Optional[int] = Field(None, description="Queries routed to all servers")
    
    # Transaction statistics
    rw_transactions: Optional[int] = Field(None, description="Read-write transactions")
    ro_transactions: Optional[int] = Field(None, description="Read-only transactions")
    replayed_transactions: Optional[int] = Field(None, description="Transactions replayed after failover")
    
    # Router-specific settings
    master_accept_reads: Optional[bool] = None
    transaction_replay: Optional[bool] = None
    slave_selection_criteria: Optional[str] = None


class MaxScaleConfig(BaseModel):
    """MaxScale configuration and status."""
    enabled: bool = True
    version: Optional[str] = Field(None, description="MaxScale version")
    
    # Server definitions
    servers: list[MaxScaleServer] = Field(default_factory=list)
    
    # Service definitions
    services: list[MaxScaleService] = Field(default_factory=list)
    
    # Global MaxScale statistics
    uptime_seconds: Optional[int] = Field(None, description="MaxScale uptime in seconds")
    total_connections: Optional[int] = Field(None, description="Total connections handled")
    current_connections: Optional[int] = Field(None, description="Current active connections")
    
    # Raw configuration (optional)
    raw_config: Optional[dict] = Field(None, description="Raw maxscale.cnf parsed content")
    
    # MaxScale resource usage
    system_resources: Optional[SystemResources] = None
    
    # MaxScale logs (map of node name to log content)
    logs: Optional[dict[str, str]] = Field(None, description="MaxScale log content per node")


class ClusterReviewRequest(BaseModel):
    """
    Complete request for cluster architecture and capacity review.
    """
    # Basic info
    cluster_name: str = Field(..., description="Name/identifier for this cluster")
    topology_type: TopologyType = Field(..., description="Type of topology")
    
    # Node data
    nodes: list[NodeData] = Field(..., min_length=1, description="Data from each node")
    
    # MaxScale (optional)
    maxscale: Optional[MaxScaleConfig] = Field(None, description="MaxScale configuration if present")
    
    # Context
    description: Optional[str] = Field(None, description="Additional context about the deployment")
    
    # Expected workload (optional, for capacity planning)
    expected_queries_per_second: Optional[float] = None
    expected_connections: Optional[int] = None
    expected_write_percentage: Optional[float] = Field(None, ge=0, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "cluster_name": "production-galera",
                "topology_type": "galera",
                "nodes": [
                    {
                        "hostname": "node1",
                        "role": "galera_node",
                        "global_status": {
                            "Questions": "1000000",
                            "Uptime": "86400",
                            "Threads_connected": "50",
                            "wsrep_cluster_size": "3",
                            "wsrep_cluster_status": "Primary",
                            "wsrep_ready": "ON",
                            "wsrep_flow_control_paused": "0.001"
                        },
                        "global_variables": {
                            "max_connections": "500",
                            "innodb_buffer_pool_size": "17179869184"
                        },
                        "system_resources": {
                            "cpu_cores": 8,
                            "ram_gb": 32,
                            "disk_total_gb": 500,
                            "disk_used_gb": 250
                        }
                    }
                ]
            }
        }
