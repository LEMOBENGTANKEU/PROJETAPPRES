import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import ManifestError

DEFAULT_PIECE_SIZE = 256 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _root_hash(piece_hashes):
    return hashlib.sha256(
        b"".join(bytes.fromhex(digest) for digest in piece_hashes)
    ).hexdigest()


@dataclass(frozen=True)
class FileManifest:
    file_size: int
    piece_size: int
    piece_hashes: tuple[str, ...]
    root_hash: str

    def __post_init__(self):
        if self.file_size <= 0:
            raise ManifestError("Le fichier doit contenir au moins un octet.")
        if self.piece_size <= 0:
            raise ManifestError("La taille d'un bloc doit être supérieure à zéro.")
        expected_count = (self.file_size + self.piece_size - 1) // self.piece_size
        if len(self.piece_hashes) != expected_count:
            raise ManifestError("Le nombre d'empreintes ne correspond pas au fichier.")
        if any(_SHA256_RE.fullmatch(digest) is None for digest in self.piece_hashes):
            raise ManifestError("Une empreinte de bloc n'est pas un SHA-256 hexadécimal.")
        if _SHA256_RE.fullmatch(self.root_hash) is None:
            raise ManifestError("L'empreinte racine n'est pas un SHA-256 hexadécimal.")
        if _root_hash(self.piece_hashes) != self.root_hash:
            raise ManifestError("L'empreinte racine ne correspond pas au manifeste.")

    @property
    def piece_count(self):
        return len(self.piece_hashes)

    def piece_length(self, index):
        if not 0 <= index < self.piece_count:
            raise IndexError("Index de bloc hors limites.")
        if index < self.piece_count - 1:
            return self.piece_size
        return self.file_size - index * self.piece_size


def build_manifest(path, piece_size=DEFAULT_PIECE_SIZE):
    path = Path(path)
    if piece_size <= 0:
        raise ManifestError("La taille d'un bloc doit être supérieure à zéro.")
    file_size = path.stat().st_size
    if file_size <= 0:
        raise ManifestError("Le fichier doit contenir au moins un octet.")

    piece_hashes = []
    with path.open("rb") as source:
        while chunk := source.read(piece_size):
            piece_hashes.append(hashlib.sha256(chunk).hexdigest())

    if path.stat().st_size != file_size:
        raise ManifestError("Le fichier a changé pendant le calcul du manifeste.")

    hashes = tuple(piece_hashes)
    return FileManifest(
        file_size=file_size,
        piece_size=piece_size,
        piece_hashes=hashes,
        root_hash=_root_hash(hashes),
    )
