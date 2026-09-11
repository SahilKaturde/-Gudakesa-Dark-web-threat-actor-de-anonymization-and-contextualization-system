import uuid

from django.db import models


class ExtractedFeature(models.Model):

    class FeatureType(models.TextChoices):
        USERNAME = "username", "Username"
        EMAIL = "email", "Email"
        IP = "ip", "IP Address"
        POST = "post", "Post"
        REVIEW = "review", "Review"
        PRODUCT = "product", "Product"
        OTHER = "other", "Other"

    feature_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    domain = models.ForeignKey(
        "projects.CrawledDomain",
        on_delete=models.CASCADE,
        related_name="extracted_features",
    )

    page = models.ForeignKey(
        "projects.PageContent",
        on_delete=models.CASCADE,
        related_name="extracted_features",
    )

    feature_type = models.CharField(
        max_length=50,
        choices=FeatureType.choices,
    )

    feature_value = models.TextField()

    context = models.TextField(
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    confidence_score = models.FloatField(
        null=True,
        blank=True,
    )

    extracted_timestamp = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.feature_type}: {self.feature_value}"