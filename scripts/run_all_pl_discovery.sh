#!/usr/bin/env bash
# run_all_pl_discovery.sh — run Wave 2 + Google News discovery on VPS
set -euo pipefail

echo "=== Full Polish Discovery ==="
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -5

echo ""
echo "=== Wave 2: Curated feeds ==="
docker cp add_polish_feeds_wave2.py crawler-web:/app/add_polish_feeds_wave2.py
docker exec crawler-web python /app/add_polish_feeds_wave2.py 2>&1

echo ""
echo "=== Google News PL Discovery ==="
docker cp discover_google_news_pl.py crawler-web:/app/discover_google_news_pl.py
docker exec crawler-web python /app/discover_google_news_pl.py 2>&1

echo ""
echo "=== Final feed count ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(id) as cnt FROM feeds WHERE is_active=true GROUP BY language ORDER BY cnt DESC;"

echo ""
echo "=== Total ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(id) as total FROM feeds;"

echo "=== Done ==="
