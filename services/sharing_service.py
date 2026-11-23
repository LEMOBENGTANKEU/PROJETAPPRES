import asyncio
import base64
import ipaddress
import logging
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

from core.discovery import UdpPeerDiscovery
from core.p2p import FileManifest, PeerBlockServer, PieceStore
from .backend_client import BackendApiError
from .local_state import LocalStateStore

logger = logging.getLogger(__name__)


class SharingService:
    def __init__(
        self,
        backend_client,
        *,
        cache_dir=None,
        state_store=None,
        listen_ip=None,
        listen_port=0,
        heartbeat_interval=30,
        discovery_port=37020,
        enable_discovery=True,
    ):
        self.backend_client = backend_client
        home = Path.home() / "CampusShare"
        self.cache_dir = Path(cache_dir) if cache_dir else home / "cache"
        self.state_store = state_store or LocalStateStore()
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.heartbeat_interval = heartbeat_interval
        self.discovery_port = discovery_port
        self.enable_discovery = enable_discovery
        self.server = None
        self.node_id = None
        self.discovery = None
        self._shared_resources = {}
        self._heartbeat_task = None
        self._operation_lock = asyncio.Lock()

    async def share_resource(self, resource, file_path, remember=True):
        if not self.backend_client.is_authenticated:
            raise BackendApiError("Connectez-vous au serveur du campus avant de partager.")

        manifest = FileManifest(
            file_size=resource["file_size"],
            piece_size=resource["piece_size"],
            piece_hashes=tuple(resource["manifest"]),
            root_hash=resource["root_hash"],
        )
        if (
            manifest.piece_count != resource["piece_count"]
            or manifest.piece_count < 1
        ):
            raise ValueError("Le manifeste de la ressource est incohérent.")
        resource_id = str(resource["id"])
        async with self._operation_lock:
            if resource_id in self._shared_resources:
                if remember:
                    self.state_store.remember_shared_resource(resource)
                return

            first_resource = self.server is None
            if first_resource:
                server = PeerBlockServer(file_path, manifest)
                lan_ip = self.listen_ip or self._discover_lan_ip()
                address = await server.start(lan_ip, self.listen_port)
                self.server = server
                self.listen_ip, self.listen_port = address[0], address[1]
            else:
                self.server.add_resource(file_path, manifest)

            announced = False
            try:
                await self._ensure_node_registered_locked()
                await self._announce_resource_locked(resource_id, manifest)
                announced = True
            finally:
                if not announced:
                    if not first_resource:
                        self.server.remove_resource(manifest.root_hash)
                    if first_resource:
                        await self._shutdown_server_locked()
                        await self._unregister_node_locked()

            self._shared_resources[resource_id] = {
                "file_path": str(file_path),
                "manifest": manifest,
            }
            if remember:
                self.state_store.remember_shared_resource(resource)
            await self._ensure_discovery_locked()
            if self._heartbeat_task is None:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def restore_consented_shares(self):
        if not self.backend_client.is_authenticated:
            return 0
        state = self.state_store.ensure_node_identity()
        restored = 0
        for record in state.get("shared_resources", {}).values():
            try:
                restored += await self._restore_shared_record(record)
            except (BackendApiError, OSError, ValueError, TypeError, KeyError):
                logger.exception(
                    "Impossible de restaurer le partage de la ressource %s.",
                    record.get("id"),
                )
        return restored

    async def _restore_shared_record(self, record):
        resource_id = str(record["id"])
        if resource_id in self._shared_resources:
            return 0
        manifest = FileManifest(
            file_size=record["file_size"],
            piece_size=record["piece_size"],
            piece_hashes=tuple(record["manifest"]),
            root_hash=record["root_hash"],
        )
        if manifest.piece_count != record["piece_count"]:
            raise ValueError("Le manifeste local de la ressource est incohérent.")
        store = PieceStore(self.cache_dir, manifest)
        if not store.is_complete:
            return 0
        await self.share_resource(record, store.completed_path, remember=False)
        return 1

    async def close(self):
        async with self._operation_lock:
            heartbeat_task = self._heartbeat_task
            self._heartbeat_task = None
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            await self._stop_discovery_locked()
            await self._shutdown_server_locked()
            await self._unregister_node_locked()

    def discovered_peers(self):
        discovery = self.discovery
        if discovery is None:
            return []
        return discovery.peers()

    def is_resource_shared(self, resource_id):
        return str(resource_id) in self._shared_resources

    def consented_resources(self):
        return self.state_store.list_shared_resources()

    async def unshare_resource(self, resource_id, revoke_consent=True):
        resource_id = str(resource_id)
        async with self._operation_lock:
            entry = self._shared_resources.pop(resource_id, None)
            if entry is not None and self.server is not None:
                root_hash = entry.get("manifest").root_hash
                try:
                    self.server.remove_resource(root_hash)
                except Exception:
                    logger.exception("Impossible de retirer la ressource %s du serveur P2P.", resource_id)
            if revoke_consent:
                try:
                    self.state_store.forget_shared_resource(resource_id)
                except Exception:
                    logger.exception("Impossible de retirer le consentement local pour %s.", resource_id)
            if not self._shared_resources:
                heartbeat_task = self._heartbeat_task
                self._heartbeat_task = None
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
                await self._stop_discovery_locked()
                await self._shutdown_server_locked()
                await self._unregister_node_locked()

    async def _ensure_discovery_locked(self):
        if not self.enable_discovery or self.discovery is not None:
            return
        node_name = self.state_store.ensure_node_identity().get("node", {}).get("node_name", "campusshare")
        try:
            discovery = UdpPeerDiscovery(
                listen_port=self.discovery_port,
                broadcast_port=self.discovery_port,
                service_port=self.listen_port,
                node_name=node_name,
            )
            await discovery.start()
            self.discovery = discovery
        except OSError:
            self.discovery = None
            logger.exception("Impossible de démarrer la découverte UDP des pairs.")

    async def _stop_discovery_locked(self):
        discovery = self.discovery
        self.discovery = None
        if discovery is not None:
            try:
                await discovery.stop()
            except OSError:
                logger.exception("Impossible d'arrêter la découverte UDP des pairs.")

    async def _ensure_node_registered_locked(self):
        if self.node_id is not None:
            return
        state = self.state_store.ensure_node_identity()
        identity = state.get("node", {})
        node_name = identity.get("node_name")
        public_key = identity.get("public_key")
        if not node_name or not public_key:
            raise BackendApiError("L'identité locale du nœud est invalide.")

        try:
            nodes = await self.backend_client.list_nodes()
        except BackendApiError:
            nodes = []
        for node in nodes:
            if node.get("node_name") == node_name and isinstance(node.get("id"), str):
                try:
                    await self.backend_client.delete_node(node["id"])
                except BackendApiError:
                    logger.debug(
                        "Impossible de supprimer l'ancien nœud %s.", node.get("id"),
                        exc_info=True,
                    )

        node = await self.backend_client.register_node(
            {
                "node_name": node_name,
                "public_key": public_key,
                "lan_ip": self.listen_ip,
                "tcp_port": self.listen_port,
                "platform": "DESKTOP",
            }
        )
        node_id = node.get("id")
        if not isinstance(node_id, str):
            raise BackendApiError(
                "Le serveur n'a pas renvoyé l'identifiant du nœud."
            )
        self.node_id = node_id

    async def _announce_resource_locked(self, resource_id, manifest):
        bitfield = base64.b64encode(
            bytes([0xFF] * (manifest.piece_count // 8))
            + (
                bytes([(1 << (manifest.piece_count % 8)) - 1])
                if manifest.piece_count % 8
                else b""
            )
        ).decode("ascii")
        await self.backend_client.announce_seeder(
            resource_id,
            self.node_id,
            bitfield,
            manifest.piece_count,
        )

    async def _shutdown_server_locked(self):
        server = self.server
        self.server = None
        self._shared_resources.clear()
        if server is not None:
            await server.close()

    async def _unregister_node_locked(self):
        node_id = self.node_id
        self.node_id = None
        if node_id is not None and self.backend_client.is_authenticated:
            try:
                await self.backend_client.delete_node(node_id)
            except BackendApiError:
                logger.exception("Impossible de désenregistrer le nœud CampusShare.")

    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                await self._heartbeat_tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Échec du cycle de présence du nœud CampusShare.")

    async def _heartbeat_tick(self):
        async with self._operation_lock:
            if self.node_id is None or not self.backend_client.is_authenticated:
                return
            if self.server is None or not self._shared_resources:
                return
            try:
                await self.backend_client.heartbeat_node(self.node_id)
                return
            except BackendApiError as exc:
                if exc.status_code not in {401, 403, 404}:
                    raise

            # Le nœud a expiré ou la session a changé : réenregistrement + annonces.
            self.node_id = None
            try:
                await self._ensure_node_registered_locked()
                for resource_id, payload in list(self._shared_resources.items()):
                    await self._announce_resource_locked(
                        resource_id,
                        payload["manifest"],
                    )
            except BackendApiError:
                logger.exception(
                    "Impossible de réenregistrer le nœud et ses ressources."
                )

    def _discover_lan_ip(self):
        override = os.environ.get("CAMPUSSHARE_NODE_IP")
        if override:
            address = ipaddress.ip_address(override)
            if address.is_private and not address.is_loopback:
                return str(address)
            raise ValueError("CAMPUSSHARE_NODE_IP doit être une adresse LAN privée.")

        host = urlsplit(self.backend_client.base_url).hostname
        candidates = []
        if host:
            try:
                addresses = socket.getaddrinfo(host, None, socket.AF_INET)
                candidates.extend(item[4][0] for item in addresses)
            except socket.gaierror:
                pass
        for candidate in candidates:
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if address.is_private and not address.is_loopback:
                return str(address)

        try:
            addresses = socket.getaddrinfo(
                socket.gethostname(),
                None,
                socket.AF_INET,
            )
        except socket.gaierror:
            addresses = ()
        for item in addresses:
            address = ipaddress.ip_address(item[4][0])
            if address.is_private and not address.is_loopback:
                return str(address)
        raise ValueError(
            "Impossible de détecter l'adresse LAN. Configurez CAMPUSSHARE_NODE_IP."
        )
