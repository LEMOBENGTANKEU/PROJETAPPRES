from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User

from .models import PeerNodeIdentity


class PeerNodeApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="node-owner",
            password="StrongCampusPass123!",
        )
        self.other_user = User.objects.create_user(
            username="other-user",
            password="StrongCampusPass123!",
        )
        self.payload = {
            "node_name": "laptop-campus",
            "public_key": "a" * 64,
            "lan_ip": "192.168.1.25",
            "tcp_port": 8765,
            "platform": PeerNodeIdentity.Platform.DESKTOP,
        }
        self.list_url = reverse("node-list")
        self.client.force_authenticate(self.owner)

    def create_node(self, **overrides):
        attributes = {
            "user": self.owner,
            "node_name": "laptop-campus",
            "public_key": "a" * 64,
            "lan_ip": "192.168.1.25",
            "tcp_port": 8765,
            "platform": PeerNodeIdentity.Platform.DESKTOP,
            "last_seen": timezone.now(),
        }
        attributes.update(overrides)
        return PeerNodeIdentity.objects.create(**attributes)

    def test_registration_associates_node_with_authenticated_user(self):
        response = self.client.post(self.list_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        node = PeerNodeIdentity.objects.get(node_name="laptop-campus")
        self.assertEqual(node.user, self.owner)
        self.assertEqual(node.lan_ip, "192.168.1.25")
        self.assertNotIn("public_key", response.data)

    def test_registration_rejects_non_private_ip(self):
        response = self.client.post(
            self.list_url,
            {**self.payload, "lan_ip": "8.8.8.8"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lan_ip", response.data)

    def test_registration_rejects_invalid_public_key(self):
        response = self.client.post(
            self.list_url,
            {**self.payload, "public_key": "not-a-public-key"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("public_key", response.data)

    def test_duplicate_node_name_for_same_user_is_rejected(self):
        self.create_node()

        response = self.client.post(self.list_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.list_url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_peers_list_only_active_nodes_without_public_keys(self):
        online_node = self.create_node()
        stale_node = self.create_node(
            node_name="stale-laptop",
            lan_ip="192.168.1.26",
            last_seen=timezone.now() - timedelta(seconds=120),
        )

        response = self.client.get(reverse("peer-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        peers = response.data["results"]
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(str(peers[0]["id"]), str(online_node.id))
        self.assertNotIn("public_key", peers[0])
        self.assertNotIn(str(stale_node.id), [str(peer["id"]) for peer in peers])

    def test_nodes_endpoint_lists_only_the_authenticated_users_devices(self):
        owned_node = self.create_node()
        other_node = self.create_node(
            user=self.other_user,
            node_name="other-laptop",
            lan_ip="192.168.1.26",
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nodes = response.data["results"]
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(str(nodes[0]["id"]), str(owned_node.id))
        self.assertNotIn(str(other_node.id), [str(node["id"]) for node in nodes])

    def test_heartbeat_refreshes_last_seen_and_online_status(self):
        node = self.create_node(
            is_online=False,
            last_seen=timezone.now() - timedelta(minutes=10),
        )

        response = self.client.post(
            reverse("node-heartbeat", args=[node.id]),
            {},
            format="json",
        )

        node.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(node.is_online)
        self.assertGreater(node.last_seen, timezone.now() - timedelta(seconds=10))

    def test_node_owner_can_delete_node_but_other_user_cannot(self):
        node = self.create_node()
        url = reverse("node-delete", args=[node.id])

        self.client.force_authenticate(self.other_user)
        forbidden_response = self.client.delete(url)
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.owner)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PeerNodeIdentity.objects.filter(id=node.id).exists())

    @override_settings(PEER_HEARTBEAT_TIMEOUT_SECONDS=60)
    def test_prune_command_marks_expired_nodes_offline(self):
        stale_node = self.create_node(
            last_seen=timezone.now() - timedelta(seconds=61)
        )
        current_node = self.create_node(
            node_name="current-laptop",
            lan_ip="192.168.1.26",
        )

        from django.core.management import call_command

        call_command("prune_stale_nodes", verbosity=0)

        stale_node.refresh_from_db()
        current_node.refresh_from_db()
        self.assertFalse(stale_node.is_online)
        self.assertTrue(current_node.is_online)
