from django.contrib import admin

from .models import PeerNodeIdentity


@admin.register(PeerNodeIdentity)
class PeerNodeIdentityAdmin(admin.ModelAdmin):
    list_display = (
        "node_name",
        "user",
        "lan_ip",
        "tcp_port",
        "platform",
        "is_online",
        "last_seen",
    )
    list_filter = ("platform", "is_online")
    search_fields = ("node_name", "user__username", "lan_ip")
    readonly_fields = ("id", "created_at")
