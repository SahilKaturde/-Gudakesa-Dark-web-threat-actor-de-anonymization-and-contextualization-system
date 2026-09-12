from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExtractedFeatureViewSet

router = DefaultRouter()
router.register(r"features", ExtractedFeatureViewSet, basename="extracted-feature")

urlpatterns = [
    path("", include(router.urls)),
]
