"""CampusShare - point d'entree de l'application de bureau de partage LAN.

Execution :
    python main.py          fenetre de bureau (Flet)
    flet run main.py        rechargement a chaud (hot reload)
"""

import logging
import os

import flet as ft
import theme
from compat import pad_all, run_app
from components.sidebar import build_sidebar
from components.topbar import build_topbar
from services.backend_client import BackendApiError, BackendClient
from services.sharing_service import SharingService
from views.calls_view import build_calls_view
from views.chat_view import build_chat_view
from views.courses_view import build_courses_view
from views.placeholder_view import build_placeholder_view
from views.settings_view import build_settings_view

logger = logging.getLogger(__name__)


def main(page: ft.Page):
    backend_client = BackendClient(
        os.environ.get("CAMPUSSHARE_API_URL", "http://127.0.0.1:8000")
    )
    sharing_service = SharingService(backend_client)

    async def on_close(_e):
        dispose = state.get("dispose")
        if callable(dispose):
            try:
                dispose()
            except Exception:
                logger.exception("Impossible de fermer la vue active.")
        try:
            await sharing_service.close()
        except (BackendApiError, OSError):
            logger.exception("Impossible d'arrêter proprement le partage P2P.")

    page.on_close = on_close
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

    state = {"view": "courses", "dispose": None}

    def navigate(key: str):
        state["view"] = key
        render()

    def build_content():
        previous_dispose = state.get("dispose")
        if callable(previous_dispose):
            try:
                previous_dispose()
            except Exception:
                logger.exception("Erreur lors du nettoyage de la vue précédente.")
        state["dispose"] = None

        if state["view"] == "courses":
            return build_courses_view(
                page,
                backend_client,
                on_open_settings=lambda: navigate("settings"),
                sharing_service=sharing_service,
            )
        if state["view"] == "chat":
            control, dispose = build_chat_view(page, backend_client)
            state["dispose"] = dispose
            return control
        if state["view"] == "calls":
            control, dispose = build_calls_view(page, backend_client)
            state["dispose"] = dispose
            return control
        if state["view"] == "settings":
            return build_settings_view(
                page,
                backend_client,
                on_connected=lambda: navigate("courses"),
                sharing_service=sharing_service,
            )
        return build_placeholder_view(
            "Section indisponible",
            ft.Icons.INFO_OUTLINE,
            "Cette section n'est pas disponible.",
        )

    def render():
        page.controls.clear()
        page.add(
            ft.Row(
                expand=True,
                spacing=0,
                controls=[
                    build_sidebar(
                        page,
                        state["view"],
                        navigate,
                        backend_client=backend_client,
                        sharing_service=sharing_service,
                    ),
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