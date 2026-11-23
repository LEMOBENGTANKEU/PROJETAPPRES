"""Vue de discussion par UE avec historique REST, WebSocket temps réel si disponible et repli périodique."""
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


def build_chat_view(page: ft.Page, backend_client):
    state = {
        "ue_code": "INF101",
        "messages": [],
        "active": True,
        "poll_task": None,
        "ws_task": None,
        "ws_connected": False,
    }
    status = ft.Text("", size=12, color=theme.TEXT_MUTED)
    ue_field = ft.TextField(label="Code UE", value=state["ue_code"], width=180)
    message_field = ft.TextField(
        hint_text="Écrire un message...",
        expand=True,
        multiline=False,
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
            author = msg.get("author_username") or msg.get("author") or "?"
            created = str(msg.get("created_at", ""))[:19].replace("T", " ")
            controls.append(
                ft.Container(
                    bgcolor=theme.BG_CARD,
                    border_radius=10,
                    padding=pad_all(10),
                    content=ft.Column(
                        spacing=2,
                        tight=True,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(str(author), size=11, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                                    ft.Text(created, size=10, color=theme.TEXT_MUTED),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(str(msg.get("content", "")), size=13, color=theme.TEXT, selectable=True),
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
            status.value = "Connectez-vous au serveur dans Paramètres pour accéder au chat."
            status.color = theme.WARNING
            render_messages()
            safe_update()
            return
        ue_code = (ue_field.value or "").strip() or "INF101"
        state["ue_code"] = ue_code
        try:
            messages = await backend_client.list_chat_messages(ue_code)
            merge_messages(messages, replace=reset)
            render_messages()
            update_status(f"Salon UE {ue_code} — {len(state['messages'])} message(s)")
        except (BackendApiError, ValueError, TypeError, KeyError) as exc:
            status.value = f"Chat indisponible : {exc}"
            status.color = theme.ERROR
            logger.exception("Erreur chargement chat")
        safe_update()

    async def send_message(_e=None):
        if backend_client is None or not backend_client.is_authenticated:
            notify(page, "Connectez-vous au serveur pour envoyer un message.", "warning")
            return
        content = (message_field.value or "").strip()
        if not content:
            return
        ue_code = (ue_field.value or "").strip() or "INF101"
        send_button.disabled = True
        safe_update()
        try:
            await backend_client.send_chat_message(ue_code, content)
            message_field.value = ""
            await load_messages(reset=False)
        except (BackendApiError, ValueError) as exc:
            notify(page, f"Envoi impossible : {exc}", "error")
            status.value = str(exc)
            status.color = theme.ERROR
        finally:
            send_button.disabled = False
            safe_update()

    async def poll_loop():
        while state["active"]:
            await asyncio.sleep(3 if not state["ws_connected"] else 8)
            if not state["active"]:
                break
            try:
                await load_messages(reset=False)
            except Exception:
                logger.exception("Erreur polling chat")

    async def ws_loop():
        if websockets is None:
            return
        while state["active"]:
            if backend_client is None or not getattr(backend_client, "is_authenticated", False):
                state["ws_connected"] = False
                await asyncio.sleep(2)
                continue
            ue_code = (ue_field.value or "").strip() or "INF101"
            try:
                ws_url = backend_client.websocket_url(f"/ws/chat/{ue_code}/")
            except Exception:
                state["ws_connected"] = False
                await asyncio.sleep(3)
                continue
            try:
                async with websockets.connect(ws_url, open_timeout=5, close_timeout=2, ping_interval=20, ping_timeout=20) as ws:
                    state["ws_connected"] = True
                    update_status(f"Salon UE {ue_code} — {len(state['messages'])} message(s)")
                    safe_update()
                    while state["active"]:
                        current_ue = (ue_field.value or "").strip() or "INF101"
                        if current_ue != ue_code:
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            data = json.loads(raw)
                        except Exception:
                            continue
                        if isinstance(data, dict) and data.get("error"):
                            continue
                        if isinstance(data, dict) and data.get("id") is not None:
                            merge_messages([data], replace=False)
                            render_messages()
                            update_status(f"Salon UE {ue_code} — {len(state['messages'])} message(s)")
                            safe_update()
            except asyncio.CancelledError:
                raise
            except Exception:
                state["ws_connected"] = False
                if state["active"]:
                    try:
                        update_status(f"Salon UE {state.get('ue_code', ue_code)} — {len(state['messages'])} message(s)")
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
                logger.exception("Impossible de démarrer le polling chat")
        if websockets is not None and state["ws_task"] is None:
            try:
                state["ws_task"] = page.run_task(ws_loop) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(ws_loop())
            except Exception:
                logger.exception("Impossible de démarrer le WebSocket chat")

    async def on_load(_e=None):
        await load_messages(reset=True)
        start_tasks()

    message_field.on_submit = lambda e: page.run_task(send_message, e) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(send_message(e))
    load_button = ft.OutlinedButton("Charger / Rejoindre", icon=ft.Icons.REFRESH, on_click=lambda e: page.run_task(on_load) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(on_load()))
    send_button = ft.Button("Envoyer", icon=ft.Icons.SEND, on_click=lambda e: page.run_task(send_message, e) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(send_message(e)))

    view = ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Text("Discussion par unité d'enseignement", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Text(
                "Chat de salon (UE) via l'API REST du serveur avec réception temps réel WebSocket lorsque disponible (repli automatique en polling).",
                size=12,
                color=theme.TEXT_MUTED,
            ),
            ft.Row(controls=[ue_field, load_button, status], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(
                expand=True,
                bgcolor=theme.BG_INPUT,
                border_radius=theme.CARD_RADIUS,
                padding=pad_all(12),
                content=messages_column,
            ),
            ft.Row(controls=[message_field, send_button], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ],
    )

    try:
        if hasattr(page, "run_task"):
            page.run_task(on_load)
        else:
            asyncio.get_running_loop().create_task(on_load())
    except Exception:
        logger.exception("Chargement initial chat impossible")

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
