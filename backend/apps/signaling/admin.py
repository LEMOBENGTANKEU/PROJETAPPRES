from django.contrib import admin

from .models import SignalingMessage


@admin.register(SignalingMessage)
class SignalingMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "room_id", "sender", "message_type", "created_at")
    list_filter = ("room_id", "message_type", "created_at")
    search_fields = ("room_id", "sender__username", "message_type")
