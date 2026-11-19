from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Étudiant"
        TEACHER = "TEACHER", "Enseignant"
        ADMIN = "ADMIN", "Administrateur"

    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.STUDENT,
    )
