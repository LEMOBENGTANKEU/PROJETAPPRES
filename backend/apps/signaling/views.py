from rest_framework import generics, permissions

from .models import SignalingMessage
from .serializers import SignalingMessageSerializer


class SignalingMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = SignalingMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = SignalingMessage.objects.filter(
            room_id=self.kwargs["room_id"]
        ).select_related("sender")
        after = self.request.query_params.get("after")
        if after:
            try:
                queryset = queryset.filter(id__gt=int(after))
            except (TypeError, ValueError):
                pass
        return queryset

    def perform_create(self, serializer):
        message_type = self.request.data.get("message_type") or "signal"
        payload = self.request.data.get("payload", self.request.data)
        if not isinstance(payload, dict):
            payload = {"value": payload}
        serializer.save(
            sender=self.request.user,
            room_id=self.kwargs["room_id"],
            message_type=str(message_type),
            payload=payload,
        )
