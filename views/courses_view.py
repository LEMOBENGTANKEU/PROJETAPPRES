"""Ecran du catalogue local ou distant, avec telechargement P2P."""

import flet as ft
import theme
from compat import border_all, notify, pad_all, pad_sym
from components.course_header import build_course_header
from components.filter_bar import build_filter_bar
from components.resource_card import build_resource_card
from core.p2p.errors import P2PError
from data import FILTER_TO_CATEGORY, RESOURCES
from services.backend_client import BackendApiError
from services.download_service import DownloadService

BACKEND_CATEGORY_LABELS = {
    "COURSE": "Course Material (CM)",
    "EXERCISE": "Tutorials (TD)",
    "EXAM": "Past Exams",
    "PROJECT": "Projects",
    "MEDIA": "Recordings",
}


def _format_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def _to_card_resource(resource):
    category = BACKEND_CATEGORY_LABELS.get(
        resource.get("category"),
        resource.get("category", "Resource"),
    )
    uploaded = str(resource.get("created_at", "-"))[:10]
    return {
        "id": resource["id"],
        "category": category,
        "seeders": resource.get("seeders", 0),
        "leechers": 0,
        "title": resource["title"],
        "description": resource.get("description") or resource["file_name"],
        "uploader": resource.get("uploaded_by", "-"),
        "uploaded": uploaded,
        "size": _format_size(resource["file_size"]),
        "sha": resource["root_hash"][:12],
        "verified": False,
        "action": "download",
        "downloads": 0,
        "backend_resource": resource,
    }


