#!/usr/bin/env bash
# benchmark_multi.sh — compare coverage for multiple Polish brands
set -euo pipefail

echo "=============================================="
echo " BENCHMARK: Multi-Brand Coverage (7 days)"
echo "=============================================="

BRANDS=("orlen" "biedronka" "allegro" "pzu" "kghm" "tvp" "tusk" "duda")

for BRAND in "${BRANDS[@]}"; do
  echo ""
  echo "━━━ $BRAND ━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  docker exec crawler-db psql -U crawler -d feed_crawler -t -c "
  SELECT 
    '$BRAND' as brand,
    COUNT(*) as articles,
    COUNT(DISTINCT a.feed_id) as sources
  FROM articles a
  WHERE (LOWER(a.title) LIKE '%${BRAND}%' OR LOWER(a.summary) LIKE '%${BRAND}%')
  AND a.fetched_at > NOW() - INTERVAL '7 days';
  "

  echo "  Top sources:"
  docker exec crawler-db psql -U crawler -d feed_crawler -t -c "
  SELECT '    ' || f.name || ' (' || COUNT(*) || ')'
  FROM articles a JOIN feeds f ON a.feed_id = f.id
  WHERE (LOWER(a.title) LIKE '%${BRAND}%' OR LOWER(a.summary) LIKE '%${BRAND}%')
  AND a.fetched_at > NOW() - INTERVAL '7 days'
  GROUP BY f.name ORDER BY COUNT(*) DESC LIMIT 5;
  "
done

echo ""
echo "=============================================="
echo " SUMMARY TABLE"
echo "=============================================="
docker exec crawler-db psql -U crawler -d feed_crawler -c "
SELECT brand, articles, sources FROM (
  VALUES 
    ('orlen', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%orlen%' OR LOWER(summary) LIKE '%orlen%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%orlen%' OR LOWER(summary) LIKE '%orlen%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('biedronka', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%biedronka%' OR LOWER(summary) LIKE '%biedronka%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%biedronka%' OR LOWER(summary) LIKE '%biedronka%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('allegro', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%allegro%' OR LOWER(summary) LIKE '%allegro%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%allegro%' OR LOWER(summary) LIKE '%allegro%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('pzu', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%pzu%' OR LOWER(summary) LIKE '%pzu%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%pzu%' OR LOWER(summary) LIKE '%pzu%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('kghm', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%kghm%' OR LOWER(summary) LIKE '%kghm%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%kghm%' OR LOWER(summary) LIKE '%kghm%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('tusk', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%tusk%' OR LOWER(summary) LIKE '%tusk%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%tusk%' OR LOWER(summary) LIKE '%tusk%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('duda', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%duda%' OR LOWER(summary) LIKE '%duda%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%duda%' OR LOWER(summary) LIKE '%duda%') AND fetched_at > NOW() - INTERVAL '7 days')),
    ('tvp', (SELECT COUNT(*) FROM articles WHERE (LOWER(title) LIKE '%tvp%' OR LOWER(summary) LIKE '%tvp%') AND fetched_at > NOW() - INTERVAL '7 days'), (SELECT COUNT(DISTINCT feed_id) FROM articles WHERE (LOWER(title) LIKE '%tvp%' OR LOWER(summary) LIKE '%tvp%') AND fetched_at > NOW() - INTERVAL '7 days'))
) AS t(brand, articles, sources)
ORDER BY articles DESC;
"

echo "=== DONE ==="
