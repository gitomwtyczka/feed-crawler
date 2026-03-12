#!/usr/bin/env bash
# run_gn_discovery.sh — run Google News PL discovery with URL unwrap
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker cp discover_google_news_pl.py crawler-web:/app/discover_google_news_pl.py
echo "--- Running Google News PL Discovery (this takes ~5 min) ---"
docker exec crawler-web timeout 600 python /app/discover_google_news_pl.py 2>&1 | tail -40
echo ""
echo "=== Feed totals ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(*) FROM feeds WHERE is_active=true GROUP BY language ORDER BY COUNT DESC;"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(DISTINCT SPLIT_PART(rss_url, '/', 3)) as unique_domains FROM feeds WHERE is_active=true;"
echo "=== AI progress ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FROM articles WHERE ai_processed=true AND ai_category IS NOT NULL;"
