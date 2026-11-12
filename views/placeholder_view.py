"""Ecran de substitution elegante pour les sections encore en developpement."""
import flet as ft
import theme
from compat import pad_all


def build_placeholder_view(title: str, icon, subtitle: str) -> ft.Control:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        padding=pad_all(24),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
            controls=[
                ft.Icon(icon, size=60, color=theme.TEXT_LIGHT),
                ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                ft.Text(subtitle, size=14, color=theme.TEXT_MUTED),
            ],
        ),
    )