#!/usr/bin/env bash
# deploy_and_reset.sh
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
echo "--- Reset bad Bielik AI data ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "UPDATE articles SET ai_processed=false, ai_category=NULL, ai_keywords=NULL, ai_sentiment=NULL WHERE ai_processed=true;"
echo "--- Rebuild + restart ---"
docker compose build --no-cache crawler-web crawler-daemon 2>&1 | tail -5
docker compose up -d 2>&1 | tail -5
echo "--- Done ---"
