from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import CrawledDomain, PageContent, Project
from .serializers import (
    CrawledDomainSerializer,
    PageContentSerializer,
    ProjectSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )


class CrawledDomainListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/projects/{project_id}/domains/
    POST /api/projects/{project_id}/domains/
    """
    serializer_class = CrawledDomainSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CrawledDomain.objects.filter(
            project__project_id=self.kwargs["project_id"],
            project__user=self.request.user,
        ).order_by("domain_index")

    def perform_create(self, serializer):
        project = Project.objects.get(
            project_id=self.kwargs["project_id"],
            user=self.request.user,
        )
        # Auto-assign domain_index
        next_index = (
            CrawledDomain.objects.filter(project=project).count() + 1
        )
        serializer.save(
            project=project,
            domain_index=next_index,
        )


class PageContentListView(generics.ListAPIView):
    """
    GET /api/domains/{domain_id}/pages/
    Returns all scraped pages for a given domain.
    """
    serializer_class = PageContentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PageContent.objects.filter(
            domain__domain_id=self.kwargs["domain_id"],
            domain__project__user=self.request.user,
        ).order_by("-crawl_timestamp")