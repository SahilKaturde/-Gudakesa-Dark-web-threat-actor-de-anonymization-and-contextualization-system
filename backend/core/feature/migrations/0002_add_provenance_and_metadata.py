from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feature", "0001_initial"),
    ]

    operations = [
        # Investigative metadata fields
        migrations.AddField(
            model_name="extractedfeature",
            name="short_label",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="category",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="risk_level",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="actor_role",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="related_indicators",
            field=models.JSONField(blank=True, default=list),
        ),
        # Source provenance fields — powers frontend line-highlight hyperlinks
        migrations.AddField(
            model_name="extractedfeature",
            name="source_line_start",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="source_line_end",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="source_method",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Extraction method: regex, regex_review, regex_vendor, llm, etc.",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="extractedfeature",
            name="page_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Classified page type: PRODUCT_DETAIL, CATALOG_LISTING, GENERAL.",
                max_length=30,
            ),
        ),
        # Expand feature_type choices
        migrations.AlterField(
            model_name="extractedfeature",
            name="feature_type",
            field=models.CharField(
                choices=[
                    ("username", "Username"),
                    ("email", "Email"),
                    ("ip", "IP Address"),
                    ("post", "Post"),
                    ("review", "Review"),
                    ("product", "Product"),
                    ("crypto_wallet", "Crypto Wallet"),
                    ("pgp_key", "PGP Key"),
                    ("onion_url", "Onion URL"),
                    ("xmpp", "XMPP/Jabber"),
                    ("phone", "Phone"),
                    ("financial_account", "Financial Account"),
                    ("other", "Other"),
                ],
                max_length=50,
            ),
        ),
    ]
