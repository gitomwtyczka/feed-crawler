#!/usr/bin/env bash
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker compose build --no-cache web 2>&1 | tail -3
docker compose up -d 2>&1 | tail -3
sleep 8
echo "=== Test client panel ==="
# Login as client
curl -s -c /tmp/cl.txt -X POST -d "username=diaverum&password=test123" -L http://localhost:8002/client/login > /dev/null
curl -s -b /tmp/cl.txt -o /dev/null -w "Dashboard → %{http_code}\n" http://localhost:8002/client/dashboard
curl -s -b /tmp/cl.txt -o /dev/null -w "Project PZU → %{http_code}\n" "http://localhost:8002/client/project/pzu?days=30"
echo "=== Check for Chart.js ==="
curl -s -b /tmp/cl.txt "http://localhost:8002/client/project/pzu?days=30" 2>/dev/null | grep -c 'trendChart' || echo "No chart ❌"
echo "=== Check for KPI hero ==="
curl -s -b /tmp/cl.txt http://localhost:8002/client/dashboard 2>/dev/null | grep -c 'kpi-value' || echo "No KPI ❌"
echo "=== DONE ==="
