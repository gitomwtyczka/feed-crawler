#!/usr/bin/env bash
# migrate.sh — run on VPS to add missing DB columns
# Usage: scp migrate.sh vps: && ssh vps bash migrate.sh

set -euo pipefail

echo "=== DB Migration: AI columns + journalists table ==="

docker exec crawler-db psql -U crawler -d feed_crawler <<'EOSQL'
-- AI enrichment columns on articles
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ai_category VARCHAR(100);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ai_keywords TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ai_sentiment VARCHAR(20);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS ai_processed BOOLEAN DEFAULT false;

-- Journalists table
CREATE TABLE IF NOT EXISTS journalists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    media_outlet VARCHAR(255),
    beat VARCHAR(255),
    bio TEXT,
    region VARCHAR(100),
    is_verified BOOLEAN NOT NULL DEFAULT false,
    rodo_consent BOOLEAN NOT NULL DEFAULT false,
    rodo_consent_date TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journalists_email ON journalists(email);
CREATE INDEX IF NOT EXISTS idx_articles_ai_processed ON articles(ai_processed);

SELECT 'Migration OK' AS status;
EOSQL

echo "=== Done ==="
