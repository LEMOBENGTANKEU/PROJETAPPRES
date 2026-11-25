"""Optional WebRTC media service for Flet desktop client.

Provides device enumeration, local capture (mic/camera/screen), aiortc-based
peer connections, SDP/ICE helpers, and base64 frame previews for Flet Image.
All heavy media dependencies are optional; the service reports capabilities and
fails with explicit errors when a requested backend is unavailable.
"""
from __future__ import annotations

import asyncio
import base64
import fractions
import importlib
import io
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _optional_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


aiortc = _optional_import("aiortc")
aiortc_rtc = _optional_import("aiortc.rtcpeerconnection")  # older layouts; keep probe harmless
av = _optional_import("av")
cv2 = _optional_import("cv2")
mss = _optional_import("mss")
sounddevice = _optional_import("sounddevice")
numpy = _optional_import("numpy")


@dataclass
class MediaCapabilities:
    webrtc: bool = False
    audio_capture: bool = False
    video_capture: bool = False
    screen_capture: bool = False
    local_preview: bool = False
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "webrtc": self.webrtc,
            "audio_capture": self.audio_capture,
            "video_capture": self.video_capture,
            "screen_capture": self.screen_capture,
            "local_preview": self.local_preview,
            "missing": list(self.missing),
        }


def detect_capabilities() -> MediaCapabilities:
    missing: list[str] = []
    webrtc = aiortc is not None and av is not None
    audio_capture = sounddevice is not None
    video_capture = cv2 is not None
    screen_capture = mss is not None and numpy is not None
    local_preview = cv2 is not None or (mss is not None and numpy is not None)
    if aiortc is None:
        missing.append("aiortc")
    if av is None:
        missing.append("av")
    if cv2 is None:
        missing.append("opencv-python")
    if sounddevice is None:
        missing.append("sounddevice")
    if mss is None:
        missing.append("mss")
    if numpy is None:
        missing.append("numpy")
    return MediaCapabilities(
        webrtc=webrtc,
        audio_capture=audio_capture,
        video_capture=video_capture,
        screen_capture=screen_capture,
        local_preview=local_preview,
        missing=missing,
    )


def list_media_devices() -> dict[str, list[dict[str, Any]]]:
    devices = {"audio_inputs": [], "audio_outputs": [], "video_inputs": [], "screen_inputs": []}
    if sounddevice is not None:
        try:
            for idx, dev in enumerate(sounddevice.query_devices()):
                item = {
                    "id": str(idx),
                    "name": dev.get("name", f"Device {idx}"),
                    "max_input_channels": dev.get("max_input_channels", 0),
                    "max_output_channels": dev.get("max_output_channels", 0),
                }
                if int(dev.get("max_input_channels", 0)) > 0:
                    devices["audio_inputs"].append(item)
                if int(dev.get("max_output_channels", 0)) > 0:
                    devices["audio_outputs"].append(item)
        except Exception:
            logger.exception("Audio device enumeration failed")
    if cv2 is not None:
        # Probe common camera indices; cheap and avoids platform-specific APIs.
        for idx in range(4):
            cap = None
            try:
                cap = cv2.VideoCapture(idx)
                if cap is not None and cap.isOpened():
                    devices["video_inputs"].append({"id": str(idx), "name": f"Caméra {idx}"})
            except Exception:
                continue
            finally:
                try:
                    if cap is not None:
                        cap.release()
                except Exception:
                    pass
    if mss is not None:
        try:
            with mss.mss() as sct:
                for i, mon in enumerate(sct.monitors):
                    label = "Écran complet" if i == 0 else f"Écran {i}"
                    devices["screen_inputs"].append({"id": str(i), "name": label, "monitor": mon})
        except Exception:
            logger.exception("Screen enumeration failed")
    return devices


def _bgr_frame_to_base64_jpeg(frame) -> str | None:
    if cv2 is None or frame is None:
        return None
    try:
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if not ok:
            return None
        return base64.b64encode(buf.tobytes()).decode("ascii")
    except Exception:
        return None


class _BaseVideoTrack:
    kind = "video"

    async def recv(self):  # pragma: no cover - exercised only with aiortc runtime
        raise NotImplementedError


