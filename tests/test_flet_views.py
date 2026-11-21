import unittest
from unittest.mock import Mock

import flet as ft

from services.backend_client import BackendClient
from views.courses_view import build_courses_view
from views.settings_view import build_settings_view


class FletViewTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock()
        self.page.theme_mode = ft.ThemeMode.LIGHT

    def test_courses_view_builds_with_backend_client(self):
        view = build_courses_view(
            self.page,
            BackendClient(),
            on_open_settings=Mock(),
        )

        self.assertIsInstance(view, ft.Column)
        self.assertGreater(len(view.controls), 0)

    def test_settings_view_builds_login_form(self):
        view = build_settings_view(
            self.page,
            BackendClient(),
            on_connected=Mock(),
        )

        self.assertIsInstance(view, ft.Column)
        self.assertGreater(len(view.controls), 0)
