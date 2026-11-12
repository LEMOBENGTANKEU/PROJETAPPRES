"""
Helpers robustes multi-versions de Flet : espacements, bordures,
notifications SnackBar, presse-papiers et lancement de l'application.
"""

import flet as ft
import theme

try:
    import pyperclip  # type: ignore
    _HAS_CLIPBOARD = True
except Exception:  # pragma: no cover - dependance optionnelle
    pyperclip = None  # type: ignore
    _HAS_CLIPBOARD = False

INFO_BG = "#EFF6FF"


def pad(left=0, top=0, right=0, bottom=0):
    return ft.Padding(left=left, top=top, right=right, bottom=bottom)


def pad_sym(h=0, v=0):
    return ft.Padding(left=h, top=v, right=h, bottom=v)


def pad_all(v):
    return ft.Padding(left=v, top=v, right=v, bottom=v)


def border_all(width, color):
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def border_right(width, color):
    return ft.Border(right=ft.BorderSide(width, color))


def border_bottom(width, color):
    return ft.Border(bottom=ft.BorderSide(width, color))


def radius(r):
    return ft.BorderRadius(top_left=r, top_right=r, bottom_left=r, bottom_right=r)


def dropdown_option(text):
    """ft.DropdownOption (recent) ou ft.dropdown.Option (ancien)."""
    if hasattr(ft, "DropdownOption"):
        return ft.DropdownOption(text)
    return ft.dropdown.Option(text)


def clipboard_write(text: str) -> bool:
    if _HAS_CLIPBOARD and pyperclip:
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            return False
    return False


_ICONS = {
    "info": ft.Icons.INFO_OUTLINE,
    "success": ft.Icons.CHECK_CIRCLE_OUTLINE,
    "warning": ft.Icons.WARNING_AMBER_OUTLINED,
    "error": ft.Icons.ERROR_OUTLINE,
}
_BG = {
    "info": INFO_BG,
    "success": theme.SUCCESS_SOFT,
    "warning": theme.WARNING_SOFT,
    "error": theme.ERROR_SOFT,
}
_FG = {
    "info": theme.PRIMARY,
    "success": theme.SUCCESS,
    "warning": theme.WARNING,
    "error": theme.ERROR,
}


def notify(page: ft.Page, message: str, kind: str = "info", duration: int = 4000):
    bar = ft.SnackBar(
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(_ICONS[kind], size=18, color=_FG[kind]),
                ft.Text(message, size=13, color=theme.TEXT, weight=ft.FontWeight.W_500),
            ],
        ),
        bgcolor=_BG[kind],
        duration=duration,
        show_close_icon=True,
    )
    _open(page, bar)


def _open(page: ft.Page, control: ft.Control):
    if hasattr(page, "open"):
        page.open(control)
    else:
        if isinstance(control, ft.SnackBar):
            page.snack_bar = control
            control.open = True
        page.update()


def run_app(main):
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)