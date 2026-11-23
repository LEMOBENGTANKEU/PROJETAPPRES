"""Vue de discussion par UE avec historique REST et rafraîchissement périodique."""
import asyncio
import logging

import flet as ft
import theme
from compat import notify, pad_all, pad_sym
from services.backend_client import BackendApiError

logger = logging.getLogger(__name__)


def build_chat_view(page: ft.Page, backend_client):
    state = {"ue_code": "INF101", "messages": [], "last_id": None, "active": True, "task": None}
    status = ft.Text("", size=12, color=theme.TEXT_MUTED)
    ue_field = ft.TextField(label="Code UE", value=state["ue_code"], width=180)
    message_field = ft.TextField(
        hint_text="Écrire un message...",
        expand=True,
        multiline=False,
        on_submit=lambda e: page.run_task(send_message, e) if hasattr(page, "run_task") else None,
    )
    messages_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

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

    async def load_messages(reset=False):
        if backend_client is None or not backend_client.is_authenticated:
            status.value = "Connectez-vous au serveur dans Paramètres pour accéder au chat."
            status.color = theme.WARNING
            render_messages()
            if page.controls:
                page.update()
            return
        ue_code = (ue_field.value or "").strip() or "INF101"
        state["ue_code"] = ue_code
        try:
            if reset:
                messages = await backend_client.list_chat_messages(ue_code)
                state["messages"] = messages
            else:
                messages = await backend_client.list_chat_messages(ue_code)
                known = {m.get("id") for m in state["messages"]}
                for msg in messages:
                    if msg.get("id") not in known:
                        state["messages"].append(msg)
            state["messages"].sort(key=lambda m: (m.get("created_at", ""), m.get("id", 0)))
            state["last_id"] = state["messages"][-1]["id"] if state["messages"] else None
            status.value = f"Salon UE {ue_code} — {len(state['messages'])} message(s)."
            status.color = theme.SUCCESS
            render_messages()
        except (BackendApiError, ValueError, TypeError, KeyError) as exc:
            status.value = f"Chat indisponible : {exc}"
            status.color = theme.ERROR
            logger.exception("Erreur chargement chat")
        try:
            page.update()
        except Exception:
            pass

    async def send_message(_e=None):
        if backend_client is None or not backend_client.is_authenticated:
            notify(page, "Connectez-vous au serveur pour envoyer un message.", "warning")
            return
        content = (message_field.value or "").strip()
        if not content:
            return
        ue_code = (ue_field.value or "").strip() or "INF101"
        send_button.disabled = True
        try:
            await backend_client.send_chat_message(ue_code, content)
            message_field.value = ""
            await load_messages(reset=True)
        except (BackendApiError, ValueError) as exc:
            notify(page, f"Envoi impossible : {exc}", "error")
            status.value = str(exc)
            status.color = theme.ERROR
        finally:
            send_button.disabled = False
            try:
                page.update()
            except Exception:
                pass

    async def poll_loop():
        while state["active"]:
            await asyncio.sleep(3)
            if not state["active"]:
                break
            try:
                await load_messages(reset=False)
            except Exception:
                logger.exception("Erreur polling chat")

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
            logger.exception("Impossible de démarrer le polling chat")

    async def on_load(_e=None):
        await load_messages(reset=True)
        start_polling()

    load_button = ft.OutlinedButton("Charger", icon=ft.Icons.REFRESH, on_click=lambda e: page.run_task(on_load) if hasattr(page, "run_task") else None)
    send_button = ft.Button("Envoyer", icon=ft.Icons.SEND, on_click=lambda e: page.run_task(send_message, e) if hasattr(page, "run_task") else None)

    view = ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Text("Discussion par unité d'enseignement", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Text(
                "Chat de salon (UE) via l'API du serveur. Le temps réel WebSocket est disponible côté backend; cette vue utilise un rafraîchissement périodique.",
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

    # Chargement initial asynchrone.
    try:
        if hasattr(page, "run_task"):
            page.run_task(on_load)
        else:
            asyncio.get_running_loop().create_task(on_load())
    except Exception:
        logger.exception("Chargement initial chat impossible")

    def dispose():
        state["active"] = False
        task = state.get("task")
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass

    return view, dispose
