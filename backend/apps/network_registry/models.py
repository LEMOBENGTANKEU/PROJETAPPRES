import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PeerNodeIdentity(models.Model):
    class Platform(models.TextChoices):
        DESKTOP = "DESKTOP", "Ordinateur"
        ANDROID = "ANDROID", "Android"
        IOS = "IOS", "iOS"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    node_name = models.CharField(max_length=100)
    public_key = models.CharField(max_length=128)
    lan_ip = models.GenericIPAddressField()
    tcp_port = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(65535)]
    )
    platform = models.CharField(max_length=8, choices=Platform.choices)
    is_online = models.BooleanField(default=True)
    last_seen = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "node_name"],
                name="uniq_user_node_name",
            ),
        ]
        ordering = ["node_name", "id"]

    def __str__(self):
        return f"{self.node_name} ({self.lan_ip}:{self.tcp_port})"
