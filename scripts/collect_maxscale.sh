#!/bin/bash
#
# MaxScale Data Collector
# Collects MaxScale configuration, status, and traffic statistics for analysis
#
# Usage: ./collect_maxscale.sh [output_file]
#

OUTPUT_FILE="${1:-maxscale_data.json}"

echo "Collecting MaxScale data..."

# Check if maxctrl is available
if ! command -v maxctrl &> /dev/null; then
    echo "Error: maxctrl not found. Please run this on the MaxScale host."
    exit 1
fi

# Get MaxScale version and uptime
VERSION=$(maxctrl show maxscale 2>/dev/null | grep -i "version" | head -1 | awk '{print $NF}' || echo "unknown")
UPTIME=$(maxctrl show maxscale 2>/dev/null | grep -i "uptime" | awk '{print $NF}' || echo "0")

# Convert uptime to seconds if needed (maxscale reports in various formats)
# Try to extract just the number
UPTIME_SECONDS=$(echo "$UPTIME" | grep -oE '[0-9]+' | head -1 || echo "0")

# Get global connection stats
TOTAL_CONNECTIONS=$(maxctrl show maxscale 2>/dev/null | grep -i "total_connections" | awk '{print $NF}' || echo "0")
CURRENT_CONNECTIONS=$(maxctrl show maxscale 2>/dev/null | grep -i "current_connections" | awk '{print $NF}' || echo "0")

echo "Collecting server information with statistics..."
# Get detailed server stats using JSON output
SERVERS=$(maxctrl list servers --tsv 2>/dev/null | tail -n +2 | while read line; do
    NAME=$(echo "$line" | awk '{print $1}')
    ADDRESS=$(echo "$line" | awk '{print $2}')
    PORT=$(echo "$line" | awk '{print $3}')
    CONNECTIONS=$(echo "$line" | awk '{print $4}')
    STATE=$(echo "$line" | awk '{print $5}')
    
    # Get detailed stats for this server
    SERVER_DETAILS=$(maxctrl show server "$NAME" 2>/dev/null)
    TOTAL_CONN=$(echo "$SERVER_DETAILS" | grep -i "total_connections" | awk '{print $NF}' || echo "null")
    QUERIES=$(echo "$SERVER_DETAILS" | grep -i "queries" | head -1 | awk '{print $NF}' || echo "null")
    
    # Try to get read/write breakdown if available
    READ_QUERIES=$(echo "$SERVER_DETAILS" | grep -i "read_queries\|selects" | awk '{print $NF}' || echo "null")
    WRITE_QUERIES=$(echo "$SERVER_DETAILS" | grep -i "write_queries\|writes" | awk '{print $NF}' || echo "null")
    
    cat << SERVEREOF
{
    "name": "$NAME",
    "address": "$ADDRESS",
    "port": $PORT,
    "state": "$STATE",
    "connections": $CONNECTIONS,
    "total_connections": $TOTAL_CONN,
    "queries": $QUERIES,
    "read_queries": $READ_QUERIES,
    "write_queries": $WRITE_QUERIES
}
SERVEREOF
done | paste -sd ',' -)

echo "Collecting service information with router statistics..."
SERVICES=$(maxctrl list services --tsv 2>/dev/null | tail -n +2 | while read line; do
    NAME=$(echo "$line" | awk '{print $1}')
    ROUTER=$(echo "$line" | awk '{print $2}')
    CONNECTIONS=$(echo "$line" | awk '{print $3}')
    TOTAL_CONN=$(echo "$line" | awk '{print $4}' || echo "null")
    
    # Get detailed service stats
    SERVICE_DETAILS=$(maxctrl show service "$NAME" 2>/dev/null)
    
    # Get servers for this service
    SERVICE_SERVERS=$(echo "$SERVICE_DETAILS" | grep -A 100 "Servers" | grep -B 100 "Parameters" | grep -v "Servers\|Parameters" | awk '{print $1}' | grep -v "^$" | tr '\n' ',' | sed 's/,$//')
    
    # Router statistics (for readwritesplit)
    ROUTE_MASTER=$(echo "$SERVICE_DETAILS" | grep -i "route_master\|routed_to_master" | awk '{print $NF}' || echo "null")
    ROUTE_SLAVE=$(echo "$SERVICE_DETAILS" | grep -i "route_slave\|routed_to_slave" | awk '{print $NF}' || echo "null")
    ROUTE_ALL=$(echo "$SERVICE_DETAILS" | grep -i "route_all\|queries" | head -1 | awk '{print $NF}' || echo "null")
    
    # Transaction statistics
    RW_TRANSACTIONS=$(echo "$SERVICE_DETAILS" | grep -i "rw_transactions" | awk '{print $NF}' || echo "null")
    RO_TRANSACTIONS=$(echo "$SERVICE_DETAILS" | grep -i "ro_transactions" | awk '{print $NF}' || echo "null")
    REPLAYED=$(echo "$SERVICE_DETAILS" | grep -i "replayed_transactions" | awk '{print $NF}' || echo "null")
    
    cat << SERVICEEOF
{
    "name": "$NAME",
    "router": "$ROUTER",
    "connections": $CONNECTIONS,
    "total_connections": $TOTAL_CONN,
    "servers": ["${SERVICE_SERVERS//,/\", \"}"],
    "route_master": $ROUTE_MASTER,
    "route_slave": $ROUTE_SLAVE,
    "route_all": $ROUTE_ALL,
    "rw_transactions": $RW_TRANSACTIONS,
    "ro_transactions": $RO_TRANSACTIONS,
    "replayed_transactions": $REPLAYED
}
SERVICEEOF
done | paste -sd ',' -)

# Build JSON output
cat > "$OUTPUT_FILE" << EOF
{
    "enabled": true,
    "version": "$VERSION",
    "uptime_seconds": $UPTIME_SECONDS,
    "total_connections": $TOTAL_CONNECTIONS,
    "current_connections": $CURRENT_CONNECTIONS,
    "servers": [
        $SERVERS
    ],
    "services": [
        $SERVICES
    ]
}
EOF

echo ""
echo "MaxScale data collected and saved to $OUTPUT_FILE"
echo ""
echo "Summary:"
echo "  - Version: $VERSION"
echo "  - Uptime: $UPTIME_SECONDS seconds"
echo "  - Current connections: $CURRENT_CONNECTIONS"
echo "  - Total connections: $TOTAL_CONNECTIONS"
