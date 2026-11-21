from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AcademicResource, FileSeeder
from .permissions import CanManageResource, CanPublishResources, is_administrator
from .serializers import (
    AcademicResourceSerializer,
    FileSeederSerializer,
    ResourceManifestSerializer,
    SeederAnnounceSerializer,
)


class ResourceQuerysetMixin:
    def get_queryset(self):
        user = self.request.user
        cutoff = timezone.now() - timedelta(
            seconds=settings.PEER_HEARTBEAT_TIMEOUT_SECONDS
        )
        queryset = AcademicResource.objects.select_related("uploaded_by").annotate(
            online_seeders=Count(
                "seeders",
                filter=Q(
                    seeders__node__is_online=True,
                    seeders__node__last_seen__gte=cutoff,
                ),
            )
        ).order_by("-created_at", "id")
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


class ResourceSeederListView(ResourceQuerysetMixin, RetrieveAPIView):
    serializer_class = FileSeederSerializer
    permission_classes = [CanManageResource]
    lookup_field = "id"

    def retrieve(self, request, *_args, **_kwargs):
        resource = self.get_object()
        cutoff = timezone.now() - timedelta(
            seconds=settings.PEER_HEARTBEAT_TIMEOUT_SECONDS
        )
        seeders = FileSeeder.objects.filter(
            resource=resource,
            node__is_online=True,
            node__last_seen__gte=cutoff,
            pieces_available__gt=0,
        ).select_related("node").order_by("-last_announced", "node_id")
        paginator = PageNumberPagination()
        paginator.page_size = 100
        page = paginator.paginate_queryset(seeders, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SeederAnnounceView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SeederAnnounceSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        seeder = serializer.save()
        return Response(
            FileSeederSerializer(seeder).data,
            status=201,
        )
