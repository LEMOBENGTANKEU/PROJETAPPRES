from django.conf import settings
from django.db import models


class SignalingMessage(models.Model):
    room_id = models.CharField(max_length=64, db_index=True)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signaling_messages",
    )
    message_type = models.CharField(max_length=64, default="signal")
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.room_id} {self.message_type}"
