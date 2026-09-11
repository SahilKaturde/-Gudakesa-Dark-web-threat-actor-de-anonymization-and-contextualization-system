import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validate_onion_url(value):
    """
    Validate that the supplied domain is an HTTP/HTTPS .onion URL.
    """
    value = value.strip().lower()

    if not value.startswith(("http://", "https://")):
        raise ValidationError(
            "Domain must be a valid HTTP/HTTPS .onion URL."
        )

    if not value.split("://", 1)[1].split("/", 1)[0].endswith(".onion"):
        raise ValidationError(
            "Domain must be a .onion address."
        )


class Project(models.Model):
    project_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )

    project_title = models.CharField(
        max_length=255,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.project_title


class CrawledDomain(models.Model):
    domain_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="crawled_domains",
    )

    domain_index = models.PositiveIntegerField()

    domain_name = models.URLField(
        max_length=255,
        validators=[validate_onion_url],
    )

    crawl_timestamp = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.domain_name


class PageContent(models.Model):
    page_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    domain = models.ForeignKey(
        CrawledDomain,
        on_delete=models.CASCADE,
        related_name="pages",
    )

    page_url = models.URLField(
        max_length=500,
    )

    page_name = models.CharField(
        max_length=255,
    )

    page_text = models.TextField()

    content_length = models.PositiveIntegerField()

    crawl_timestamp = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.page_name