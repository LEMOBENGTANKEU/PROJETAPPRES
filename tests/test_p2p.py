import asyncio
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
)
from core.p2p.errors import IntegrityError, ManifestError, ProtocolError


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

    async def asyncTearDown(self):
        await self.server.close()
        self.temporary_directory.cleanup()

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
