"""
Log analyzer for MariaDB, Galera, and MaxScale logs.
Parses error logs, slow query logs, and MaxScale logs to identify issues.
"""

import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.models.output import Severity, Category, Finding, Recommendation


class LogEntry(BaseModel):
    """Represents a parsed log entry."""
    timestamp: Optional[str] = None
    level: str = "info"
    source: str = ""
    message: str = ""
    raw_line: str = ""


class LogSummary(BaseModel):
    """Summary of log analysis results."""
    total_lines: int = 0
    error_count: int = 0
    warning_count: int = 0
    critical_events: list[dict] = Field(default_factory=list)
    sst_events: list[dict] = Field(default_factory=list)
    ist_events: list[dict] = Field(default_factory=list)
    flow_control_events: list[dict] = Field(default_factory=list)
    connection_errors: list[dict] = Field(default_factory=list)
    state_changes: list[dict] = Field(default_factory=list)
    disk_issues: list[dict] = Field(default_factory=list)
    inconsistency_events: list[dict] = Field(default_factory=list)
    
    # InnoDB buffer pool issues
    innodb_buffer_issues: list[dict] = Field(default_factory=list)
    innodb_oom_events: list[dict] = Field(default_factory=list)
    innodb_corruption_events: list[dict] = Field(default_factory=list)
    
    # Crash and restart events
    crash_events: list[dict] = Field(default_factory=list)
    startup_events: list[dict] = Field(default_factory=list)
    unexpected_shutdown_events: list[dict] = Field(default_factory=list)
    oom_killer_events: list[dict] = Field(default_factory=list)
    
    # Replication issues
    replication_errors: list[dict] = Field(default_factory=list)
    binlog_errors: list[dict] = Field(default_factory=list)
    gtid_errors: list[dict] = Field(default_factory=list)
    slave_stopped_events: list[dict] = Field(default_factory=list)
    
    # Connection critical issues
    max_connection_errors: list[dict] = Field(default_factory=list)
    connection_refused_events: list[dict] = Field(default_factory=list)
    host_blocked_events: list[dict] = Field(default_factory=list)
    ssl_errors: list[dict] = Field(default_factory=list)
    
    # Performance issues
    deadlock_events: list[dict] = Field(default_factory=list)
    lock_wait_events: list[dict] = Field(default_factory=list)
    long_semaphore_events: list[dict] = Field(default_factory=list)


