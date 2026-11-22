from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "ue_code", "author", "created_at")
    list_filter = ("ue_code", "created_at")
    search_fields = ("ue_code", "author__username", "content")
