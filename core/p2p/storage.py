import hashlib
import json
import os
from pathlib import Path

from .errors import IntegrityError, StorageError
from .manifest import FileManifest


class PieceStore:
    def __init__(self, cache_dir, manifest):
        if not isinstance(manifest, FileManifest):
            raise TypeError("manifest doit être un FileManifest.")
        self.manifest = manifest
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.part_path = self.cache_dir / f"{manifest.root_hash}.part"
        self.journal_path = self.cache_dir / f"{manifest.root_hash}.json"
        self.completed_path = self.cache_dir / f"{manifest.root_hash}.complete"
        self._completed = set()
        self._is_complete = False

        if self.completed_path.exists():
            self._verify_completed_file()
            self._completed = set(range(manifest.piece_count))
            self._is_complete = True
            return

        self._load_journal()
        self._verify_journaled_pieces()
        with self.part_path.open("r+b" if self.part_path.exists() else "w+b") as part:
            part.truncate(manifest.file_size)
            part.flush()
            os.fsync(part.fileno())

    @property
    def completed_pieces(self):
        return frozenset(self._completed)

    @property
    def is_complete(self):
        return self._is_complete

    def has_piece(self, index):
        return index in self._completed

    def _load_journal(self):
        if not self.journal_path.exists():
            return
        try:
            payload = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError("Le journal de reprise est illisible.") from exc

        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or payload.get("root_hash") != self.manifest.root_hash
            or payload.get("piece_count") != self.manifest.piece_count
            or not isinstance(payload.get("completed"), list)
        ):
            raise StorageError("Le journal de reprise ne correspond pas au manifeste.")

        completed = payload["completed"]
        if any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < self.manifest.piece_count
            for index in completed
        ):
            raise StorageError("Le journal contient un index de bloc invalide.")
        self._completed = set(completed)

    def _verify_journaled_pieces(self):
        if not self._completed:
            return
        if not self.part_path.exists():
            self._completed.clear()
            self._save_journal(self._completed)
            return

        valid = set()
        with self.part_path.open("rb") as part:
            for index in self._completed:
                if self._piece_matches(part, index):
                    valid.add(index)
        if valid != self._completed:
            self._completed = valid
            self._save_journal(valid)

    def _piece_matches(self, part, index):
        part.seek(index * self.manifest.piece_size)
        data = part.read(self.manifest.piece_length(index))
        return (
            len(data) == self.manifest.piece_length(index)
            and hashlib.sha256(data).hexdigest()
            == self.manifest.piece_hashes[index]
        )

    def _save_journal(self, completed):
        payload = {
            "version": 1,
            "root_hash": self.manifest.root_hash,
            "piece_count": self.manifest.piece_count,
            "completed": sorted(completed),
        }
        temporary_path = self.journal_path.with_suffix(".json.tmp")
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as journal:
                json.dump(payload, journal, separators=(",", ":"))
                journal.flush()
                os.fsync(journal.fileno())
            os.replace(temporary_path, self.journal_path)
        except OSError as exc:
            raise StorageError("Impossible d'enregistrer le journal de reprise.") from exc

    def write_piece(self, index, data):
        if self._is_complete:
            raise StorageError("Le fichier est déjà complet.")
        expected_hash = self.manifest.piece_hashes[index]
        expected_length = self.manifest.piece_length(index)
        if len(data) != expected_length:
            raise IntegrityError("La taille du bloc reçu est incorrecte.")
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise IntegrityError("L'empreinte SHA-256 du bloc reçu est invalide.")

        try:
            with self.part_path.open("r+b") as part:
                part.seek(index * self.manifest.piece_size)
                part.write(data)
                part.flush()
                os.fsync(part.fileno())
            completed = self._completed | {index}
            self._save_journal(completed)
        except OSError as exc:
            raise StorageError("Impossible d'écrire le bloc sur le disque.") from exc
        self._completed = completed

    def read_piece(self, index):
        if not self.has_piece(index):
            raise StorageError("Le bloc demandé n'est pas encore validé.")
        source_path = self.completed_path if self._is_complete else self.part_path
        with source_path.open("rb") as source:
            source.seek(index * self.manifest.piece_size)
            return source.read(self.manifest.piece_length(index))

    def finalize(self):
        if self._is_complete:
            return self.completed_path
        if len(self._completed) != self.manifest.piece_count:
            raise StorageError("Impossible de finaliser un transfert incomplet.")

        with self.part_path.open("rb") as part:
            actual_hashes = []
            for index in range(self.manifest.piece_count):
                data = part.read(self.manifest.piece_length(index))
                digest = hashlib.sha256(data).hexdigest()
                if digest != self.manifest.piece_hashes[index]:
                    raise IntegrityError("Le fichier partiel a été modifié.")
                actual_hashes.append(bytes.fromhex(digest))
        actual_root = hashlib.sha256(b"".join(actual_hashes)).hexdigest()
        if actual_root != self.manifest.root_hash:
            raise IntegrityError("L'empreinte racine du fichier est invalide.")

        try:
            os.replace(self.part_path, self.completed_path)
            self.journal_path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Impossible de finaliser le fichier téléchargé.") from exc
        self._is_complete = True
        return self.completed_path

    def _verify_completed_file(self):
        try:
            if self.completed_path.stat().st_size != self.manifest.file_size:
                raise IntegrityError("La taille du fichier final est incorrecte.")
            actual_hashes = []
            with self.completed_path.open("rb") as completed:
                for index in range(self.manifest.piece_count):
                    data = completed.read(self.manifest.piece_length(index))
                    digest = hashlib.sha256(data).hexdigest()
                    if digest != self.manifest.piece_hashes[index]:
                        raise IntegrityError("Un bloc du fichier final est corrompu.")
                    actual_hashes.append(bytes.fromhex(digest))
            if hashlib.sha256(b"".join(actual_hashes)).hexdigest() != self.manifest.root_hash:
                raise IntegrityError("L'empreinte racine du fichier final est invalide.")
        except OSError as exc:
            raise StorageError("Impossible de vérifier le fichier final.") from exc
