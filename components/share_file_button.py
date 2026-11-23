"""Bouton 'Partager un fichier' (publication catalogue + partage local)."""
import flet as ft
import theme
from compat import pad_sym
from views.publish_dialog import open_publish_dialog


def build_share_file_button(page: ft.Page, backend_client=None, sharing_service=None) -> ft.Control:
    def on_click(e):
        if hasattr(page, "run_task"):
            page.run_task(open_publish_dialog, page, backend_client, sharing_service)
        else:
            import asyncio

            asyncio.get_running_loop().create_task(
                open_publish_dialog(page, backend_client, sharing_service)
            )

    return ft.Container(
        bgcolor=theme.PRIMARY,
        border_radius=theme.BUTTON_RADIUS,
        padding=pad_sym(h=14, v=14),
        ink=True,
        on_click=on_click,
        tooltip="Publier et partager un document sur le réseau local (LAN)",
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color="#FFFFFF", size=20),
                ft.Text("Partager un fichier", size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ],
        ),
    )