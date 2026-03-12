#!/usr/bin/env bash
# deploy_reprint.sh — deploy reprint detection + DB migration
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3

echo "--- DB migration: add reprint columns ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
ALTER TABLE articles ADD COLUMN IF NOT EXISTS reprint_type VARCHAR(20);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS original_article_id INTEGER REFERENCES articles(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS similarity_score FLOAT;
"

echo "--- Rebuild + restart ---"
docker compose build 2>&1 | tail -5
docker compose up -d 2>&1 | tail -5

echo "--- Wait 90s for AI+reprint to fire ---"
sleep 90

echo "--- Reprint results ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT reprint_type, COUNT(*) FROM articles 
WHERE reprint_type IS NOT NULL 
GROUP BY reprint_type;
"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT LEFT(title,45), reprint_type, similarity_score 
FROM articles 
WHERE reprint_type IS NOT NULL 
ORDER BY fetched_at DESC LIMIT 5;
"
echo "--- AI+Reprint logs ---"
docker logs crawler-daemon --tail 10 2>&1 | grep -i 'AI:\|enrich' || echo "no logs yet"
