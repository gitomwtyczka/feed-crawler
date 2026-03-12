#!/usr/bin/env bash
# run_fmcg_alerts.sh — deploy + run FMCG brand monitoring feeds
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker cp add_google_alerts.py crawler-web:/app/add_google_alerts.py
docker exec crawler-web python /app/add_google_alerts.py 2>&1

echo ""
echo "=== Feed count after FMCG ==="
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT language, COUNT(id) as cnt FROM feeds WHERE is_active=true GROUP BY language ORDER BY cnt DESC;"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(id) as total FROM feeds;"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT feed_type, COUNT(id) FROM feeds GROUP BY feed_type ORDER BY COUNT DESC;"
