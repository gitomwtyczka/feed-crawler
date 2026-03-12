#!/usr/bin/env bash
# fix_502_deploy.sh — rebuild + verify site is up
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker compose build 2>&1 | tail -3
docker compose up -d 2>&1 | tail -5
sleep 10
echo "--- Container status ---"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep crawler
echo ""
echo "--- Web health ---"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "FAIL"
echo ""
echo "--- AI+Reprint progress ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FROM articles WHERE ai_processed=true AND ai_category IS NOT NULL;"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FROM articles WHERE reprint_type IS NOT NULL;"
