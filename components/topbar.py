"""Barre superieure : recherche, statut Wi-Fi, IP, debit, mode RAM, connexion, profil."""
import flet as ft
import theme
from compat import pad_sym, border_all, border_bottom, notify
from components.avatar_button import build_avatar_button


def _chip(icon, label, bgcolor, border_color, icon_color, text_color=theme.TEXT, radius=theme.CHIP_RADIUS):
    return ft.Container(
        bgcolor=bgcolor,
        border=border_all(1, border_color),
        border_radius=radius,
        padding=pad_sym(h=12, v=7),
        content=ft.Row(
            spacing=7,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon, size=14, color=icon_color),
                ft.Text(label, size=10, color=text_color, weight=ft.FontWeight.W_500, max_lines=2, width=170),
            ],
        ),
    )


def build_topbar(page: ft.Page) -> ft.Control:
    search = ft.TextField(
        hint_text="Rechercher...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=theme.BG_INPUT,
        border=ft.InputBorder.NONE,
        border_radius=theme.INPUT_RADIUS,
        content_padding=pad_sym(h=14, v=10),
        width=250,
    )

    wifi = _chip(ft.Icons.WIFI, "Campus Wi-Fi local - 0 Mo Internet - Amphi 250 UY1",
                 theme.SUCCESS_SOFT, "#86EFAC", theme.SUCCESS)
    tethering = _chip(ft.Icons.WIFI_TETHERING, "192.168.1.42", "#F8FAFC", theme.BORDER, theme.SUCCESS)
    speed = _chip(ft.Icons.SPEED, "48,2 Mo/s", "#F8FAFC", theme.BORDER, theme.TEXT_MUTED)
    ram_mode = _chip(ft.Icons.MEMORY, "Mode basse RAM", "#F1F5F9", theme.BORDER, theme.SUCCESS, radius=10)

    def on_connect(e):
        notify(page, "Detection des pairs du LAN en cours...", kind="info")

    connect_node = ft.Container(
        bgcolor=theme.PRIMARY,
        border_radius=theme.BUTTON_RADIUS,
        padding=pad_sym(h=14, v=10),
        ink=True,
        on_click=on_connect,
        content=ft.Row(
            spacing=7,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.SENSORS, size=16, color="#FFFFFF"),
                ft.Text("Connecter un pair", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ],
        ),
    )

    return ft.Container(
        bgcolor=theme.BG_CARD,
        border=border_bottom(1, theme.BORDER),
        padding=pad_sym(h=16, v=10),
        content=ft.Row(
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                search,
                wifi,
                tethering,
                speed,
                ram_mode,
                ft.VerticalDivider(width=1, color=theme.BORDER),
                connect_node,
                ft.Container(width=12),
                build_avatar_button(page),
            ],
        ),
    )