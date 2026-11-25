import unittest
from unittest.mock import Mock

import flet as ft

from services.webrtc_media_service import detect_capabilities, list_media_devices


class WebRTCMediaServiceTests(unittest.TestCase):
    def test_detect_capabilities_returns_expected_keys(self):
        caps = detect_capabilities()
        data = caps.as_dict()
        self.assertIn("webrtc", data)
        self.assertIn("audio_capture", data)
        self.assertIn("video_capture", data)
        self.assertIn("screen_capture", data)
        self.assertIn("local_preview", data)
        self.assertIn("missing", data)
        self.assertIsInstance(data["missing"], list)

    def test_list_media_devices_shape(self):
        devices = list_media_devices()
        self.assertIn("audio_inputs", devices)
        self.assertIn("audio_outputs", devices)
        self.assertIn("video_inputs", devices)
        self.assertIn("screen_inputs", devices)
        for key in ("audio_inputs", "audio_outputs", "video_inputs", "screen_inputs"):
            self.assertIsInstance(devices[key], list)


class CallsViewBuildTests(unittest.TestCase):
    def test_calls_view_builds_and_disposes(self):
        import asyncio
        from views.calls_view import build_calls_view
        from services.backend_client import BackendClient

        def _close_coro(coro, *args):
            if asyncio.iscoroutine(coro):
                coro.close()

        page = Mock()
        page.theme_mode = ft.ThemeMode.LIGHT
        page.run_task = Mock(side_effect=_close_coro)
        view, dispose = build_calls_view(page, BackendClient())
        self.assertIsInstance(view, ft.Column)
        self.assertTrue(callable(dispose))
        dispose()
