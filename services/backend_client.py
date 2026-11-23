import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen


class BackendApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class BackendClient:
    def __init__(self, base_url="http://127.0.0.1:8000", timeout=15):
        self.base_url = ""
        self.timeout = timeout
        self.access_token = None
        self.refresh_token = None
        self.set_base_url(base_url)

    @property
    def is_authenticated(self):
        return bool(self.access_token)

    def set_base_url(self, base_url):
        parsed = urlsplit(base_url.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Saisissez une adresse HTTP/HTTPS valide du serveur.")
        normalized = base_url.strip().rstrip("/")
        if normalized != self.base_url:
            self.access_token = None
            self.refresh_token = None
        self.base_url = normalized

    async def login(self, username, password):
        self.access_token = None
        self.refresh_token = None
        payload = await asyncio.to_thread(
            self._request_sync,
            "POST",
            self.base_url + "/api/v1/auth/login/",
            {"username": username, "password": password},
            False,
            False,
        )
        access = payload.get("access")
        refresh = payload.get("refresh")
        if not isinstance(access, str) or not isinstance(refresh, str):
            raise BackendApiError("Le backend n'a pas renvoyé les jetons JWT attendus.")
        self.access_token = access
        self.refresh_token = refresh

    async def list_resources(self, *, query="", category=None, course_code=None):
        params = {}
        if query:
            params["q"] = query
        if category:
            params["category"] = category
        if course_code:
            params["course_code"] = course_code
        url = self.base_url + "/api/v1/repository/resources/"
        if params:
            url += "?" + urlencode(params)
        return await self._fetch_paginated(url)

    async def list_seeders(self, resource_id):
        url = (
            f"{self.base_url}/api/v1/repository/resources/"
            f"{resource_id}/seeders/"
        )
        return await self._fetch_paginated(url)

    async def list_nodes(self):
        return await self._fetch_paginated(
            self.base_url + "/api/v1/network/nodes/"
        )

    async def register_node(self, node):
        return await asyncio.to_thread(
            self._request_sync,
            "POST",
            self.base_url + "/api/v1/network/nodes/",
            node,
            True,
            True,
        )

    async def heartbeat_node(self, node_id):
        return await asyncio.to_thread(
            self._request_sync,
            "POST",
            f"{self.base_url}/api/v1/network/nodes/{node_id}/heartbeat/",
            {},
            True,
            True,
        )

    async def delete_node(self, node_id):
        return await asyncio.to_thread(
            self._request_sync,
            "DELETE",
            f"{self.base_url}/api/v1/network/nodes/{node_id}/",
            None,
            True,
            True,
        )

    async def announce_seeder(
        self,
        resource_id,
        node_id,
        bitfield,
        pieces_available,
    ):
        return await asyncio.to_thread(
            self._request_sync,
            "POST",
            self.base_url + "/api/v1/repository/seeders/announce/",
            {
                "resource_id": str(resource_id),
                "node_id": str(node_id),
                "bitfield": bitfield,
                "pieces_available": pieces_available,
            },
            True,
            True,
        )

    async def list_chat_messages(self, ue_code, after=None):
        params = {}
        if after is not None:
            params["after"] = str(after)
        url = f"{self.base_url}/api/v1/chat/{ue_code}/messages/"
        if params:
            url += "?" + urlencode(params)
        return await self._fetch_paginated(url)

    async def send_chat_message(self, ue_code, content):
        return await asyncio.to_thread(
            self._request_sync,
            "POST",
            f"{self.base_url}/api/v1/chat/{ue_code}/messages/",
            {"content": content},
            True,
            True,
        )

    async def list_signaling_messages(self, room_id, after=None):
        params = {}
        if after is not None:
            params["after"] = str(after)
        url = f"{self.base_url}/api/v1/signaling/{room_id}/messages/"
        if params:
            url += "?" + urlencode(params)
        return await self._fetch_paginated(url)

    async def send_signaling_message(self, room_id, message_type, payload):
        return await asyncio.to_thread(
            self._request_sync,
            "POST",
            f"{self.base_url}/api/v1/signaling/{room_id}/messages/",
            {"message_type": message_type, "payload": payload},
            True,
            True,
        )

    async def create_resource(self, payload):
        return await asyncio.to_thread(
            self._request_sync,
            "POST",
            self.base_url + "/api/v1/repository/resources/",
            payload,
            True,
            True,
        )

    async def _fetch_paginated(self, url):
        results = []
        expected_origin = self._origin(self.base_url)
        page_count = 0
        while url:
            page_count += 1
            if page_count > 1000:
                raise BackendApiError("Le backend a renvoyé trop de pages.")
            if self._origin(url) != expected_origin:
                raise BackendApiError(
                    "Le backend a renvoyé une pagination vers un autre serveur."
                )
            payload = await asyncio.to_thread(
                self._request_sync,
                "GET",
                url,
                None,
                True,
                True,
            )
            if not isinstance(payload, dict) or not isinstance(
                payload.get("results"), list
            ):
                raise BackendApiError("La réponse paginée du backend est invalide.")
            if any(not isinstance(item, dict) for item in payload["results"]):
                raise BackendApiError("Le backend a renvoyé un résultat invalide.")
            results.extend(payload["results"])
            next_url = payload.get("next")
            if next_url is not None and not isinstance(next_url, str):
                raise BackendApiError("L'URL de pagination renvoyée est invalide.")
            url = urljoin(url, next_url) if next_url else None
        return results

    @staticmethod
    def _origin(url):
        parsed = urlsplit(url)
        return parsed.scheme, parsed.netloc

    def _request_sync(
        self,
        method,
        url,
        payload=None,
        authenticate=True,
        retry_unauthorized=True,
    ):
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticate:
            if not self.access_token:
                raise BackendApiError("Connectez-vous au serveur du campus.")
            headers["Authorization"] = f"Bearer {self.access_token}"

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = exc.read()
            exc.close()
            if (
                exc.code == 401
                and authenticate
                and retry_unauthorized
                and self.refresh_token
            ):
                self._refresh_access_sync()
                return self._request_sync(
                    method,
                    url,
                    payload,
                    authenticate,
                    False,
                )
            detail = self._response_detail(raw)
            if exc.code == 401 and authenticate:
                self.access_token = None
                self.refresh_token = None
            raise BackendApiError(
                f"Erreur du serveur ({exc.code}) : {detail}",
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise BackendApiError(
                f"Serveur inaccessible : {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise BackendApiError("Le délai de réponse du serveur a expiré.") from exc

        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendApiError("Le backend a renvoyé une réponse JSON invalide.") from exc
        if not isinstance(data, dict):
            raise BackendApiError("Le backend a renvoyé une réponse inattendue.")
        return data

    def _refresh_access_sync(self):
        try:
            payload = self._request_sync(
                "POST",
                self.base_url + "/api/v1/auth/refresh/",
                {"refresh": self.refresh_token},
                False,
                False,
            )
            access = payload.get("access")
            if not isinstance(access, str):
                raise BackendApiError("Le backend n'a pas renouvelé le jeton JWT.")
            self.access_token = access
        except BackendApiError:
            self.access_token = None
            self.refresh_token = None
            raise

    @staticmethod
    def _response_detail(raw):
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "réponse non détaillée"
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str):
                return detail
            return "; ".join(
                f"{key}: {value}"
                for key, value in payload.items()
            )
        return "réponse non détaillée"
