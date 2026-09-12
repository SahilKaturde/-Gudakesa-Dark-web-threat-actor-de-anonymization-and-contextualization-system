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
        ]
        read_only_fields = ["feature_id", "extracted_timestamp"]
