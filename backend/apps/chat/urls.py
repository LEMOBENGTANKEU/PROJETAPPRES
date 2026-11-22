from django.urls import path

from .views import ChatMessageListCreateView

urlpatterns = [
    path("<str:ue_code>/messages/", ChatMessageListCreateView.as_view(), name="chat-messages"),
]
