"""Parametres de l'application : apparence, reseau, a propos."""
import flet as ft
import theme
from compat import pad_all, notify


def build_settings_view(page: ft.Page) -> ft.Control:
    def on_theme_change(e):
        page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        page.update()
        notify(page, "Thème : " + ("Sombre" if e.control.value else "Clair"), kind="info")

    theme_switch = ft.Switch(
        label="Theme sombre",
        value=(page.theme_mode == ft.ThemeMode.DARK),
        on_change=on_theme_change,
    )

    def close_about(dlg):
        dlg.open = False
        page.update()

    def on_about(e):
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("A propos de CampusShare"),
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    ft.Text(f"{theme.APP_NAME} v{theme.APP_VERSION}", weight=ft.FontWeight.BOLD),
                    ft.Text("Partage de ressources academiques en pair a pair sur le reseau local (LAN)."),
                    ft.Text("Conçu pour l'UY1 - Amphi 250.", size=12, color=theme.TEXT_MUTED),
                ],
            ),
            actions=[
                ft.TextButton("Fermer", on_click=lambda e: close_about(dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dlg)

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=24,
        controls=[
            ft.Text("Parametres", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Container(
                bgcolor=theme.BG_CARD,
                border_radius=theme.CARD_RADIUS,
                padding=pad_all(20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.BRIGHTNESS_6, color=theme.TEXT_MUTED, size=20),
                                ft.Text("Apparence", size=15, weight=ft.FontWeight.W_700, color=theme.TEXT),
                            ],
                        ),
                        theme_switch,
                        ft.Divider(color=theme.BORDER),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, color=theme.TEXT_MUTED, size=20),
                                ft.Text("A propos", size=15, weight=ft.FontWeight.W_700, color=theme.TEXT),
                            ],
                        ),
                        ft.Container(
                            bgcolor="#F8FAFC",
                            border_radius=10,
                            padding=pad_all(14),
                            ink=True,
                            on_click=on_about,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text("Version et licences", size=13, weight=ft.FontWeight.W_600, color=theme.PRIMARY),
                                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=14, color=theme.TEXT_LIGHT),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
        ],
    )