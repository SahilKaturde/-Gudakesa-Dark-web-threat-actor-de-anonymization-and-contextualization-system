from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
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
