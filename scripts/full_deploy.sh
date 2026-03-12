#!/usr/bin/env bash
# full_deploy.sh
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker compose build 2>&1 | tail -5
docker compose up -d 2>&1 | tail -5
sleep 45
echo "--- AI check after 45s ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true) as done FROM articles;"
echo "--- Latest AI logs ---"
docker logs crawler-daemon --tail 10 2>&1 | grep -i 'enrich\|brain\|AI' || echo "no AI logs yet"
echo "--- Sample AI articles ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,50), ai_category, ai_sentiment FROM articles WHERE ai_processed=true AND ai_category IS NOT NULL LIMIT 5;"
