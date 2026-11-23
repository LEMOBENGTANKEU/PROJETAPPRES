import json
import os
import secrets
import socket
import tempfile
import uuid
from pathlib import Path


class LocalStateStore:
    def __init__(self, state_path=None):
        home = Path.home() / "CampusShare"
        self.state_path = Path(state_path) if state_path else home / "state.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return self._default_state()
        except (OSError, json.JSONDecodeError):
            return self._default_state()
        if not isinstance(data, dict):
            return self._default_state()
        state = self._default_state()
        node = data.get("node")
        if isinstance(node, dict):
            for key in ("node_name", "public_key"):
                value = node.get(key)
                if isinstance(value, str) and value:
                    state["node"][key] = value
        shared = data.get("shared_resources")
        if isinstance(shared, dict):
            for resource_id, record in shared.items():
                if not isinstance(resource_id, str) or not isinstance(record, dict):
                    continue
                normalized = self._normalize_shared_record(resource_id, record)
                if normalized is not None:
                    state["shared_resources"][resource_id] = normalized
        return state

    def save(self, state):
        payload = self._default_state()
        node = state.get("node") if isinstance(state, dict) else None
        if isinstance(node, dict):
            payload["node"]["node_name"] = node.get("node_name") or payload["node"]["node_name"]
            payload["node"]["public_key"] = node.get("public_key") or payload["node"]["public_key"]
        shared = state.get("shared_resources") if isinstance(state, dict) else None
        if isinstance(shared, dict):
            for resource_id, record in shared.items():
                normalized = self._normalize_shared_record(resource_id, record)
                if normalized is not None:
                    payload["shared_resources"][resource_id] = normalized
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=self.state_path.parent,
                delete=False,
                suffix=".tmp",
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.state_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
        return payload

    def ensure_node_identity(self, state=None):
        state = state or self.load()
        node = state.setdefault("node", {})
        changed = False
        if not isinstance(node.get("public_key"), str) or not node.get("public_key"):
            node["public_key"] = secrets.token_hex(32)
            changed = True
        if not isinstance(node.get("node_name"), str) or not node.get("node_name"):
            host = socket.gethostname() or "CampusShare"
            node["node_name"] = f"CampusShare-{host[:72]}-{uuid.uuid4().hex[:8]}"
            changed = True
        if changed:
            state = self.save(state)
        return state

    def remember_shared_resource(self, resource):
        state = self.ensure_node_identity()
        record = self._normalize_shared_record(str(resource.get("id", "")), resource)
        if record is None:
            raise ValueError("La ressource partagée est invalide.")
        state["shared_resources"][record["id"]] = record
        return self.save(state)

    def forget_shared_resource(self, resource_id):
        state = self.ensure_node_identity()
        resource_id = str(resource_id)
        shared = state.get("shared_resources", {})
        if resource_id in shared:
            shared.pop(resource_id, None)
            return self.save(state)
        return state

    def list_shared_resources(self):
        state = self.load()
        shared = state.get("shared_resources", {})
        if not isinstance(shared, dict):
            return []
        return list(shared.values())

    def _normalize_shared_record(self, resource_id, record):
        if not isinstance(resource_id, str) or not resource_id:
            resource_id = str(record.get("id", ""))
        if not resource_id:
            return None
        manifest = record.get("manifest")
        if not isinstance(manifest, list):
            return None
        try:
            file_size = int(record["file_size"])
            piece_size = int(record["piece_size"])
            piece_count = int(record["piece_count"])
        except (KeyError, TypeError, ValueError):
            return None
        root_hash = record.get("root_hash")
        file_name = record.get("file_name")
        if not isinstance(root_hash, str) or not root_hash:
            return None
        if not isinstance(file_name, str) or not file_name:
            file_name = root_hash
        return {
            "id": resource_id,
            "file_name": file_name,
            "file_size": file_size,
            "piece_size": piece_size,
            "piece_count": piece_count,
            "manifest": [str(item) for item in manifest],
            "root_hash": root_hash,
        }

    @staticmethod
    def _default_state():
        return {"node": {}, "shared_resources": {}}
