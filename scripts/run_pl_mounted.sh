#!/usr/bin/env bash
# run_pl_mounted.sh — copy script into running container, then execute
set -euo pipefail

echo "=== Polish Feed Discovery ==="
cd /opt/feed-crawler

# Copy script into running container
docker cp add_polish_feeds.py crawler-web:/app/add_polish_feeds.py
docker exec crawler-web python /app/add_polish_feeds.py

echo ""
echo "=== Feed count ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(id) as cnt FROM feeds WHERE is_active=true GROUP BY language ORDER BY cnt DESC;"
echo "=== Done ==="
