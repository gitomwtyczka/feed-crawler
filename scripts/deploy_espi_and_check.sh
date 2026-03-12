#!/usr/bin/env bash
# deploy_espi_and_check.sh
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker cp add_espi_feeds.py crawler-web:/app/add_espi_feeds.py
docker exec crawler-web python /app/add_espi_feeds.py 2>&1
echo ""
echo "=== AI enrichment progress ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true AND ai_category IS NOT NULL) as ai_done FROM articles;"
echo "=== Feed totals ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(*) FROM feeds WHERE is_active=true GROUP BY language ORDER BY COUNT DESC;"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(DISTINCT SPLIT_PART(rss_url, '/', 3)) as unique_domains FROM feeds WHERE is_active=true;"
