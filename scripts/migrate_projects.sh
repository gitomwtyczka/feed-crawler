#!/usr/bin/env bash
# migrate_projects.sh — run on VPS to create projects + project_keywords tables
# Usage: scp scripts/migrate_projects.sh vps: && ssh vps bash migrate_projects.sh

set -euo pipefail

echo "=== DB Migration: projects + project_keywords tables ==="

docker exec crawler-db psql -U crawler -d feed_crawler <<'EOSQL'
-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Project keywords table
CREATE TABLE IF NOT EXISTS project_keywords (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    match_type VARCHAR(20) NOT NULL DEFAULT 'contains'
);

CREATE INDEX IF NOT EXISTS idx_project_keywords_project_id ON project_keywords(project_id);

-- Seed test projects
INSERT INTO projects (name, slug) VALUES
    ('Strabag', 'strabag'),
    ('Orlen', 'orlen'),
    ('PZU', 'pzu'),
    ('TVP', 'tvp')
ON CONFLICT (slug) DO NOTHING;

-- Seed keywords (only if project exists and keyword not already there)
INSERT INTO project_keywords (project_id, keyword)
SELECT p.id, kw.keyword FROM projects p
CROSS JOIN (VALUES ('Strabag'), ('STRABAG')) AS kw(keyword)
WHERE p.slug = 'strabag'
AND NOT EXISTS (
    SELECT 1 FROM project_keywords pk WHERE pk.project_id = p.id AND pk.keyword = kw.keyword
);

INSERT INTO project_keywords (project_id, keyword)
SELECT p.id, kw.keyword FROM projects p
CROSS JOIN (VALUES ('Orlen'), ('PKN Orlen'), ('ORLEN')) AS kw(keyword)
WHERE p.slug = 'orlen'
AND NOT EXISTS (
    SELECT 1 FROM project_keywords pk WHERE pk.project_id = p.id AND pk.keyword = kw.keyword
);

INSERT INTO project_keywords (project_id, keyword)
SELECT p.id, kw.keyword FROM projects p
CROSS JOIN (VALUES ('PZU'), ('Powszechny Zakład Ubezpieczeń')) AS kw(keyword)
WHERE p.slug = 'pzu'
AND NOT EXISTS (
    SELECT 1 FROM project_keywords pk WHERE pk.project_id = p.id AND pk.keyword = kw.keyword
);

INSERT INTO project_keywords (project_id, keyword)
SELECT p.id, kw.keyword FROM projects p
CROSS JOIN (VALUES ('TVP'), ('Telewizja Polska')) AS kw(keyword)
WHERE p.slug = 'tvp'
AND NOT EXISTS (
    SELECT 1 FROM project_keywords pk WHERE pk.project_id = p.id AND pk.keyword = kw.keyword
);

SELECT 'Migration + seed OK' AS status;
SELECT p.name, COUNT(pk.id) AS keywords FROM projects p LEFT JOIN project_keywords pk ON pk.project_id = p.id GROUP BY p.name;
EOSQL

echo "=== Done ==="
