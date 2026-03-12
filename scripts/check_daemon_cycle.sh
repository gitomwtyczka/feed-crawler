#!/usr/bin/env bash
# check_daemon_cycle.sh — check if daemon finished first cycle + when AI last ran
echo "--- Daemon uptime ---"
docker ps --filter name=crawler-daemon --format "{{.Status}}"
echo "--- Check if initial cycle completed ---"
docker logs crawler-daemon 2>&1 | grep -i 'cycle\|scout complete\|enrich\|AI:' | tail -20
echo "--- Scheduler job list ---"
docker logs crawler-daemon 2>&1 | grep -i 'Added job\|started\|scheduler' | tail -10
echo "--- Total AI processed ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true AND ai_category IS NOT NULL) FROM articles;"
