import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.authentication.ws_auth import authenticate_scope

from .models import SignalingMessage


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
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "event": "joined",
                    "room_id": self.room_id,
                    "user_id": user.id,
                    "username": user.username,
                }
            )
        )

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
        message_type = str(payload.get("type", "signal"))
        message_payload = payload.get("payload", payload)
        if not isinstance(message_payload, dict):
            message_payload = {"value": message_payload}

        saved = await self._create_message(
            user=user,
            room_id=self.room_id,
            message_type=message_type,
            payload=message_payload,
        )
        event = {
            "type": "signaling.message",
            "sender_channel": self.channel_name,
            "message": {
                "id": saved.id,
                "room_id": saved.room_id,
                "sender": user.id,
                "sender_username": user.username,
                "message_type": saved.message_type,
                "payload": saved.payload,
                "created_at": saved.created_at.isoformat(),
            },
        }
        await self.channel_layer.group_send(self.group_name, event)

    async def signaling_message(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps(event["message"]))

    @database_sync_to_async
    def _create_message(self, user, room_id, message_type, payload):
        return SignalingMessage.objects.create(
            sender=user,
            room_id=room_id,
            message_type=message_type,
            payload=payload,
        )
