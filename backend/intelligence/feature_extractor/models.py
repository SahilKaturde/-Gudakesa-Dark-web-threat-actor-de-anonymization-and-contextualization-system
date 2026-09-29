import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .database import Base


class Project(Base):
    __tablename__ = "projects_project"

    project_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    project_title = Column(
        String(255),
    )

    created_at = Column(
        DateTime,
    )

    updated_at = Column(
        DateTime,
    )


class CrawledDomain(Base):
    __tablename__ = "projects_crawleddomain"

    domain_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects_project.project_id"),
    )

    domain_index = Column(
        Integer,
    )

    domain_name = Column(
        String(255),
    )

    crawl_timestamp = Column(
        DateTime,
    )


class PageContent(Base):
    __tablename__ = "projects_pagecontent"

    page_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    domain_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects_crawleddomain.domain_id"),
    )

    page_url = Column(
        String(500),
    )

    page_name = Column(
        String(255),
    )

    page_text = Column(
        Text,
    )

    content_length = Column(
        Integer,
    )

    crawl_timestamp = Column(
        DateTime,
    )


class ExtractedFeature(Base):
    __tablename__ = "feature_extractedfeature"

    feature_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    domain_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects_crawleddomain.domain_id"),
    )

    page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects_pagecontent.page_id"),
    )

    feature_type = Column(
        String(50),
    )

    feature_value = Column(
        Text,
    )

    context = Column(
        Text,
        default="",
    )

    description = Column(
        Text,
        default="",
    )

    confidence_score = Column(
        Float,
        nullable=True,
    )

    extracted_timestamp = Column(
        DateTime,
    )

    # --- Investigative metadata (added for richer feature extraction) -----
    # NOTE: run a migration to add these columns to the existing
    # feature_extractedfeature table — they're nullable so it's a safe,
    # non-breaking ALTER TABLE for any rows that predate this change:
    #   ALTER TABLE feature_extractedfeature ADD COLUMN short_label VARCHAR(120);
    #   ALTER TABLE feature_extractedfeature ADD COLUMN category VARCHAR(50);
    #   ALTER TABLE feature_extractedfeature ADD COLUMN risk_level VARCHAR(20);
    #   ALTER TABLE feature_extractedfeature ADD COLUMN actor_role VARCHAR(50);
    #   ALTER TABLE feature_extractedfeature ADD COLUMN tags JSONB;
    #   ALTER TABLE feature_extractedfeature ADD COLUMN related_indicators JSONB;
    short_label = Column(String(120), nullable=True)
    category = Column(String(50), nullable=True)
    risk_level = Column(String(20), nullable=True)
    actor_role = Column(String(50), nullable=True)
    tags = Column(JSONB, nullable=True)
    related_indicators = Column(JSONB, nullable=True)

    # Source provenance — enables frontend line-highlight hyperlinks
    # Migration SQL:
    #   ALTER TABLE feature_extractedfeature ADD COLUMN source_line_start INTEGER;
    #   ALTER TABLE feature_extractedfeature ADD COLUMN source_line_end INTEGER;
    #   ALTER TABLE feature_extractedfeature ADD COLUMN source_method VARCHAR(50);
    #   ALTER TABLE feature_extractedfeature ADD COLUMN page_type VARCHAR(30);
    source_line_start = Column(Integer, nullable=True)
    source_line_end = Column(Integer, nullable=True)
    source_method = Column(String(50), nullable=True)
    page_type = Column(String(30), nullable=True)


class InvestigationReport(Base):
    """
    Persists every generated CTI investigation report to Postgres so a report
    isn't lost the moment the API response is sent — the frontend can fetch
    report history per page/domain, and re-runs can compare against the
    previous version instead of starting from zero context each time.
    """
    __tablename__ = "feature_investigationreport"

    report_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    domain_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects_crawleddomain.domain_id"),
    )

    page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects_pagecontent.page_id"),
    )

    page_url = Column(
        String(500),
        default="",
    )

    page_name = Column(
        String(255),
        default="",
    )

    # Full structured report payload (whatever generate_investigation_report
    # returns) stored as native JSONB — queryable, not just an opaque blob.
    report_json = Column(
        JSONB,
    )

    # Denormalized columns for fast listing/filtering without unpacking JSON.
    summary = Column(
        Text,
        default="",
    )

    risk_level = Column(
        String(50),
        nullable=True,
    )

    feature_count = Column(
        Integer,
        default=0,
    )

    generated_at = Column(
        DateTime,
    )