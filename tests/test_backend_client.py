import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from services.backend_client import BackendApiError, BackendClient


class BackendHandler(BaseHTTPRequestHandler):
    external_pagination = False
    authorization_headers = []
    requests = []

    def log_message(self, _format_string, *_args):
        return

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _respond(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self._read_json()
        if self.path == "/api/v1/auth/login/":
            return self._respond(
                200,
                {"access": "expired-access", "refresh": "refresh-token"},
            )
        if self.path == "/api/v1/auth/refresh/":
            return self._respond(200, {"access": "fresh-access"})
        return self._respond(404, {"detail": "Not found"})

    def do_GET(self):
        BackendHandler.authorization_headers.append(
            self.headers.get("Authorization")
        )
        BackendHandler.requests.append(self.path)
        if self.headers.get("Authorization") == "Bearer expired-access":
            return self._respond(401, {"detail": "Token expired"})
        if self.headers.get("Authorization") != "Bearer fresh-access":
            return self._respond(401, {"detail": "Authentication required"})

        query = parse_qs(urlsplit(self.path).query)
        if query.get("page") == ["2"]:
            return self._respond(
                200,
                {"count": 2, "next": None, "results": [{"id": "second"}]},
            )

        if BackendHandler.external_pagination:
            next_url = "http://example.invalid/resources/?page=2"
        else:
            next_url = (
                f"http://{self.headers['Host']}"
                "/api/v1/repository/resources/?page=2"
            )
        return self._respond(
            200,
            {
                "count": 2,
                "next": next_url,
                "results": [{"id": "first"}],
            },
        )


class BackendClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        BackendHandler.external_pagination = False
        BackendHandler.authorization_headers = []
        BackendHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), BackendHandler)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.server_thread.start()
        host, port = self.server.server_address
        self.client = BackendClient(f"http://{host}:{port}")

    async def asyncTearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)

    async def test_login_refresh_and_pagination_use_authenticated_requests(self):
        await self.client.login("student", "password")

        resources = await self.client.list_resources(query="networks")

        self.assertEqual(resources, [{"id": "first"}, {"id": "second"}])
        self.assertEqual(self.client.access_token, "fresh-access")
        self.assertEqual(
            BackendHandler.authorization_headers,
            ["Bearer expired-access", "Bearer fresh-access", "Bearer fresh-access"],
        )
        self.assertIn("q=networks", BackendHandler.requests[0])

    async def test_pagination_cannot_forward_authentication_to_another_server(self):
        BackendHandler.external_pagination = True
        await self.client.login("student", "password")

        with self.assertRaises(BackendApiError):
            await self.client.list_resources()

        self.assertEqual(
            sum("page=2" in request for request in BackendHandler.requests),
            0,
        )

    def test_websocket_url_includes_access_token(self):
        self.client.access_token = "abc123"
        ws_url = self.client.websocket_url("/ws/chat/INF101/")
        self.assertTrue(ws_url.startswith("ws://"))
        self.assertIn("/ws/chat/INF101/", ws_url)
        self.assertIn("token=abc123", ws_url)
