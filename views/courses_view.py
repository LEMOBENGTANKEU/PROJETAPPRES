"""Ecran principal 'Cours & TP': entete, recherche, filtres, grille, etat vide."""
import flet as ft
import theme
from compat import pad_all, pad_sym
from components.course_header import build_course_header
from components.filter_bar import build_filter_bar
from components.resource_card import build_resource_card
from data import RESOURCES, CATEGORIES, FILTER_TO_CATEGORY


def build_courses_view(page: ft.Page) -> ft.Control:
    state = {"category": "All Resources", "level": None, "query": "", "sort": "recent"}

    search = ft.TextField(
        hint_text="Titre, auteur ou mot-cle...",
        prefix_icon=ft.Icons.SEARCH,
        filled=True,
        bgcolor=theme.BG_INPUT,
        border=ft.InputBorder.NONE,
        border_radius=theme.INPUT_RADIUS,
        content_padding=pad_sym(h=14, v=10),
        width=260,
    )

    grid = ft.Row(wrap=True, spacing=16, run_spacing=16)
    filters_holder = ft.Container()
    count_text = ft.Text("", size=12, color=theme.TEXT_MUTED)

    def visible_resources():
        items = RESOURCES
        cat = state["category"]
        if cat != "All Resources":
            wanted = FILTER_TO_CATEGORY[cat]
            items = [r for r in items if r.get("category") == wanted]
        lvl = state["level"]
        if lvl:
            items = [r for r in items if r.get("level") == lvl]
        q = state["query"].strip().lower()
        if q:
            items = [r for r in items
                     if q in r["title"].lower()
                     or q in r.get("description", "").lower()
                     or q in r.get("uploader", "").lower()]
        if state["sort"] == "az":
            items = sorted(items, key=lambda r: r["title"].lower())
        else:
            items = sorted(items, key=lambda r: r.get("downloads", 0), reverse=True)
        return items

    def refresh():
        items = visible_resources()
        grid.controls = [build_resource_card(page, r) for r in items]
        count_text.value = f"{len(items)} ressource(s)"
        empty.visible = len(items) == 0
        filters_holder.content = build_filter_bar(state["category"], on_select, state["level"], on_level_change)
        search.value = state["query"]
        page.update()

    def on_select(cat):
        state["category"] = cat
        state["level"] = None
        refresh()

    def on_level_change(e):
        val = e.control.value
        state["level"] = None if (val is None or val == "Tous les niveaux") else val
        refresh()

    def on_search(e):
        state["query"] = e.control.value or ""
        refresh()

    search.on_change = on_search

    grid.controls = [build_resource_card(page, r) for r in visible_resources()]
    count_text.value = f"{len(visible_resources())} ressource(s)"
    filters_holder.content = build_filter_bar(state["category"], on_select, state["level"], on_level_change)

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
                ft.Text("Aucune ressource trouvee", size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                ft.Text("Essayez d'autres filtres ou mots-cles.", size=13, color=theme.TEXT_MUTED),
            ],
        ),
    )

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=20,
        controls=[
            build_course_header(page),
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("Ressources academiques", size=16, weight=ft.FontWeight.W_700, color=theme.TEXT),
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