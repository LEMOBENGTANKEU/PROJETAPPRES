"""Bouton de navigation generique de la barre laterale."""
import flet as ft
import theme
from compat import pad_sym


def build_nav_item(icon, label: str, active: bool, on_click, tooltip: str = None):
    color = theme.PRIMARY_DARK if active else theme.TEXT
    weight = ft.FontWeight.W_600 if active else ft.FontWeight.W_500
    bg = theme.PRIMARY_SOFT if active else None
    return ft.Container(
        bgcolor=bg,
        border_radius=theme.BUTTON_RADIUS,
        padding=pad_sym(h=14, v=12),
        ink=True,
        on_click=on_click,
        tooltip=tooltip,
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=19, color=color),
                ft.Text(label, size=13, weight=weight, color=color, expand=True),
            ],
        ),
    )