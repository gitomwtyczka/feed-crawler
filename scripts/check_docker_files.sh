#!/usr/bin/env bash
# check_docker_files.sh — verify what's inside the container
set -euo pipefail

echo "=== Files in /app/ ==="
docker exec crawler-web ls -la /app/*.py 2>&1 || echo "No .py files in /app root"

echo ""
echo "=== Docker image rebuild ==="
cd /opt/feed-crawler
docker compose build --no-cache crawler-web 2>&1 | tail -10

echo ""
echo "=== Check again ==="
docker compose up -d 2>&1 | tail -3
sleep 2
docker exec crawler-web ls -la /app/*.py 2>&1 || echo "Still no .py files"
