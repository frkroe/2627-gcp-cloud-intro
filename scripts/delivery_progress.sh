#!/bin/bash
# Lab 3: every 30 s, count how many orders each consumer has started delivering
# since this script started. Stop with Ctrl+C.
#
#   ./scripts/delivery_progress.sh
set -uo pipefail

: "${PROJECT_ID:?run 'source config.env' first}"
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

count() {
  gcloud logging read "timestamp>=\"$SINCE\" AND $1" --project="$PROJECT_ID" \
    --limit=5000 --format="value(timestamp)" 2>/dev/null | wc -l | tr -d ' '
}

VMS='logName:"gcplogs-docker-driver" AND jsonPayload.message:"Delivering order"'
FUNCTION='resource.type="cloud_run_revision" AND resource.labels.service_name="delivery-function" AND textPayload:"Delivering order"'

echo "Counting deliveries since $SINCE (Ctrl+C to stop)"
printf "%-10s %18s %18s\n" "time" "VM(s)" "function"
while true; do
  printf "%-10s %18s %18s\n" "$(date +%H:%M:%S)" "$(count "$VMS")" "$(count "$FUNCTION")"
  sleep 30
done
