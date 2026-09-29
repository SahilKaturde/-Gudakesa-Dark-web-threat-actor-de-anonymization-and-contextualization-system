"""
One-off migration runner for the new investigative-metadata columns and the
feature_investigationreport table.

Usage (from your backend project root, with .venv active):
    python -m intelligence.feature_extractor.run_migration

Safe to run more than once — every statement in migration.sql is idempotent
(IF NOT EXISTS everywhere).
"""
import os
from sqlalchemy import text

from .database import engine

MIGRATION_SQL = """
ALTER TABLE feature_extractedfeature ADD COLUMN IF NOT EXISTS short_label VARCHAR(120);
ALTER TABLE feature_extractedfeature ADD COLUMN IF NOT EXISTS category VARCHAR(50);
ALTER TABLE feature_extractedfeature ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20);
ALTER TABLE feature_extractedfeature ADD COLUMN IF NOT EXISTS actor_role VARCHAR(50);
ALTER TABLE feature_extractedfeature ADD COLUMN IF NOT EXISTS tags JSONB;
ALTER TABLE feature_extractedfeature ADD COLUMN IF NOT EXISTS related_indicators JSONB;

CREATE TABLE IF NOT EXISTS feature_investigationreport (
    report_id            UUID PRIMARY KEY,
    domain_id            UUID REFERENCES projects_crawleddomain(domain_id),
    page_id              UUID REFERENCES projects_pagecontent(page_id),
    page_url             VARCHAR(500) DEFAULT '',
    page_name            VARCHAR(255) DEFAULT '',
    report_json          JSONB,
    summary              TEXT DEFAULT '',
    risk_level           VARCHAR(50),
    feature_count        INTEGER DEFAULT 0,
    generated_at         TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_investigationreport_domain
    ON feature_investigationreport(domain_id);
CREATE INDEX IF NOT EXISTS idx_investigationreport_page
    ON feature_investigationreport(page_id);
"""


def run_migration() -> None:
    statements = [s.strip() for s in MIGRATION_SQL.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            print(f"[Migration] Running: {stmt.splitlines()[0][:80]}...")
            conn.execute(text(stmt))
    print(f"[Migration] Done — {len(statements)} statements applied (or already present).")


if __name__ == "__main__":
    run_migration()