if aiortc is not None and av is not None:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate  # type: ignore
    from aiortc.mediastreams import MediaStreamTrack  # type: ignore

    class CameraVideoTrack(MediaStreamTrack):
        kind = "video"

        def __init__(self, device_index: int = 0):
            super().__init__()
            if cv2 is None:
                raise RuntimeError("opencv-python requis pour la capture caméra")
            self._cap = cv2.VideoCapture(device_index)
            if not self._cap.isOpened():
                self._cap.release()
                raise RuntimeError(f"Caméra {device_index} indisponible")
            self._start = time.time()
            self._pts = 0

        async def recv(self):
            pts, time_base = self._pts, fractions.Fraction(1, 30)
            self._pts += 1
            await asyncio.sleep(1 / 30)
            ok, frame = self._cap.read()
            if not ok or frame is None:
                frame = numpy.zeros((480, 640, 3), dtype=numpy.uint8) if numpy is not None else None
            if frame is None:
                raise RuntimeError("Frame caméra invalide")
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.pts = pts
            video_frame.time_base = time_base
            return video_frame

        def stop(self):
            try:
                if self._cap is not None:
                    self._cap.release()
            except Exception:
                pass
            super().stop()

    class ScreenVideoTrack(MediaStreamTrack):
        kind = "video"

        def __init__(self, monitor_index: int = 0):
            super().__init__()
            if mss is None or numpy is None:
                raise RuntimeError("mss et numpy requis pour le partage d'écran")
            self._sct = mss.mss()
            monitors = self._sct.monitors
            self._monitor = monitors[monitor_index] if 0 <= monitor_index < len(monitors) else monitors[0]
            self._pts = 0

        async def recv(self):
            pts, time_base = self._pts, fractions.Fraction(1, 15)
            self._pts += 1
            await asyncio.sleep(1 / 15)
            shot = self._sct.grab(self._monitor)
            frame = numpy.array(shot)[:, :, :3]
            frame = frame[:, :, ::-1]  # BGRA->BGR then to RGB below
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if cv2 is not None else frame[:, :, ::-1]
            video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.pts = pts
            video_frame.time_base = time_base
            return video_frame

        def stop(self):
            try:
                self._sct.close()
            except Exception:
                pass
            super().stop()

else:
    RTCPeerConnection = None  # type: ignore
    RTCSessionDescription = None  # type: ignore
    RTCIceCandidate = None  # type: ignore
    CameraVideoTrack = None  # type: ignore
    ScreenVideoTrack = None  # type: ignore


