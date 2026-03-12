#!/usr/bin/env bash
# fix_502.sh — diagnose and fix 502
echo "--- Container status ---"
docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep crawler
echo ""
echo "--- Web container logs (last 30 lines) ---"
docker logs crawler-web --tail 30 2>&1
echo ""
echo "--- Daemon logs (last 10 lines) ---"
docker logs crawler-daemon --tail 10 2>&1
