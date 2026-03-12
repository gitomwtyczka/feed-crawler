#!/usr/bin/env bash
# run_ai_direct.sh — manually trigger AI enrichment from daemon
docker exec crawler-daemon python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from datetime import datetime, timedelta
from src.database import SessionLocal
from src.models import Article, Feed
from src.ai_router import _post_sync, check_router_health

print('=== Manual AI enrichment test ===')

h = check_router_health()
print(f'Router health: {h}')

db = SessionLocal()
cutoff = datetime.utcnow() - timedelta(hours=24)

articles = (
    db.query(Article)
    .join(Feed, Article.feed_id == Feed.id)
    .filter(
        Article.ai_processed.is_(False),
        Article.fetched_at >= cutoff,
        Feed.language == 'pl',
    )
    .order_by(Article.fetched_at.desc())
    .limit(2)
    .all()
)
print(f'Found {len(articles)} PL articles to process')

for art in articles:
    print(f'\nProcessing: {art.title[:60]}...')
    text = f'{art.title}. {(art.summary or \"\")[:300]}'
    result = _post_sync('/ask', {
        'prompt': f'Przeanalizuj ten polski artykuł prasowy:\n\n\"{text}\"\n\nOdpowiedz DOKŁADNIE w tym formacie (każda linia osobno):\nKATEGORIA: [polityka, gospodarka, sport, technologia, kultura, nauka, zdrowie, społeczeństwo, prawo, energetyka, inne]\nSŁOWA KLUCZOWE: [max 5 słów kluczowych po przecinku]\nSENTYMENT: [positive, negative, neutral]',
        'max_tokens': 200,
    })
    print(f'Result: {result}')
    if result and result.get('response'):
        resp = result['response']
        for line in resp.split('\n'):
            line = line.strip()
            low = line.upper()
            if 'KATEGORIA' in low and ':' in line:
                val = line.split(':', 1)[1].strip().lower()
                print(f'  → category: {val}')
                art.ai_category = val[:100]
            elif 'KLUCZOWE' in low and ':' in line:
                val = line.split(':', 1)[1].strip()
                print(f'  → keywords: {val}')
                art.ai_keywords = val[:500]
            elif 'SENTYMENT' in low and ':' in line:
                val = line.split(':', 1)[1].strip().lower()
                print(f'  → sentiment: {val}')
                art.ai_sentiment = val[:20]
        art.ai_processed = True
        db.commit()
        print('  ✅ Saved!')

db.close()
print('\n=== Done ===')
" 2>&1