def build_courses_view(
    page: ft.Page,
    backend_client=None,
    on_open_settings=None,
    sharing_service=None,
) -> ft.Control:
    state = {
        "category": "All Resources",
        "level": None,
        "query": "",
        "sort": "recent",
        "resources": RESOURCES,
        "is_live": False,
        "status": (
            "Connecté — chargez le catalogue du campus."
            if backend_client and backend_client.is_authenticated
            else "Mode démonstration — connectez-vous au serveur pour charger le catalogue."
        ),
    }
    download_service = DownloadService(backend_client) if backend_client else None

    search = ft.TextField(
        hint_text="Titre, auteur ou mot-cle...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=theme.BG_INPUT,
        border=ft.NoInputBorder(),
        border_radius=theme.INPUT_RADIUS,
        content_padding=pad_sym(h=14, v=10),
        width=260,
    )
    grid = ft.Row(wrap=True, spacing=16, run_spacing=16)
    filters_holder = ft.Container()
    count_text = ft.Text("", size=12, color=theme.TEXT_MUTED)
    status_text = ft.Text(state["status"], size=12, color=theme.TEXT_MUTED, expand=True)

    def open_settings(_e=None):
        if on_open_settings is not None:
            on_open_settings()
        else:
            notify(page, "Configurez la connexion au serveur dans les paramètres.")

    def category_bar():
        filters_holder.content = build_filter_bar(
            state["category"],
            on_select,
            state["level"],
            on_level_change,
            show_level=not state["is_live"],
        )

    async def download_resource(resource, on_piece_complete=None):
        if not backend_client or not backend_client.is_authenticated:
            notify(page, "Connectez-vous au serveur du campus avant de télécharger.", "warning")
            return
        try:
            destination, _ = await download_service.download(
                resource,
                on_piece_complete=on_piece_complete,
            )
        except (
            BackendApiError,
            P2PError,
            OSError,
            ValueError,
            TypeError,
            KeyError,
        ) as exc:
            status_text.value = f"Échec du téléchargement : {exc}"
            status_text.color = theme.ERROR
            page.update()
            notify(page, f"Téléchargement impossible : {exc}", kind="error")
            return

        status_text.value = f"Téléchargement terminé : {destination}"
        status_text.color = theme.SUCCESS
        page.update()
        notify(page, f"Fichier enregistré dans {destination}", kind="success")
        if sharing_service is not None:
            confirm_share(resource, destination)

    def confirm_share(resource, file_path):
        async def share(_e):
            dialog.open = False
            page.update()
            try:
                await sharing_service.share_resource(resource, file_path)
            except (BackendApiError, OSError, ValueError, TypeError, KeyError) as exc:
                status_text.value = f"Partage impossible : {exc}"
                status_text.color = theme.ERROR
                page.update()
                notify(page, str(exc), kind="error")
            else:
                status_text.value = "Ressource partagée sur le réseau local."
                status_text.color = theme.SUCCESS
                page.update()
                notify(page, "Cette ressource est partagée pendant cette session.", kind="success")

        def decline(_e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Partager cette ressource ?"),
            content=ft.Text(
                "Les autres appareils du campus pourront télécharger ce fichier "
                "pendant que CampusShare reste ouvert."
            ),
            actions=[
                ft.TextButton("Pas maintenant", on_click=decline),
                ft.Button("Partager", on_click=share),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dialog)

    def visible_resources():
        items = state["resources"]
        category = state["category"]
        if category != "All Resources":
            wanted = FILTER_TO_CATEGORY[category]
            items = [resource for resource in items if resource.get("category") == wanted]
        level = state["level"]
        if level and not state["is_live"]:
            items = [resource for resource in items if resource.get("level") == level]
        query = state["query"].strip().lower()
        if query:
            items = [
                resource
                for resource in items
                if query in resource["title"].lower()
                or query in resource.get("description", "").lower()
                or query in resource.get("uploader", "").lower()
            ]
        if state["sort"] == "az":
            items = sorted(items, key=lambda resource: resource["title"].lower())
        else:
            items = sorted(
                items,
                key=lambda resource: resource.get("downloads", 0),
                reverse=True,
            )
        return items

    def refresh():
        items = visible_resources()
        grid.controls = [
            build_resource_card(
                page,
                resource,
                on_download=download_resource
                if resource.get("backend_resource") is not None
                else None,
            )
            for resource in items
        ]
        count_text.value = f"{len(items)} ressource(s)"
        empty.visible = len(items) == 0
        category_bar()
        search.value = state["query"]
        page.update()

    async def load_catalog(_e=None):
        if not backend_client or not backend_client.is_authenticated:
            notify(page, "Connectez-vous au serveur du campus dans les paramètres.", "warning")
            open_settings()
            return

        load_button.disabled = True
        status_text.value = "Chargement du catalogue du campus..."
        status_text.color = theme.TEXT_MUTED
        page.update()
        try:
            remote_resources = await backend_client.list_resources()
            state["resources"] = [
                _to_card_resource(resource) for resource in remote_resources
            ]
            state["is_live"] = True
            state["level"] = None
            state["status"] = (
                f"Connecté — {len(remote_resources)} ressource(s) du catalogue campus."
            )
            status_text.value = state["status"]
            status_text.color = theme.SUCCESS
            refresh()
        except (BackendApiError, KeyError, TypeError, ValueError) as exc:
            state["is_live"] = False
            state["status"] = f"Catalogue indisponible : {exc} — données de démonstration conservées."
            status_text.value = state["status"]
            status_text.color = theme.ERROR
            notify(page, str(exc), kind="error")
            refresh()
        finally:
            load_button.disabled = False
            page.update()

    def on_select(category):
        state["category"] = category
        state["level"] = None
        refresh()

    def on_level_change(e):
        value = e.control.value
        state["level"] = None if value in (None, "Tous les niveaux") else value
        refresh()

    def on_search(e):
        state["query"] = e.control.value or ""
        refresh()

    search.on_change = on_search
    load_button = ft.OutlinedButton(
        "Charger le catalogue",
        icon=ft.Icons.REFRESH,
        on_click=load_catalog,
    )

    empty = ft.Container(
        visible=False,
        alignment=ft.Alignment(0, 0),
        padding=pad_all(40),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(ft.Icons.SEARCH_OFF, size=52, color=theme.TEXT_LIGHT),
                ft.Text(
                    "Aucune ressource trouvee",
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=theme.TEXT,
                ),
                ft.Text(
                    "Essayez d'autres filtres ou mots-cles.",
                    size=13,
                    color=theme.TEXT_MUTED,
                ),
            ],
        ),
    )

    category_bar()
    grid.controls = [build_resource_card(page, resource) for resource in visible_resources()]
    count_text.value = f"{len(visible_resources())} ressource(s)"

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=20,
        controls=[
            build_course_header(page),
            ft.Container(
                bgcolor=theme.BG_CARD,
                border=border_all(1, theme.BORDER),
                border_radius=theme.CARD_RADIUS,
                padding=pad_sym(h=16, v=10),
                content=ft.Row(
                    controls=[
                        status_text,
                        ft.TextButton(
                            "Se connecter",
                            icon=ft.Icons.SETTINGS,
                            on_click=open_settings,
                            visible=not (
                                backend_client and backend_client.is_authenticated
                            ),
                        ),
                        load_button,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(
                        "Ressources academiques",
                        size=16,
                        weight=ft.FontWeight.W_700,
                        color=theme.TEXT,
                    ),
                    ft.Container(expand=True),
                    search,
                ],
            ),
            filters_holder,
            count_text,
            empty,
            grid,
        ],
    )
