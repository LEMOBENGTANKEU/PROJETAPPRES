from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from .models import ChatMessage


class ChatApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student1",
            password="StrongCampusPass123!",
        )
        self.other = User.objects.create_user(
            username="student2",
            password="StrongCampusPass123!",
        )

    def messages_url(self, ue_code="INF101"):
        return reverse("chat-messages", kwargs={"ue_code": ue_code})

    def test_messages_require_authentication(self):
        response = self.client.get(self.messages_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_create_and_list_messages_for_ue(self):
        self.client.force_authenticate(self.user)
        create_response = self.client.post(
            self.messages_url("INF101"),
            {"content": "Bonjour le cours"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data["ue_code"], "INF101")
        self.assertEqual(create_response.data["author_username"], "student1")

        list_response = self.client.get(self.messages_url("INF101"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["content"], "Bonjour le cours")

    def test_messages_are_scoped_by_ue_code(self):
        ChatMessage.objects.create(ue_code="INF101", author=self.user, content="A")
        ChatMessage.objects.create(ue_code="MAT202", author=self.other, content="B")
        self.client.force_authenticate(self.user)

        response = self.client.get(self.messages_url("INF101"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["content"], "A")
