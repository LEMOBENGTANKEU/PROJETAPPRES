from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
import json

from apps.authentication.ws_auth import authenticate_scope


class SignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await authenticate_scope(self.scope)
        user = self.scope.get("user") or AnonymousUser()
        if not user.is_authenticated:
            await self.close(code=4401)
            return

        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"signaling_{self.room_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "presence",
            "event": "joined",
            "room_id": self.room_id,
            "user_id": user.id,
            "username": user.username,
        }))

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "invalid_json"}))
            return

        user = self.scope.get("user")
        event = {
            "type": "signaling.message",
            "sender_channel": self.channel_name,
            "message": {
                "type": payload.get("type", "signal"),
                "room_id": getattr(self, "room_id", None),
                "from_user_id": getattr(user, "id", None),
                "from_username": getattr(user, "username", None),
                "payload": payload.get("payload", payload),
            },
        }
        await self.channel_layer.group_send(self.group_name, event)

    async def signaling_message(self, event):
        # Avoid echoing the sender's own message back to them.
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps(event["message"]))
