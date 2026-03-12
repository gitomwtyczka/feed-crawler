#!/usr/bin/env bash
# fix_gnews2.sh
docker exec crawler-db psql -U crawler -d feed_crawler -c "UPDATE feeds SET fetch_interval=60 WHERE rss_url LIKE '%news.google.com%';"
echo "--- GNews intervals ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT feed_type, fetch_interval, COUNT(*) FROM feeds GROUP BY feed_type, fetch_interval ORDER BY feed_type;"
echo "--- AI processed ---"
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true) as done, COUNT(*) FILTER (WHERE ai_processed IS NOT true) as todo FROM articles;"
echo "--- AI samples ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,50) as title, ai_category, ai_sentiment FROM articles WHERE ai_processed=true LIMIT 5;"
echo "--- daemon AI logs ---"
docker logs crawler-daemon --tail 20 2>&1 | grep -i 'enrich\|bielik\|brain' || echo "no AI logs"
