#!/usr/bin/env bash
# reset_and_wait.sh — reset old AI data + wait for new enrichment
docker exec crawler-db psql -U crawler -d feed_crawler -c "UPDATE articles SET ai_processed=false, ai_category=NULL, ai_keywords=NULL, ai_sentiment=NULL WHERE ai_processed=true;"
echo "--- Waiting 90s for enrichment cycle ---"
sleep 90
echo "--- AI status ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true AND ai_category IS NOT NULL) as with_ai FROM articles;"
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,55) as title, ai_category, LEFT(ai_keywords,40) as keywords, ai_sentiment FROM articles WHERE ai_category IS NOT NULL ORDER BY fetched_at DESC LIMIT 5;"
echo "--- Daemon AI logs ---"
docker logs crawler-daemon --tail 30 2>&1 | grep -i 'brain\|enrich\|AI:' || echo "no AI logs yet"
