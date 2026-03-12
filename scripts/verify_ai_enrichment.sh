#!/usr/bin/env bash
# verify_ai_enrichment.sh — check if Bielik/Gemini is processing articles
set -euo pipefail

echo "=== AI Enrichment Verification ==="

echo "--- 1. Articles processed by AI ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT 
  COUNT(*) FILTER (WHERE ai_processed = true) as processed,
  COUNT(*) FILTER (WHERE ai_processed = false OR ai_processed IS NULL) as unprocessed,
  COUNT(*) as total
FROM articles;
"

echo "--- 2. Sample AI-processed articles ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT title, ai_category, ai_sentiment, LEFT(ai_summary, 80) as summary_preview
FROM articles 
WHERE ai_processed = true
ORDER BY fetched_at DESC
LIMIT 10;
"

echo "--- 3. AI enrichment job in scheduler logs ---"
docker logs crawler-daemon --tail 50 2>&1 | grep -i 'ai\|enrich\|bielik\|router' || echo "No AI logs found"

echo "--- 4. AI Router health from crawler ---"
docker exec crawler-web python -c "
import httpx
try:
    r = httpx.get('http://95.179.201.157:8000/health', timeout=5)
    print('Router:', r.json())
except Exception as e:
    print('FAIL:', e)
" 2>&1

echo "=== DONE ==="
