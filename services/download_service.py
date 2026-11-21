import os
import shutil
from pathlib import Path

from core.p2p import (
    FileManifest,
    PeerEndpoint,
    PieceStore,
    download_resource,
)
from core.p2p.errors import TransferError


class DownloadService:
    def __init__(self, backend_client, cache_dir=None, download_dir=None):
        self.backend_client = backend_client
        home = Path.home() / "CampusShare"
        self.cache_dir = Path(cache_dir) if cache_dir else home / "cache"
        self.download_dir = (
            Path(download_dir) if download_dir else home / "downloads"
        )

    async def download(self, resource, on_piece_complete=None):
        required_fields = (
            "id",
            "file_name",
            "file_size",
            "piece_size",
            "piece_count",
            "manifest",
            "root_hash",
        )
        if any(field not in resource for field in required_fields):
            raise ValueError("La ressource ne contient pas le manifeste requis.")

        manifest = FileManifest(
            file_size=resource["file_size"],
            piece_size=resource["piece_size"],
            piece_hashes=tuple(resource["manifest"]),
            root_hash=resource["root_hash"],
        )
        if manifest.piece_count != resource["piece_count"]:
            raise ValueError("Le nombre de blocs ne correspond pas au manifeste.")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        store = PieceStore(self.cache_dir, manifest)
        if len(store.completed_pieces) == manifest.piece_count:
            peers = ()
        else:
            seeder_records = await self.backend_client.list_seeders(resource["id"])
            peers = tuple(
                dict.fromkeys(
                    PeerEndpoint(record["lan_ip"], record["tcp_port"])
                    for record in seeder_records
                )
            )
            if not peers:
                raise TransferError("Aucun pair actif ne partage cette ressource.")

        summary = await download_resource(
            peers,
            manifest,
            store,
            on_piece_complete=on_piece_complete,
        )
        destination = self._copy_without_overwrite(
            summary.file_path,
            resource["file_name"],
        )
        return destination, summary

    def _copy_without_overwrite(self, source_path, file_name):
        safe_name = str(file_name).replace("\\", "/").rsplit("/", 1)[-1].strip()
        safe_name = "".join(
            "_" if character in '<>:"|?*' or ord(character) < 32 else character
            for character in safe_name
        ).rstrip(" .")
        if safe_name in {"", ".", ".."}:
            raise ValueError("Le nom de fichier fourni par le serveur est invalide.")

        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        if stem.upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{index}" for index in range(1, 10)),
            *(f"LPT{index}" for index in range(1, 10)),
        }:
            safe_name = f"_{safe_name}"
            stem = Path(safe_name).stem
            suffix = Path(safe_name).suffix

        candidate = self.download_dir / safe_name
        counter = 1
        while True:
            if counter > 1:
                candidate = self.download_dir / f"{stem} ({counter - 1}){suffix}"
            created = False
            try:
                with candidate.open("xb") as destination:
                    created = True
                    with Path(source_path).open("rb") as source:
                        shutil.copyfileobj(source, destination)
                    destination.flush()
                    os.fsync(destination.fileno())
                return candidate
            except FileExistsError:
                counter += 1
            except OSError as exc:
                if created:
                    try:
                        candidate.unlink(missing_ok=True)
                    except OSError as cleanup_error:
                        raise OSError(
                            f"Échec de copie ({exc}); le fichier partiel "
                            f"{candidate} n'a pas pu être supprimé."
                        ) from cleanup_error
                raise
