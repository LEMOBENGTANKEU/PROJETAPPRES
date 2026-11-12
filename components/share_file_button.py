"""Bouton 'Partager un fichier' (action professionnelle sans controle flottant instable)."""
import flet as ft
import theme
from compat import pad_sym, notify


def build_share_file_button(page: ft.Page) -> ft.Control:
    def on_click(e):
        # Le selecteur de fichiers sera branche ici des que l'overlay de page
        # sera initialise de maniere stable dans main.py.
        notify(page, "Ouverture du selecteur de fichiers...", kind="info")

    return ft.Container(
        bgcolor=theme.PRIMARY,
        border_radius=theme.BUTTON_RADIUS,
        padding=pad_sym(h=14, v=14),
        ink=True,
        on_click=on_click,
        tooltip="Partager un document sur le reseau local (LAN)",
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color="#FFFFFF", size=20),
                ft.Text("Partager un fichier", size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ],
        ),
    )