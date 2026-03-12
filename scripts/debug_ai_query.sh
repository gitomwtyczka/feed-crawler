#!/usr/bin/env bash
# debug_ai_query.sh — check what the AI enrichment query finds
set -euo pipefail

echo "--- PL articles in last 24h, ai_processed=false ---"
docker exec crawler-daemon python -c "
from src.database import SessionLocal
from src.models import Article, Feed
from datetime import datetime, timedelta

db = SessionLocal()
cutoff = datetime.utcnow() - timedelta(hours=24)

# Check total PL articles in last 24h
total_pl = db.query(Article).join(Feed, Article.feed_id == Feed.id).filter(
    Article.fetched_at >= cutoff,
    Feed.language == 'pl',
).count()
print(f'Total PL articles (24h): {total_pl}')

# Check unprocessed PL articles
unprocessed = db.query(Article).join(Feed, Article.feed_id == Feed.id).filter(
    Article.ai_processed.is_(False),
    Article.fetched_at >= cutoff,
    Feed.language == 'pl',
).count()
print(f'Unprocessed PL articles (24h): {unprocessed}')

# Check what ai_processed looks like  
nulls = db.query(Article).filter(Article.ai_processed.is_(None)).count()
falses = db.query(Article).filter(Article.ai_processed == False).count()
print(f'ai_processed=NULL: {nulls}')
print(f'ai_processed=False: {falses}')

# Sample a PL article
sample = db.query(Article).join(Feed, Article.feed_id == Feed.id).filter(
    Article.fetched_at >= cutoff,
    Feed.language == 'pl',
).first()
if sample:
    print(f'Sample: {sample.title[:60]}... ai_processed={sample.ai_processed}')
else:
    print('No PL articles found!')
db.close()
" 2>&1
