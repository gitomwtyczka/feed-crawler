#!/usr/bin/env bash
set -euo pipefail
cd /opt/feed-crawler
git pull origin main 2>&1 | tail -3
docker compose build 2>&1 | tail -3
docker compose up -d 2>&1 | tail -5
sleep 8
echo "--- Auth check: should get 302 redirect to /login ---"
curl -s -o /dev/null -w "HTTP %{http_code} → %{redirect_url}\n" http://localhost:8000/
curl -s -o /dev/null -w "HTTP %{http_code} → %{redirect_url}\n" http://localhost:8000/admin
echo "--- Login page check ---"
curl -s http://localhost:8000/login | grep -o "Admin Login" || echo "NO LOGIN PAGE"
echo "--- Container status ---"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep crawler
