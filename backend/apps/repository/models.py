import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class AcademicResource(models.Model):
    class Category(models.TextChoices):
        COURSE = "COURSE", "Cours"
        EXERCISE = "EXERCISE", "Travaux dirigés"
        EXAM = "EXAM", "Annales"
        PROJECT = "PROJECT", "Projet"
        MEDIA = "MEDIA", "Enregistrement"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    course_code = models.CharField(max_length=32, db_index=True)
    category = models.CharField(max_length=16, choices=Category.choices)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    mime_type = models.CharField(max_length=127)
    piece_size = models.PositiveIntegerField(default=262144)
    piece_count = models.PositiveIntegerField()
    root_hash = models.CharField(max_length=64, unique=True)
    manifest = models.JSONField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resources",
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["course_code", "category"])]

    def __str__(self):
        return f"{self.title} ({self.course_code})"
