#!/usr/bin/env bash
# run_pl_discovery.sh — run inside Docker on Oracle VPS
set -euo pipefail

echo "=== Polish Feed Discovery ==="
cd /opt/feed-crawler

# Rebuild to include new scripts
docker compose up -d --build 2>&1 | tail -3

# Run discovery script inside container
docker exec crawler-web python add_polish_feeds.py 2>&1

echo "=== Feed count after discovery ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(id) as cnt FROM feeds WHERE is_active=true GROUP BY language ORDER BY cnt DESC;"

echo "=== Done ==="
