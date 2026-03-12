#!/usr/bin/env bash
# deploy.sh — pull + rebuild + restart containers
set -euo pipefail

echo "=== Deploy Feed Crawler ==="
cd /opt/feed-crawler
git pull origin main 2>&1
docker compose up -d --build 2>&1 | tail -5
echo ""
echo "=== Container status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>&1
echo "=== Deploy complete ==="