class MariaDBLogAnalyzer:
    """Analyzer for MariaDB/Galera error logs."""
    
    # Patterns to detect in MariaDB logs
    PATTERNS = {
        # General error/warning patterns
        "error": re.compile(r'\[ERROR\]|\[error\]|ERROR:', re.IGNORECASE),
        "warning": re.compile(r'\[Warning\]|\[warning\]|Warning:', re.IGNORECASE),
        
        # Galera/WSREP patterns
        "wsrep": re.compile(r'WSREP:', re.IGNORECASE),
        "sst": re.compile(r'SST|State Transfer|state transfer', re.IGNORECASE),
        "ist": re.compile(r'IST|Incremental State Transfer', re.IGNORECASE),
        "flow_control": re.compile(r'flow.control|Flow-control', re.IGNORECASE),
        "inconsistent": re.compile(r'Inconsistent|INCONSISTENT|inconsistency', re.IGNORECASE),
        "quorum": re.compile(r'quorum|non-primary|NON-PRIMARY|split.brain', re.IGNORECASE),
        "donor": re.compile(r'donor|DONOR|Donor/Desynced', re.IGNORECASE),
        "joiner": re.compile(r'joiner|JOINER', re.IGNORECASE),
        "cluster_size": re.compile(r'cluster_size|wsrep_cluster_size', re.IGNORECASE),
        "vote": re.compile(r'vote|voting|voted out', re.IGNORECASE),
        
        # InnoDB buffer pool patterns
        "innodb_buffer": re.compile(r'InnoDB.*buffer.pool|buffer.pool', re.IGNORECASE),
        "innodb_buffer_warning": re.compile(r'buffer.pool.*warning|cannot allocate|memory.*exhausted|oom|out.of.memory', re.IGNORECASE),
        "innodb_buffer_resize": re.compile(r'buffer.pool.*resize|resizing.*buffer', re.IGNORECASE),
        "innodb_oom": re.compile(r'InnoDB.*Cannot allocate|InnoDB.*out of memory|mmap.*failed', re.IGNORECASE),
        "innodb_corruption": re.compile(r'corrupt|corruption|checksum.*mismatch|page.*invalid', re.IGNORECASE),
        "innodb_recovery": re.compile(r'InnoDB.*recovery|crash.recovery|Starting.crash.recovery', re.IGNORECASE),
        
        # Crash and restart patterns
        "crash": re.compile(r'crash|CRASH|segfault|SIGSEGV|SIGABRT|SIGKILL|assertion.*fail|mysqld.*got.*signal', re.IGNORECASE),
        "startup": re.compile(r'starting.*mysqld|MariaDB.*starting|ready for connections|Server.*socket.*created', re.IGNORECASE),
        "shutdown": re.compile(r'shutdown.*complete|Normal.*shutdown|Shutdown.*completed|mysqld.*ended', re.IGNORECASE),
        "unexpected_shutdown": re.compile(r'unexpected|abnormal|unclean|not.*graceful|killed|SIGTERM|SIGKILL', re.IGNORECASE),
        "oom_killer": re.compile(r'oom.killer|Out.of.memory.*Killed|invoked.oom-killer|memory.cgroup', re.IGNORECASE),
        
        # Async replication patterns
        "replication_error": re.compile(r'Slave.*error|replication.*error|Last_Error|Slave_IO_Running.*No|Slave_SQL_Running.*No', re.IGNORECASE),
        "replication_lag": re.compile(r'Seconds_Behind_Master|slave.*behind|replication.*lag|delay', re.IGNORECASE),
        "binlog_error": re.compile(r'binlog.*error|binary.log.*error|relay.log.*error|could not.*binlog', re.IGNORECASE),
        "gtid_error": re.compile(r'GTID.*error|gtid.*mismatch|gtid.*gap|gtid.*skip', re.IGNORECASE),
        "duplicate_key": re.compile(r'Duplicate.entry|duplicate.*key|Error.*1062', re.IGNORECASE),
        "table_not_exist": re.compile(r"Table.*doesn't exist|Unknown.*table|Error.*1146", re.IGNORECASE),
        "slave_stopped": re.compile(r'Slave.*stopped|slave.*thread.*exiting|stopping.*slave', re.IGNORECASE),
        
        # Connection critical patterns
        "max_connections": re.compile(r'max_connections|too.many.connections|Connection.*refused|ERROR.*1040', re.IGNORECASE),
        "connection_timeout": re.compile(r'connection.*timeout|wait_timeout|connect_timeout|Lost.connection', re.IGNORECASE),
        "connection_refused": re.compile(r'connection.*refused|Access.denied|ERROR.*1045|Host.*blocked', re.IGNORECASE),
        "connection_abort": re.compile(r'Aborted.connection|Got.an.error.reading|communication.packets', re.IGNORECASE),
        "ssl_error": re.compile(r'SSL.*error|TLS.*error|certificate.*error|handshake.*fail', re.IGNORECASE),
        "host_blocked": re.compile(r'Host.*blocked|blocked.because.of.many.connection.errors', re.IGNORECASE),
        
        # Disk and storage patterns
        "disk_full": re.compile(r'table.*is full|disk full|no space|HA_ERR_RECORD_FILE_FULL|errno.*28', re.IGNORECASE),
        "disk_io_error": re.compile(r'disk.*I/O.*error|read.*error|write.*error|pread.*failed|pwrite.*failed', re.IGNORECASE),
        
        # General performance patterns
        "timeout": re.compile(r'timeout|timed out', re.IGNORECASE),
        "deadlock": re.compile(r'deadlock|DEADLOCK', re.IGNORECASE),
        "lock_wait": re.compile(r'lock.wait.timeout|waiting.for.*lock', re.IGNORECASE),
        "slow_query": re.compile(r'slow query|Query_time:', re.IGNORECASE),
        "long_semaphore": re.compile(r'long.semaphore.wait|Semaphore.wait|waited.*seconds', re.IGNORECASE),
    }
    
    # Timestamp patterns
    TIMESTAMP_PATTERNS = [
        re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'),  # 2025-12-08 18:08:38
        re.compile(r'(\d{6}\s+\d{2}:\d{2}:\d{2})'),  # 251208 12:45:08
    ]
    
    def __init__(self):
        self.findings: list[Finding] = []
        self.recommendations: list[Recommendation] = []
    
    def analyze_log_content(self, log_content: str, log_name: str = "mariadb.log") -> dict:
        """Analyze MariaDB/Galera log content."""
        self.findings = []
        self.recommendations = []
        
        summary = LogSummary()
        lines = log_content.split('\n')
        summary.total_lines = len(lines)
        
        for line in lines:
            if not line.strip():
                continue
            
            # Parse timestamp
            timestamp = self._extract_timestamp(line)
            
            # Check for errors
            if self.PATTERNS["error"].search(line):
                summary.error_count += 1
                self._categorize_error(line, timestamp, summary)
            
            # Check for warnings
            if self.PATTERNS["warning"].search(line):
                summary.warning_count += 1
            
            # Check for specific events
            self._check_galera_events(line, timestamp, summary)
        
        # Generate findings from summary
        self._generate_findings(summary, log_name)
        
        return {
            "summary": summary.model_dump(),
            "findings": self.findings,
            "recommendations": self.recommendations,
            "critical_issues": len(summary.critical_events),
            "sst_count": len(summary.sst_events),
            "ist_count": len(summary.ist_events),
            "disk_issues": len(summary.disk_issues),
            "inconsistencies": len(summary.inconsistency_events),
            # New metrics
            "innodb_buffer_issues": len(summary.innodb_buffer_issues),
            "innodb_oom_events": len(summary.innodb_oom_events),
            "innodb_corruption_events": len(summary.innodb_corruption_events),
            "crash_events": len(summary.crash_events),
            "startup_events": len(summary.startup_events),
            "oom_killer_events": len(summary.oom_killer_events),
            "replication_errors": len(summary.replication_errors),
            "binlog_errors": len(summary.binlog_errors),
            "gtid_errors": len(summary.gtid_errors),
            "max_connection_errors": len(summary.max_connection_errors),
            "host_blocked_events": len(summary.host_blocked_events),
            "ssl_errors": len(summary.ssl_errors),
            "deadlock_events": len(summary.deadlock_events),
            "connection_errors": len(summary.connection_errors),
        }
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line."""
        for pattern in self.TIMESTAMP_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(1)
        return None
    
    def _categorize_error(self, line: str, timestamp: Optional[str], summary: LogSummary):
        """Categorize error based on content."""
        event = {"timestamp": timestamp, "message": line[:200]}
        
        # Disk issues
        if self.PATTERNS["disk_full"].search(line):
            summary.disk_issues.append(event)
            summary.critical_events.append({**event, "type": "disk_full"})
        
        if self.PATTERNS["disk_io_error"].search(line):
            summary.disk_issues.append(event)
            summary.critical_events.append({**event, "type": "disk_io_error"})
        
        # Inconsistency
        if self.PATTERNS["inconsistent"].search(line):
            summary.inconsistency_events.append(event)
            summary.critical_events.append({**event, "type": "inconsistency"})
        
        # Connection errors
        if self.PATTERNS["connection_abort"].search(line):
            summary.connection_errors.append(event)
        
        # InnoDB buffer pool issues
        if self.PATTERNS["innodb_buffer_warning"].search(line) or self.PATTERNS["innodb_oom"].search(line):
            summary.innodb_buffer_issues.append(event)
            summary.critical_events.append({**event, "type": "innodb_memory"})
        
        if self.PATTERNS["innodb_oom"].search(line):
            summary.innodb_oom_events.append(event)
            summary.critical_events.append({**event, "type": "innodb_oom"})
        
        if self.PATTERNS["innodb_corruption"].search(line):
            summary.innodb_corruption_events.append(event)
            summary.critical_events.append({**event, "type": "innodb_corruption"})
        
        # Crash events
        if self.PATTERNS["crash"].search(line):
            summary.crash_events.append(event)
            summary.critical_events.append({**event, "type": "crash"})
        
        if self.PATTERNS["oom_killer"].search(line):
            summary.oom_killer_events.append(event)
            summary.critical_events.append({**event, "type": "oom_killer"})
        
        # Replication errors
        if self.PATTERNS["replication_error"].search(line):
            summary.replication_errors.append(event)
            summary.critical_events.append({**event, "type": "replication_error"})
        
        if self.PATTERNS["binlog_error"].search(line):
            summary.binlog_errors.append(event)
            summary.critical_events.append({**event, "type": "binlog_error"})
        
        if self.PATTERNS["gtid_error"].search(line):
            summary.gtid_errors.append(event)
        
        if self.PATTERNS["slave_stopped"].search(line):
            summary.slave_stopped_events.append(event)
        
        # Connection critical errors
        if self.PATTERNS["max_connections"].search(line):
            summary.max_connection_errors.append(event)
            summary.critical_events.append({**event, "type": "max_connections"})
        
        if self.PATTERNS["connection_refused"].search(line):
            summary.connection_refused_events.append(event)
        
        if self.PATTERNS["host_blocked"].search(line):
            summary.host_blocked_events.append(event)
            summary.critical_events.append({**event, "type": "host_blocked"})
        
        if self.PATTERNS["ssl_error"].search(line):
            summary.ssl_errors.append(event)
        
        # Performance issues
        if self.PATTERNS["deadlock"].search(line):
            summary.deadlock_events.append(event)
        
        if self.PATTERNS["lock_wait"].search(line):
            summary.lock_wait_events.append(event)
        
        if self.PATTERNS["long_semaphore"].search(line):
            summary.long_semaphore_events.append(event)
            summary.critical_events.append({**event, "type": "long_semaphore"})
    
    def _check_galera_events(self, line: str, timestamp: Optional[str], summary: LogSummary):
        """Check for Galera-specific and general events."""
        event = {"timestamp": timestamp, "message": line[:200]}
        
        # SST events
        if self.PATTERNS["sst"].search(line) and "SST" in line.upper():
            summary.sst_events.append(event)
        
        # IST events
        if self.PATTERNS["ist"].search(line) and "IST" in line.upper():
            summary.ist_events.append(event)
        
        # Flow control
        if self.PATTERNS["flow_control"].search(line):
            summary.flow_control_events.append(event)
        
        # State changes
        if "state change" in line.lower() or "Shifting" in line:
            summary.state_changes.append(event)
        
        # Startup events (track restarts)
        if self.PATTERNS["startup"].search(line):
            summary.startup_events.append(event)
        
        # Unexpected shutdown
        if self.PATTERNS["unexpected_shutdown"].search(line) and self.PATTERNS["error"].search(line):
            summary.unexpected_shutdown_events.append(event)
        
        # InnoDB recovery (indicates restart after crash)
        if self.PATTERNS["innodb_recovery"].search(line):
            summary.crash_events.append({**event, "type": "recovery_after_crash"})
    
    def _generate_findings(self, summary: LogSummary, log_name: str):
        """Generate findings from log summary."""
        
        # ===== CRITICAL: Disk issues =====
        if summary.disk_issues:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.STORAGE,
                title=f"Disk space issues detected in {log_name}",
                description=f"Found {len(summary.disk_issues)} disk/table full errors",
                details=str(summary.disk_issues[:3])
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.STORAGE,
                title="Address disk space issues immediately",
                description="Tables or disk becoming full caused node failures",
                action="1. Check disk space with df -h\n2. Identify large tables\n3. Clean up old data or expand storage",
                impact="Critical - prevents node failures",
                effort="medium"
            ))
        
        # ===== CRITICAL: InnoDB buffer/memory issues =====
        if summary.innodb_buffer_issues:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.RESOURCE,
                title=f"InnoDB buffer pool issues in {log_name}",
                description=f"Found {len(summary.innodb_buffer_issues)} InnoDB buffer/memory warnings",
                details=str(summary.innodb_buffer_issues[:3])
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.RESOURCE,
                title="Review InnoDB buffer pool configuration",
                description="Buffer pool memory issues can cause severe performance degradation",
                action="1. Check innodb_buffer_pool_size vs available RAM\n2. Monitor memory usage\n3. Consider reducing buffer pool or adding RAM",
                impact="Critical - prevents OOM and crashes",
                effort="medium"
            ))
        
        if summary.innodb_oom_events:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.RESOURCE,
                title=f"InnoDB out-of-memory events in {log_name}",
                description=f"Found {len(summary.innodb_oom_events)} InnoDB OOM events",
                details="InnoDB could not allocate memory - may cause crashes"
            ))
        
        if summary.innodb_corruption_events:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.STORAGE,
                title=f"InnoDB corruption detected in {log_name}",
                description=f"Found {len(summary.innodb_corruption_events)} corruption/checksum errors",
                details="Data corruption detected - immediate investigation required"
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.STORAGE,
                title="Investigate InnoDB corruption immediately",
                description="Data corruption can lead to data loss",
                action="1. Run CHECK TABLE on affected tables\n2. Check disk health (SMART status)\n3. Consider restoring from backup if severe",
                impact="Critical - data integrity at risk",
                effort="high"
            ))
        
        # ===== CRITICAL: Crash and restart events =====
        if summary.crash_events:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.AVAILABILITY,
                title=f"Crash/recovery events detected in {log_name}",
                description=f"Found {len(summary.crash_events)} crash or recovery events",
                details=str(summary.crash_events[:3])
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.AVAILABILITY,
                title="Investigate MariaDB crashes",
                description="Crashes indicate severe issues requiring investigation",
                action="1. Check for segfaults in system logs\n2. Review memory usage patterns\n3. Check for known bugs in MariaDB version",
                impact="Critical - service availability",
                effort="high"
            ))
        
        if summary.oom_killer_events:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.RESOURCE,
                title=f"OOM killer events detected in {log_name}",
                description=f"Found {len(summary.oom_killer_events)} OOM killer invocations",
                details="Linux OOM killer terminated MariaDB due to memory exhaustion"
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.RESOURCE,
                title="Address memory exhaustion",
                description="OOM killer is terminating MariaDB",
                action="1. Reduce innodb_buffer_pool_size\n2. Add swap space\n3. Increase server RAM\n4. Check for memory leaks",
                impact="Critical - prevents unplanned restarts",
                effort="medium"
            ))
        
        # Track restart frequency
        if len(summary.startup_events) > 5:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.AVAILABILITY,
                title=f"Frequent restarts detected in {log_name}",
                description=f"Found {len(summary.startup_events)} server startup events",
                details="Multiple restarts may indicate instability"
            ))
        
        # ===== CRITICAL: Replication errors =====
        if summary.replication_errors:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.REPLICATION,
                title=f"Replication errors in {log_name}",
                description=f"Found {len(summary.replication_errors)} replication errors",
                details=str(summary.replication_errors[:3])
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.REPLICATION,
                title="Fix replication errors",
                description="Replication is broken or experiencing errors",
                action="1. Check SHOW SLAVE STATUS\\G\n2. Identify and fix the error\n3. Consider pt-table-sync for data drift",
                impact="Critical - data consistency at risk",
                effort="medium"
            ))
        
        if summary.binlog_errors:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.REPLICATION,
                title=f"Binary log errors in {log_name}",
                description=f"Found {len(summary.binlog_errors)} binlog/relay log errors",
                details="Binary log errors can break replication"
            ))
        
        if summary.gtid_errors:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.REPLICATION,
                title=f"GTID errors in {log_name}",
                description=f"Found {len(summary.gtid_errors)} GTID-related errors",
                details="GTID gaps or mismatches can cause replication issues"
            ))
        
        if summary.slave_stopped_events:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.REPLICATION,
                title=f"Slave stopped events in {log_name}",
                description=f"Found {len(summary.slave_stopped_events)} slave stopped events",
                details="Replication slave has stopped - may need manual intervention"
            ))
        
        # ===== CRITICAL: Connection issues =====
        if summary.max_connection_errors:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.CAPACITY,
                title=f"Max connections exceeded in {log_name}",
                description=f"Found {len(summary.max_connection_errors)} max_connections errors",
                details="Clients are being refused due to connection limit"
            ))
            self.recommendations.append(Recommendation(
                priority=1,
                category=Category.CAPACITY,
                title="Increase max_connections or implement pooling",
                description="Connection limit is being hit",
                action="1. Increase max_connections\n2. Implement connection pooling\n3. Review application connection handling",
                impact="Critical - clients cannot connect",
                effort="low"
            ))
        
        if summary.host_blocked_events:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.SECURITY,
                title=f"Hosts blocked in {log_name}",
                description=f"Found {len(summary.host_blocked_events)} host blocked events",
                details="Hosts are being blocked due to too many connection errors"
            ))
            self.recommendations.append(Recommendation(
                priority=2,
                category=Category.SECURITY,
                title="Investigate blocked hosts",
                description="Hosts are being blocked - may be attack or misconfiguration",
                action="1. Run FLUSH HOSTS to unblock\n2. Increase max_connect_errors\n3. Investigate source of failed connections",
                impact="Clients from blocked hosts cannot connect",
                effort="low"
            ))
        
        if summary.ssl_errors:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.SECURITY,
                title=f"SSL/TLS errors in {log_name}",
                description=f"Found {len(summary.ssl_errors)} SSL/TLS errors",
                details="SSL handshake or certificate issues"
            ))
        
        if len(summary.connection_errors) > 100:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.NETWORK,
                title=f"High connection abort rate in {log_name}",
                description=f"Found {len(summary.connection_errors)} aborted connections",
                details="High abort rate may indicate network issues or client problems"
            ))
        
        # ===== WARNING: Performance issues =====
        if summary.deadlock_events:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.PERFORMANCE,
                title=f"Deadlocks detected in {log_name}",
                description=f"Found {len(summary.deadlock_events)} deadlock events",
                details="Deadlocks cause transaction rollbacks"
            ))
            self.recommendations.append(Recommendation(
                priority=3,
                category=Category.PERFORMANCE,
                title="Investigate deadlocks",
                description="Deadlocks are occurring",
                action="1. Enable innodb_print_all_deadlocks\n2. Review transaction isolation levels\n3. Optimize transaction ordering",
                impact="Reduces failed transactions",
                effort="medium"
            ))
        
        if summary.lock_wait_events:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.PERFORMANCE,
                title=f"Lock wait timeouts in {log_name}",
                description=f"Found {len(summary.lock_wait_events)} lock wait timeout events",
                details="Transactions are timing out waiting for locks"
            ))
        
        if summary.long_semaphore_events:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.PERFORMANCE,
                title=f"Long semaphore waits in {log_name}",
                description=f"Found {len(summary.long_semaphore_events)} long semaphore wait events",
                details="InnoDB is experiencing internal contention"
            ))
        
        # ===== Galera-specific =====
        if summary.inconsistency_events:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.GALERA,
                title=f"Galera inconsistency detected in {log_name}",
                description=f"Found {len(summary.inconsistency_events)} inconsistency events - nodes were voted out",
                details=str(summary.inconsistency_events[:3])
            ))
        
        if len(summary.sst_events) > 3:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.GALERA,
                title=f"Frequent SST events in {log_name}",
                description=f"Found {len(summary.sst_events)} SST (full state transfer) events",
                details="Frequent SST indicates nodes frequently need full resync"
            ))
            self.recommendations.append(Recommendation(
                priority=2,
                category=Category.GALERA,
                title="Enable gcache to allow IST instead of SST",
                description=f"{len(summary.sst_events)} SST events detected - IST would be faster",
                action="Set gcache.size to 1G or higher based on write volume",
                impact="Faster node recovery",
                effort="low"
            ))
        
        if len(summary.flow_control_events) > 10:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.PERFORMANCE,
                title=f"Flow control activity in {log_name}",
                description=f"Found {len(summary.flow_control_events)} flow control related events",
                details="Flow control pauses replication when nodes can't keep up"
            ))
        
        # ===== Summary =====
        self.findings.append(Finding(
            severity=Severity.INFO,
            category=Category.GENERAL,
            title=f"Log summary for {log_name}",
            description=f"Total lines: {summary.total_lines}, Errors: {summary.error_count}, Warnings: {summary.warning_count}",
            details=f"Crashes: {len(summary.crash_events)}, Restarts: {len(summary.startup_events)}, SST: {len(summary.sst_events)}, Replication errors: {len(summary.replication_errors)}"
        ))


class MaxScaleLogAnalyzer:
    """Analyzer for MaxScale logs."""
    
    PATTERNS = {
        "error": re.compile(r'error\s*:', re.IGNORECASE),
        "warning": re.compile(r'warning\s*:', re.IGNORECASE),
        "notice": re.compile(r'notice\s*:', re.IGNORECASE),
        "server_down": re.compile(r'server_down|slave_down|master_down', re.IGNORECASE),
        "server_up": re.compile(r'server_up|slave_up|master_up|new_master|new_slave', re.IGNORECASE),
        "connection_error": re.compile(r"Can't connect|connection refused|unable to connect", re.IGNORECASE),
        "lost_master": re.compile(r'lost_master', re.IGNORECASE),
        "lost_slave": re.compile(r'lost_slave', re.IGNORECASE),
        "no_cluster": re.compile(r'no cluster members|There are no cluster members', re.IGNORECASE),
        "inconsistent": re.compile(r'Inconsistent', re.IGNORECASE),
        "transaction_replay": re.compile(r'transaction.replay|replaying transaction', re.IGNORECASE),
        "protocol_error": re.compile(r'protocol|unexpected sequence|invalid.*Request', re.IGNORECASE),
    }
    
    TIMESTAMP_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})')
    
    def __init__(self):
        self.findings: list[Finding] = []
        self.recommendations: list[Recommendation] = []
    
    def analyze_log_content(self, log_content: str, log_name: str = "maxscale.log") -> dict:
        """Analyze MaxScale log content."""
        self.findings = []
        self.recommendations = []
        
        lines = log_content.split('\n')
        
        summary = {
            "total_lines": len(lines),
            "error_count": 0,
            "warning_count": 0,
            "server_down_events": [],
            "server_up_events": [],
            "master_changes": [],
            "connection_errors": [],
            "cluster_issues": [],
            "protocol_errors": [],
        }
        
        for line in lines:
            if not line.strip():
                continue
            
            timestamp = self._extract_timestamp(line)
            event = {"timestamp": timestamp, "message": line[:200]}
            
            if self.PATTERNS["error"].search(line):
                summary["error_count"] += 1
                
                if self.PATTERNS["connection_error"].search(line):
                    summary["connection_errors"].append(event)
                elif self.PATTERNS["protocol_error"].search(line):
                    summary["protocol_errors"].append(event)
                elif self.PATTERNS["no_cluster"].search(line):
                    summary["cluster_issues"].append(event)
            
            if self.PATTERNS["warning"].search(line):
                summary["warning_count"] += 1
            
            # Server state changes
            if self.PATTERNS["server_down"].search(line):
                summary["server_down_events"].append(event)
            
            if self.PATTERNS["server_up"].search(line):
                summary["server_up_events"].append(event)
            
            if self.PATTERNS["lost_master"].search(line) or "new_master" in line.lower():
                summary["master_changes"].append(event)
        
        # Generate findings
        self._generate_findings(summary, log_name)
        
        return {
            "summary": summary,
            "findings": self.findings,
            "recommendations": self.recommendations,
            "server_down_count": len(summary["server_down_events"]),
            "master_changes": len(summary["master_changes"]),
            "connection_errors": len(summary["connection_errors"])
        }
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line."""
        match = self.TIMESTAMP_PATTERN.search(line)
        return match.group(1) if match else None
    
    def _generate_findings(self, summary: dict, log_name: str):
        """Generate findings from MaxScale log summary."""
        
        # Many server down events
        if len(summary["server_down_events"]) > 5:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.AVAILABILITY,
                title=f"Frequent server down events in {log_name}",
                description=f"Found {len(summary['server_down_events'])} server down events",
                details="Investigate network connectivity or server stability issues"
            ))
        
        # Master changes indicate instability
        if len(summary["master_changes"]) > 3:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.AVAILABILITY,
                title=f"Frequent master changes in {log_name}",
                description=f"Found {len(summary['master_changes'])} master role changes",
                details="Frequent master changes may indicate Galera node instability or network issues"
            ))
        
        # Cluster issues
        if summary["cluster_issues"]:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category=Category.GALERA,
                title=f"Cluster membership issues in {log_name}",
                description=f"Found {len(summary['cluster_issues'])} 'no cluster members' events",
                details="MaxScale lost visibility to cluster - all nodes were unavailable"
            ))
        
        # Connection errors
        if len(summary["connection_errors"]) > 10:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.NETWORK,
                title=f"Connection errors in {log_name}",
                description=f"Found {len(summary['connection_errors'])} connection errors",
                details="Check network connectivity between MaxScale and backend servers"
            ))
        
        # Summary
        self.findings.append(Finding(
            severity=Severity.INFO,
            category=Category.GENERAL,
            title=f"MaxScale log summary for {log_name}",
            description=f"Total lines: {summary['total_lines']}, Errors: {summary['error_count']}, Warnings: {summary['warning_count']}",
            details=f"Server down: {len(summary['server_down_events'])}, Server up: {len(summary['server_up_events'])}, Master changes: {len(summary['master_changes'])}"
        ))


