"""Bouton 'Parametres & Reseau'."""
import flet as ft
from components.nav_item import build_nav_item

KEY = "settings"


def build_settings_button(active: bool, on_navigate) -> ft.Control:
    return build_nav_item(
        ft.Icons.SETTINGS_ETHERNET,
        "Parametres",
        active,
        lambda e: on_navigate(KEY),
        tooltip="Parametres et reseau",
    )