#!/bin/bash
#
# MariaDB Cluster Data Collector
# Collects status and variable data from MariaDB nodes for analysis
#
# Usage: ./collect_data.sh <hostname> <mysql_user> [mysql_password] [output_dir]
#

set -e

HOSTNAME="${1:-localhost}"
MYSQL_USER="${2:-root}"
MYSQL_PASSWORD="${3:-}"
OUTPUT_DIR="${4:-.}"
OUTPUT_FILE="${OUTPUT_DIR}/${HOSTNAME}_data.json"

# MySQL command
if [ -n "$MYSQL_PASSWORD" ]; then
    MYSQL_CMD="mysql -h $HOSTNAME -u $MYSQL_USER -p$MYSQL_PASSWORD -N -B"
else
    MYSQL_CMD="mysql -h $HOSTNAME -u $MYSQL_USER -N -B"
fi

echo "Collecting data from $HOSTNAME..."

# Get version
VERSION=$($MYSQL_CMD -e "SELECT VERSION();" 2>/dev/null || echo "unknown")

# Get uptime
UPTIME=$($MYSQL_CMD -e "SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='Uptime';" 2>/dev/null || echo "0")

# Collect GLOBAL STATUS
echo "Collecting GLOBAL STATUS..."
GLOBAL_STATUS=$($MYSQL_CMD -e "SELECT CONCAT('\"', VARIABLE_NAME, '\": \"', VARIABLE_VALUE, '\"') FROM information_schema.GLOBAL_STATUS;" 2>/dev/null | paste -sd ',' -)

# Collect GLOBAL VARIABLES
echo "Collecting GLOBAL VARIABLES..."
GLOBAL_VARIABLES=$($MYSQL_CMD -e "SELECT CONCAT('\"', VARIABLE_NAME, '\": \"', VARIABLE_VALUE, '\"') FROM information_schema.GLOBAL_VARIABLES;" 2>/dev/null | paste -sd ',' -)

# Check if this is a Galera node
WSREP_ON=$($MYSQL_CMD -e "SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_VARIABLES WHERE VARIABLE_NAME='wsrep_on';" 2>/dev/null || echo "OFF")

# Determine role
ROLE="standalone"
if [ "$WSREP_ON" = "ON" ]; then
    ROLE="galera_node"
else
    # Check for slave status
    SLAVE_STATUS=$($MYSQL_CMD -e "SHOW SLAVE STATUS\G" 2>/dev/null || echo "")
    if [ -n "$SLAVE_STATUS" ]; then
        ROLE="replica"
    else
        # Check for master status
        MASTER_STATUS=$($MYSQL_CMD -e "SHOW MASTER STATUS\G" 2>/dev/null || echo "")
        if [ -n "$MASTER_STATUS" ]; then
            ROLE="master"
        fi
    fi
fi

# Collect SLAVE STATUS if applicable
SLAVE_STATUS_JSON=""
if [ "$ROLE" = "replica" ]; then
    echo "Collecting SLAVE STATUS..."
    SLAVE_STATUS_JSON=$($MYSQL_CMD -e "
        SELECT CONCAT(
            '\"Slave_IO_Running\": \"', Slave_IO_Running, '\", ',
            '\"Slave_SQL_Running\": \"', Slave_SQL_Running, '\", ',
            '\"Seconds_Behind_Master\": \"', IFNULL(Seconds_Behind_Master, 'NULL'), '\", ',
            '\"Master_Host\": \"', Master_Host, '\", ',
            '\"Last_Error\": \"', REPLACE(Last_Error, '\"', '\\\\\"'), '\"'
        )
        FROM information_schema.SLAVE_STATUS;
    " 2>/dev/null || echo "")
fi

# Get system resources (if available)
CPU_CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "0")
RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo "0")
DISK_TOTAL=$(df -BG /var/lib/mysql 2>/dev/null | awk 'NR==2{print $2}' | tr -d 'G' || echo "0")
DISK_USED=$(df -BG /var/lib/mysql 2>/dev/null | awk 'NR==2{print $3}' | tr -d 'G' || echo "0")

# Build JSON output
cat > "$OUTPUT_FILE" << EOF
{
    "hostname": "$HOSTNAME",
    "role": "$ROLE",
    "version": "$VERSION",
    "uptime_seconds": $UPTIME,
    "global_status": {
        $GLOBAL_STATUS
    },
    "global_variables": {
        $GLOBAL_VARIABLES
    },
    "slave_status": $([ -n "$SLAVE_STATUS_JSON" ] && echo "{$SLAVE_STATUS_JSON}" || echo "null"),
    "system_resources": {
        "cpu_cores": $CPU_CORES,
        "ram_gb": $RAM_GB,
        "disk_total_gb": $DISK_TOTAL,
        "disk_used_gb": $DISK_USED,
        "disk_mount_point": "/var/lib/mysql"
    }
}
EOF

echo "Data collected and saved to $OUTPUT_FILE"
echo "Role detected: $ROLE"
