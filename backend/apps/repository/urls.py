from django.urls import path

from .views import ResourceDetailView, ResourceListCreateView, ResourceManifestView

urlpatterns = [
    path("resources/", ResourceListCreateView.as_view(), name="resource-list"),
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
]
