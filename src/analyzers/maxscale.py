"""
MaxScale analyzer with traffic statistics analysis.
"""

from typing import Optional
from src.models.input import MaxScaleConfig, ClusterReviewRequest
from src.models.output import Severity, Category, Finding, Recommendation


class MaxScaleAnalyzer:
    """Analyzer for MaxScale proxy configuration, health, and traffic statistics."""
    
    def __init__(self):
        self.findings: list[Finding] = []
        self.recommendations: list[Recommendation] = []
    
    def analyze(self, maxscale: MaxScaleConfig, request: ClusterReviewRequest) -> dict:
        """Analyze MaxScale configuration and return findings."""
        self.findings = []
        self.recommendations = []
        
        result = {
            "healthy": True,
            "status": Severity.INFO,
            "summary": "",
            "findings": [],
            "recommendations": [],
            "server_count": len(maxscale.servers),
            "service_count": len(maxscale.services),
            # Traffic statistics
            "traffic_stats": self._calculate_traffic_stats(maxscale),
            "load_distribution": self._calculate_load_distribution(maxscale)
        }
        
        # Analyze servers
        self._analyze_servers(maxscale)
        
        # Analyze services
        self._analyze_services(maxscale, request)
        
        # Analyze routing configuration
        self._analyze_routing(maxscale, request)
        
        # Analyze traffic statistics
        self._analyze_traffic(maxscale, request)
        
        # Analyze load distribution
        self._analyze_load_distribution(maxscale)
        
        # Compile results
        result["findings"] = self.findings
        result["recommendations"] = self.recommendations
        
        # Determine overall health
        critical_findings = [f for f in self.findings if f.severity == Severity.CRITICAL]
        warning_findings = [f for f in self.findings if f.severity == Severity.WARNING]
        
        if critical_findings:
            result["healthy"] = False
            result["status"] = Severity.CRITICAL
            result["summary"] = f"MaxScale has {len(critical_findings)} critical issues"
        elif warning_findings:
            result["status"] = Severity.WARNING
            result["summary"] = f"MaxScale has {len(warning_findings)} warnings"
        else:
            result["summary"] = "MaxScale configuration appears healthy"
        
        return result
    
    def _calculate_traffic_stats(self, maxscale: MaxScaleConfig) -> dict:
        """Calculate traffic statistics from MaxScale data."""
        stats = {
            "total_client_connections": maxscale.total_connections,
            "current_client_connections": maxscale.current_connections,
            "connections_per_second": None,
            "total_queries_routed": 0,
            "queries_per_second": None,
            "total_reads": 0,
            "total_writes": 0,
            "read_write_ratio": None,
            "transactions_total": 0,
            "transactions_replayed": 0
        }
        
        # Calculate from services
        for service in maxscale.services:
            if service.route_master:
                stats["total_writes"] += service.route_master
            if service.route_slave:
                stats["total_reads"] += service.route_slave
            if service.route_all:
                stats["total_queries_routed"] += service.route_all
            if service.rw_transactions:
                stats["transactions_total"] += service.rw_transactions
            if service.ro_transactions:
                stats["transactions_total"] += service.ro_transactions
            if service.replayed_transactions:
                stats["transactions_replayed"] += service.replayed_transactions
        
        # Also sum from servers
        for server in maxscale.servers:
            if server.queries:
                stats["total_queries_routed"] += server.queries
        
        # Calculate rates if uptime available
        if maxscale.uptime_seconds and maxscale.uptime_seconds > 0:
            if maxscale.total_connections:
                stats["connections_per_second"] = round(
                    maxscale.total_connections / maxscale.uptime_seconds, 2
                )
            if stats["total_queries_routed"] > 0:
                stats["queries_per_second"] = round(
                    stats["total_queries_routed"] / maxscale.uptime_seconds, 2
                )
        
        # Calculate read/write ratio
        if stats["total_writes"] > 0:
            stats["read_write_ratio"] = round(
                stats["total_reads"] / stats["total_writes"], 2
            )
        
        return stats
    
    def _calculate_load_distribution(self, maxscale: MaxScaleConfig) -> dict:
        """Calculate how load is distributed across servers."""
        distribution = {
            "servers": [],
            "balanced": True,
            "imbalance_pct": 0
        }
        
        total_queries = sum(s.queries or 0 for s in maxscale.servers)
        total_connections = sum(s.connections or 0 for s in maxscale.servers)
        
        for server in maxscale.servers:
            server_stats = {
                "name": server.name,
                "state": server.state,
                "connections": server.connections,
                "connection_pct": None,
                "queries": server.queries,
                "query_pct": None
            }
            
            if total_connections > 0 and server.connections:
                server_stats["connection_pct"] = round(
                    (server.connections / total_connections) * 100, 1
                )
            
            if total_queries > 0 and server.queries:
                server_stats["query_pct"] = round(
                    (server.queries / total_queries) * 100, 1
                )
            
            distribution["servers"].append(server_stats)
        
        # Check for imbalance (exclude master from balance check for reads)
        query_pcts = [s["query_pct"] for s in distribution["servers"] 
                      if s["query_pct"] is not None and "master" not in (s["state"] or "").lower()]
        
        if query_pcts and len(query_pcts) > 1:
            max_pct = max(query_pcts)
            min_pct = min(query_pcts)
            distribution["imbalance_pct"] = round(max_pct - min_pct, 1)
            if distribution["imbalance_pct"] > 20:  # More than 20% difference
                distribution["balanced"] = False
        
        return distribution
    
    def _analyze_servers(self, maxscale: MaxScaleConfig):
        """Analyze MaxScale server definitions."""
        if not maxscale.servers:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title="No servers defined",
                description="MaxScale configuration has no server definitions"
            ))
            return
        
        # Check server states
        down_servers = []
        maintenance_servers = []
        
        for server in maxscale.servers:
            if server.state:
                state_lower = server.state.lower()
                if "down" in state_lower:
                    down_servers.append(server.name)
                elif "maintenance" in state_lower:
                    maintenance_servers.append(server.name)
        
        if down_servers:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.AVAILABILITY,
                title="Servers down",
                description=f"The following servers are down: {', '.join(down_servers)}"
            ))
        
        if maintenance_servers:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.AVAILABILITY,
                title="Servers in maintenance",
                description=f"The following servers are in maintenance: {', '.join(maintenance_servers)}"
            ))
    
    def _analyze_services(self, maxscale: MaxScaleConfig, request: ClusterReviewRequest):
        """Analyze MaxScale service configurations."""
        if not maxscale.services:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title="No services defined",
                description="MaxScale configuration has no service definitions"
            ))
            return
        
        for service in maxscale.services:
            # Check router type
            router = service.router.lower()
            
            # For Galera clusters, check appropriate router
            if request.topology_type.value == "galera":
                if router == "readconnroute":
                    self.findings.append(Finding(
                        severity=Severity.INFO,
                        category=Category.CONFIGURATION,
                        title="ReadConnRoute with Galera",
                        description=f"Service '{service.name}' uses readconnroute. "
                                   "Consider readwritesplit for better query distribution."
                    ))
            
            # Check readwritesplit settings
            if router == "readwritesplit":
                self._analyze_readwritesplit(service)
            
            # Check server assignments
            if not service.servers:
                self.findings.append(Finding(
                    severity=Severity.WARNING,
                    category=Category.CONFIGURATION,
                    title="Service has no servers",
                    description=f"Service '{service.name}' has no backend servers assigned"
                ))
    
    def _analyze_readwritesplit(self, service):
        """Analyze readwritesplit router configuration."""
        # Check transaction replay
        if service.transaction_replay is None:
            self.recommendations.append(Recommendation(
                priority=3,
                category=Category.AVAILABILITY,
                title="Consider transaction replay",
                description=f"Service '{service.name}' may benefit from transaction_replay",
                action="Enable transaction_replay=true for automatic retry on master failure",
                impact="Improved availability during failover",
                effort="low"
            ))
        
        # Check master_accept_reads for Galera
        if service.master_accept_reads is False:
            self.findings.append(Finding(
                severity=Severity.INFO,
                category=Category.CONFIGURATION,
                title="Master not accepting reads",
                description=f"Service '{service.name}' has master_accept_reads=false. "
                           "This is fine if you have dedicated read replicas."
            ))
    
    def _analyze_routing(self, maxscale: MaxScaleConfig, request: ClusterReviewRequest):
        """Analyze routing configuration for the topology."""
        # Check if all nodes are being used
        backend_count = len(maxscale.servers)
        node_count = len(request.nodes)
        
        if backend_count < node_count:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.CONFIGURATION,
                title="Not all nodes in MaxScale",
                description=f"MaxScale has {backend_count} servers but cluster has {node_count} nodes"
            ))
        
        # For Galera, check if using galera monitor
        if request.topology_type.value == "galera":
            # Check for common Galera-specific configurations
            for service in maxscale.services:
                if service.slave_selection_criteria:
                    criteria = service.slave_selection_criteria.upper()
                    if criteria not in ("ADAPTIVE_ROUTING", "LEAST_GLOBAL_CONNECTIONS", "LEAST_ROUTER_CONNECTIONS"):
                        self.findings.append(Finding(
                            severity=Severity.INFO,
                            category=Category.CONFIGURATION,
                            title="Review slave selection",
                            description=f"Service '{service.name}' uses {criteria}. "
                                       "Consider ADAPTIVE_ROUTING for Galera."
                        ))
        
        # Check for single points of failure
        if len(maxscale.servers) == 1:
            self.recommendations.append(Recommendation(
                priority=2,
                category=Category.AVAILABILITY,
                title="Add more backend servers",
                description="MaxScale only has one backend server",
                action="Add additional backend servers for failover capability",
                impact="Improved availability",
                effort="medium"
            ))
    
    def _analyze_traffic(self, maxscale: MaxScaleConfig, request: ClusterReviewRequest):
        """Analyze traffic statistics and patterns."""
        # Check connection rates
        if maxscale.current_connections and maxscale.total_connections:
            # High connection churn might indicate connection pooling issues
            if maxscale.uptime_seconds and maxscale.uptime_seconds > 3600:
                conn_per_hour = (maxscale.total_connections / maxscale.uptime_seconds) * 3600
                avg_concurrent = maxscale.current_connections
                
                if conn_per_hour > avg_concurrent * 100:
                    self.recommendations.append(Recommendation(
                        priority=2,
                        category=Category.PERFORMANCE,
                        title="High connection churn detected",
                        description=f"~{int(conn_per_hour)} connections/hour vs {avg_concurrent} concurrent. "
                                   "Consider connection pooling on the application side.",
                        action="Implement connection pooling in the application",
                        impact="Reduced connection overhead",
                        effort="medium"
                    ))
        
        # Analyze service-level traffic
        for service in maxscale.services:
            # Check for transaction replays (indicates failover events)
            if service.replayed_transactions and service.replayed_transactions > 0:
                severity = Severity.INFO if service.replayed_transactions < 100 else Severity.WARNING
                self.findings.append(Finding(
                    severity=severity,
                    category=Category.AVAILABILITY,
                    title="Transaction replays detected",
                    description=f"Service '{service.name}' has {service.replayed_transactions} replayed transactions, "
                               "indicating failover events occurred."
                ))
            
            # Calculate read/write distribution if available
            if service.route_master and service.route_slave:
                total_routed = service.route_master + service.route_slave
                write_pct = (service.route_master / total_routed) * 100 if total_routed > 0 else 0
                read_pct = (service.route_slave / total_routed) * 100 if total_routed > 0 else 0
                
                self.findings.append(Finding(
                    severity=Severity.INFO,
                    category=Category.PERFORMANCE,
                    title=f"Traffic distribution for {service.name}",
                    description=f"Read traffic: {read_pct:.1f}% ({service.route_slave:,} queries), "
                               f"Write traffic: {write_pct:.1f}% ({service.route_master:,} queries)"
                ))
                
                # If write-heavy, suggest optimization
                if write_pct > 50:
                    self.findings.append(Finding(
                        severity=Severity.INFO,
                        category=Category.PERFORMANCE,
                        title="Write-heavy workload",
                        description=f"Service '{service.name}' has {write_pct:.1f}% writes. "
                                   "This is expected for OLTP workloads."
                    ))
    
    def _analyze_load_distribution(self, maxscale: MaxScaleConfig):
        """Analyze how load is distributed across backend servers."""
        if not maxscale.servers:
            return
        
        # Check for unbalanced load
        servers_with_queries = [(s.name, s.queries, s.state) for s in maxscale.servers if s.queries]
        
        if len(servers_with_queries) > 1:
            total_queries = sum(q for _, q, _ in servers_with_queries)
            if total_queries > 0:
                # Find slaves only for balance check
                slave_queries = [(name, queries) for name, queries, state in servers_with_queries 
                                if state and "slave" in state.lower()]
                
                if len(slave_queries) > 1:
                    slave_total = sum(q for _, q in slave_queries)
                    expected_per_slave = slave_total / len(slave_queries)
                    
                    for name, queries in slave_queries:
                        deviation = abs(queries - expected_per_slave) / expected_per_slave * 100 if expected_per_slave > 0 else 0
                        if deviation > 30:
                            self.findings.append(Finding(
                                severity=Severity.WARNING,
                                category=Category.PERFORMANCE,
                                title="Unbalanced read distribution",
                                description=f"Server '{name}' has {deviation:.1f}% deviation from average. "
                                           f"({queries:,} queries vs {int(expected_per_slave):,} expected)"
                            ))
                            self.recommendations.append(Recommendation(
                                priority=3,
                                category=Category.PERFORMANCE,
                                title="Review load balancing configuration",
                                description=f"Server '{name}' is handling uneven load",
                                action="Review slave_selection_criteria setting. Consider ADAPTIVE_ROUTING.",
                                impact="Better query distribution",
                                effort="low"
                            ))
        
        # Check for servers with no queries
        for server in maxscale.servers:
            if server.state and "running" in server.state.lower() and server.queries == 0:
                self.findings.append(Finding(
                    severity=Severity.WARNING,
                    category=Category.CONFIGURATION,
                    title="Server receiving no queries",
                    description=f"Server '{server.name}' is running but has received no queries. "
                               "Check if it's properly assigned to services."
                ))
