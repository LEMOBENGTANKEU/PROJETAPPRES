"""Vue de signalisation d'appels/salles (échange SDP/ICE) via API REST."""
import asyncio
import json
import logging

import flet as ft
import theme
from compat import notify, pad_all
from services.backend_client import BackendApiError

logger = logging.getLogger(__name__)


def build_calls_view(page: ft.Page, backend_client):
    state = {"room_id": "room-demo", "messages": [], "active": True, "task": None}
    status = ft.Text("", size=12, color=theme.TEXT_MUTED)
    room_field = ft.TextField(label="ID de salle", value=state["room_id"], width=220)
    type_field = ft.TextField(label="Type", value="offer", width=160)
    payload_field = ft.TextField(
        label="Payload JSON",
        value='{"sdp":"..."}',
        multiline=True,
        min_lines=3,
        max_lines=6,
        expand=True,
    )
    messages_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def render_messages():
        controls = []
        for msg in state["messages"]:
            sender = msg.get("sender_username") or msg.get("sender") or "?"
            created = str(msg.get("created_at", ""))[:19].replace("T", " ")
            payload = msg.get("payload", msg)
            try:
                payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
            except Exception:
                payload_text = str(payload)
            controls.append(
                ft.Container(
                    bgcolor=theme.BG_CARD,
                    border_radius=10,
                    padding=pad_all(10),
                    content=ft.Column(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(f"{sender} · {msg.get('message_type', msg.get('type', 'signal'))}", size=11, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                                    ft.Text(created, size=10, color=theme.TEXT_MUTED),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(payload_text, size=11, color=theme.TEXT, selectable=True, font_family="Consolas, monospace"),
                        ],
                    ),
                )
            )
        messages_column.controls = controls

    async def load_messages(reset=False):
        if backend_client is None or not backend_client.is_authenticated:
            status.value = "Connectez-vous au serveur dans Paramètres pour utiliser la signalisation."
            status.color = theme.WARNING
            render_messages()
            try:
                page.update()
            except Exception:
                pass
            return
        room_id = (room_field.value or "").strip() or "room-demo"
        state["room_id"] = room_id
        try:
            messages = await backend_client.list_signaling_messages(room_id)
            state["messages"] = messages
            status.value = f"Salle {room_id} — {len(messages)} message(s) de signalisation."
            status.color = theme.SUCCESS
            render_messages()
        except (BackendApiError, ValueError, TypeError, KeyError) as exc:
            status.value = f"Signalisation indisponible : {exc}"
            status.color = theme.ERROR
            logger.exception("Erreur chargement signalisation")
        try:
            page.update()
        except Exception:
            pass

    async def send_signal(_e=None):
        if backend_client is None or not backend_client.is_authenticated:
            notify(page, "Connectez-vous au serveur pour envoyer un signal.", "warning")
            return
        room_id = (room_field.value or "").strip() or "room-demo"
        message_type = (type_field.value or "signal").strip() or "signal"
        raw = (payload_field.value or "").strip() or "{}"
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                payload = {"value": payload}
        except json.JSONDecodeError:
            notify(page, "Le payload doit être un JSON valide.", "error")
            return
        send_button.disabled = True
        try:
            await backend_client.send_signaling_message(room_id, message_type, payload)
            await load_messages(reset=True)
            notify(page, "Message de signalisation envoyé.", "success")
        except (BackendApiError, ValueError) as exc:
            notify(page, f"Envoi impossible : {exc}", "error")
        finally:
            send_button.disabled = False
            try:
                page.update()
            except Exception:
                pass

    async def poll_loop():
        while state["active"]:
            await asyncio.sleep(2)
            if not state["active"]:
                break
            try:
                await load_messages(reset=False)
            except Exception:
                logger.exception("Erreur polling signalisation")

    def start_polling():
        if state["task"] is not None:
            return
        try:
            if hasattr(page, "run_task"):
                state["task"] = page.run_task(poll_loop)
            else:
                loop = asyncio.get_running_loop()
                state["task"] = loop.create_task(poll_loop())
        except Exception:
            logger.exception("Impossible de démarrer le polling signalisation")

    async def on_load(_e=None):
        await load_messages(reset=True)
        start_polling()

    load_button = ft.OutlinedButton("Rejoindre / Rafraîchir", icon=ft.Icons.REFRESH, on_click=lambda e: page.run_task(on_load) if hasattr(page, "run_task") else None)
    send_button = ft.Button("Envoyer le signal", icon=ft.Icons.SEND, on_click=lambda e: page.run_task(send_signal, e) if hasattr(page, "run_task") else None)

    view = ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Text("Appels P2P locaux — signalisation", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Text(
                "Échange de messages de signalisation (SDP/ICE) par salle via l'API REST du backend "
                "(et relais WebSocket disponible côté serveur: /ws/signaling/<room_id>/). "
                "Le transport média WebRTC audio/vidéo/partage d'écran nécessite un client média compatible et n'est pas intégré dans cette interface desktop.",
                size=12,
                color=theme.TEXT_MUTED,
            ),
            ft.Row(controls=[room_field, load_button, status], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                expand=True,
                bgcolor=theme.BG_INPUT,
                border_radius=theme.CARD_RADIUS,
                padding=pad_all(12),
                content=messages_column,
            ),
            ft.Row(controls=[type_field], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            payload_field,
            ft.Row(controls=[send_button], alignment=ft.MainAxisAlignment.END),
        ],
    )

    try:
        if hasattr(page, "run_task"):
            page.run_task(on_load)
        else:
            asyncio.get_running_loop().create_task(on_load())
    except Exception:
        logger.exception("Chargement initial signalisation impossible")

    def dispose():
        state["active"] = False
        task = state.get("task")
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass

    return view, dispose
