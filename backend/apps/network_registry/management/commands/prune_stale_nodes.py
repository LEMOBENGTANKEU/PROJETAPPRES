from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.network_registry.models import PeerNodeIdentity


class Command(BaseCommand):
    help = "Mark nodes offline when their heartbeat has expired."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(
            seconds=settings.PEER_HEARTBEAT_TIMEOUT_SECONDS
        )
        count = PeerNodeIdentity.objects.filter(
            is_online=True,
            last_seen__lt=cutoff,
        ).update(is_online=False)
        self.stdout.write(f"Marked {count} stale node(s) offline.")