class SlowQueryLogAnalyzer:
    """Analyzer for slow query logs."""
    
    QUERY_TIME_PATTERN = re.compile(r'Query_time:\s*([\d.]+)')
    LOCK_TIME_PATTERN = re.compile(r'Lock_time:\s*([\d.]+)')
    ROWS_SENT_PATTERN = re.compile(r'Rows_sent:\s*(\d+)')
    ROWS_EXAMINED_PATTERN = re.compile(r'Rows_examined:\s*(\d+)')
    
    def __init__(self):
        self.findings: list[Finding] = []
        self.recommendations: list[Recommendation] = []
    
    def analyze_log_content(self, log_content: str, log_name: str = "slow_query.log") -> dict:
        """Analyze slow query log content."""
        self.findings = []
        self.recommendations = []
        
        lines = log_content.split('\n')
        
        summary = {
            "total_queries": 0,
            "total_query_time": 0.0,
            "max_query_time": 0.0,
            "avg_query_time": 0.0,
            "total_lock_time": 0.0,
            "queries_over_10s": 0,
            "queries_over_60s": 0,
            "high_rows_examined": 0,
        }
        
        for line in lines:
            # Extract query time
            qt_match = self.QUERY_TIME_PATTERN.search(line)
            if qt_match:
                query_time = float(qt_match.group(1))
                summary["total_queries"] += 1
                summary["total_query_time"] += query_time
                summary["max_query_time"] = max(summary["max_query_time"], query_time)
                
                if query_time > 10:
                    summary["queries_over_10s"] += 1
                if query_time > 60:
                    summary["queries_over_60s"] += 1
            
            # Extract lock time
            lt_match = self.LOCK_TIME_PATTERN.search(line)
            if lt_match:
                summary["total_lock_time"] += float(lt_match.group(1))
            
            # Extract rows examined
            re_match = self.ROWS_EXAMINED_PATTERN.search(line)
            if re_match:
                rows = int(re_match.group(1))
                if rows > 1000000:
                    summary["high_rows_examined"] += 1
        
        if summary["total_queries"] > 0:
            summary["avg_query_time"] = summary["total_query_time"] / summary["total_queries"]
        
        # Generate findings
        self._generate_findings(summary, log_name)
        
        return {
            "summary": summary,
            "findings": self.findings,
            "recommendations": self.recommendations
        }
    
    def _generate_findings(self, summary: dict, log_name: str):
        """Generate findings from slow query log."""
        
        if summary["queries_over_60s"] > 0:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.PERFORMANCE,
                title=f"Very slow queries in {log_name}",
                description=f"Found {summary['queries_over_60s']} queries taking over 60 seconds",
                details=f"Max query time: {summary['max_query_time']:.2f}s"
            ))
            self.recommendations.append(Recommendation(
                priority=2,
                category=Category.PERFORMANCE,
                title="Optimize slow queries",
                description=f"{summary['queries_over_60s']} queries exceed 60 seconds",
                action="Review slow query log, add indexes, optimize query patterns",
                impact="Improved response times",
                effort="medium"
            ))
        
        if summary["high_rows_examined"] > 0:
            self.findings.append(Finding(
                severity=Severity.WARNING,
                category=Category.PERFORMANCE,
                title=f"Queries examining many rows in {log_name}",
                description=f"Found {summary['high_rows_examined']} queries examining over 1M rows",
                details="These queries may benefit from better indexes"
            ))


