from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_id",
            "project_title",
            "created_at",
        ]
        read_only_fields = [
            "project_id",
            "created_at",
        ]