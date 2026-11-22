from rest_framework import serializers

from .models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "ue_code", "author", "author_username", "content", "created_at"]
        read_only_fields = ["id", "ue_code", "author", "author_username", "created_at"]
