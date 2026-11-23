import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

from core.p2p import PieceStore, PeerEndpoint, build_manifest, get_peer_pieces
from services.backend_client import BackendApiError
from services.local_state import LocalStateStore
from services.sharing_service import SharingService


class FakeBackendClient:
    def __init__(self):
        self.is_authenticated = True
        self.nodes = []
        self.registered_nodes = []
        self.node_ids = []
        self.announcements = []
        self.heartbeats = []
        self.deleted_nodes = []

    async def list_nodes(self):
        return list(self.nodes)

    async def register_node(self, node):
        self.registered_nodes.append(node)
        node_id = str(uuid.uuid4())
        self.node_ids.append(node_id)
        self.nodes.append({"id": node_id, **node})
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
        self.nodes = [node for node in self.nodes if node.get("id") != node_id]


class SharingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.cache_dir = self.root / "cache"
        self.backend = FakeBackendClient()
        self.state_store = LocalStateStore(self.root / "state.json")
        self.service = SharingService(
            self.backend,
            cache_dir=self.cache_dir,
            state_store=self.state_store,
            listen_ip="127.0.0.1",
            heartbeat_interval=3600,
            enable_discovery=False,
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
            "file_name": name,
            "file_size": manifest.file_size,
            "piece_size": manifest.piece_size,
            "piece_count": manifest.piece_count,
            "manifest": list(manifest.piece_hashes),
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
        state = self.state_store.load()
        self.assertEqual(
            set(state["shared_resources"]),
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
        self.assertEqual(self.state_store.load()["shared_resources"], {})

    async def test_restore_consented_shares_from_completed_cache(self):
        path, resource, manifest = self.make_resource("course.pdf", b"course content")
        store = PieceStore(self.cache_dir, manifest)
        for index in range(manifest.piece_count):
            start = index * manifest.piece_size
            end = start + manifest.piece_length(index)
            store.write_piece(index, path.read_bytes()[start:end])
        store.finalize()
        self.state_store.remember_shared_resource(resource)

        restored = await self.service.restore_consented_shares()

        self.assertEqual(restored, 1)
        endpoint = PeerEndpoint("127.0.0.1", self.service.listen_port)
        self.assertEqual(
            await get_peer_pieces(endpoint, manifest),
            frozenset(range(manifest.piece_count)),
        )
        self.assertEqual(len(self.backend.announcements), 1)

    async def test_heartbeat_reregisters_after_stale_node(self):
        path, resource, manifest = self.make_resource("course.pdf", b"course content")
        await self.service.share_resource(resource, path)
        old_node_id = self.backend.node_ids[0]

        async def stale_heartbeat(_node_id):
            raise BackendApiError("expired", status_code=404)

        self.backend.heartbeat_node = stale_heartbeat
        await self.service._heartbeat_tick()

        self.assertNotEqual(self.service.node_id, old_node_id)
        self.assertEqual(len(self.backend.registered_nodes), 2)
        self.assertEqual(len(self.backend.announcements), 2)
        endpoint = PeerEndpoint("127.0.0.1", self.service.listen_port)
        self.assertEqual(
            await get_peer_pieces(endpoint, manifest),
            frozenset(range(manifest.piece_count)),
        )

    async def test_unshare_resource_stops_server_and_revokes_consent(self):
        path, resource, _manifest = self.make_resource("course.pdf", b"course content")
        await self.service.share_resource(resource, path)
        self.assertTrue(self.service.is_resource_shared(resource["id"]))
        self.assertTrue(self.service.consented_resources())

        await self.service.unshare_resource(resource["id"], revoke_consent=True)

        self.assertFalse(self.service.is_resource_shared(resource["id"]))
        self.assertEqual(self.service.consented_resources(), [])
        self.assertEqual(self.backend.deleted_nodes, self.backend.node_ids)
        self.assertIsNone(self.service.server)
        self.assertEqual(self.state_store.load()["shared_resources"], {})
