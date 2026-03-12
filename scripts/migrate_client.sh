#!/usr/bin/env bash
set -euo pipefail

echo "--- Create client_accounts table ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
CREATE TABLE IF NOT EXISTS client_accounts (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    tier VARCHAR(20) NOT NULL DEFAULT 'basic',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);"

echo "--- Add client_id to projects ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client_accounts(id);"

echo "--- Verify ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "\d client_accounts"
docker exec crawler-db psql -U crawler -d feed_crawler -c "\d projects"
