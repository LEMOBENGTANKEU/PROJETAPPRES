"""Barre de filtres : puces de categorie + selecteur de niveau d'etudes."""
import flet as ft
import theme
from compat import pad_sym, border_all, dropdown_option
from data import CATEGORIES, LEVELS


def _chip(label, active, on_click):
    return ft.Container(
        bgcolor=theme.PRIMARY if active else theme.BG_CARD,
        border=border_all(1, theme.PRIMARY if active else theme.BORDER),
        border_radius=theme.CHIP_RADIUS,
        padding=pad_sym(h=14, v=7),
        ink=True,
        on_click=on_click,
        content=ft.Text(
            label,
            size=11,
            weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_500,
            color="#FFFFFF" if active else theme.TEXT,
        ),
    )


def build_filter_bar(active_category, on_select, active_level=None, on_level_change=None):
    chips = ft.Row(
        wrap=True,
        spacing=8,
        run_spacing=8,
        controls=[_chip(c, c == active_category, lambda e, c=c: on_select(c)) for c in CATEGORIES],
    )

    options = []
    for lbl, val in LEVELS:
        if hasattr(ft, "DropdownOption"):
            options.append(ft.DropdownOption(text=lbl, key=val))
        else:
            options.append(ft.dropdown.Option(text=lbl, key=val))
    level = ft.Dropdown(
        label="Niveau",
        value=active_level,
        options=options,
        width=210,
        content_padding=pad_sym(h=12, v=0),
        border_radius=theme.INPUT_RADIUS,
        border_color=theme.BORDER,
        bgcolor=theme.BG_CARD,
    )
    if on_level_change:
        level.on_change = on_level_change

    return ft.Row(
        vertical_alignment=ft.CrossAxisAlignment.START,
        controls=[chips, ft.Container(width=24), level],
    )