"""
Metric calculation utilities for MariaDB analysis.
"""

from typing import Optional
from src.models.input import NodeData


def calculate_queries_per_second(node: NodeData) -> float:
    """Calculate queries per second from status variables."""
    questions = node.get_status_int("Questions", 0)
    uptime = node.uptime_seconds or node.get_status_int("Uptime", 1)
    if uptime == 0:
        return 0.0
    return questions / uptime


def calculate_writes_per_second(node: NodeData) -> float:
    """Calculate write operations per second."""
    inserts = node.get_status_int("Com_insert", 0)
    updates = node.get_status_int("Com_update", 0)
    deletes = node.get_status_int("Com_delete", 0)
    replaces = node.get_status_int("Com_replace", 0)
    uptime = node.uptime_seconds or node.get_status_int("Uptime", 1)
    if uptime == 0:
        return 0.0
    return (inserts + updates + deletes + replaces) / uptime


def calculate_reads_per_second(node: NodeData) -> float:
    """Calculate read operations per second."""
    selects = node.get_status_int("Com_select", 0)
    uptime = node.uptime_seconds or node.get_status_int("Uptime", 1)
    if uptime == 0:
        return 0.0
    return selects / uptime


def calculate_read_write_ratio(node: NodeData) -> float:
    """Calculate read to write ratio."""
    reads = node.get_status_int("Com_select", 0)
    writes = (
        node.get_status_int("Com_insert", 0) +
        node.get_status_int("Com_update", 0) +
        node.get_status_int("Com_delete", 0) +
        node.get_status_int("Com_replace", 0)
    )
    if writes == 0:
        return float('inf') if reads > 0 else 0.0
    return reads / writes


def calculate_connection_utilization(node: NodeData) -> float:
    """Calculate connection utilization percentage."""
    max_used = node.get_status_int("Max_used_connections", 0)
    max_connections = node.get_variable_int("max_connections", 1)
    if max_connections == 0:
        return 0.0
    return max_used / max_connections


def calculate_buffer_pool_hit_ratio(node: NodeData) -> float:
    """Calculate InnoDB buffer pool hit ratio."""
    reads = node.get_status_int("Innodb_buffer_pool_reads", 0)
    read_requests = node.get_status_int("Innodb_buffer_pool_read_requests", 1)
    if read_requests == 0:
        return 1.0  # No reads means 100% hit ratio
    return 1 - (reads / read_requests)


def calculate_buffer_pool_usage(node: NodeData) -> float:
    """Calculate buffer pool usage percentage."""
    pages_data = node.get_status_int("Innodb_buffer_pool_pages_data", 0)
    pages_total = node.get_status_int("Innodb_buffer_pool_pages_total", 1)
    if pages_total == 0:
        return 0.0
    return pages_data / pages_total


def calculate_slow_queries_per_hour(node: NodeData) -> float:
    """Calculate slow queries per hour."""
    slow_queries = node.get_status_int("Slow_queries", 0)
    uptime = node.uptime_seconds or node.get_status_int("Uptime", 1)
    if uptime == 0:
        return 0.0
    hours = uptime / 3600
    if hours == 0:
        return 0.0
    return slow_queries / hours


def calculate_aborted_connections_per_hour(node: NodeData) -> float:
    """Calculate aborted connections per hour."""
    aborted = node.get_status_int("Aborted_connects", 0)
    uptime = node.uptime_seconds or node.get_status_int("Uptime", 1)
    if uptime == 0:
        return 0.0
    hours = uptime / 3600
    if hours == 0:
        return 0.0
    return aborted / hours


def get_wsrep_status(node: NodeData, key: str, default=None):
    """Get a WSREP status variable."""
    # First check wsrep_status dict if provided
    if node.wsrep_status and key in node.wsrep_status:
        return node.wsrep_status[key]
    # Fall back to global_status
    return node.get_status(key, default)


def get_wsrep_status_float(node: NodeData, key: str, default: float = 0.0) -> float:
    """Get a WSREP status variable as float."""
    val = get_wsrep_status(node, key, default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def get_wsrep_status_int(node: NodeData, key: str, default: int = 0) -> int:
    """Get a WSREP status variable as integer."""
    val = get_wsrep_status(node, key, default)
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def calculate_galera_flow_control_paused(node: NodeData) -> float:
    """Get Galera flow control paused fraction."""
    return get_wsrep_status_float(node, "wsrep_flow_control_paused", 0.0)


def calculate_galera_recv_queue_avg(node: NodeData) -> float:
    """Get Galera receive queue average."""
    return get_wsrep_status_float(node, "wsrep_local_recv_queue_avg", 0.0)


def calculate_galera_send_queue_avg(node: NodeData) -> float:
    """Get Galera send queue average."""
    return get_wsrep_status_float(node, "wsrep_local_send_queue_avg", 0.0)


def calculate_galera_cert_conflicts_per_hour(node: NodeData) -> float:
    """Calculate Galera certification conflicts per hour."""
    conflicts = get_wsrep_status_int(node, "wsrep_local_cert_failures", 0)
    uptime = node.uptime_seconds or node.get_status_int("Uptime", 1)
    if uptime == 0:
        return 0.0
    hours = uptime / 3600
    if hours == 0:
        return 0.0
    return conflicts / hours


def is_galera_node_healthy(node: NodeData) -> bool:
    """Check if a Galera node is healthy."""
    ready = get_wsrep_status(node, "wsrep_ready", "OFF")
    connected = get_wsrep_status(node, "wsrep_connected", "OFF")
    cluster_status = get_wsrep_status(node, "wsrep_cluster_status", "")
    local_state = get_wsrep_status(node, "wsrep_local_state_comment", "")
    
    return (
        str(ready).upper() == "ON" and
        str(connected).upper() == "ON" and
        cluster_status == "Primary" and
        local_state in ("Synced", "Donor/Desynced")
    )


def parse_bytes_to_gb(value) -> float:
    """Convert bytes value to GB."""
    try:
        bytes_val = int(value)
        return bytes_val / (1024 * 1024 * 1024)
    except (ValueError, TypeError):
        return 0.0


def format_bytes(bytes_val: int) -> str:
    """Format bytes to human readable string."""
    if bytes_val >= 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"
    elif bytes_val >= 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.2f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.2f} KB"
    return f"{bytes_val} bytes"


def get_replication_lag(node: NodeData) -> Optional[int]:
    """Get replication lag in seconds from slave status."""
    if not node.slave_status:
        return None
    lag = node.slave_status.get("Seconds_Behind_Master")
    if lag is None or lag == "NULL":
        return None
    try:
        return int(lag)
    except (ValueError, TypeError):
        return None


def is_replication_running(node: NodeData) -> tuple[bool, bool]:
    """Check if replication IO and SQL threads are running."""
    if not node.slave_status:
        return False, False
    
    io_running = str(node.slave_status.get("Slave_IO_Running", "No")).upper() == "YES"
    sql_running = str(node.slave_status.get("Slave_SQL_Running", "No")).upper() == "YES"
    
    return io_running, sql_running
