"""Barre laterale : logo, partage, navigation, badge reseau et aide."""
import flet as ft
import theme
from compat import pad, pad_sym, border_right
from components.logo import build_logo
from components.share_file_button import build_share_file_button
from components.nav_chat_button import build_chat_button
from components.nav_courses_button import build_courses_button
from components.nav_calls_button import build_calls_button
from components.nav_settings_button import build_settings_button
from components.avatar_button import build_avatar_button


def _wifi_direct_badge() -> ft.Control:
    return ft.Container(
        bgcolor=theme.SUCCESS_SOFT,
        border_radius=8,
        padding=pad_sym(h=10, v=8),
        content=ft.Row(
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.SENSORS, size=16, color=theme.SUCCESS),
                ft.Text("Wi-Fi Direct", size=10, color=theme.TEXT_MUTED, expand=True),
                ft.Text("<4 ms", size=10, weight=ft.FontWeight.BOLD, color=theme.SUCCESS),
            ],
        ),
    )


def _help_item() -> ft.Control:
    return ft.Container(
        padding=pad_sym(h=10, v=8),
        content=ft.Row(
            spacing=10,
            controls=[
                ft.Icon(ft.Icons.HELP_OUTLINE, size=18, color=theme.TEXT),
                ft.Text("Aide & Docs", size=12, color=theme.TEXT),
            ],
        ),
    )


def build_sidebar(page: ft.Page, active: str, on_navigate) -> ft.Control:
    return ft.Container(
        width=theme.SIDEBAR_WIDTH,
        bgcolor=theme.BG_SIDEBAR,
        border=border_right(1, theme.BORDER),
        padding=pad(left=10, top=14, right=10, bottom=10),
        content=ft.Column(
            spacing=6,
            controls=[
                build_logo(),
                ft.Container(height=8),
                build_share_file_button(page),
                ft.Container(height=8),
                build_chat_button(active == "chat", on_navigate),
                build_courses_button(active == "courses", on_navigate),
                build_calls_button(active == "calls", on_navigate),
                build_settings_button(active == "settings", on_navigate),
                ft.Container(expand=True),
                _wifi_direct_badge(),
                ft.Container(height=8),
                _help_item(),
                ft.Container(height=8),
                build_avatar_button(page),
            ],
        ),
    )