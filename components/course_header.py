"""En-tete de l'ecran cours : titre, badge de statistiques, bouton de partage."""
import flet as ft
import theme
from compat import pad_sym, pad_all, border_all, notify


def build_course_header(page: ft.Page) -> ft.Control:
    def on_share(e):
        notify(page, "Partage de document sur le LAN...", kind="info")

    docs_badge = ft.Container(
        bgcolor="#EFF6FF",
        border=border_all(1, "#BFDBFE"),
        border_radius=12,
        padding=pad_sym(h=10, v=4),
        content=ft.Text("124 documents locaux - 1,8 Go partage", size=9, color=theme.PRIMARY_DARK,
                        weight=ft.FontWeight.W_600),
    )

    share_button = ft.Container(
        bgcolor=theme.PRIMARY,
        border_radius=theme.BUTTON_RADIUS,
        padding=pad_sym(h=16, v=12),
        ink=True,
        on_click=on_share,
        content=ft.Row(
            spacing=8,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=18, color="#FFFFFF"),
                ft.Text("Partager sur le LAN", size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ],
        ),
    )

    left = ft.Column(
        spacing=6,
        expand=True,
        controls=[
            ft.Row(
                wrap=True,
                spacing=10,
                run_spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text("Depot de cours & TP", size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                    docs_badge,
                ],
            ),
            ft.Text(
                "Stockage LAN descentralise sans quota Internet - Amphi 250 UY1 - "
                "Cache anti-coupure (Anti-Blackout).",
                size=11,
                color=theme.TEXT_MUTED,
            ),
        ],
    )

    return ft.Container(
        bgcolor=theme.BG_CARD,
        border=border_all(1, theme.BORDER),
        border_radius=theme.CARD_RADIUS,
        padding=pad_all(18),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[left, share_button],
        ),
    )