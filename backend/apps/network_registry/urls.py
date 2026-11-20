from django.urls import path

from .views import (
    OnlinePeerListView,
    PeerNodeDeleteView,
    PeerNodeHeartbeatView,
    PeerNodeListCreateView,
)

urlpatterns = [
    path("nodes/", PeerNodeListCreateView.as_view(), name="node-list"),
    path("nodes/<uuid:node_id>/heartbeat/", PeerNodeHeartbeatView.as_view(), name="node-heartbeat"),
    path("nodes/<uuid:node_id>/", PeerNodeDeleteView.as_view(), name="node-delete"),
    path("peers/", OnlinePeerListView.as_view(), name="peer-list"),
]
