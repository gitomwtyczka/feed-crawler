#!/usr/bin/env bash
# deploy_and_verify_ai.sh — full rebuild + verify AI enrichment fires
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker compose build 2>&1 | tail -5
# Reset old bad AI data
docker exec crawler-db psql -U crawler -d feed_crawler -c "UPDATE articles SET ai_processed=false, ai_category=NULL, ai_keywords=NULL, ai_sentiment=NULL WHERE ai_processed=true;" 2>/dev/null || true
docker compose up -d 2>&1 | tail -5
echo "--- Waiting 60s for AI enrichment to fire ---"
sleep 60
echo "--- AI status ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FROM articles WHERE ai_processed=true AND ai_category IS NOT NULL;"
echo "--- AI samples ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,50), ai_category, LEFT(ai_keywords,35), ai_sentiment FROM articles WHERE ai_category IS NOT NULL LIMIT 5;"
echo "--- AI daemon logs ---"
docker logs crawler-daemon --tail 15 2>&1 | grep -i 'AI:\|enrich\|brain' || echo "no AI logs"
