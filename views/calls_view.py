"""Vue d'appels P2P locaux: signalisation REST/WS + session média WebRTC optionnelle."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import flet as ft
import theme
from compat import notify, pad_all
from services.backend_client import BackendApiError
from services.webrtc_media_service import WebRTCMediaSession, detect_capabilities, list_media_devices

try:
    import websockets
except Exception:  # pragma: no cover - optional runtime dependency
    websockets = None

logger = logging.getLogger(__name__)


_BLANK_IMAGE_SRC = "data:image/gif;base64,R0lGODlhAQABAAAAACw="


def _b64_image(src_b64: str | None) -> ft.Image:
    return ft.Image(
        src=f"data:image/jpeg;base64,{src_b64}" if src_b64 else _BLANK_IMAGE_SRC,
        width=320,
        height=180,
        fit=ft.BoxFit.CONTAIN,
        border_radius=8,
        visible=bool(src_b64),
    )


def build_calls_view(page: ft.Page, backend_client):
    caps = detect_capabilities()
    state: dict[str, Any] = {
        "room_id": "room-demo",
        "messages": [],
        "active": True,
        "poll_task": None,
        "ws_task": None,
        "ws_connected": False,
        "media": None,
        "media_busy": False,
        "local_preview_b64": None,
        "remote_preview_b64": None,
        "devices": list_media_devices(),
    }

    status = ft.Text("", size=12, color=theme.TEXT_MUTED)
    media_status = ft.Text("", size=12, color=theme.TEXT_MUTED)
    room_field = ft.TextField(label="ID de salle", value=state["room_id"], width=220)
    type_field = ft.TextField(label="Type signal", value="offer", width=160)
    payload_field = ft.TextField(
        label="Payload JSON (signal manuel)",
        value='{"sdp":"..."}',
        multiline=True,
        min_lines=2,
        max_lines=5,
        expand=True,
    )
    messages_column = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    local_preview = _b64_image(None)
    remote_preview = _b64_image(None)
    local_preview_placeholder = ft.Container(
        width=320, height=180, bgcolor=theme.BG_CARD, border_radius=8,
        alignment=ft.Alignment(0, 0), content=ft.Text("Aperçu local", size=11, color=theme.TEXT_MUTED),
    )
    remote_preview_placeholder = ft.Container(
        width=320, height=180, bgcolor=theme.BG_CARD, border_radius=8,
        alignment=ft.Alignment(0, 0), content=ft.Text("Flux distant", size=11, color=theme.TEXT_MUTED),
    )

    def device_options(kind: str):
        items = [ft.dropdown.Option("", "(défaut/aucun)")]
        for dev in state["devices"].get(kind, []):
            label = dev.get("name") or dev.get("id")
            items.append(ft.dropdown.Option(str(dev.get("id", "")), label))
        return items

    camera_dropdown = ft.Dropdown(label="Caméra", width=220, options=device_options("video_inputs"), value="")
    mic_dropdown = ft.Dropdown(label="Micro", width=220, options=device_options("audio_inputs"), value="")
    screen_dropdown = ft.Dropdown(label="Écran", width=220, options=device_options("screen_inputs"), value="")

    def safe_update():
        try:
            page.update()
        except Exception:
            pass

    def set_media_status(text: str, color=theme.TEXT_MUTED):
        media_status.value = text
        media_status.color = color
        safe_update()

    def refresh_previews():
        local_b64 = state.get("local_preview_b64")
        remote_b64 = state.get("remote_preview_b64")
        local_preview.src = f"data:image/jpeg;base64,{local_b64}" if local_b64 else _BLANK_IMAGE_SRC
        local_preview.visible = bool(local_b64)
        local_preview_placeholder.visible = not local_preview.visible
        remote_preview.src = f"data:image/jpeg;base64,{remote_b64}" if remote_b64 else _BLANK_IMAGE_SRC
        remote_preview.visible = bool(remote_b64)
        remote_preview_placeholder.visible = not remote_preview.visible

    def render_messages():
        controls = []
        for msg in state["messages"][-100:]:
            sender = msg.get("sender_username") or msg.get("sender") or "?"
            created = str(msg.get("created_at", ""))[:19].replace("T", " ")
            payload = msg.get("payload", msg)
            try:
                payload_text = json.dumps(payload, ensure_ascii=False)
            except Exception:
                payload_text = str(payload)
            if len(payload_text) > 600:
                payload_text = payload_text[:600] + "…"
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
            state["messages"] = [m for m in messages if isinstance(m, dict)]
        else:
            known = {m.get("id") for m in state["messages"] if isinstance(m, dict)}
            for msg in messages:
                if isinstance(msg, dict) and msg.get("id") not in known:
                    state["messages"].append(msg)
        state["messages"].sort(key=lambda m: (str(m.get("created_at", "")), m.get("id", 0)))

    def update_status(base_message):
        transport = "WebSocket" if state["ws_connected"] else "REST/polling"
        status.value = f"{base_message} — mode {transport}."
        status.color = theme.SUCCESS if backend_client and backend_client.is_authenticated else theme.WARNING

    async def ensure_media_session():
        media: WebRTCMediaSession | None = state.get("media")
        if media is not None:
            return media

        def on_local(label, b64):
            state["local_preview_b64"] = b64
            refresh_previews()
            safe_update()

        def on_remote(label, b64):
            state["remote_preview_b64"] = b64
            refresh_previews()
            safe_update()

        def on_state(payload):
            event = payload.get("event", "state")
            mode = payload.get("mode", "")
            set_media_status(f"Média: {event} ({mode})", theme.TEXT_MUTED)

        media = WebRTCMediaSession(on_local_frame=on_local, on_remote_frame=on_remote, on_state=on_state)
        state["media"] = media
        return media

    async def send_signal_message(message_type: str, payload: dict[str, Any]):
        if backend_client is None or not backend_client.is_authenticated:
            raise BackendApiError("Non authentifié.")
        room_id = (room_field.value or "").strip() or "room-demo"
        await backend_client.send_signaling_message(room_id, message_type, payload)

    async def handle_incoming_media_message(msg: dict[str, Any]):
        media: WebRTCMediaSession | None = state.get("media")
        if media is None or media.pc is None:
            return
        mtype = msg.get("message_type") or msg.get("type")
        payload = msg.get("payload")
        if not isinstance(payload, dict):
            return
        try:
            if mtype == "offer" and "sdp" in payload and payload.get("type") == "offer":
                answer = await media.create_answer(payload)
                await send_signal_message("answer", answer)
                set_media_status("Offre reçue, réponse envoyée.", theme.SUCCESS)
            elif mtype == "answer" and "sdp" in payload and payload.get("type") == "answer":
                await media.apply_remote_description(payload)
                set_media_status("Réponse SDP appliquée.", theme.SUCCESS)
            elif mtype in {"ice", "ice_candidate", "candidate"} and payload.get("candidate"):
                await media.add_ice_candidate(payload)
        except Exception as exc:
            logger.exception("Erreur traitement signal média entrant")
            set_media_status(f"Erreur média entrant: {exc}", theme.ERROR)

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
            if reset:
                # Apply latest media-related messages only when a session exists.
                for msg in state["messages"][-20:]:
                    await handle_incoming_media_message(msg)
        except (BackendApiError, ValueError, TypeError, KeyError) as exc:
            status.value = f"Signalisation indisponible : {exc}"
            status.color = theme.ERROR
            logger.exception("Erreur chargement signalisation")
        safe_update()

    async def send_manual_signal(_e=None):
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

    async def start_media(kind: str):
        if state.get("media_busy"):
            return
        state["media_busy"] = True
        try:
            media = await ensure_media_session()
            caps_now = detect_capabilities()
            state["devices"] = list_media_devices()
            camera_dropdown.options = device_options("video_inputs")
            mic_dropdown.options = device_options("audio_inputs")
            screen_dropdown.options = device_options("screen_inputs")

            async def on_ice(candidate_payload):
                try:
                    await send_signal_message("ice_candidate", candidate_payload)
                except Exception:
                    logger.exception("Envoi ICE impossible")

            await media.create_peer_connection(on_ice_candidate=on_ice)
            if kind == "camera":
                if not caps_now.video_capture or not caps_now.webrtc:
                    raise RuntimeError("Caméra/WebRTC indisponible. Installez aiortc, av, opencv-python, numpy.")
                idx = int(camera_dropdown.value or "0")
                await media.add_camera(device_index=idx)
                set_media_status(f"Caméra démarrée (index {idx}).", theme.SUCCESS)
            elif kind == "screen":
                if not caps_now.screen_capture or not caps_now.webrtc:
                    raise RuntimeError("Partage d'écran/WebRTC indisponible. Installez aiortc, av, mss, numpy.")
                idx = int(screen_dropdown.value or "0")
                await media.add_screen(monitor_index=idx)
                set_media_status(f"Partage d'écran démarré (écran {idx}).", theme.SUCCESS)
            elif kind == "audio":
                if not caps_now.webrtc:
                    raise RuntimeError("WebRTC indisponible. Installez aiortc et av.")
                dev = mic_dropdown.value or None
                await media.add_microphone(device_id=dev)
                set_media_status("Micro démarré (si backend audio disponible).", theme.SUCCESS)
            elif kind == "offer":
                if not media.pc:
                    raise RuntimeError("Aucun média local. Démarrez caméra/écran/audio avant l'offre.")
                offer = await media.create_offer()
                await send_signal_message("offer", offer)
                set_media_status("Offre SDP envoyée.", theme.SUCCESS)
            else:
                raise RuntimeError(f"Action média inconnue: {kind}")
        except Exception as exc:
            logger.exception("Erreur démarrage média")
            set_media_status(f"Média indisponible: {exc}", theme.ERROR)
            notify(page, f"Média: {exc}", "warning")
        finally:
            state["media_busy"] = False
            safe_update()

    async def close_media(_e=None):
        media: WebRTCMediaSession | None = state.get("media")
        state["media"] = None
        state["local_preview_b64"] = None
        state["remote_preview_b64"] = None
        refresh_previews()
        if media is not None:
            try:
                await media.close()
            except Exception:
                logger.exception("Erreur fermeture média")
        set_media_status("Session média fermée.", theme.TEXT_MUTED)

    async def refresh_devices(_e=None):
        state["devices"] = list_media_devices()
        camera_dropdown.options = device_options("video_inputs")
        mic_dropdown.options = device_options("audio_inputs")
        screen_dropdown.options = device_options("screen_inputs")
        caps_now = detect_capabilities()
        missing = ", ".join(caps_now.missing) if caps_now.missing else "aucune"
        set_media_status(f"Périphériques rafraîchis. Dépendances manquantes: {missing}.", theme.TEXT_MUTED)

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
                            await handle_incoming_media_message(data)
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
        await refresh_devices()

    load_button = ft.OutlinedButton("Rejoindre / Rafraîchir", icon=ft.Icons.REFRESH, on_click=lambda e: page.run_task(on_load) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(on_load()))
    send_button = ft.Button("Envoyer signal manuel", icon=ft.Icons.SEND, on_click=lambda e: page.run_task(send_manual_signal, e) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(send_manual_signal(e)))

    def media_btn(label, icon, kind, disabled=False):
        return ft.OutlinedButton(label, icon=icon, disabled=disabled, on_click=lambda e, k=kind: page.run_task(start_media, k) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(start_media(k)))

    caps_text = "Capacités média détectées: " + ", ".join([k for k, v in caps.as_dict().items() if k != "missing" and v]) + "."
    if caps.missing:
        caps_text += " Manquantes: " + ", ".join(caps.missing) + "."
    caps_text += " Les permissions OS (caméra/micro/capture écran) doivent être accordées sur la machine cible."

    view = ft.Column(
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Text("Appels P2P locaux — signalisation et média WebRTC", size=22, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Text(
                "Signalisation SDP/ICE via REST + WebSocket (/api/v1/signaling/... et /ws/signaling/<room_id>/). "
                "Le média WebRTC (audio/vidéo/partage d'écran) utilise un backend optionnel aiortc/av/cv2/mss/sounddevice "
                "quand les dépendances et permissions matérielles sont disponibles sur la machine cible.",
                size=12, color=theme.TEXT_MUTED,
            ),
            ft.Container(bgcolor=theme.BG_CARD, border_radius=10, padding=pad_all(10), content=ft.Text(caps_text, size=11, color=theme.TEXT_MUTED)),
            ft.Row(controls=[room_field, load_button, status], vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
            ft.Container(
                bgcolor=theme.BG_INPUT,
                border_radius=theme.CARD_RADIUS,
                padding=pad_all(12),
                content=ft.Column([
                    ft.Text("Contrôles média WebRTC", size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT),
                    ft.Row([camera_dropdown, mic_dropdown, screen_dropdown, ft.OutlinedButton("Rafraîchir périphériques", icon=ft.Icons.DEVICES, on_click=lambda e: page.run_task(refresh_devices) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(refresh_devices()))], wrap=True),
                    ft.Row([
                        media_btn("Démarrer caméra", ft.Icons.VIDEOCAM, "camera", disabled=not (caps.webrtc and caps.video_capture)),
                        media_btn("Partager écran", ft.Icons.SCREEN_SHARE, "screen", disabled=not (caps.webrtc and caps.screen_capture)),
                        media_btn("Démarrer micro", ft.Icons.MIC, "audio", disabled=not caps.webrtc),
                        media_btn("Créer/Envoyer offre", ft.Icons.CALL_MADE, "offer", disabled=not caps.webrtc),
                        ft.OutlinedButton("Fermer média", icon=ft.Icons.CALL_END, on_click=lambda e: page.run_task(close_media) if hasattr(page, "run_task") else asyncio.get_running_loop().create_task(close_media())),
                    ], wrap=True),
                    media_status,
                    ft.Row([
                        ft.Column([ft.Text("Local", size=11, color=theme.TEXT_MUTED), ft.Stack([local_preview_placeholder, local_preview])], tight=True),
                        ft.Column([ft.Text("Distant", size=11, color=theme.TEXT_MUTED), ft.Stack([remote_preview_placeholder, remote_preview])], tight=True),
                    ], wrap=True),
                ], spacing=8),
            ),
            ft.Text("Journal de signalisation", size=14, weight=ft.FontWeight.BOLD, color=theme.TEXT),
            ft.Container(height=240, bgcolor=theme.BG_INPUT, border_radius=theme.CARD_RADIUS, padding=pad_all(12), content=messages_column),
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
        media = state.get("media")
        if media is not None:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(media.close())
                else:
                    loop.run_until_complete(media.close())
            except Exception:
                pass

    return view, dispose
