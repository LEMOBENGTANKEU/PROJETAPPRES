import ipaddress
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import PeerNodeIdentity


class PeerNodeRegistrationSerializer(serializers.ModelSerializer):
    public_key = serializers.CharField(max_length=128, write_only=True)
    tcp_port = serializers.IntegerField(min_value=1, max_value=65535)

    class Meta:
        model = PeerNodeIdentity
        fields = (
            "id",
            "node_name",
            "public_key",
            "lan_ip",
            "tcp_port",
            "platform",
            "is_online",
            "last_seen",
            "created_at",
        )
        read_only_fields = ("id", "is_online", "last_seen", "created_at")

    def validate_public_key(self, value):
        if re.fullmatch(r"(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{128})", value) is None:
            raise serializers.ValidationError(
                "La clé publique doit être encodée en hexadécimal (32 ou 64 octets)."
            )
        return value.lower()

    def validate_lan_ip(self, value):
        address = ipaddress.ip_address(value)
        if (
            not address.is_private
            or address.is_loopback
            or address.is_multicast
            or address.is_unspecified
        ):
            raise serializers.ValidationError(
                "L'adresse du nœud doit appartenir à un réseau privé."
            )
        return value

    def validate_node_name(self, value):
        user = self.context["request"].user
        if PeerNodeIdentity.objects.filter(user=user, node_name=value).exists():
            raise serializers.ValidationError(
                "Un appareil portant ce nom est déjà enregistré pour ce compte."
            )
        return value


class PeerNodeListSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source="user.username")
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = PeerNodeIdentity
        fields = (
            "id",
            "username",
            "node_name",
            "lan_ip",
            "tcp_port",
            "platform",
            "is_online",
            "last_seen",
        )

    def get_is_online(self, obj):
        cutoff = timezone.now() - timedelta(
            seconds=settings.PEER_HEARTBEAT_TIMEOUT_SECONDS
        )
        return obj.is_online and obj.last_seen >= cutoff
