"""Une carte ressource : tag categorie, seeders, titre, description, meta, action."""
import flet as ft
import theme
from compat import pad_sym, pad_all, border_all, notify, clipboard_write


def _tag(text, bg, fg):
    return ft.Container(
        bgcolor=bg,
        border_radius=6,
        padding=pad_sym(h=8, v=2),
        content=ft.Text(text, size=9, weight=ft.FontWeight.W_600, color=fg),
    )


def _right_badge(resource):
    if resource.get("verified"):
        return ft.Container(
            bgcolor="#EFF6FF",
            border_radius=10,
            padding=pad_sym(h=8, v=2),
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.VERIFIED, size=11, color=theme.PRIMARY),
                    ft.Text("Verifie", size=9, color=theme.PRIMARY_DARK, weight=ft.FontWeight.W_600),
                ],
            ),
        )
    return ft.Container(
        bgcolor=theme.SUCCESS_SOFT,
        border_radius=10,
        padding=pad_sym(h=8, v=2),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.PEOPLE, size=11, color=theme.SUCCESS),
                ft.Text(f"{resource.get('seeders', 0)} seeders", size=9, color=theme.SUCCESS,
                        weight=ft.FontWeight.W_600),
            ],
        ),
    )


def build_resource_card(page: ft.Page, resource: dict, width: int = theme.CARD_WIDTH) -> ft.Control:
    bg, fg = theme.CATEGORY_COLORS.get(resource["category"], ("#F1F5F9", "#475569"))

    is_copy = resource.get("action") == "copy"
    if is_copy:
        action_icon, action_label = ft.Icons.CONTENT_COPY, "Copier le script"
        action_bg, action_fg = "#F1F5F9", theme.TEXT
    else:
        action_icon, action_label = ft.Icons.DOWNLOAD, "Telecharger (LAN)"
        action_bg, action_fg = theme.PRIMARY, "#FFFFFF"

    def on_action(e):
        if is_copy:
            ok = clipboard_write(resource["title"])
            notify(page, f"Copie : {resource['title']}" if ok else "Presse-papiers indisponible",
                   kind="success" if ok else "warning")
        else:
            notify(page, f"Transfert LAN : {resource['title']}...", kind="info")

    card = ft.Container(
        width=width,
        bgcolor=theme.BG_CARD,
        border=border_all(1, theme.BORDER),
        border_radius=theme.CARD_RADIUS,
        padding=pad_all(14),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[_tag(resource["category"], bg, fg), _right_badge(resource)],
                ),
                ft.Text(resource["title"], size=13, weight=ft.FontWeight.BOLD, color=theme.TEXT,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(resource.get("description", ""), size=10.5, color=theme.TEXT_MUTED,
                        max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(f"par {resource.get('uploader', '-')}", size=9, color=theme.TEXT_LIGHT),
                            ft.Text("•", size=9, color=theme.TEXT_LIGHT),
                            ft.Text(resource.get("uploaded", "-"), size=9, color=theme.TEXT_LIGHT),
                            ft.Text("•", size=9, color=theme.TEXT_LIGHT),
                            ft.Text(f"{resource.get('size', '-')}", size=9, color=theme.TEXT_LIGHT,
                                    font_family="Consolas, monospace"),
                        ],
                    ),
                    padding=pad_sym(v=4),
                ),
                ft.Container(
                    bgcolor=action_bg,
                    border_radius=8,
                    padding=pad_sym(h=12, v=10),
                    ink=True,
                    on_click=on_action,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=7,
                        controls=[
                            ft.Icon(action_icon, size=15, color=action_fg),
                            ft.Text(action_label, size=10.5, weight=ft.FontWeight.BOLD, color=action_fg),
                        ],
                    ),
                ),
            ],
        ),
    )

    def on_hover(e):
        card.border = border_all(1, theme.PRIMARY if e.data == "true" else theme.BORDER)
        card.update()

    card.on_hover = on_hover
    return card