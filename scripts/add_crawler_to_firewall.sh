#!/usr/bin/env bash
# add_crawler_to_firewall.sh — run on VPS-LLM (95.179.201.157)
# Adds Oracle ARM crawler IP to UFW allowed list for port 8000
set -euo pipefail

echo "=== Adding Oracle Crawler IP to firewall ==="

# Allow Oracle ARM VPS (crawler) to reach AI Router
ufw allow from 147.224.162.100 to any port 8000 comment 'Oracle ARM - Feed Crawler'

echo ""
echo "=== Current UFW rules for port 8000 ==="
ufw status | grep 8000

echo ""
echo "=== Testing AI Router health ==="
curl -s http://localhost:8000/health | head -c 200

echo ""
echo "=== Done ==="
