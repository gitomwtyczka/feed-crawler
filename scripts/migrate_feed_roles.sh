#!/bin/bash
# Migration: Add aggregate/child feed support columns
# Run on VPS inside the Docker container

set -e

echo "=== Feed Aggregate/Child Migration ==="

cd /app

# Run migration via Python (SQLAlchemy doesn't auto-migrate)
python3 -c "
from src.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Add new columns (IF NOT EXISTS for idempotency)
    migrations = [
        'ALTER TABLE feeds ADD COLUMN IF NOT EXISTS parent_feed_id INTEGER REFERENCES feeds(id)',
        'ALTER TABLE feeds ADD COLUMN IF NOT EXISTS feed_role VARCHAR(20) DEFAULT \'standalone\'',
        'ALTER TABLE feeds ADD COLUMN IF NOT EXISTS audit_interval INTEGER DEFAULT 360',
        'ALTER TABLE feeds ADD COLUMN IF NOT EXISTS last_audit TIMESTAMP',
    ]
    for sql in migrations:
        try:
            conn.execute(text(sql))
            print(f'  OK: {sql[:60]}...')
        except Exception as e:
            print(f'  SKIP: {e}')
    conn.commit()

print('Migration complete!')

# Verify
result = conn.execute(text(\"\"\"
    SELECT column_name, data_type, column_default
    FROM information_schema.columns
    WHERE table_name = 'feeds'
    AND column_name IN ('parent_feed_id', 'feed_role', 'audit_interval', 'last_audit')
    ORDER BY column_name
\"\"\"))
for row in result:
    print(f'  ✅ {row[0]}: {row[1]} (default: {row[2]})')
"

echo "=== Migration done ==="
