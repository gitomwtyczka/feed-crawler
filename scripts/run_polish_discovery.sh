#!/usr/bin/env bash
# run_polish_discovery.sh — runs the PL feed discovery script inside Docker
set -euo pipefail

echo "=== Running Polish Feed Discovery ==="
cd /opt/feed-crawler

# Run inside web container (has Python + deps)
docker exec crawler-web python add_polish_feeds.py 2>&1 || {
    echo "Script not in container, trying direct Python..."
    docker exec crawler-web python -c "
import sys; sys.path.insert(0, '.')
from add_polish_feeds import add_feeds
print('Starting discovery...')
r = add_feeds()
print(f'Results: {r}')
" 2>&1 || echo "Script not available in container. Need to rebuild."
}

echo "=== Done ==="
