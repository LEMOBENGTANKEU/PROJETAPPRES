import hashlib
import tempfile
import unittest
from pathlib import Path

from core.p2p import (
    FileManifest,
    PeerBlockServer,
    PeerEndpoint,
    PieceStore,
    build_manifest,
    download_piece,
    download_resource,
    order_pieces_by_rarity,
)
from core.p2p.errors import (
    IntegrityError,
    ManifestError,
    ProtocolError,
    TransferError,
)


class ManifestTests(unittest.TestCase):
    def test_build_manifest_hashes_each_piece_and_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "course.pdf"
            source.write_bytes(b"abcdefghij")

            manifest = build_manifest(source, piece_size=4)

            expected_hashes = tuple(
                hashlib.sha256(chunk).hexdigest()
                for chunk in (b"abcd", b"efgh", b"ij")
            )
            expected_root = hashlib.sha256(
                b"".join(bytes.fromhex(digest) for digest in expected_hashes)
            ).hexdigest()
            self.assertEqual(manifest.piece_hashes, expected_hashes)
            self.assertEqual(manifest.root_hash, expected_root)
            self.assertEqual(manifest.piece_length(2), 2)

    def test_rejects_empty_file_and_inconsistent_manifest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "empty.pdf"
            source.write_bytes(b"")
            with self.assertRaises(ManifestError):
                build_manifest(source)

        with self.assertRaises(ManifestError):
            FileManifest(
                file_size=5,
                piece_size=4,
                piece_hashes=("0" * 64,),
                root_hash="0" * 64,
            )

    def test_peer_endpoint_rejects_public_ip_addresses(self):
        with self.assertRaises(ValueError):
            PeerEndpoint("8.8.8.8", 9000)

    def test_rarest_pieces_are_scheduled_first(self):
        order = order_pieces_by_rarity(
            {0, 1, 2, 3},
            ({0, 1, 3}, {0, 2}, {0, 3}),
        )

        self.assertEqual(order, (1, 2, 3, 0))


class PeerTransferTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source.bin"
        self.contents = b"first block|second block|last"
        self.source.write_bytes(self.contents)
        self.manifest = build_manifest(self.source, piece_size=12)
        self.server = PeerBlockServer(self.source, self.manifest)
        address = await self.server.start("127.0.0.1", 0)
        self.endpoint = PeerEndpoint(address[0], address[1])
        self.cache = self.root / "cache"
        self.store = PieceStore(self.cache, self.manifest)
        self.extra_servers = []

    async def asyncTearDown(self):
        await self.server.close()
        for server in self.extra_servers:
            await server.close()
        self.temporary_directory.cleanup()

    async def start_peer(self, source, available_pieces=None):
        server = PeerBlockServer(source, self.manifest, available_pieces)
        address = await server.start("127.0.0.1", 0)
        self.extra_servers.append(server)
        return PeerEndpoint(address[0], address[1])

    async def test_downloads_and_finalizes_verified_pieces(self):
        first = await download_piece(self.endpoint, self.manifest, 0, self.store)
        self.assertEqual(first, self.contents[:12])
        self.assertTrue(self.store.has_piece(0))

        resumed_store = PieceStore(self.cache, self.manifest)
        self.assertTrue(resumed_store.has_piece(0))
        for index in range(1, self.manifest.piece_count):
            await download_piece(self.endpoint, self.manifest, index, resumed_store)

        completed_path = resumed_store.finalize()
        self.assertEqual(completed_path.read_bytes(), self.contents)
        self.assertTrue(PieceStore(self.cache, self.manifest).is_complete)

    async def test_resume_rechecks_journaled_piece_before_reuse(self):
        await download_piece(self.endpoint, self.manifest, 0, self.store)
        with self.store.part_path.open("r+b") as partial:
            partial.write(b"corrupted!!!")
            partial.flush()

        resumed_store = PieceStore(self.cache, self.manifest)

        self.assertFalse(resumed_store.has_piece(0))
        recovered = await download_piece(
            self.endpoint,
            self.manifest,
            0,
            resumed_store,
        )
        self.assertEqual(recovered, self.contents[:12])

    async def test_corrupt_source_is_rejected_without_marking_piece_received(self):
        self.source.write_bytes(b"X" + self.contents[1:])

        with self.assertRaises(ProtocolError):
            await download_piece(self.endpoint, self.manifest, 0, self.store)

        self.assertFalse(self.store.has_piece(0))

    async def test_partial_seeder_does_not_advertise_unavailable_pieces(self):
        self.server.update_availability({0})

        with self.assertRaises(ProtocolError):
            await download_piece(self.endpoint, self.manifest, 1, self.store)

        self.assertFalse(self.store.has_piece(1))

    async def test_server_refuses_to_bind_to_all_interfaces(self):
        candidate = PeerBlockServer(self.source, self.manifest)
        with self.assertRaises(ValueError):
            await candidate.start("0.0.0.0", 0)

    async def test_invalid_piece_data_is_never_written(self):
        with self.assertRaises(IntegrityError):
            self.store.write_piece(0, b"wrong bytes")
        self.assertFalse(self.store.has_piece(0))

    async def test_scheduler_downloads_rare_and_distributed_pieces_from_two_peers(self):
        self.server.update_availability({0, 2})
        second_endpoint = await self.start_peer(self.source, {1, 2})
        progress = []

        summary = await download_resource(
            [self.endpoint, second_endpoint],
            self.manifest,
            self.store,
            concurrency=2,
            per_peer_concurrency=1,
            on_piece_complete=progress.append,
        )

        self.assertEqual(Path(summary.file_path).read_bytes(), self.contents)
        self.assertEqual(summary.completed_pieces, self.manifest.piece_count)
        self.assertEqual(sum(summary.peer_piece_counts.values()), self.manifest.piece_count)
        self.assertEqual(len(progress), self.manifest.piece_count)
        self.assertEqual(
            sorted(item.completed_pieces for item in progress),
            [1, 2, self.manifest.piece_count],
        )

    async def test_scheduler_retries_failed_piece_from_another_peer(self):
        valid_source = self.root / "valid-source.bin"
        valid_source.write_bytes(self.contents)
        bad_source = self.root / "bad-source.bin"
        bad_source.write_bytes(b"X" + self.contents[1:])
        bad_server = PeerBlockServer(bad_source, self.manifest, {0})
        bad_address = await bad_server.start("127.0.0.1", 0)
        self.extra_servers.append(bad_server)
        valid_endpoint = await self.start_peer(
            valid_source,
            set(range(self.manifest.piece_count)),
        )
        bad_endpoint = PeerEndpoint(bad_address[0], bad_address[1])

        summary = await download_resource(
            [bad_endpoint, valid_endpoint],
            self.manifest,
            self.store,
            concurrency=1,
        )

        self.assertEqual(Path(summary.file_path).read_bytes(), self.contents)
        self.assertEqual(
            summary.peer_piece_counts,
            {valid_endpoint: self.manifest.piece_count},
        )

    async def test_scheduler_reports_missing_pieces_without_discarding_valid_ones(self):
        self.server.update_availability({0})

        with self.assertRaises(TransferError):
            await download_resource(
                [self.endpoint],
                self.manifest,
                self.store,
                concurrency=2,
            )

        self.assertEqual(self.store.completed_pieces, {0})
        self.assertFalse(self.store.is_complete)
