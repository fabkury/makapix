#!/bin/bash

# Monitor CTA website statistics from Caddy access logs
# Shows total visits and unique visitors every 15 seconds

LOG_FILE="/var/log/caddy/access.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV_FILE="${SCRIPT_DIR}/cta-stats.csv"
CTA_DOMAINS=("makapix.club" "www.makapix.club")

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to get statistics
get_stats() {
    # Filter logs for CTA domains and extract relevant fields
    local temp_file=$(mktemp)
    
    # Extract entries for CTA domains with host and client_ip
    jq -r --argjson domains "$(printf '%s\n' "${CTA_DOMAINS[@]}" | jq -R . | jq -s .)" '
        select(.request.host as $h | $domains | index($h)) |
        "\(.request.client_ip)|\(.ts)"
    ' "$LOG_FILE" 2>/dev/null > "$temp_file"
    
    if [ ! -s "$temp_file" ]; then
        echo "0|0"
        rm -f "$temp_file"
        return
    fi
    
    # Count total visits
    local total_visits=$(wc -l < "$temp_file" | tr -d ' ')
    
    # Count unique visitors (unique IPs)
    local unique_visitors=$(cut -d'|' -f1 "$temp_file" | sort -u | wc -l | tr -d ' ')
    
    echo "${total_visits}|${unique_visitors}"
    rm -f "$temp_file"
}

# Function to format and display statistics
display_stats() {
    local stats=$1
    local total_visits=$(echo "$stats" | cut -d'|' -f1)
    local unique_visitors=$(echo "$stats" | cut -d'|' -f2)
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    printf "${BLUE}[%s]${NC} " "$timestamp"
    printf "${GREEN}Total Visits:${NC} %-10s " "$total_visits"
    printf "${GREEN}Unique Visitors:${NC} %s\n" "$unique_visitors"
}

# Function to append statistics to CSV file
append_to_csv() {
    local stats=$1
    local total_visits=$(echo "$stats" | cut -d'|' -f1)
    local unique_visitors=$(echo "$stats" | cut -d'|' -f2)
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local csv_dir=$(dirname "$CSV_FILE")
    
    # Create directory if it doesn't exist
    mkdir -p "$csv_dir"
    
    # Write header if file doesn't exist
    if [ ! -f "$CSV_FILE" ]; then
        echo "timestamp,total_visits,unique_visitors" > "$CSV_FILE"
    fi
    
    # Append data row
    echo "${timestamp},${total_visits},${unique_visitors}" >> "$CSV_FILE"
}

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "Error: Log file not found at $LOG_FILE" >&2
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Please install jq." >&2
    exit 1
fi

# Check if log file is readable
if [ ! -r "$LOG_FILE" ]; then
    echo "Error: Cannot read log file $LOG_FILE. Check permissions." >&2
    exit 1
fi

echo "Monitoring CTA website statistics from $LOG_FILE"
echo "CSV output: $CSV_FILE"
echo "Press Ctrl+C to stop"
echo "----------------------------------------"

# Main loop
while true; do
    stats=$(get_stats)
    display_stats "$stats"
    append_to_csv "$stats"
    sleep 120
done

