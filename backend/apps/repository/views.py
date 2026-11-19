from django.db.models import Q
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)

from .models import AcademicResource
from .permissions import CanManageResource, CanPublishResources, is_administrator
from .serializers import AcademicResourceSerializer, ResourceManifestSerializer


class ResourceQuerysetMixin:
    def get_queryset(self):
        user = self.request.user
        queryset = AcademicResource.objects.select_related("uploaded_by")
        if not is_administrator(user):
            queryset = queryset.filter(Q(is_published=True) | Q(uploaded_by=user))

        course_code = self.request.query_params.get("course_code")
        if course_code:
            queryset = queryset.filter(course_code__iexact=course_code.strip())

        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category.strip().upper())

        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(file_name__icontains=query)
                | Q(course_code__icontains=query)
            )
        return queryset


class ResourceListCreateView(ResourceQuerysetMixin, ListCreateAPIView):
    serializer_class = AcademicResourceSerializer
    permission_classes = [CanPublishResources]

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class ResourceDetailView(ResourceQuerysetMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = AcademicResourceSerializer
    permission_classes = [CanManageResource]
    lookup_field = "id"


class ResourceManifestView(ResourceQuerysetMixin, RetrieveAPIView):
    serializer_class = ResourceManifestSerializer
    permission_classes = [CanManageResource]
    lookup_field = "id"
