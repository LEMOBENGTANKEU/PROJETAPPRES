import asyncio
import json
import socket
import time
import unittest

from core.discovery import UdpPeerDiscovery


class UdpPeerDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_datagram_registers_remote_peer(self):
        discovery = UdpPeerDiscovery(
            service_port=9000,
            node_name="self",
            broadcast_port=8766,
        )
        payload = json.dumps(
            {
                "type": "campusshare.peer",
                "instance_id": "remote-1",
                "node_name": "laptop-a",
                "service_port": 9100,
                "timestamp": time.time(),
            }
        ).encode("utf-8")

        discovery.handle_datagram(payload, ("192.168.1.20", 8766))

        peers = discovery.peers
        self.assertIn("remote-1", peers)
        self.assertEqual(peers["remote-1"]["host"], "192.168.1.20")
        self.assertEqual(peers["remote-1"]["service_port"], 9100)

    async def test_ignores_self_and_invalid_payloads(self):
        discovery = UdpPeerDiscovery(service_port=9000, node_name="self")
        self_payload = json.dumps(
            {
                "type": "campusshare.peer",
                "instance_id": discovery.instance_id,
                "node_name": "self",
                "service_port": 9000,
            }
        ).encode("utf-8")
        discovery.handle_datagram(self_payload, ("192.168.1.2", 8766))
        discovery.handle_datagram(b"not-json", ("192.168.1.3", 8766))
        discovery.handle_datagram(
            json.dumps({"type": "other", "instance_id": "x"}).encode("utf-8"),
            ("192.168.1.4", 8766),
        )
        self.assertEqual(discovery.peers, {})

    async def test_prunes_expired_peers(self):
        discovery = UdpPeerDiscovery(
            service_port=9000,
            node_name="self",
            peer_ttl=0.01,
        )
        discovery.handle_datagram(
            json.dumps(
                {
                    "type": "campusshare.peer",
                    "instance_id": "remote-1",
                    "node_name": "laptop-a",
                    "service_port": 9100,
                }
            ).encode("utf-8"),
            ("192.168.1.20", 8766),
        )
        await asyncio.sleep(0.05)
        self.assertEqual(discovery.peers, {})

    async def test_start_stop_and_receive_unicast_datagram(self):
        # Port 0 n'est pas pratique pour UDP bind dans cette implémentation;
        # on choisit un port élevé probablement libre.
        port = 18766
        discovery = UdpPeerDiscovery(
            service_port=9000,
            node_name="self",
            broadcast_port=port,
            interval=60,
            bind_ip="127.0.0.1",
        )
        await discovery.start()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                payload = json.dumps(
                    {
                        "type": "campusshare.peer",
                        "instance_id": "remote-live",
                        "node_name": "remote",
                        "service_port": 9200,
                    }
                ).encode("utf-8")
                sock.sendto(payload, ("127.0.0.1", port))
            finally:
                sock.close()
            for _ in range(50):
                if "remote-live" in discovery.peers:
                    break
                await asyncio.sleep(0.02)
            self.assertIn("remote-live", discovery.peers)
        finally:
            await discovery.stop()
