import asyncio
import base64
import ipaddress
import logging
import os
import secrets
import socket
import uuid
from urllib.parse import urlsplit

from core.p2p import FileManifest, PeerBlockServer
from .backend_client import BackendApiError

logger = logging.getLogger(__name__)


class SharingService:
    def __init__(
        self,
        backend_client,
        *,
        listen_ip=None,
        listen_port=0,
        heartbeat_interval=30,
    ):
        self.backend_client = backend_client
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.heartbeat_interval = heartbeat_interval
        self.server = None
        self.node_id = None
        self._shared_resources = set()
        self._heartbeat_task = None

    async def share_resource(self, resource, file_path):
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
        if resource_id in self._shared_resources:
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
            if self.node_id is None:
                node = await self.backend_client.register_node(
                    {
                        "node_name": self._node_name(),
                        "public_key": secrets.token_hex(32),
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
            announced = True
        finally:
            if not announced:
                if not first_resource:
                    self.server.remove_resource(manifest.root_hash)
                if first_resource:
                    await self._rollback_first_share()

        self._shared_resources.add(resource_id)
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def close(self):
        heartbeat_task = self._heartbeat_task
        self._heartbeat_task = None
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        server = self.server
        self.server = None
        self._shared_resources.clear()
        if server is not None:
            await server.close()

        node_id = self.node_id
        self.node_id = None
        if node_id is not None and self.backend_client.is_authenticated:
            await self.backend_client.delete_node(node_id)

    async def _rollback_first_share(self):
        if self.server is not None:
            await self.server.close()
            self.server = None
        node_id = self.node_id
        self.node_id = None
        if node_id is not None:
            try:
                await self.backend_client.delete_node(node_id)
            except BackendApiError:
                logger.exception("Impossible de supprimer le nœud après l'échec du partage.")

    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            if self.node_id is None or not self.backend_client.is_authenticated:
                continue
            try:
                await self.backend_client.heartbeat_node(self.node_id)
            except BackendApiError:
                logger.exception("Échec du heartbeat du nœud CampusShare.")

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

    @staticmethod
    def _node_name():
        host = socket.gethostname()
        suffix = uuid.uuid4().hex[:8]
        return f"CampusShare-{host[:78]}-{suffix}"
