#!/bin/bash
# Monitor makapix.club visitor statistics
# Prints unique visitors (IPs) and total visits every 15 seconds

LOG_FILE="/var/log/caddy/access.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Error: Log file not found at $LOG_FILE"
    exit 1
fi

echo "Monitoring makapix.club traffic..."
echo "Press Ctrl+C to stop"
echo ""

while true; do
    # Extract all client_ip values from JSON logs and count unique/total
    if [ -f "$LOG_FILE" ] && [ -s "$LOG_FILE" ]; then
        STATS=$(grep -o '"client_ip":"[^"]*"' "$LOG_FILE" 2>/dev/null | \
                cut -d'"' -f4 | \
                sort | \
                awk '{
                    total++
                    ips[$1]++
                }
                END {
                    print length(ips), total
                }')
        
        UNIQUE_IPS=$(echo "$STATS" | awk '{print $1}')
        TOTAL_VISITS=$(echo "$STATS" | awk '{print $2}')
        
        # Default to 0 if empty
        UNIQUE_IPS=${UNIQUE_IPS:-0}
        TOTAL_VISITS=${TOTAL_VISITS:-0}
    else
        UNIQUE_IPS=0
        TOTAL_VISITS=0
    fi
    
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$TIMESTAMP] Unique visitors: $UNIQUE_IPS | Total visits: $TOTAL_VISITS"
    
    sleep 15
done

