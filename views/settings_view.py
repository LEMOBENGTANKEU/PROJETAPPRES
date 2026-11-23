"""Parametres de l'application : apparence, reseau, a propos."""
import logging

import flet as ft
import theme
from compat import pad_all, notify
from services.backend_client import BackendApiError

logger = logging.getLogger(__name__)


def build_settings_view(
    page: ft.Page,
    backend_client=None,
    on_connected=None,
    sharing_service=None,
) -> ft.Control:
    def on_theme_change(e):
        page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        page.update()
        notify(page, "ThÃ¨me : " + ("Sombre" if e.control.value else "Clair"), kind="info")

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

    peers_text = ft.Text(
        "La dÃ©couverte UDP dÃ©marre lorsque le partage P2P est actif.",
        size=12,
        color=theme.TEXT_MUTED,
        selectable=True,
    )
    shares_column = ft.Column(spacing=8)

    def refresh_peers(_e=None):
        if sharing_service is None or not hasattr(sharing_service, "discovered_peers"):
            peers_text.value = "Service de dÃ©couverte indisponible."
            peers_text.color = theme.TEXT_MUTED
        else:
            peers = sharing_service.discovered_peers()
            if peers:
                lines = []
                for peer in peers:
                    lines.append(
                        f"- {peer.get('node_name', '?')} @ {peer.get('ip', '?')}:{peer.get('service_port', '?')}"
                    )
                peers_text.value = "\n".join(lines)
                peers_text.color = theme.SUCCESS
            else:
                peers_text.value = (
                    "Aucun pair dÃ©couvert pour le moment. Lancez un partage ou vÃ©rifiez le rÃ©seau LAN/UDP."
                )
                peers_text.color = theme.TEXT_MUTED
        try:
            page.update()
        except Exception:
            pass

    async def on_revoke_share(resource_id):
        if sharing_service is None:
            notify(page, "Service de partage indisponible.", kind="error")
            return
        try:
            await sharing_service.unshare_resource(resource_id, revoke_consent=True)
            notify(page, "Partage rÃ©voquÃ© pour cette ressource.", kind="success")
        except Exception as exc:
            logger.exception("RÃ©vocation du partage impossible.")
            notify(page, f"Impossible de rÃ©voquer le partage : {exc}", kind="error")
        refresh_shares()

    def refresh_shares(_e=None):
        shares_column.controls.clear()
        records = []
        if sharing_service is not None and hasattr(sharing_service, "consented_resources"):
            try:
                records = sharing_service.consented_resources()
            except Exception:
                records = []
        if not records:
            shares_column.controls.append(
                ft.Text(
                    "Aucune ressource partagÃ©e avec consentement enregistrÃ©.",
                    size=12,
                    color=theme.TEXT_MUTED,
                )
            )
        else:
            for record in records:
                resource_id = str(record.get("id", ""))
                title = str(record.get("file_name") or record.get("id") or "Ressource")
                active = sharing_service.is_resource_shared(resource_id) if sharing_service else False
                status_label = "actif" if active else "consenti (sera restaurÃ© Ã  la connexion si disponible)"
                shares_column.controls.append(
                    ft.Container(
                        bgcolor="#F8FAFC",
                        border_radius=10,
                        padding=pad_all(10),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                    controls=[
                                        ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=theme.TEXT),
                                        ft.Text(f"ID: {resource_id} Â· {status_label}", size=11, color=theme.TEXT_MUTED),
                                    ],
                                ),
                                ft.TextButton(
                                    "RÃ©voquer",
                                    icon=ft.Icons.STOP_CIRCLE_OUTLINED,
                                    on_click=lambda _e, rid=resource_id: page.run_task(on_revoke_share, rid) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(on_revoke_share(rid)),
                                ),
                            ],
                        ),
                    )
                )
        try:
            page.update()
        except Exception:
            pass

    async def on_connect(_e):
        if backend_client is None:
            notify(page, "Le client du serveur n'est pas configurÃ©.", kind="error")
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
            connection_status.value = f"ConnectÃ© Ã  {backend_client.base_url}"
            connection_status.color = theme.SUCCESS
            password.value = ""
            notify(page, "Connexion rÃ©ussie au serveur CampusShare.", kind="success")
            if sharing_service is not None:
                try:
                    restored = await sharing_service.restore_consented_shares()
                    if restored:
                        notify(
                            page,
                            f"{restored} ressource(s) partagÃ©e(s) automatiquement.",
                            kind="success",
                        )
                except (BackendApiError, OSError, ValueError, TypeError, KeyError) as exc:
                    logger.exception("Impossible de restaurer les partages consentis.")
                    notify(
                        page,
                        f"Partage automatique indisponible : {exc}",
                        kind="warning",
                    )
                    refresh_shares()
            refresh_peers()
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

    refresh_shares()

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
                    ft.Text("ConÃ§u pour l'UY1 - Amphi 250.", size=12, color=theme.TEXT_MUTED),
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
                            "L'adresse doit pointer vers le serveur Django du mÃªme rÃ©seau local.",
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
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.WIFI_TETHERING, color=theme.TEXT_MUTED, size=20),
                                ft.Text(
                                    "DÃ©couverte des pairs (UDP LAN)",
                                    size=15,
                                    weight=ft.FontWeight.W_700,
                                    color=theme.TEXT,
                                ),
                            ],
                        ),
                        ft.Text(
                            "Affiche les pairs CampusShare dÃ©tectÃ©s par beacon UDP sur le rÃ©seau local.",
                            size=12,
                            color=theme.TEXT_MUTED,
                        ),
                        ft.OutlinedButton("Actualiser les pairs", icon=ft.Icons.REFRESH, on_click=refresh_peers),
                        peers_text,
                    ],
                ),
            ),
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
                                ft.Icon(ft.Icons.FOLDER_SHARED, color=theme.TEXT_MUTED, size=20),
                                ft.Text(
                                    "Partages consentis",
                                    size=15,
                                    weight=ft.FontWeight.W_700,
                                    color=theme.TEXT,
                                ),
                            ],
                        ),
                        ft.Text(
                            "Ressources que vous avez accepté de partager. Vous pouvez révoquer le consentement à tout moment.",
                            size=12,
                            color=theme.TEXT_MUTED,
                        ),
                        ft.OutlinedButton("Actualiser les partages", icon=ft.Icons.REFRESH, on_click=refresh_shares),
                        shares_column,
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