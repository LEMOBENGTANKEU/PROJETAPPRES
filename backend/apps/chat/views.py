from rest_framework import generics, permissions

from .models import ChatMessage
from .serializers import ChatMessageSerializer


class ChatMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatMessage.objects.filter(ue_code=self.kwargs["ue_code"]).select_related("author")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, ue_code=self.kwargs["ue_code"])
