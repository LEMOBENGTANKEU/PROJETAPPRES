"""Bouton 'Appels P2P locaux'."""
import flet as ft
from components.nav_item import build_nav_item

KEY = "calls"


def build_calls_button(active: bool, on_navigate) -> ft.Control:
    return build_nav_item(
        ft.Icons.PHONE_IN_TALK_OUTLINED,
        "Appels locaux",
        active,
        lambda e: on_navigate(KEY),
        tooltip="Appels P2P sur le LAN",
    )