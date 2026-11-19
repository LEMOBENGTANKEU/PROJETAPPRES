from django.contrib import admin

from .models import AcademicResource


@admin.register(AcademicResource)
class AcademicResourceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course_code",
        "category",
        "uploaded_by",
        "is_published",
        "created_at",
    )
    list_filter = ("category", "is_published", "course_code")
    search_fields = ("title", "file_name", "course_code")
    readonly_fields = ("id", "created_at")
