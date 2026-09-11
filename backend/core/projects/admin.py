from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "project_id",
        "project_title",
        "user",
        "created_at",
    )

    search_fields = (
        "project_title",
        "user__username",
        "user__email",
    )

    list_filter = (
        "created_at",
    )

    readonly_fields = (
        "project_id",
        "created_at",
    )

    ordering = (
        "-created_at",
    )