"""Vue de signalisation d'appels/salles (échange SDP/ICE) via REST avec WebSocket temps réel si disponible."""
import asyncio
import json
import logging

import flet as ft
import theme
from compat import notify, pad_all
from services.backend_client import BackendApiError

try:
    import websockets
except Exception:  # pragma: no cover - optional runtime dependency
    websockets = None

logger = logging.getLogger(__name__)


def build_calls_view(page: ft.Page, backend_client):
    state = {
        "room_id": "room-demo",
        "messages": [],
        "active": True,
        "poll_task": None,
        "ws_task": None,
        "ws_connected": False,
    }
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

    def safe_update():
        try:
            page.update()
        except Exception:
            pass

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
            msg_type = msg.get("message_type", msg.get("type", "signal"))
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
                                    ft.Text(f"{sender} · {msg_type}", size=11, weight=ft.FontWeight.BOLD, color=theme.TEXT),
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

    def merge_messages(messages, replace=False):
        if replace:
            state["messages"] = list(messages)
        else:
            known = {m.get("id") for m in state["messages"]}
            for msg in messages:
                if isinstance(msg, dict) and msg.get("id") not in known:
                    state["messages"].append(msg)
        state["messages"].sort(key=lambda m: (str(m.get("created_at", "")), m.get("id", 0)))

    def update_status(base_message):
        transport = "WebSocket" if state["ws_connected"] else "REST/polling"
        status.value = f"{base_message} — mode {transport}."
        status.color = theme.SUCCESS if backend_client and backend_client.is_authenticated else theme.WARNING

    async def load_messages(reset=False):
        if backend_client is None or not backend_client.is_authenticated:
            state["ws_connected"] = False
            status.value = "Connectez-vous au serveur dans Paramètres pour utiliser la signalisation."
            status.color = theme.WARNING
            render_messages()
            safe_update()
            return
        room_id = (room_field.value or "").strip() or "room-demo"
        state["room_id"] = room_id
        try:
            messages = await backend_client.list_signaling_messages(room_id)
            merge_messages(messages, replace=reset)
            render_messages()
            update_status(f"Salle {room_id} — {len(state['messages'])} message(s) de signalisation")
        except (BackendApiError, ValueError, TypeError, KeyError) as exc:
            status.value = f"Signalisation indisponible : {exc}"
            status.color = theme.ERROR
            logger.exception("Erreur chargement signalisation")
        safe_update()

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
        safe_update()
        try:
            await backend_client.send_signaling_message(room_id, message_type, payload)
            await load_messages(reset=False)
            notify(page, "Message de signalisation envoyé.", "success")
        except (BackendApiError, ValueError) as exc:
            notify(page, f"Envoi impossible : {exc}", "error")
        finally:
            send_button.disabled = False
            safe_update()

    async def poll_loop():
        while state["active"]:
            await asyncio.sleep(2 if not state["ws_connected"] else 6)
            if not state["active"]:
                break
            try:
                await load_messages(reset=False)
            except Exception:
                logger.exception("Erreur polling signalisation")

    async def ws_loop():
        if websockets is None:
            return
        while state["active"]:
            if backend_client is None or not getattr(backend_client, "is_authenticated", False):
                state["ws_connected"] = False
                await asyncio.sleep(2)
                continue
            room_id = (room_field.value or "").strip() or "room-demo"
            try:
                ws_url = backend_client.websocket_url(f"/ws/signaling/{room_id}/")
            except Exception:
                state["ws_connected"] = False
                await asyncio.sleep(3)
                continue
            try:
                async with websockets.connect(ws_url, open_timeout=5, close_timeout=2, ping_interval=20, ping_timeout=20) as ws:
                    state["ws_connected"] = True
                    update_status(f"Salle {room_id} — {len(state['messages'])} message(s) de signalisation")
                    safe_update()
                    while state["active"]:
                        current_room = (room_field.value or "").strip() or "room-demo"
                        if current_room != room_id:
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            data = json.loads(raw)
                        except Exception:
                            continue
                        if isinstance(data, dict) and data.get("type") == "presence":
                            continue
                        if isinstance(data, dict) and data.get("error"):
                            continue
                        if isinstance(data, dict) and data.get("id") is not None:
                            merge_messages([data], replace=False)
                            render_messages()
                            update_status(f"Salle {room_id} — {len(state['messages'])} message(s) de signalisation")
                            safe_update()
            except asyncio.CancelledError:
                raise
            except Exception:
                state["ws_connected"] = False
                if state["active"]:
                    try:
                        update_status(f"Salle {state.get('room_id', room_id)} — {len(state['messages'])} message(s) de signalisation")
                    except Exception:
                        pass
                    safe_update()
                    await asyncio.sleep(2)
            finally:
                state["ws_connected"] = False

    def start_tasks():
        if state["poll_task"] is None:
            try:
                state["poll_task"] = page.run_task(poll_loop) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(poll_loop())
            except Exception:
                logger.exception("Impossible de démarrer le polling signalisation")
        if websockets is not None and state["ws_task"] is None:
            try:
                state["ws_task"] = page.run_task(ws_loop) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(ws_loop())
            except Exception:
                logger.exception("Impossible de démarrer le WebSocket signalisation")

    async def on_load(_e=None):
        await load_messages(reset=True)
        start_tasks()

    load_button = ft.OutlinedButton("Rejoindre / Rafraîchir", icon=ft.Icons.REFRESH, on_click=lambda e: page.run_task(on_load) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(on_load()))
    send_button = ft.Button("Envoyer le signal", icon=ft.Icons.SEND, on_click=lambda e: page.run_task(send_signal, e) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(send_signal(e)))

    view = ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Text("Appels P2P locaux — signalisation", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Text(
                "Échange de messages de signalisation (SDP/ICE) par salle via REST avec réception WebSocket temps réel lorsque disponible "
                "(routes backend: /api/v1/signaling/... et /ws/signaling/<room_id>/). "
                "Le transport média WebRTC audio/vidéo/partage d'écran nécessite un client média compatible, des permissions matérielles et une validation sur LAN réel; "
                "cette interface gère la signalisation et le pilotage de session, pas le flux média natif complet.",
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
        for key in ("poll_task", "ws_task"):
            task = state.get(key)
            if task is not None:
                try:
                    task.cancel()
                except Exception:
                    pass

    return view, dispose
