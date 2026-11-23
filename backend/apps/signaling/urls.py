from django.urls import path

from .views import SignalingMessageListCreateView

urlpatterns = [
    path("<str:room_id>/messages/", SignalingMessageListCreateView.as_view(), name="signaling-messages"),
]
