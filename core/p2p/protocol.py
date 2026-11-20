import asyncio
import base64
import binascii
import hashlib
import ipaddress
import json
import logging
import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import IntegrityError, ProtocolError
from .manifest import FileManifest
from .storage import PieceStore

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
MAX_HEADER_BYTES = 64 * 1024
MAX_CONCURRENT_PEERS = 16
PEER_IO_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class PeerEndpoint:
    host: str
    port: int

    def __post_init__(self):
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError as exc:
            raise ValueError("L'adresse du pair doit être une adresse IP.") from exc
        if (
            not address.is_private
            and not address.is_loopback
            or address.is_multicast
            or address.is_unspecified
            or address.is_link_local
        ):
            raise ValueError("Les transferts P2P sont limités aux adresses IP privées.")
        if not 1 <= self.port <= 65535:
            raise ValueError("Le port doit être compris entre 1 et 65535.")


async def _send_json(writer, payload):
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if not encoded or len(encoded) > MAX_HEADER_BYTES:
        raise ProtocolError("La trame JSON dépasse la taille maximale.")
    writer.write(struct.pack("!I", len(encoded)) + encoded)
    await writer.drain()


async def _read_json(reader):
    try:
        prefix = await asyncio.wait_for(
            reader.readexactly(4),
            timeout=PEER_IO_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise ProtocolError("Le pair n'a pas envoyé de message à temps.") from exc
    size = struct.unpack("!I", prefix)[0]
    if not 1 <= size <= MAX_HEADER_BYTES:
        raise ProtocolError("La taille de la trame JSON est invalide.")
    try:
        raw = await asyncio.wait_for(
            reader.readexactly(size),
            timeout=PEER_IO_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise ProtocolError("Le pair n'a pas terminé son message à temps.") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("La trame JSON est invalide.") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("La trame JSON doit être un objet.")
    return payload


def _make_bitfield(piece_count, available_pieces):
    bitfield = bytearray((piece_count + 7) // 8)
    for index in available_pieces:
        bitfield[index // 8] |= 1 << (index % 8)
    return base64.b64encode(bitfield).decode("ascii")


def _decode_bitfield(encoded, piece_count):
    if not isinstance(encoded, str):
        raise ProtocolError("Le bitfield doit être encodé en base64.")
    try:
        bitfield = base64.b64decode(encoded, validate=True)
    except (TypeError, ValueError, binascii.Error) as exc:
        raise ProtocolError("Le bitfield reçu n'est pas du base64 valide.") from exc
    expected_size = (piece_count + 7) // 8
    if len(bitfield) != expected_size:
        raise ProtocolError("La taille du bitfield ne correspond pas au manifeste.")
    if piece_count % 8 and bitfield:
        unused_mask = 0xFF << (piece_count % 8) & 0xFF
        if bitfield[-1] & unused_mask:
            raise ProtocolError("Le bitfield contient des blocs hors manifeste.")
    return bitfield


class PeerBlockServer:
    def __init__(self, source_path, manifest, available_pieces=None):
        self.source_path = Path(source_path)
        self.manifest = manifest
        self._server = None
        self._slots = asyncio.Semaphore(MAX_CONCURRENT_PEERS)
        if self.source_path.stat().st_size != manifest.file_size:
            raise ValueError("Le fichier source ne correspond pas à la taille du manifeste.")
        if available_pieces is None:
            available_pieces = range(manifest.piece_count)
        self.update_availability(available_pieces)

    def update_availability(self, available_pieces):
        available = set(available_pieces)
        if any(
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < self.manifest.piece_count
            for index in available
        ):
            raise ValueError("La disponibilité contient un index de bloc invalide.")
        self._available_pieces = frozenset(available)

    async def start(self, host, port):
        if self._server is not None:
            raise RuntimeError("Le serveur P2P est déjà démarré.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("Le serveur doit être lié à une adresse IP locale explicite.") from exc
        if (
            (not address.is_private and not address.is_loopback)
            or address.is_multicast
            or address.is_unspecified
            or address.is_link_local
        ):
            raise ValueError("Le serveur P2P ne peut écouter que sur une adresse LAN privée.")
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError("Le port doit être compris entre 0 et 65535.")
        self._server = await asyncio.start_server(
            self._handle_client,
            host,
            port,
            limit=MAX_HEADER_BYTES + 4,
        )
        return self._server.sockets[0].getsockname()

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def serve_forever(self):
        if self._server is None:
            raise RuntimeError("Le serveur P2P n'est pas démarré.")
        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(self, reader, writer):
        try:
            async with self._slots:
                await self._serve_client(reader, writer)
        except asyncio.IncompleteReadError:
            pass
        except (ConnectionError, OSError):
            logger.debug("Connexion P2P interrompue.", exc_info=True)
        except ProtocolError:
            logger.warning("Message P2P invalide reçu.", exc_info=True)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                logger.debug("Fermeture de connexion P2P interrompue.", exc_info=True)

    async def _serve_client(self, reader, writer):
        hello = await _read_json(reader)
        if (
            hello.get("type") != "HELLO"
            or type(hello.get("protocol")) is not int
            or hello.get("protocol") != PROTOCOL_VERSION
        ):
            await _send_json(writer, {"type": "ERROR", "message": "Version de protocole invalide."})
            return
        if hello.get("root_hash") != self.manifest.root_hash:
            await _send_json(writer, {"type": "ERROR", "message": "Ressource inconnue."})
            return

        await _send_json(
            writer,
            {
                "type": "BITFIELD",
                "root_hash": self.manifest.root_hash,
                "piece_count": self.manifest.piece_count,
                "bitfield": _make_bitfield(
                    self.manifest.piece_count,
                    self._available_pieces,
                ),
            },
        )

        while True:
            request = await _read_json(reader)
            index = request.get("index")
            if (
                request.get("type") != "REQUEST"
                or not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < self.manifest.piece_count
            ):
                await _send_json(writer, {"type": "ERROR", "message": "Demande de bloc invalide."})
                return
            if index not in self._available_pieces:
                await _send_json(writer, {"type": "ERROR", "message": "Bloc indisponible."})
                return

            expected_length = self.manifest.piece_length(index)
            with self.source_path.open("rb") as source:
                source.seek(index * self.manifest.piece_size)
                data = source.read(expected_length)
            if (
                len(data) != expected_length
                or hashlib.sha256(data).hexdigest()
                != self.manifest.piece_hashes[index]
            ):
                await _send_json(writer, {"type": "ERROR", "message": "Le bloc source est corrompu."})
                return

            await _send_json(
                writer,
                {"type": "PIECE", "index": index, "size": len(data)},
            )
            writer.write(data)
            await writer.drain()


async def download_piece(endpoint, manifest, index, store, timeout=10):
    if not isinstance(endpoint, PeerEndpoint):
        raise TypeError("endpoint doit être un PeerEndpoint.")
    if not isinstance(manifest, FileManifest) or store.manifest != manifest:
        raise ValueError("Le manifeste du stockage et du transfert doit correspondre.")
    if not 0 <= index < manifest.piece_count:
        raise IndexError("Index de bloc hors limites.")
    if store.has_piece(index):
        return store.read_piece(index)

    async def transfer():
        reader, writer = await asyncio.open_connection(endpoint.host, endpoint.port)
        try:
            await _send_json(
                writer,
                {
                    "type": "HELLO",
                    "protocol": PROTOCOL_VERSION,
                    "root_hash": manifest.root_hash,
                },
            )
            bitfield_frame = await _read_json(reader)
            if bitfield_frame.get("type") == "ERROR":
                raise ProtocolError(bitfield_frame.get("message", "Le pair a refusé la connexion."))
            if (
                bitfield_frame.get("type") != "BITFIELD"
                or bitfield_frame.get("root_hash") != manifest.root_hash
                or type(bitfield_frame.get("piece_count")) is not int
                or bitfield_frame.get("piece_count") != manifest.piece_count
            ):
                raise ProtocolError("Le pair a renvoyé un manifeste différent.")
            bitfield = _decode_bitfield(
                bitfield_frame.get("bitfield", ""),
                manifest.piece_count,
            )
            if not bitfield[index // 8] & (1 << (index % 8)):
                raise ProtocolError("Le pair ne possède pas le bloc demandé.")

            await _send_json(writer, {"type": "REQUEST", "index": index})
            piece_frame = await _read_json(reader)
            if piece_frame.get("type") == "ERROR":
                raise ProtocolError(piece_frame.get("message", "Le pair a refusé le bloc."))
            expected_length = manifest.piece_length(index)
            if (
                piece_frame.get("type") != "PIECE"
                or type(piece_frame.get("index")) is not int
                or piece_frame.get("index") != index
                or type(piece_frame.get("size")) is not int
                or piece_frame.get("size") != expected_length
            ):
                raise ProtocolError("La réponse du pair ne correspond pas au bloc demandé.")
            data = await reader.readexactly(expected_length)
            if hashlib.sha256(data).hexdigest() != manifest.piece_hashes[index]:
                raise IntegrityError("L'empreinte SHA-256 du bloc reçu est invalide.")
            store.write_piece(index, data)
            return data
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                logger.debug("Fermeture de connexion P2P interrompue.", exc_info=True)

    try:
        return await asyncio.wait_for(transfer(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise ProtocolError("Le délai de connexion au pair a expiré.") from exc


async def get_peer_pieces(endpoint, manifest, timeout=10):
    if not isinstance(endpoint, PeerEndpoint):
        raise TypeError("endpoint doit être un PeerEndpoint.")
    if not isinstance(manifest, FileManifest):
        raise TypeError("manifest doit être un FileManifest.")

    async def query():
        reader, writer = await asyncio.open_connection(endpoint.host, endpoint.port)
        try:
            await _send_json(
                writer,
                {
                    "type": "HELLO",
                    "protocol": PROTOCOL_VERSION,
                    "root_hash": manifest.root_hash,
                },
            )
            frame = await _read_json(reader)
            if frame.get("type") == "ERROR":
                raise ProtocolError(frame.get("message", "Le pair a refusé la connexion."))
            if (
                frame.get("type") != "BITFIELD"
                or frame.get("root_hash") != manifest.root_hash
                or type(frame.get("piece_count")) is not int
                or frame.get("piece_count") != manifest.piece_count
            ):
                raise ProtocolError("Le pair a renvoyé un manifeste différent.")
            bitfield = _decode_bitfield(frame.get("bitfield", ""), manifest.piece_count)
            return frozenset(
                index
                for index in range(manifest.piece_count)
                if bitfield[index // 8] & (1 << (index % 8))
            )
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                logger.debug("Fermeture de connexion P2P interrompue.", exc_info=True)

    try:
        return await asyncio.wait_for(query(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise ProtocolError("Le délai de connexion au pair a expiré.") from exc
