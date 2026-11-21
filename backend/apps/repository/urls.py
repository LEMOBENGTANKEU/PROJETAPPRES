from django.urls import path

from .views import (
    ResourceDetailView,
    ResourceListCreateView,
    ResourceManifestView,
    ResourceSeederListView,
    SeederAnnounceView,
)

urlpatterns = [
    path("resources/", ResourceListCreateView.as_view(), name="resource-list"),
    path("seeders/announce/", SeederAnnounceView.as_view(), name="seeder-announce"),
    path(
        "resources/<uuid:id>/",
        ResourceDetailView.as_view(),
        name="resource-detail",
    ),
    path(
        "resources/<uuid:id>/manifest/",
        ResourceManifestView.as_view(),
        name="resource-manifest",
    ),
    path(
        "resources/<uuid:id>/seeders/",
        ResourceSeederListView.as_view(),
        name="resource-seeders",
    ),
]
