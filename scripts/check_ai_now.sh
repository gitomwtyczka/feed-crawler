#!/usr/bin/env bash
# check_ai_now.sh
docker exec crawler-db psql -U crawler -d feed_crawler -t -c "SELECT COUNT(*) FILTER (WHERE ai_processed=true) as done, COUNT(*) FILTER (WHERE ai_category IS NOT NULL) as with_cat FROM articles;"
docker exec crawler-db psql -U crawler -d feed_crawler -c "SELECT LEFT(title,60) as title, ai_category, ai_keywords, ai_sentiment FROM articles WHERE ai_category IS NOT NULL LIMIT 5;"
docker logs crawler-daemon --tail 20 2>&1 | grep -i 'enrich\|brain\|AI\|bielik' || echo "no AI logs"
