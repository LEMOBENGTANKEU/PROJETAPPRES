from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from .models import SignalingMessage


class SignalingApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="caller",
            password="StrongCampusPass123!",
        )
        self.other = User.objects.create_user(
            username="callee",
            password="StrongCampusPass123!",
        )

    def messages_url(self, room_id="room-1"):
        return reverse("signaling-messages", kwargs={"room_id": room_id})

    def test_messages_require_authentication(self):
        response = self.client.get(self.messages_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_create_and_poll_room_messages(self):
        self.client.force_authenticate(self.user)
        create_response = self.client.post(
            self.messages_url("room-1"),
            {"message_type": "offer", "payload": {"sdp": "abc"}},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["room_id"], "room-1")
        self.assertEqual(create_response.data["message_type"], "offer")
        self.assertEqual(create_response.data["sender_username"], "caller")

        list_response = self.client.get(self.messages_url("room-1"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        msg_id = list_response.data["results"][0]["id"]

        after_response = self.client.get(self.messages_url("room-1"), {"after": msg_id})
        self.assertEqual(after_response.status_code, status.HTTP_200_OK)
        self.assertEqual(after_response.data["count"], 0)

    def test_messages_are_scoped_by_room(self):
        SignalingMessage.objects.create(
            room_id="room-1", sender=self.user, message_type="offer", payload={"sdp": "1"}
        )
        SignalingMessage.objects.create(
            room_id="room-2", sender=self.other, message_type="offer", payload={"sdp": "2"}
        )
        self.client.force_authenticate(self.user)
        response = self.client.get(self.messages_url("room-1"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
