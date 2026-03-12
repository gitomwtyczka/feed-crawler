#!/usr/bin/env bash
# check_all_status.sh — full system health check
echo "=== AI Enrichment ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FROM articles WHERE ai_processed=true AND ai_category IS NOT NULL;"
echo "=== Reprint Detection ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT reprint_type, COUNT(*) FROM articles WHERE reprint_type IS NOT NULL GROUP BY reprint_type;"
echo "=== Latest AI+Reprint samples ==="
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,40) as title, ai_category, reprint_type, similarity_score FROM articles WHERE ai_category IS NOT NULL ORDER BY fetched_at DESC LIMIT 8;"
echo "=== Daemon logs ==="
docker logs crawler-daemon --tail 10 2>&1 | grep -i 'AI:\|enrich\|reprint' || echo "no AI logs yet"