class LogAnalysisInput(BaseModel):
    """Input model for log analysis."""
    mariadb_logs: Optional[dict[str, str]] = Field(None, description="Map of node name to MariaDB log content")
    maxscale_logs: Optional[dict[str, str]] = Field(None, description="Map of node name to MaxScale log content")
    slow_query_logs: Optional[dict[str, str]] = Field(None, description="Map of node name to slow query log content")


class CombinedLogAnalyzer:
    """Combined analyzer for all log types."""
    
    def __init__(self):
        self.mariadb_analyzer = MariaDBLogAnalyzer()
        self.maxscale_analyzer = MaxScaleLogAnalyzer()
        self.slow_query_analyzer = SlowQueryLogAnalyzer()
    
    def analyze(self, logs: LogAnalysisInput) -> dict:
        """Analyze all provided logs and return combined results."""
        results = {
            "mariadb_logs": {},
            "maxscale_logs": {},
            "slow_query_logs": {},
            "combined_findings": [],
            "combined_recommendations": [],
            "summary": {
                "total_critical_issues": 0,
                "total_warnings": 0,
                "disk_issues_detected": False,
                "inconsistency_detected": False,
                "frequent_sst": False,
                "cluster_instability": False,
            }
        }
        
        all_findings = []
        all_recommendations = []
        
        # Analyze MariaDB logs
        if logs.mariadb_logs:
            for node_name, log_content in logs.mariadb_logs.items():
                result = self.mariadb_analyzer.analyze_log_content(log_content, f"mariadb.log ({node_name})")
                results["mariadb_logs"][node_name] = result
                all_findings.extend(result["findings"])
                all_recommendations.extend(result["recommendations"])
                
                if result["disk_issues"] > 0:
                    results["summary"]["disk_issues_detected"] = True
                if result["inconsistencies"] > 0:
                    results["summary"]["inconsistency_detected"] = True
                if result["sst_count"] > 3:
                    results["summary"]["frequent_sst"] = True
        
        # Analyze MaxScale logs
        if logs.maxscale_logs:
            for node_name, log_content in logs.maxscale_logs.items():
                result = self.maxscale_analyzer.analyze_log_content(log_content, f"maxscale.log ({node_name})")
                results["maxscale_logs"][node_name] = result
                all_findings.extend(result["findings"])
                all_recommendations.extend(result["recommendations"])
                
                if result["master_changes"] > 3:
                    results["summary"]["cluster_instability"] = True
        
        # Analyze slow query logs
        if logs.slow_query_logs:
            for node_name, log_content in logs.slow_query_logs.items():
                result = self.slow_query_analyzer.analyze_log_content(log_content, f"slow_query.log ({node_name})")
                results["slow_query_logs"][node_name] = result
                all_findings.extend(result["findings"])
                all_recommendations.extend(result["recommendations"])
        
        # Deduplicate and summarize
        results["combined_findings"] = all_findings
        results["combined_recommendations"] = all_recommendations
        results["summary"]["total_critical_issues"] = len([f for f in all_findings if f.severity == Severity.CRITICAL])
        results["summary"]["total_warnings"] = len([f for f in all_findings if f.severity == Severity.WARNING])
        
        return results
