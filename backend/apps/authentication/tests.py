from django.test import TestCase

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
