"""Parametres de l'application : apparence, reseau, a propos."""
import flet as ft
import theme
from compat import pad_all, notify
from services.backend_client import BackendApiError


def build_settings_view(
    page: ft.Page,
    backend_client=None,
    on_connected=None,
) -> ft.Control:
    def on_theme_change(e):
        page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        page.update()
        notify(page, "Thème : " + ("Sombre" if e.control.value else "Clair"), kind="info")

    theme_switch = ft.Switch(
        label="Theme sombre",
        value=(page.theme_mode == ft.ThemeMode.DARK),
        on_change=on_theme_change,
    )

    server_url = ft.TextField(
        label="Adresse du serveur CampusShare",
        value=backend_client.base_url if backend_client else "http://127.0.0.1:8000",
        hint_text="http://192.168.1.10:8000",
        width=440,
    )
    username = ft.TextField(
        label="Nom d'utilisateur",
        width=280,
        autofill_hints=ft.AutofillHint.USERNAME,
    )
    password = ft.TextField(
        label="Mot de passe",
        password=True,
        can_reveal_password=True,
        width=280,
    )
    connection_status = ft.Text(
        "Connectez-vous pour charger le catalogue du campus.",
        size=12,
        color=theme.TEXT_MUTED,
    )

    async def on_connect(_e):
        if backend_client is None:
            notify(page, "Le client du serveur n'est pas configuré.", kind="error")
            return
        connect_button.disabled = True
        connection_status.value = "Connexion au serveur..."
        connection_status.color = theme.TEXT_MUTED
        page.update()
        try:
            backend_client.set_base_url(server_url.value or "")
            await backend_client.login(username.value or "", password.value or "")
        except (BackendApiError, ValueError) as exc:
            connection_status.value = str(exc)
            connection_status.color = theme.ERROR
            notify(page, str(exc), kind="error")
        else:
            connection_status.value = f"Connecté à {backend_client.base_url}"
            connection_status.color = theme.SUCCESS
            password.value = ""
            notify(page, "Connexion réussie au serveur CampusShare.", kind="success")
            if on_connected is not None:
                on_connected()
        finally:
            connect_button.disabled = False
            page.update()

    connect_button = ft.Button(
        "Se connecter",
        icon=ft.Icons.LAN,
        on_click=on_connect,
    )

    def close_about(dlg):
        dlg.open = False
        page.update()

    def on_about(_e):
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
                ft.TextButton("Fermer", on_click=lambda _e: close_about(dlg)),
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
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.LAN, color=theme.TEXT_MUTED, size=20),
                                ft.Text(
                                    "Connexion au serveur du campus",
                                    size=15,
                                    weight=ft.FontWeight.W_700,
                                    color=theme.TEXT,
                                ),
                            ],
                        ),
                        ft.Text(
                            "L'adresse doit pointer vers le serveur Django du même réseau local.",
                            size=12,
                            color=theme.TEXT_MUTED,
                        ),
                        server_url,
                        username,
                        password,
                        ft.Row(
                            controls=[connect_button, connection_status],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                ),
            ),
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