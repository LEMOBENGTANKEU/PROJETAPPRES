from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    ue_code = models.CharField(max_length=32, db_index=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.ue_code} {self.author_id}: {self.content[:30]}"
