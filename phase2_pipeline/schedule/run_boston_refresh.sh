#!/bin/bash
# Monthly Boston refresh — called by launchd (see com.uncornered.boston-refresh.plist).
# Appends each run's output to phase2_pipeline/logs/boston_refresh.log.

set -uo pipefail

PHASE2_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PHASE2_ROOT/logs"
LOG_FILE="$LOG_DIR/boston_refresh.log"
mkdir -p "$LOG_DIR"

{
  echo "=================================================================="
  echo "Run started: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  /usr/bin/python3 -W ignore "$PHASE2_ROOT/fetch/fetch_boston_to_sheets.py"
  status=$?
  if [ $status -eq 0 ]; then
    echo "Run finished OK: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  else
    echo "Run FAILED (exit $status): $(date '+%Y-%m-%d %H:%M:%S %Z')"
  fi
} >> "$LOG_FILE" 2>&1

exit ${status:-1}
