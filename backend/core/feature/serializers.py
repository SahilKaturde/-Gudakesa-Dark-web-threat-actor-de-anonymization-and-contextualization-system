from rest_framework import serializers
from .models import ExtractedFeature


class ExtractedFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractedFeature
        fields = [
            "feature_id",
            "domain",
            "page",
            "feature_type",
            "feature_value",
            "context",
            "description",
            "confidence_score",
            "extracted_timestamp",
            # Investigative metadata
            "short_label",
            "category",
            "risk_level",
            "actor_role",
            "tags",
            "related_indicators",
            # Source provenance — for frontend line-highlight
            "source_line_start",
            "source_line_end",
            "source_method",
            "page_type",
        ]
        read_only_fields = ["feature_id", "extracted_timestamp"]
