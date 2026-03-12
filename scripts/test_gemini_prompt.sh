#!/usr/bin/env bash
# test_gemini_prompt.sh — test Gemini with real article and debug response
set -euo pipefail

echo "--- Test enrichment with real article ---"
docker exec crawler-daemon python -c "
import logging
logging.basicConfig(level=logging.INFO)
from src.ai_router import _post_sync

# Test 1: task=summarize (Gemini)
print('=== Test 1: task=summarize ===')
r1 = _post_sync('/ask', {
    'prompt': 'Przeanalizuj ten polski artykuł: \"Orlen kupuje Grupę Azoty Polyolefins za 1.14 mld zł. To największa transakcja w polskiej chemii od lat.\"\n\nOdpowiedz w formacie:\nKATEGORIA: gospodarka\nSŁOWA KLUCZOWE: Orlen, Grupa Azoty, chemia, przejęcie\nSENTYMENT: neutral',
    'task': 'summarize',
    'max_tokens': 200,
})
print(f'Response: {r1}')

# Test 2: without task hint (let router decide)
print()
print('=== Test 2: no task hint ===')
r2 = _post_sync('/ask', {
    'prompt': 'Przeanalizuj ten polski artykuł: \"Orlen kupuje Grupę Azoty Polyolefins za 1.14 mld zł. To największa transakcja w polskiej chemii od lat.\"\n\nOdpowiedz w formacie:\nKATEGORIA: gospodarka\nSŁOWA KLUCZOWE: Orlen, Grupa Azoty, chemia, przejęcie\nSENTYMENT: neutral',
    'max_tokens': 200,
})
print(f'Response: {r2}')

# Test 3: direct /ask without structured format
print()
print('=== Test 3: simple ask ===')
r3 = _post_sync('/ask', {
    'prompt': 'Jaka jest kategoria tego artykułu (polityka/gospodarka/sport): Orlen kupuje Grupę Azoty Polyolefins za 1.14 mld zł',
    'max_tokens': 50,
})
print(f'Response: {r3}')
" 2>&1