class WebRTCMediaSession:
    """Manages one room media session with optional aiortc backend."""

    def __init__(self, on_local_frame: Callable[[str, str], None] | None = None, on_remote_frame: Callable[[str, str], None] | None = None, on_state: Callable[[dict[str, Any]], None] | None = None):
        self.capabilities = detect_capabilities()
        self.on_local_frame = on_local_frame
        self.on_remote_frame = on_remote_frame
        self.on_state = on_state
        self.pc = None
        self.local_tracks: list[Any] = []
        self.remote_tracks: list[Any] = []
        self._preview_tasks: list[asyncio.Task] = []
        self._closed = False
        self.room_id: str | None = None
        self.mode: str = "idle"  # idle/audio/video/screen

    def _emit_state(self, **extra):
        if self.on_state is None:
            return
        payload = {"mode": self.mode, "capabilities": self.capabilities.as_dict(), **extra}
        try:
            self.on_state(payload)
        except Exception:
            logger.exception("State callback failed")

    def ensure_webrtc(self):
        if RTCPeerConnection is None or av is None:
            missing = ", ".join(self.capabilities.missing) or "aiortc/av"
            raise RuntimeError(
                "WebRTC média indisponible: dépendances manquantes (" + missing + "). "
                "Installez les dépendances média optionnelles sur une machine cible compatible."
            )

    async def create_peer_connection(self, on_ice_candidate: Callable[[dict[str, Any]], Any] | None = None):
        self.ensure_webrtc()
        if self.pc is not None:
            return self.pc
        pc = RTCPeerConnection()

        @pc.on("icecandidate")
        async def _on_ice(candidate):
            if candidate is None or on_ice_candidate is None:
                return
            try:
                payload = {
                    "candidate": candidate.candidate,
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                }
                result = on_ice_candidate(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception("ICE callback failed")

        @pc.on("track")
        async def _on_track(track):
            self.remote_tracks.append(track)
            self._emit_state(event="remote_track", kind=track.kind)
            if track.kind == "video":
                self._preview_tasks.append(asyncio.create_task(self._consume_remote_video(track)))
            if track.kind == "audio":
                self._preview_tasks.append(asyncio.create_task(self._consume_remote_audio(track)))

        @pc.on("connectionstatechange")
        async def _on_state_change():
            self._emit_state(event="connection_state", connection_state=getattr(pc, "connectionState", "unknown"))

        self.pc = pc
        self._emit_state(event="pc_created")
        return pc

    async def add_camera(self, device_index: int = 0):
        self.ensure_webrtc()
        if CameraVideoTrack is None:
            raise RuntimeError("Capture caméra indisponible (opencv-python/aiortc manquant)")
        track = CameraVideoTrack(device_index=device_index)
        self.local_tracks.append(track)
        assert self.pc is not None
        self.pc.addTrack(track)
        self.mode = "video"
        self._preview_tasks.append(asyncio.create_task(self._consume_local_video(track, label="camera")))
        self._emit_state(event="local_camera_added", device_index=device_index)
        return track

    async def add_screen(self, monitor_index: int = 0):
        self.ensure_webrtc()
        if ScreenVideoTrack is None:
            raise RuntimeError("Partage d'écran indisponible (mss/numpy/aiortc manquant)")
        track = ScreenVideoTrack(monitor_index=monitor_index)
        self.local_tracks.append(track)
        assert self.pc is not None
        self.pc.addTrack(track)
        self.mode = "screen"
        self._preview_tasks.append(asyncio.create_task(self._consume_local_video(track, label="screen")))
        self._emit_state(event="local_screen_added", monitor_index=monitor_index)
        return track

    async def add_microphone(self, device_id: str | None = None):
        self.ensure_webrtc()
        # aiortc does not ship a cross-platform microphone capture track; use
        # system default audio device through MediaPlayer when available.
        try:
            from aiortc.contrib.media import MediaPlayer  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Capture micro non disponible via aiortc sur cet environnement. "
                "Utilisez un backend audio compatible (ex. périphérique système/ffmpeg)."
            ) from exc
        # Best effort: on Windows, ffmpeg dshow name is required; expose explicit error.
        options = {}
        if device_id:
            options["audio_device"] = device_id
        try:
            player = MediaPlayer("default", format="dshow", options=options) if device_id else None
        except Exception:
            player = None
        if player is None or player.audio is None:
            raise RuntimeError(
                "Périphérique micro non ouvert. Sur Windows, configurez ffmpeg/dshow ou fournissez un backend audio compatible."
            )
        self.local_tracks.append(player.audio)
        assert self.pc is not None
        self.pc.addTrack(player.audio)
        if self.mode == "idle":
            self.mode = "audio"
        self._emit_state(event="local_audio_added", device_id=device_id)
        return player.audio

    async def create_offer(self) -> dict[str, Any]:
        self.ensure_webrtc()
        assert self.pc is not None
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        return {"sdp": self.pc.localDescription.sdp, "type": self.pc.localDescription.type}

    async def create_answer(self, remote_sdp: dict[str, Any]) -> dict[str, Any]:
        self.ensure_webrtc()
        assert self.pc is not None
        desc = RTCSessionDescription(sdp=remote_sdp["sdp"], type=remote_sdp["type"])
        await self.pc.setRemoteDescription(desc)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        return {"sdp": self.pc.localDescription.sdp, "type": self.pc.localDescription.type}

    async def apply_remote_description(self, remote_sdp: dict[str, Any]):
        self.ensure_webrtc()
        assert self.pc is not None
        desc = RTCSessionDescription(sdp=remote_sdp["sdp"], type=remote_sdp["type"])
        await self.pc.setRemoteDescription(desc)
        self._emit_state(event="remote_description", type=remote_sdp.get("type"))

    async def add_ice_candidate(self, candidate: dict[str, Any]):
        if self.pc is None or RTCIceCandidate is None:
            return
        try:
            ice = RTCIceCandidate(
                candidate=candidate.get("candidate"),
                sdpMid=candidate.get("sdpMid"),
                sdpMLineIndex=candidate.get("sdpMLineIndex"),
            )
            await self.pc.addIceCandidate(ice)
        except Exception:
            logger.exception("Failed to add ICE candidate")

    async def _consume_local_video(self, track, label: str):
        while not self._closed:
            try:
                frame = await track.recv()
                if self.on_local_frame is None:
                    continue
                img = frame.to_ndarray(format="bgr24")
                b64 = _bgr_frame_to_base64_jpeg(img)
                if b64:
                    self.on_local_frame(label, b64)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Local video preview ended for %s", label, exc_info=True)
                await asyncio.sleep(0.2)

    async def _consume_remote_video(self, track):
        while not self._closed:
            try:
                frame = await track.recv()
                if self.on_remote_frame is None:
                    continue
                img = frame.to_ndarray(format="bgr24")
                b64 = _bgr_frame_to_base64_jpeg(img)
                if b64:
                    self.on_remote_frame("remote", b64)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Remote video preview ended", exc_info=True)
                await asyncio.sleep(0.2)

    async def _consume_remote_audio(self, track):
        while not self._closed:
            try:
                await track.recv()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Remote audio ended", exc_info=True)
                await asyncio.sleep(0.2)

    async def close(self):
        self._closed = True
        for task in self._preview_tasks:
            task.cancel()
        for track in list(self.local_tracks) + list(self.remote_tracks):
            try:
                stop = getattr(track, "stop", None)
                if callable(stop):
                    stop()
            except Exception:
                pass
        if self.pc is not None:
            try:
                await self.pc.close()
            except Exception:
                pass
        self.pc = None
        self.local_tracks.clear()
        self.remote_tracks.clear()
        self.mode = "idle"
        self._emit_state(event="closed")
