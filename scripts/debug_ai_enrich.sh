#!/usr/bin/env bash
# debug_ai_enrich.sh — get full error details + test AI from inside container
set -euo pipefail

echo "--- 1. Full AI-related daemon logs ---"
docker logs crawler-daemon 2>&1 | grep -A5 -i 'ai_enrich\|ai_router\|bielik\|enrich' | tail -50

echo ""
echo "--- 2. Test AI Router from INSIDE daemon container ---"
docker exec crawler-daemon python -c "
from src.ai_router import check_router_health, classify_article
import logging
logging.basicConfig(level=logging.DEBUG)

h = check_router_health()
print(f'Health: {h}')

if h:
    r = classify_article('Orlen kupuje Grupę Azoty')
    print(f'Classify: {r}')
else:
    print('Router not reachable from daemon!')
" 2>&1

echo ""
echo "--- 3. Scheduler job list ---"
docker logs crawler-daemon 2>&1 | grep -i 'job\|schedul\|start' | head -20
