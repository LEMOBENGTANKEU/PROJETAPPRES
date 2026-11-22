from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user_for_token(token: str):
    jwt_auth = JWTAuthentication()
    try:
        validated = jwt_auth.get_validated_token(token)
        return jwt_auth.get_user(validated)
    except (InvalidToken, TokenError, Exception):
        return AnonymousUser()


async def authenticate_scope(scope):
    user = scope.get("user")
    if user and getattr(user, "is_authenticated", False):
        return user
    query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
    token = (query.get("token") or [None])[0]
    if token:
        scope["user"] = await get_user_for_token(token)
    return scope.get("user") or AnonymousUser()
