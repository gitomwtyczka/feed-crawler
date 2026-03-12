#!/usr/bin/env bash
echo "--- Test discover + search ---"
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -o /dev/null -w "GET /login      → %{http_code}\n" http://localhost:8002/login
# Login first
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST -d "username=admin&password=admin" -o /dev/null -w "POST /login     → %{http_code} redirect: %{redirect_url}\n" -L http://localhost:8002/login
# Test protected routes with cookie
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -o /dev/null -w "GET /admin/discover → %{http_code}\n" http://localhost:8002/admin/discover
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -o /dev/null -w "GET /search        → %{http_code}\n" "http://localhost:8002/search?q=orlen"
echo ""
echo "--- search results ---"
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt "http://localhost:8002/search?q=orlen" 2>&1 | grep -o "results for" || echo "no search page"
echo ""
echo "--- discover page ---"
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt http://localhost:8002/admin/discover 2>&1 | grep -o "Source Discovery" || echo "no discover page"
