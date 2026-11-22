from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/repository/", include("apps.repository.urls")),
    path("api/v1/network/", include("apps.network_registry.urls")),
    path("api/v1/chat/", include("apps.chat.urls")),
    path("api/v1/signaling/", include("apps.signaling.urls")),
]
