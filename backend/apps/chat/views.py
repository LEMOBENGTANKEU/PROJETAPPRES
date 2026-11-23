from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import generics, permissions

from .models import ChatMessage
from .serializers import ChatMessageSerializer


class ChatMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatMessage.objects.filter(ue_code=self.kwargs["ue_code"]).select_related("author")

    def perform_create(self, serializer):
        message = serializer.save(author=self.request.user, ue_code=self.kwargs["ue_code"])
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            data = ChatMessageSerializer(message).data
            async_to_sync(channel_layer.group_send)(
                f"chat_{message.ue_code}",
                {"type": "chat.message", "message": data},
            )
