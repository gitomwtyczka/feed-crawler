#!/usr/bin/env bash
# rebuild_and_check.sh — force rebuild + check logs
set -euo pipefail
cd /opt/feed-crawler

echo "--- Force rebuild ---"
docker compose build 2>&1 | tail -10
docker compose up -d 2>&1 | tail -5

echo "--- Wait 30s for startup ---"
sleep 30

echo "--- Daemon logs (last 30) ---"
docker logs crawler-daemon --tail 30 2>&1

echo "--- AI status ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true) as done FROM articles;"
