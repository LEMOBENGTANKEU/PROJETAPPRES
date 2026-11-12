"""Bouton 'Discussion'."""
import flet as ft
from components.nav_item import build_nav_item

KEY = "chat"


def build_chat_button(active: bool, on_navigate) -> ft.Control:
    return build_nav_item(
        ft.Icons.CHAT_BUBBLE_OUTLINE,
        "Discussion",
        active,
        lambda e: on_navigate(KEY),
        tooltip="Discussion P2P",
    )