#!/usr/bin/env bash
# check_logs.sh — show recent container logs
echo "=== crawler-web logs (last 30 lines) ==="
docker logs crawler-web --tail 30 2>&1

echo ""
echo "=== crawler-daemon logs (last 30 lines) ==="
docker logs crawler-daemon --tail 30 2>&1

echo ""
echo "=== DB tables check ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c '\dt'
