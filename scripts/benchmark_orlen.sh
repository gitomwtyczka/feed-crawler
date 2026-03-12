#!/usr/bin/env bash
# benchmark_orlen.sh — compare our coverage vs Google News for "Orlen"
set -euo pipefail

echo "=== BENCHMARK: PKN Orlen — Our Crawler vs Google News ==="
echo ""

echo "--- 1. Our articles mentioning 'Orlen' (last 7 days) ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT COUNT(*) as total_orlen_articles
FROM articles 
WHERE (LOWER(title) LIKE '%orlen%' OR LOWER(summary) LIKE '%orlen%')
AND fetched_at > NOW() - INTERVAL '7 days';
"

echo ""
echo "--- 2. Unique sources that mention 'Orlen' ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT f.name, COUNT(a.id) as mentions
FROM articles a
JOIN feeds f ON a.feed_id = f.id
WHERE (LOWER(a.title) LIKE '%orlen%' OR LOWER(a.summary) LIKE '%orlen%')
AND a.fetched_at > NOW() - INTERVAL '7 days'
GROUP BY f.name
ORDER BY mentions DESC
LIMIT 30;
"

echo ""
echo "--- 3. Sample Orlen articles (latest 15) ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT a.title, f.name as source, a.published_at::date as date
FROM articles a
JOIN feeds f ON a.feed_id = f.id
WHERE (LOWER(a.title) LIKE '%orlen%' OR LOWER(a.summary) LIKE '%orlen%')
AND a.fetched_at > NOW() - INTERVAL '7 days'
ORDER BY a.published_at DESC NULLS LAST
LIMIT 15;
"

echo ""
echo "--- 4. Total PL feed stats ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT 
  COUNT(*) as total_feeds,
  COUNT(*) FILTER (WHERE language='pl') as pl_feeds,
  COUNT(*) FILTER (WHERE is_active=true) as active_feeds
FROM feeds;
"

echo ""
echo "--- 5. Articles last 7 days total ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT COUNT(*) as articles_7d FROM articles WHERE fetched_at > NOW() - INTERVAL '7 days';
"

echo "=== BENCHMARK DONE ==="
