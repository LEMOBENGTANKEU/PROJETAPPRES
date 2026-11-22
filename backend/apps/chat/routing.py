from django.urls import re_path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/chat/(?P<ue_code>[^/]+)/$", ChatConsumer.as_asgi()),
]
