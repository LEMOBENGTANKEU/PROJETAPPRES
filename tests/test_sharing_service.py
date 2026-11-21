import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

from core.p2p import PeerEndpoint, build_manifest, get_peer_pieces
from services.backend_client import BackendApiError
from services.sharing_service import SharingService


class FakeBackendClient:
    def __init__(self):
        self.is_authenticated = True
        self.registered_nodes = []
        self.node_ids = []
        self.announcements = []
        self.heartbeats = []
        self.deleted_nodes = []

    async def register_node(self, node):
        self.registered_nodes.append(node)
        node_id = str(uuid.uuid4())
        self.node_ids.append(node_id)
        return {"id": node_id}

    async def announce_seeder(
        self,
        resource_id,
        node_id,
        bitfield,
        pieces_available,
    ):
        self.announcements.append(
            (resource_id, node_id, bitfield, pieces_available)
        )

    async def heartbeat_node(self, node_id):
        self.heartbeats.append(node_id)

    async def delete_node(self, node_id):
        self.deleted_nodes.append(node_id)


class SharingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.backend = FakeBackendClient()
        self.service = SharingService(
            self.backend,
            listen_ip="127.0.0.1",
            heartbeat_interval=3600,
        )

    async def asyncTearDown(self):
        await self.service.close()
        self.temporary_directory.cleanup()

    def make_resource(self, name, contents):
        path = self.root / name
        path.write_bytes(contents)
        manifest = build_manifest(path, piece_size=4)
        resource = {
            "id": str(uuid.uuid4()),
            "file_size": manifest.file_size,
            "piece_size": manifest.piece_size,
            "piece_count": manifest.piece_count,
            "manifest": manifest.piece_hashes,
            "root_hash": manifest.root_hash,
        }
        return path, resource, manifest

    async def test_registers_one_node_to_share_multiple_resources(self):
        first_path, first_resource, first_manifest = self.make_resource(
            "first.pdf",
            b"first resource",
        )
        second_path, second_resource, second_manifest = self.make_resource(
            "second.pdf",
            b"second resource",
        )

        await self.service.share_resource(first_resource, first_path)
        await self.service.share_resource(second_resource, second_path)

        endpoint = PeerEndpoint("127.0.0.1", self.service.listen_port)
        self.assertEqual(
            await get_peer_pieces(endpoint, first_manifest),
            frozenset(range(first_manifest.piece_count)),
        )
        self.assertEqual(
            await get_peer_pieces(endpoint, second_manifest),
            frozenset(range(second_manifest.piece_count)),
        )
        self.assertEqual(len(self.backend.registered_nodes), 1)
        self.assertEqual(len(self.backend.announcements), 2)
        self.assertEqual(
            {announcement[0] for announcement in self.backend.announcements},
            {first_resource["id"], second_resource["id"]},
        )

    async def test_share_requires_authentication(self):
        path, resource, _manifest = self.make_resource("course.pdf", b"course")
        self.backend.is_authenticated = False

        with self.assertRaises(BackendApiError):
            await self.service.share_resource(resource, path)

        self.assertIsNone(self.service.server)
        self.assertEqual(self.backend.registered_nodes, [])

    async def test_failed_first_announcement_closes_server_and_unregisters_node(self):
        path, resource, _manifest = self.make_resource("course.pdf", b"course")

        self.backend.announce_seeder = AsyncMock(
            side_effect=BackendApiError("backend unavailable")
        )
        with self.assertRaises(BackendApiError):
            await self.service.share_resource(resource, path)

        self.assertIsNone(self.service.server)
        self.assertEqual(self.backend.deleted_nodes, self.backend.node_ids)

