#!/usr/bin/env bash
# fix_gnews_rate_and_check_ai.sh — rate-limit Google News feeds + check AI enrichment
set -euo pipefail

echo "=== 1. Fix Google News fetch intervals (15min → 60min) ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "
UPDATE feeds 
SET fetch_interval = 60 
WHERE feed_type = 'google_news' OR rss_url LIKE '%news.google.com%';
"
echo "Updated Google News feeds to 60 min interval"

echo ""
echo "=== 2. Check Google News feed intervals ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT name, fetch_interval, feed_type 
FROM feeds 
WHERE feed_type = 'google_news' OR rss_url LIKE '%news.google.com%'
LIMIT 10;
"

echo ""
echo "=== 3. AI Enrichment status ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT 
  COUNT(*) FILTER (WHERE ai_processed = true) as processed,
  COUNT(*) FILTER (WHERE ai_processed = false OR ai_processed IS NULL) as unprocessed
FROM articles;
"

echo ""
echo "=== 4. Sample AI-processed articles ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT title, ai_category, ai_keywords, ai_sentiment
FROM articles 
WHERE ai_processed = true
ORDER BY fetched_at DESC
LIMIT 5;
"

echo ""
echo "=== 5. Recent daemon AI logs ==="
docker logs crawler-daemon --tail 30 2>&1 | grep -i 'ai\|enrich\|bielik\|🧠' || echo "No AI logs yet"
