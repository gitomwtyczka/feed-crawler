#!/usr/bin/env bash
# run_pl_direct.sh — run PL discovery directly on VPS host (not inside Docker)
set -euo pipefail

echo "=== Polish Feed Discovery (direct) ==="
cd /opt/feed-crawler

# Install deps in temp venv if needed
if [ ! -d "/tmp/crawler_venv" ]; then
    python3 -m venv /tmp/crawler_venv
    /tmp/crawler_venv/bin/pip install -q sqlalchemy psycopg2-binary httpx feedparser python-dotenv 2>&1
fi

# Run with DB connection from .env
export $(grep -v '^#' .env | xargs)
/tmp/crawler_venv/bin/python add_polish_feeds.py 2>&1

echo ""
echo "=== Feed count after discovery ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(id) as cnt FROM feeds WHERE is_active=true GROUP BY language ORDER BY cnt DESC;"

echo "=== Done ==="
