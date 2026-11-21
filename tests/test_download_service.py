import tempfile
import unittest
from pathlib import Path

from core.p2p import PeerBlockServer, build_manifest
from services.download_service import DownloadService


class FakeBackendClient:
    def __init__(self, seeders):
        self.seeders = seeders
        self.calls = 0

    async def list_seeders(self, _resource_id):
        self.calls += 1
        return self.seeders


class DownloadServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source.pdf"
        self.contents = b"course notes, with multiple blocks"
        self.source.write_bytes(self.contents)
        self.manifest = build_manifest(self.source, piece_size=8)
        self.server = PeerBlockServer(self.source, self.manifest)
        host, port = await self.server.start("127.0.0.1", 0)
        self.backend = FakeBackendClient(
            [{"lan_ip": host, "tcp_port": port}]
        )
        self.service = DownloadService(
            self.backend,
            cache_dir=self.root / "cache",
            download_dir=self.root / "downloads",
        )
        self.resource = {
            "id": "resource-id",
            "file_name": "lecture.pdf",
            "file_size": self.manifest.file_size,
            "piece_size": self.manifest.piece_size,
            "piece_count": self.manifest.piece_count,
            "manifest": list(self.manifest.piece_hashes),
            "root_hash": self.manifest.root_hash,
        }

    async def asyncTearDown(self):
        await self.server.close()
        self.temporary_directory.cleanup()

    async def test_downloads_to_local_directory_using_backend_seeders(self):
        destination, summary = await self.service.download(self.resource)

        self.assertEqual(destination.read_bytes(), self.contents)
        self.assertEqual(destination.name, "lecture.pdf")
        self.assertEqual(summary.completed_pieces, self.manifest.piece_count)
        self.assertEqual(self.backend.calls, 1)

    async def test_uses_a_new_name_instead_of_overwriting_existing_file(self):
        self.service.download_dir.mkdir(parents=True)
        existing_file = self.service.download_dir / "lecture.pdf"
        existing_file.write_bytes(b"keep this file")

        destination, _ = await self.service.download(self.resource)

        self.assertEqual(existing_file.read_bytes(), b"keep this file")
        self.assertEqual(destination.name, "lecture (1).pdf")
        self.assertEqual(destination.read_bytes(), self.contents)

    async def test_reuses_completed_local_cache_without_querying_peers(self):
        await self.service.download(self.resource)
        self.backend.seeders = []

        destination, summary = await self.service.download(self.resource)

        self.assertEqual(destination.read_bytes(), self.contents)
        self.assertEqual(summary.completed_pieces, self.manifest.piece_count)
        self.assertEqual(self.backend.calls, 1)

    async def test_sanitizes_remote_filename_and_keeps_output_in_download_directory(self):
        unsafe_resource = {
            **self.resource,
            "file_name": "..\\..\\CON.txt",
        }

        destination, _ = await self.service.download(unsafe_resource)

        self.assertEqual(destination.parent, self.service.download_dir)
        self.assertEqual(destination.name, "_CON.txt")
        self.assertEqual(destination.read_bytes(), self.contents)

    async def test_rejects_resource_with_inconsistent_piece_count(self):
        invalid_resource = {**self.resource, "piece_count": self.manifest.piece_count + 1}

        with self.assertRaises(ValueError):
            await self.service.download(invalid_resource)

        self.assertEqual(self.backend.calls, 0)
