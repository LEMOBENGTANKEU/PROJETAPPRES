"""Bouton 'Cours & TP'."""
import flet as ft
from components.nav_item import build_nav_item

KEY = "courses"


def build_courses_button(active: bool, on_navigate) -> ft.Control:
    return build_nav_item(
        ft.Icons.SCHOOL_OUTLINED,
        "Cours & TP",
        active,
        lambda e: on_navigate(KEY),
        tooltip="Ressources academiques",
    )