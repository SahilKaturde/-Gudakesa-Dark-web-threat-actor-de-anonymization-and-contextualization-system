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
        CRYPTO_WALLET = "crypto_wallet", "Crypto Wallet"
        PGP_KEY = "pgp_key", "PGP Key"
        ONION_URL = "onion_url", "Onion URL"
        XMPP = "xmpp", "XMPP/Jabber"
        PHONE = "phone", "Phone"
        FINANCIAL_ACCOUNT = "financial_account", "Financial Account"
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

    # --- Investigative metadata -----------------------------------------------
    short_label = models.CharField(max_length=120, blank=True, default="")
    category = models.CharField(max_length=50, blank=True, default="")
    risk_level = models.CharField(max_length=20, blank=True, default="")
    actor_role = models.CharField(max_length=50, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    related_indicators = models.JSONField(default=list, blank=True)

    # --- Source provenance (powers the frontend line-highlight hyperlink) -----
    # The 1-based line numbers in the source page_text where this feature
    # was extracted from. When the user clicks the source link in the UI,
    # the frontend switches to code view and scrolls to + highlights these lines.
    source_line_start = models.IntegerField(null=True, blank=True)
    source_line_end = models.IntegerField(null=True, blank=True)
    source_method = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Extraction method: regex, regex_review, regex_vendor, llm, etc.",
    )
    page_type = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Classified page type: PRODUCT_DETAIL, CATALOG_LISTING, GENERAL.",
    )

    def __str__(self):
        return f"{self.feature_type}: {self.feature_value}"