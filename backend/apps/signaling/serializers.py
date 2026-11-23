from rest_framework import serializers

from .models import SignalingMessage


class SignalingMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = SignalingMessage
        fields = [
            "id",
            "room_id",
            "sender",
            "sender_username",
            "message_type",
            "payload",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "room_id",
            "sender",
            "sender_username",
            "created_at",
        ]
