"""Logo de l'application : icone, nom et statut Pair local P2P."""
import flet as ft
import theme
from compat import pad


def build_logo() -> ft.Control:
    icon_box = ft.Container(
        width=38,
        height=38,
        bgcolor=theme.PRIMARY,
        border_radius=10,
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(ft.Icons.WIFI_TETHERING, color="#FFFFFF", size=20),
    )
    status = ft.Row(
        spacing=6,
        controls=[
            ft.Container(width=7, height=7, bgcolor=theme.SUCCESS, border_radius=4),
            ft.Text("Pair local P2P", size=10, color=theme.TEXT_MUTED, weight=ft.FontWeight.W_500),
        ],
    )
    return ft.Container(
        padding=pad(left=6, top=6, bottom=6),
        content=ft.Row(
            spacing=10,
            controls=[
                icon_box,
                ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text(theme.APP_NAME, size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                        status,
                    ],
                ),
            ],
        ),
    )