#!/usr/bin/env bash
# daemon_full_log.sh
echo "--- Full daemon logs (first 50 lines = startup) ---"
docker logs crawler-daemon 2>&1 | head -50
echo ""
echo "--- Any errors ---"
docker logs crawler-daemon 2>&1 | grep -i 'error\|exception\|traceback\|fail' | tail -20
echo ""
echo "--- Scheduler + job lines ---"
docker logs crawler-daemon 2>&1 | grep -i 'schedul\|job\|started\|enrich' | tail -20
