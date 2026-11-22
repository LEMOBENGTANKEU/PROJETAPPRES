import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from apps.authentication.ws_auth import authenticate_scope

from .models import ChatMessage


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await authenticate_scope(self.scope)
        user = self.scope.get("user") or AnonymousUser()
        if not user.is_authenticated:
            await self.close(code=4401)
            return

        self.ue_code = self.scope["url_route"]["kwargs"]["ue_code"]
        self.group_name = f"chat_{self.ue_code}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

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

        content = (payload.get("content") or "").strip()
        if not content:
            await self.send(text_data=json.dumps({"error": "empty_content"}))
            return

        user = self.scope["user"]
        message = await self._create_message(user, self.ue_code, content)
        event = {
            "type": "chat.message",
            "message": {
                "id": message.id,
                "ue_code": message.ue_code,
                "author": user.id,
                "author_username": user.username,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            },
        }
        await self.channel_layer.group_send(self.group_name, event)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    @database_sync_to_async
    def _create_message(self, user, ue_code, content):
        return ChatMessage.objects.create(author=user, ue_code=ue_code, content=content)
