#!/usr/bin/env bash
# check_gn_results.sh
echo "=== Feed totals after GN discovery ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(*) FROM feeds WHERE is_active=true GROUP BY language ORDER BY COUNT DESC;"
echo "=== Unique domains ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(DISTINCT SPLIT_PART(rss_url, '/', 3)) FROM feeds WHERE is_active=true;"
echo "=== AI progress ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FROM articles WHERE ai_processed=true AND ai_category IS NOT NULL;"
echo "=== AI samples ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,50), ai_category, ai_sentiment FROM articles WHERE ai_category IS NOT NULL ORDER BY fetched_at DESC LIMIT 5;"
