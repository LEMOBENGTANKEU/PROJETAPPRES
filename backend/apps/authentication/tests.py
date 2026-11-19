from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class UserRoleTests(TestCase):
    def test_new_user_defaults_to_student_role(self):
        user = User.objects.create_user(username="student", password="valid-password")

        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password("valid-password"))

    def test_all_project_roles_can_be_assigned(self):
        for role in User.Role.values:
            with self.subTest(role=role):
                user = User.objects.create_user(
                    username=role.lower(),
                    password="valid-password",
                    role=role,
                )

                self.assertEqual(user.role, role)


class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student",
            email="student@example.com",
            password="StrongCampusPass123!",
        )

    def test_registration_creates_student_and_does_not_allow_role_escalation(self):
        response = self.client.post(
            reverse("auth_register"),
            {
                "username": "newstudent",
                "email": "newstudent@example.com",
                "password": "StrongCampusPass123!",
                "role": User.Role.ADMIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(username="newstudent")
        self.assertEqual(created_user.role, User.Role.STUDENT)
        self.assertNotIn("password", response.data)

    def test_registration_rejects_weak_password(self):
        response = self.client.post(
            reverse("auth_register"),
            {"username": "newstudent", "password": "123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="newstudent").exists())

    def test_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "student", "password": "StrongCampusPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_rejects_invalid_password(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "student", "password": "incorrect-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        login = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "student", "password": "StrongCampusPass123!"},
            format="json",
        )

        response = self.client.post(
            reverse("token_refresh"),
            {"refresh": login.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_profile_requires_authentication_and_returns_current_user(self):
        url = reverse("auth_me")
        unauthenticated_response = self.client.get(url)

        self.assertEqual(
            unauthenticated_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        login = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "student", "password": "StrongCampusPass123!"},
            format="json",
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login.data['access']}"
        )

        profile_response = self.client.get(url)

        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data["username"], self.user.username)
        self.assertEqual(profile_response.data["role"], User.Role.STUDENT)
