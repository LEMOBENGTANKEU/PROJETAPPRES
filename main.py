"""CampusShare - point d'entree de l'application de bureau de partage LAN.

Execution :
    python main.py          fenetre de bureau (Flet)
    flet run main.py        rechargement a chaud (hot reload)
"""

import flet as ft
import theme
from compat import pad_all, run_app
from components.sidebar import build_sidebar
from components.topbar import build_topbar
from views.courses_view import build_courses_view
from views.placeholder_view import build_placeholder_view
from views.settings_view import build_settings_view

PLACEHOLDERS = {
    "chat": ("Discussion P2P", ft.Icons.CHAT_BUBBLE_OUTLINE, "La messagerie locale arrive bientot."),
    "calls": ("Appels P2P locaux", ft.Icons.PHONE_IN_TALK_OUTLINED, "La telephonie sur le LAN arrive bientot."),
}


def main(page: ft.Page):
    page.title = theme.APP_NAME
    page.padding = 0
    page.spacing = 0
    page.bgcolor = theme.BG_APP
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = theme.app_theme()

    # Fenetre bureau : taille, minima, redimensionnable.
    page.window.width = 1280
    page.window.height = 840
    page.window.min_width = 950
    page.window.min_height = 640
    page.window.resizable = True
    page.window.maximizable = True

    state = {"view": "courses"}

    def navigate(key: str):
        state["view"] = key
        render()

    def build_content():
        if state["view"] == "courses":
            return build_courses_view(page)
        if state["view"] == "settings":
            return build_settings_view(page)
        title, icon, subtitle = PLACEHOLDERS[state["view"]]
        return build_placeholder_view(title, icon, subtitle)

    def render():
        page.controls.clear()
        page.add(
            ft.Row(
                expand=True,
                spacing=0,
                controls=[
                    build_sidebar(page, state["view"], navigate),
                    ft.Container(
                        expand=True,
                        bgcolor=theme.BG_APP,
                        content=ft.Column(
                            expand=True,
                            spacing=0,
                            controls=[
                                build_topbar(page),
                                ft.Container(
                                    expand=True,
                                    padding=pad_all(24),
                                    content=build_content(),
                                ),
                            ],
                        ),
                    ),
                ],
            )
        )

    render()


if __name__ == "__main__":
    run_app(main)