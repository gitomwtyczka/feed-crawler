#!/usr/bin/env bash
# run_google_news_only.sh — re-run Google News PL discovery after bugfix
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker cp discover_google_news_pl.py crawler-web:/app/discover_google_news_pl.py
docker exec crawler-web python /app/discover_google_news_pl.py 2>&1

echo ""
echo "=== Final PL feed count ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(id) as cnt FROM feeds WHERE is_active=true GROUP BY language ORDER BY cnt DESC;"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(id) as total FROM feeds;"
