#!/usr/bin/env bash
# test_ai_router.sh — run on Oracle VPS to check if AI Router is reachable
set -euo pipefail

echo "=== Testing AI Router connectivity from Oracle VPS ==="
echo "Target: http://95.179.201.157:8000/health"

curl -s --connect-timeout 5 http://95.179.201.157:8000/health 2>&1 || echo "BLOCKED — firewall not allowing Oracle IP"

echo ""
echo "=== Oracle VPS public IP ==="
curl -s ifconfig.me 2>/dev/null || echo "unknown"
echo ""
