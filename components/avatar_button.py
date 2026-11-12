"""Bouton avatar utilisateur avec menu de profil."""
import flet as ft
import theme
from compat import pad_sym, notify


def build_avatar_button(page: ft.Page) -> ft.Control:
    def on_profile(e):
        _close_menu(page, e.control)
        notify(page, "Profil : Alexandre D. - Pair verifie (UY1)", kind="info")

    def on_settings(e):
        _close_menu(page, e.control)
        from main import navigate
        navigate("settings")

    def on_logout(e):
        _close_menu(page, e.control)
        notify(page, "Deconnexion", kind="warning")

    def _close_menu(page, menu):
        try:
            menu.open = False
            page.update()
        except Exception:
            pass

    avatar = ft.Container(
        width=34,
        height=34,
        bgcolor=theme.PRIMARY,
        border_radius=17,
        alignment=ft.Alignment(0, 0),
        content=ft.Text("AD", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
    )
    status_dot = ft.Container(
        width=10,
        height=10,
        bgcolor=theme.SUCCESS,
        border_radius=5,
        right=0,
        bottom=0,
        border=ft.Border(
            top=ft.BorderSide(2, "#FFFFFF"),
            right=ft.BorderSide(2, "#FFFFFF"),
            bottom=ft.BorderSide(2, "#FFFFFF"),
            left=ft.BorderSide(2, "#FFFFFF"),
        ),
    )
    header = ft.Container(
        border_radius=10,
        padding=pad_sym(h=8, v=4),
        content=ft.Row(
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text("Alexandre D.", size=11, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                        ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.VERIFIED, size=10, color=theme.PRIMARY),
                                ft.Text("Pair verifie (UY1)", size=9, color=theme.PRIMARY),
                            ],
                        ),
                    ],
                ),
                ft.Stack(width=34, height=34, controls=[avatar, status_dot]),
            ],
        ),
    )

    return ft.PopupMenuButton(
        content=header,
        items=[
            ft.PopupMenuItem(content=ft.Text("Mon profil"), icon=ft.Icons.PERSON, on_click=on_profile),
            ft.PopupMenuItem(content=ft.Text("Parametres"), icon=ft.Icons.SETTINGS, on_click=on_settings),
            ft.PopupMenuItem(),
            ft.PopupMenuItem(content=ft.Text("Deconnexion"), icon=ft.Icons.LOGOUT, on_click=on_logout),
        ],
    )