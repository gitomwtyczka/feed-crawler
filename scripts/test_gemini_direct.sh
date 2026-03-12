#!/usr/bin/env bash
# test_gemini_direct.sh — test AI enrichment directly from daemon container
set -euo pipefail

echo "--- Test Gemini from daemon ---"
docker exec crawler-daemon python -c "
import logging
logging.basicConfig(level=logging.INFO)
from src.ai_router import _post_sync, check_router_health

h = check_router_health()
print(f'Health: {h}')

# Test with task=summarize (routes to Gemini)
result = _post_sync('/ask', {
    'prompt': 'Przeanalizuj: Orlen kupuje Grupę Azoty za 1 mld PLN. Odpowiedz: KATEGORIA: [polityka/gospodarka/sport] SENTYMENT: [positive/negative/neutral]',
    'task': 'summarize',
    'max_tokens': 100,
})
print(f'Gemini result: {result}')
" 2>&1

echo ""
echo "--- Check scheduler jobs ---"
docker exec crawler-daemon python -c "
from src.scheduler import run_scheduled
print('Import OK')
" 2>&1

echo ""
echo "--- Recent daemon logs with AI ---"
docker logs crawler-daemon 2>&1 | grep -i 'ai\|enrich\|gemini\|router' | tail -10 || echo "no AI logs"
