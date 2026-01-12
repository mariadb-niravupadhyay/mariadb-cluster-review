"""
Base analyzer class with common analysis methods.
"""

from abc import ABC, abstractmethod
from typing import Optional
import yaml
from pathlib import Path

from src.models.input import NodeData, ClusterReviewRequest
from src.models.output import (
    Severity, Category, Finding, Recommendation, MetricAnalysis,
    NodeAnalysis, CapacityAssessment, ArchitectureAssessment,
    LoadAnalysis, ClusterReviewResponse
)
from src.utils import metrics


class BaseAnalyzer(ABC):
    """Base class for all topology analyzers."""
    
    def __init__(self):
        self.thresholds = self._load_thresholds()
        self.findings: list[Finding] = []
        self.recommendations: list[Recommendation] = []
    
    def _load_thresholds(self) -> dict:
        """Load thresholds from configuration file."""
        config_path = Path(__file__).parent.parent.parent / "config" / "thresholds.yaml"
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception:
            # Return defaults if file not found
            return self._default_thresholds()
    
    def _default_thresholds(self) -> dict:
        """Default thresholds if config file is missing."""
        return {
            "server": {
                "connection_utilization": {"warning": 0.7, "critical": 0.9, "underutilized": 0.3},
                "buffer_pool_hit_ratio": {"warning": 0.95, "critical": 0.90},
                "buffer_pool_usage": {"underutilized": 0.5},
                "slow_queries_per_hour": {"warning": 100, "critical": 500}
            },
            "galera": {
                "flow_control_paused": {"warning": 0.01, "critical": 0.2},
                "local_recv_queue_avg": {"warning": 0.5, "critical": 1.0},
                "local_send_queue_avg": {"warning": 0.5, "critical": 1.0}
            },
            "replication": {
                "seconds_behind_master": {"warning": 30, "critical": 300}
            },
            "resources": {
                "cpu": {"underutilized": 0.3, "warning": 0.8, "critical": 0.95},
                "memory": {"underutilized": 0.5, "warning": 0.9, "critical": 0.95},
                "disk": {"warning": 0.8, "critical": 0.9}
            }
        }
    
    def add_finding(
        self,
        severity: Severity,
        category: Category,
        title: str,
        description: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[str] = None,
        threshold: Optional[str] = None,
        node: Optional[str] = None
    ):
        """Add a finding to the list."""
        self.findings.append(Finding(
            severity=severity,
            category=category,
            title=title,
            description=description,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            node=node
        ))
    
    def add_recommendation(
        self,
        priority: int,
        category: Category,
        title: str,
        description: str,
        action: str,
        impact: str,
        effort: str = "medium",
        related_findings: list[str] = None
    ):
        """Add a recommendation to the list."""
        self.recommendations.append(Recommendation(
            priority=priority,
            category=category,
            title=title,
            description=description,
            action=action,
            impact=impact,
            effort=effort,
            related_findings=related_findings or []
        ))
    
    def analyze_node_performance(self, node: NodeData) -> NodeAnalysis:
        """Analyze performance metrics for a single node."""
        node_metrics: list[MetricAnalysis] = []
        node_findings: list[Finding] = []
        overall_status = Severity.INFO
        
        # Queries per second
        qps = metrics.calculate_queries_per_second(node)
        node_metrics.append(MetricAnalysis(
            name="queries_per_second",
            value=qps,
            unit="qps",
            status=Severity.INFO,
            description=f"Current query rate: {qps:.2f} queries/second"
        ))
        
        # Connection utilization
        conn_util = metrics.calculate_connection_utilization(node)
        conn_thresholds = self.thresholds.get("server", {}).get("connection_utilization", {})
        conn_status = Severity.INFO
        if conn_util >= conn_thresholds.get("critical", 0.9):
            conn_status = Severity.CRITICAL
            overall_status = Severity.CRITICAL
            node_findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.CAPACITY,
                title="Connection utilization critical",
                description=f"Connection utilization at {conn_util*100:.1f}%",
                metric_name="connection_utilization",
                metric_value=f"{conn_util*100:.1f}%",
                threshold=f"{conn_thresholds.get('critical', 0.9)*100}%",
                node=node.hostname
            ))
        elif conn_util >= conn_thresholds.get("warning", 0.7):
            conn_status = Severity.WARNING
            if overall_status != Severity.CRITICAL:
                overall_status = Severity.WARNING
        
        node_metrics.append(MetricAnalysis(
            name="connection_utilization",
            value=conn_util * 100,
            unit="%",
            status=conn_status,
            description=f"Max used connections: {node.get_status_int('Max_used_connections')} of {node.get_variable_int('max_connections')}",
            threshold_warning=conn_thresholds.get("warning", 0.7) * 100,
            threshold_critical=conn_thresholds.get("critical", 0.9) * 100
        ))
        
        # Buffer pool hit ratio
        hit_ratio = metrics.calculate_buffer_pool_hit_ratio(node)
        bp_thresholds = self.thresholds.get("server", {}).get("buffer_pool_hit_ratio", {})
        bp_status = Severity.INFO
        if hit_ratio < bp_thresholds.get("critical", 0.90):
            bp_status = Severity.CRITICAL
            overall_status = Severity.CRITICAL
            node_findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.PERFORMANCE,
                title="Buffer pool hit ratio critical",
                description=f"Buffer pool hit ratio at {hit_ratio*100:.2f}% - too many disk reads",
                metric_name="buffer_pool_hit_ratio",
                metric_value=f"{hit_ratio*100:.2f}%",
                threshold=f"{bp_thresholds.get('critical', 0.90)*100}%",
                node=node.hostname
            ))
        elif hit_ratio < bp_thresholds.get("warning", 0.95):
            bp_status = Severity.WARNING
            if overall_status != Severity.CRITICAL:
                overall_status = Severity.WARNING
        
        node_metrics.append(MetricAnalysis(
            name="buffer_pool_hit_ratio",
            value=hit_ratio * 100,
            unit="%",
            status=bp_status,
            description=f"Buffer pool efficiency: {hit_ratio*100:.2f}%",
            threshold_warning=bp_thresholds.get("warning", 0.95) * 100,
            threshold_critical=bp_thresholds.get("critical", 0.90) * 100
        ))
        
        # Buffer pool usage
        bp_usage = metrics.calculate_buffer_pool_usage(node)
        node_metrics.append(MetricAnalysis(
            name="buffer_pool_usage",
            value=bp_usage * 100,
            unit="%",
            status=Severity.INFO,
            description=f"Buffer pool pages in use: {bp_usage*100:.1f}%"
        ))
        
        # Slow queries
        slow_per_hour = metrics.calculate_slow_queries_per_hour(node)
        slow_thresholds = self.thresholds.get("server", {}).get("slow_queries_per_hour", {})
        slow_status = Severity.INFO
        if slow_per_hour >= slow_thresholds.get("critical", 500):
            slow_status = Severity.CRITICAL
            node_findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.PERFORMANCE,
                title="High slow query rate",
                description=f"Slow queries: {slow_per_hour:.1f}/hour",
                metric_name="slow_queries_per_hour",
                metric_value=f"{slow_per_hour:.1f}",
                threshold=str(slow_thresholds.get("critical", 500)),
                node=node.hostname
            ))
        elif slow_per_hour >= slow_thresholds.get("warning", 100):
            slow_status = Severity.WARNING
        
        node_metrics.append(MetricAnalysis(
            name="slow_queries_per_hour",
            value=slow_per_hour,
            unit="queries/hour",
            status=slow_status,
            description=f"Slow query rate: {slow_per_hour:.1f} per hour"
        ))
        
        return NodeAnalysis(
            hostname=node.hostname,
            role=node.role.value,
            status=overall_status,
            metrics=node_metrics,
            findings=node_findings,
            queries_per_second=qps,
            connections_current=node.get_status_int("Threads_connected"),
            connections_max_used=node.get_status_int("Max_used_connections"),
            buffer_pool_hit_ratio=hit_ratio
        )
    
    def analyze_capacity(self, request: ClusterReviewRequest) -> CapacityAssessment:
        """Analyze overall capacity of the cluster."""
        is_oversized = False
        is_undersized = False
        rightsizing_recs = []
        
        # Aggregate metrics across nodes
        total_conn_util = 0
        total_bp_usage = 0
        nodes_with_resources = 0
        
        cpu_assessment = "Unknown - no CPU data provided"
        memory_assessment = "Unknown - no memory data provided"
        disk_assessment = "Unknown - no disk data provided"
        
        for node in request.nodes:
            total_conn_util += metrics.calculate_connection_utilization(node)
            total_bp_usage += metrics.calculate_buffer_pool_usage(node)
            
            if node.system_resources:
                nodes_with_resources += 1
                
                # Check disk usage
                if node.system_resources.disk_used_gb and node.system_resources.disk_total_gb:
                    disk_pct = node.system_resources.disk_used_gb / node.system_resources.disk_total_gb
                    disk_thresholds = self.thresholds.get("resources", {}).get("disk", {})
                    if disk_pct >= disk_thresholds.get("critical", 0.9):
                        is_undersized = True
                        disk_assessment = f"CRITICAL: Disk usage at {disk_pct*100:.1f}%"
                    elif disk_pct >= disk_thresholds.get("warning", 0.8):
                        disk_assessment = f"WARNING: Disk usage at {disk_pct*100:.1f}%"
                    else:
                        disk_assessment = f"OK: Disk usage at {disk_pct*100:.1f}%"
                
                # Check CPU
                if node.system_resources.cpu_utilization_pct is not None:
                    cpu_pct = node.system_resources.cpu_utilization_pct / 100
                    cpu_thresholds = self.thresholds.get("resources", {}).get("cpu", {})
                    if cpu_pct < cpu_thresholds.get("underutilized", 0.3):
                        cpu_assessment = f"Underutilized: CPU at {cpu_pct*100:.1f}%"
                    elif cpu_pct >= cpu_thresholds.get("critical", 0.95):
                        cpu_assessment = f"CRITICAL: CPU at {cpu_pct*100:.1f}%"
                        is_undersized = True
                    elif cpu_pct >= cpu_thresholds.get("warning", 0.8):
                        cpu_assessment = f"WARNING: CPU at {cpu_pct*100:.1f}%"
                    else:
                        cpu_assessment = f"OK: CPU at {cpu_pct*100:.1f}%"
                
                # Check Memory
                if node.system_resources.ram_utilization_pct is not None:
                    mem_pct = node.system_resources.ram_utilization_pct / 100
                    mem_thresholds = self.thresholds.get("resources", {}).get("memory", {})
                    if mem_pct < mem_thresholds.get("underutilized", 0.5):
                        memory_assessment = f"Underutilized: Memory at {mem_pct*100:.1f}%"
                        is_oversized = True
                    elif mem_pct >= mem_thresholds.get("critical", 0.95):
                        memory_assessment = f"CRITICAL: Memory at {mem_pct*100:.1f}%"
                        is_undersized = True
                    else:
                        memory_assessment = f"OK: Memory at {mem_pct*100:.1f}%"
        
        # Check average connection utilization
        avg_conn_util = total_conn_util / len(request.nodes) if request.nodes else 0
        conn_thresholds = self.thresholds.get("server", {}).get("connection_utilization", {})
        if avg_conn_util < conn_thresholds.get("underutilized", 0.3):
            is_oversized = True
            rightsizing_recs.append(
                f"Connection utilization is low ({avg_conn_util*100:.1f}%). "
                f"Consider reducing max_connections or node count."
            )
        
        # Check average buffer pool usage
        avg_bp_usage = total_bp_usage / len(request.nodes) if request.nodes else 0
        bp_usage_threshold = self.thresholds.get("server", {}).get("buffer_pool_usage", {})
        if avg_bp_usage < bp_usage_threshold.get("underutilized", 0.5):
            is_oversized = True
            rightsizing_recs.append(
                f"Buffer pool usage is low ({avg_bp_usage*100:.1f}%). "
                f"Consider reducing innodb_buffer_pool_size."
            )
        
        # Determine overall status
        if is_undersized:
            status = Severity.CRITICAL
            summary = "Cluster resources are insufficient for current workload"
        elif is_oversized:
            status = Severity.WARNING
            summary = "Cluster appears to be over-provisioned for current workload"
        else:
            status = Severity.INFO
            summary = "Cluster capacity appears appropriate for current workload"
        
        # Connection assessment
        connection_assessment = f"Average connection utilization: {avg_conn_util*100:.1f}%"
        
        return CapacityAssessment(
            status=status,
            summary=summary,
            cpu_assessment=cpu_assessment,
            memory_assessment=memory_assessment,
            disk_assessment=disk_assessment,
            connection_assessment=connection_assessment,
            is_oversized=is_oversized,
            is_undersized=is_undersized,
            rightsizing_recommendations=rightsizing_recs
        )
    
    def analyze_load(self, request: ClusterReviewRequest) -> LoadAnalysis:
        """Analyze current workload across the cluster."""
        total_qps = 0
        total_writes = 0
        total_reads = 0
        total_current_conn = 0
        total_max_conn = 0
        peak_conn = 0
        
        for node in request.nodes:
            total_qps += metrics.calculate_queries_per_second(node)
            total_writes += metrics.calculate_writes_per_second(node)
            total_reads += metrics.calculate_reads_per_second(node)
            total_current_conn += node.get_status_int("Threads_connected", 0)
            total_max_conn += node.get_variable_int("max_connections", 0)
            peak_conn = max(peak_conn, node.get_status_int("Max_used_connections", 0))
        
        # Calculate read:write ratio
        if total_writes > 0:
            rw_ratio = total_reads / total_writes
        else:
            rw_ratio = float('inf') if total_reads > 0 else 0
        
        # Determine if cluster can handle load
        can_handle = True
        status = Severity.INFO
        
        # Check for issues that indicate load problems
        for node in request.nodes:
            if metrics.calculate_connection_utilization(node) > 0.9:
                can_handle = False
                status = Severity.CRITICAL
            if metrics.calculate_buffer_pool_hit_ratio(node) < 0.90:
                status = Severity.WARNING
        
        summary = f"Cluster processing {total_qps:.1f} queries/sec (R/W ratio: {rw_ratio:.1f}:1)"
        
        return LoadAnalysis(
            status=status,
            summary=summary,
            total_queries_per_second=total_qps,
            total_writes_per_second=total_writes,
            total_reads_per_second=total_reads,
            read_write_ratio=rw_ratio,
            total_current_connections=total_current_conn,
            total_max_connections=total_max_conn,
            peak_connections_used=peak_conn,
            can_handle_current_load=can_handle
        )
    
    @abstractmethod
    def analyze_architecture(self, request: ClusterReviewRequest) -> ArchitectureAssessment:
        """Analyze architecture - must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def analyze(self, request: ClusterReviewRequest) -> ClusterReviewResponse:
        """Perform full analysis - must be implemented by subclasses."""
        pass
    
    def generate_key_insights(
        self,
        request: ClusterReviewRequest,
        architecture: ArchitectureAssessment,
        capacity: CapacityAssessment,
        load: LoadAnalysis
    ) -> dict:
        """Generate key insights answering common questions."""
        return {
            "handling_current_load": load.can_handle_current_load,
            "resources_sufficient": not capacity.is_undersized,
            "is_oversized": capacity.is_oversized,
            "topology_valid": architecture.topology_valid,
            "ha_capable": architecture.ha_capable,
            "quorum_capable": architecture.quorum_capable,
            "consider_downsizing": capacity.is_oversized and len(request.nodes) > 3,
            "read_write_ratio": load.read_write_ratio,
            "queries_per_second": load.total_queries_per_second
        }
