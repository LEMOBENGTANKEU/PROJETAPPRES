import asyncio
import json
import socket
import time
import uuid


class UdpPeerDiscovery:
    def __init__(
        self,
        *,
        service_port,
        node_name,
        broadcast_port=8766,
        interval=5,
        peer_ttl=20,
        bind_ip="0.0.0.0",
    ):
        self.service_port = int(service_port)
        self.node_name = node_name
        self.broadcast_port = int(broadcast_port)
        self.interval = float(interval)
        self.peer_ttl = float(peer_ttl)
        self.bind_ip = bind_ip
        self.instance_id = uuid.uuid4().hex
        self._peers = {}
        self._transport = None
        self._protocol = None
        self._tasks = []
        self._running = False

    @property
    def peers(self):
        self._prune(time.monotonic())
        return dict(self._peers)

    async def start(self):
        if self._running:
            return
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _DiscoveryProtocol(self),
            local_addr=(self.bind_ip, self.broadcast_port),
            allow_broadcast=True,
        )
        sock = transport.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._transport = transport
        self._protocol = protocol
        self._running = True
        self._tasks = [
            asyncio.create_task(self._announce_loop()),
            asyncio.create_task(self._cleanup_loop()),
        ]
        await self.announce_once()

    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        self._protocol = None

    async def announce_once(self):
        if self._transport is None:
            return
        payload = {
            "type": "campusshare.peer",
            "instance_id": self.instance_id,
            "node_name": self.node_name,
            "service_port": self.service_port,
            "timestamp": time.time(),
        }
        message = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        try:
            self._transport.sendto(message, ("255.255.255.255", self.broadcast_port))
        except OSError:
            return

    async def _announce_loop(self):
        while self._running:
            await asyncio.sleep(self.interval)
            await self.announce_once()

    async def _cleanup_loop(self):
        while self._running:
            await asyncio.sleep(max(1.0, self.interval))
            self._prune(time.monotonic())

    def handle_datagram(self, data, addr):
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        if payload.get("type") != "campusshare.peer":
            return
        if payload.get("instance_id") == self.instance_id:
            return
        node_name = payload.get("node_name")
        service_port = payload.get("service_port")
        if not isinstance(node_name, str) or not isinstance(service_port, int):
            return
        if not 1 <= service_port <= 65535:
            return
        host = addr[0] if addr else None
        if not isinstance(host, str):
            return
        self._peers[payload.get("instance_id", f"{host}:{service_port}")] = {
            "host": host,
            "node_name": node_name,
            "service_port": service_port,
            "last_seen": time.monotonic(),
        }

    def _prune(self, now):
        expired = [
            key
            for key, peer in self._peers.items()
            if now - peer.get("last_seen", 0) > self.peer_ttl
        ]
        for key in expired:
            self._peers.pop(key, None)


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, discovery):
        self.discovery = discovery

    def datagram_received(self, data, addr):
        self.discovery.handle_datagram(data, addr)

    def error_received(self, exc):
        return
