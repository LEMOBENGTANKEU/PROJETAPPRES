from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PeerNodeIdentity
from .serializers import PeerNodeListSerializer, PeerNodeRegistrationSerializer


def active_nodes():
    cutoff = timezone.now() - timedelta(
        seconds=settings.PEER_HEARTBEAT_TIMEOUT_SECONDS
    )
    return PeerNodeIdentity.objects.filter(is_online=True, last_seen__gte=cutoff)


class PeerNodeListCreateView(ListCreateAPIView):
    serializer_class = PeerNodeRegistrationSerializer

    def get_queryset(self):
        return PeerNodeIdentity.objects.filter(user=self.request.user).select_related(
            "user"
        )

    def get_serializer_class(self):
        if self.request.method == "GET":
            return PeerNodeListSerializer
        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, last_seen=timezone.now())


class PeerNodeHeartbeatView(APIView):
    def post(self, request, node_id):
        node = get_object_or_404(
            PeerNodeIdentity,
            id=node_id,
            user=request.user,
        )
        node.last_seen = timezone.now()
        node.is_online = True
        node.save(update_fields=["last_seen", "is_online"])
        return Response(
            {"id": str(node.id), "is_online": node.is_online, "last_seen": node.last_seen},
            status=status.HTTP_200_OK,
        )


class PeerNodeDeleteView(APIView):
    def delete(self, request, node_id):
        node = get_object_or_404(
            PeerNodeIdentity,
            id=node_id,
            user=request.user,
        )
        node.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlinePeerListView(ListAPIView):
    serializer_class = PeerNodeListSerializer

    def get_queryset(self):
        return active_nodes().select_related("user")
