from rest_framework import serializers

from .models import CrawledDomain, PageContent, Project


class PageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageContent
        fields = [
            "page_id",
            "domain",
            "page_url",
            "page_name",
            "page_text",
            "content_length",
            "crawl_timestamp",
        ]
        read_only_fields = [
            "page_id",
            "crawl_timestamp",
        ]


class CrawledDomainSerializer(serializers.ModelSerializer):
    pages_count = serializers.IntegerField(
        source="pages.count",
        read_only=True,
    )

    class Meta:
        model = CrawledDomain
        fields = [
            "domain_id",
            "project",
            "domain_index",
            "domain_name",
            "crawl_timestamp",
            "pages_count",
        ]
        read_only_fields = [
            "domain_id",
            "project",
            "domain_index",
            "crawl_timestamp",
            "pages_count",
        ]


class ProjectSerializer(serializers.ModelSerializer):
    domains_count = serializers.IntegerField(
        source="crawled_domains.count",
        read_only=True,
    )

    class Meta:
        model = Project
        fields = [
            "project_id",
            "project_title",
            "created_at",
            "domains_count",
        ]
        read_only_fields = [
            "project_id",
            "created_at",
            "domains_count",
        ]