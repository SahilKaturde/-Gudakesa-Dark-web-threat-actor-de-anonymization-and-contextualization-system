from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CrawledDomainListCreateView,
    PageContentListView,
    ProjectViewSet,
)


router = DefaultRouter()

router.register(
    r"projects",
    ProjectViewSet,
    basename="project",
)

urlpatterns = router.urls + [
    path(
        "projects/<uuid:project_id>/domains/",
        CrawledDomainListCreateView.as_view(),
        name="domain-list-create",
    ),
    path(
        "domains/<uuid:domain_id>/pages/",
        PageContentListView.as_view(),
        name="page-list",
    ),
]