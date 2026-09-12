from rest_framework import viewsets, permissions
from .models import ExtractedFeature
from .serializers import ExtractedFeatureSerializer


class ExtractedFeatureViewSet(viewsets.ModelViewSet):
    queryset = ExtractedFeature.objects.all().order_by("-extracted_timestamp")
    serializer_class = ExtractedFeatureSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        domain_id = self.request.query_params.get("domain")
        page_id = self.request.query_params.get("page")

        if domain_id:
            queryset = queryset.filter(domain_id=domain_id)
        if page_id:
            queryset = queryset.filter(page_id=page_id)

        return queryset
