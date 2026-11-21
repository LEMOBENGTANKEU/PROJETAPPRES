import asyncio
import inspect
import logging
from dataclasses import dataclass

from .errors import P2PError, TransferError
from .manifest import FileManifest
from .protocol import PeerEndpoint, download_piece, get_peer_pieces

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransferProgress:
    completed_pieces: int
    total_pieces: int
    piece_index: int
    peer: PeerEndpoint


@dataclass(frozen=True)
class TransferSummary:
    file_path: str
    completed_pieces: int
    total_pieces: int
    peer_piece_counts: dict[PeerEndpoint, int]


def order_pieces_by_rarity(missing_pieces, peer_pieces):
    peer_sets = tuple(frozenset(pieces) for pieces in peer_pieces)
    return tuple(
        sorted(
            missing_pieces,
            key=lambda index: (
                sum(index in pieces for pieces in peer_sets),
                index,
            ),
        )
    )


async def download_resource(
    peers,
    manifest,
    store,
    *,
    concurrency=4,
    per_peer_concurrency=2,
    timeout=10,
    on_piece_complete=None,
):
    if not isinstance(manifest, FileManifest) or store.manifest != manifest:
        raise ValueError("Le manifeste du stockage et du transfert doit correspondre.")
    if not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1:
        raise ValueError("concurrency doit être un entier supérieur à zéro.")
    if (
        not isinstance(per_peer_concurrency, int)
        or isinstance(per_peer_concurrency, bool)
        or per_peer_concurrency < 1
    ):
        raise ValueError("per_peer_concurrency doit être un entier supérieur à zéro.")

    unique_peers = tuple(dict.fromkeys(peers))
    if any(not isinstance(peer, PeerEndpoint) for peer in unique_peers):
        raise TypeError("Tous les pairs doivent être des PeerEndpoint.")

    missing_pieces = set(range(manifest.piece_count)) - set(store.completed_pieces)
    if not missing_pieces:
        completed_path = store.finalize()
        return TransferSummary(
            str(completed_path),
            manifest.piece_count,
            manifest.piece_count,
            {},
        )
    if not unique_peers:
        raise TransferError("Aucun pair n'est disponible pour les blocs manquants.")

    async def inspect_peer(peer):
        try:
            available = await get_peer_pieces(peer, manifest, timeout=timeout)
            return peer, available, None
        except (P2PError, OSError, ConnectionError) as exc:
            logger.warning("Pair %s:%s indisponible: %s", peer.host, peer.port, exc)
            return peer, frozenset(), exc

    peer_results = await asyncio.gather(*(inspect_peer(peer) for peer in unique_peers))
    availability = {
        peer: pieces & missing_pieces
        for peer, pieces, _ in peer_results
        if pieces & missing_pieces
    }
    if not availability:
        failures = [
            f"{peer.host}:{peer.port}: {error}"
            for peer, _, error in peer_results
            if error is not None
        ]
        detail = f" Détails: {'; '.join(failures)}" if failures else ""
        raise TransferError(f"Aucun pair ne possède les blocs manquants.{detail}")

    uncovered_pieces = missing_pieces - set().union(*availability.values())
    ordered_pieces = order_pieces_by_rarity(missing_pieces, availability.values())
    queue = asyncio.Queue()
    for index in ordered_pieces:
        queue.put_nowait(index)

    peer_semaphores = {
        peer: asyncio.Semaphore(per_peer_concurrency) for peer in availability
    }
    peer_piece_counts = {peer: 0 for peer in availability}
    peer_in_flight = {peer: 0 for peer in availability}
    peer_lock = asyncio.Lock()
    completed_count = len(store.completed_pieces)
    progress_lock = asyncio.Lock()
    failures = []

    async def download_one(index):
        candidates = [
            peer for peer, pieces in availability.items() if index in pieces
        ]
        candidates.sort(key=lambda peer: (peer_in_flight[peer], peer.host, peer.port))
        last_error = None
        for peer in candidates:
            async with peer_semaphores[peer]:
                async with peer_lock:
                    peer_in_flight[peer] += 1
                try:
                    await download_piece(
                        peer,
                        manifest,
                        index,
                        store,
                        timeout=timeout,
                    )
                    peer_piece_counts[peer] += 1
                    return peer
                except (P2PError, OSError, ConnectionError) as exc:
                    last_error = exc
                    logger.warning(
                        "Échec du bloc %s depuis %s:%s: %s",
                        index,
                        peer.host,
                        peer.port,
                        exc,
                    )
                finally:
                    async with peer_lock:
                        peer_in_flight[peer] -= 1
        raise TransferError(
            f"Aucun pair n'a pu fournir le bloc {index}: {last_error}"
        )

    async def worker():
        nonlocal completed_count
        while True:
            try:
                index = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                if not any(index in pieces for pieces in availability.values()):
                    failures.append(
                        TransferError(f"Aucun pair n'annonce le bloc {index}.")
                    )
                    continue
                peer = await download_one(index)
                async with progress_lock:
                    completed_count += 1
                    progress = TransferProgress(
                        completed_pieces=completed_count,
                        total_pieces=manifest.piece_count,
                        piece_index=index,
                        peer=peer,
                    )
                    if on_piece_complete is not None:
                        result = on_piece_complete(progress)
                        if inspect.isawaitable(result):
                            await result
            except TransferError as exc:
                failures.append(exc)
            finally:
                queue.task_done()

    await asyncio.gather(
        *(worker() for _ in range(min(concurrency, len(ordered_pieces))))
    )

    if failures:
        reasons = "; ".join(str(error) for error in failures)
        if uncovered_pieces:
            missing = ", ".join(str(index) for index in sorted(uncovered_pieces))
            reasons += f"; aucun pair n'annonce les blocs {missing}"
        raise TransferError(f"Transfert incomplet: {reasons}")

    completed_path = store.finalize()
    return TransferSummary(
        file_path=str(completed_path),
        completed_pieces=manifest.piece_count,
        total_pieces=manifest.piece_count,
        peer_piece_counts={
            peer: count for peer, count in peer_piece_counts.items() if count
        },
    )
