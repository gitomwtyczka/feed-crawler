"""Run a single full fetch cycle: config→DB→fetch→dedup→store."""

import asyncio
import logging
import sys

sys.path.insert(0, ".")

from src.database import init_db
from src.scheduler import run_fetch_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

init_db()

result = asyncio.run(run_fetch_cycle())
print()
print("=== CYCLE RESULT ===")
print(f"Feeds processed: {result['feeds']}")
print(f"New articles:    {result['articles_new']}")
print(f"Errors:          {result['errors']}")
