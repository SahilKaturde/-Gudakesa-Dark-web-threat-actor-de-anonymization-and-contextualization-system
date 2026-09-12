import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

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
