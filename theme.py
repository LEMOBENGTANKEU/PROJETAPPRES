"""
CampusShare - design system.
Centralise les couleurs, la typographie, les dimensions et le thème Flet
pour garantir une interface cohérente, moderne et professionnelle.
"""

import flet as ft

# ---------------------------------------------------------------- palette ---
PRIMARY = "#2563EB"
PRIMARY_DARK = "#1D4ED8"
PRIMARY_SOFT = "#EAF1FF"

SECONDARY = "#0F766E"
SECONDARY_SOFT = "#CCFBF1"

BG_APP = "#F8FAFC"
BG_CARD = "#FFFFFF"
BG_SIDEBAR = "#FFFFFF"
BG_HOVER = "#F1F5F9"
BG_INPUT = "#F1F5F9"

BORDER = "#E2E8F0"
BORDER_LIGHT = "#CBD5E1"

TEXT = "#1E293B"
TEXT_MUTED = "#64748B"
TEXT_LIGHT = "#94A3B8"

SUCCESS = "#16A34A"
SUCCESS_SOFT = "#ECFDF5"

WARNING = "#D97706"
WARNING_SOFT = "#FEF3C7"

ERROR = "#DC2626"
ERROR_SOFT = "#FEF2F2"

INFO_BG = "#EFF6FF"

# --------------------------------------------------------- dimensions -----
SIDEBAR_WIDTH = 260
HEADER_HEIGHT = 64
CARD_WIDTH = 272
CARD_RADIUS = 16
BUTTON_RADIUS = 12
CHIP_RADIUS = 20
INPUT_RADIUS = 10

GAP = 10
GAP_LG = 18
GAP_XL = 28

# ------------------------------------------------------ catégories ----------
# (fond, texte)
CATEGORY_COLORS = {
    "All Resources": (BG_CARD, TEXT),
    "Course Material (CM)": ("#DBEAFE", "#1D4ED8"),
    "Tutorials (TD)": ("#CCFBF1", "#0F766E"),
    "Practical Works (TP)": ("#E0E7FF", "#4338CA"),
    "Past Exams": ("#FEF3C7", "#B45309"),
    "Summary": ("#F1F5F9", "#475569"),
}

LEVELS = [
    ("Tous les niveaux", None),
    ("Software Engineering - L3", "L3 SE"),
    ("Networks - L2", "L2 Réseaux"),
    ("Mathematics - L1", "L1 Maths"),
]

APP_NAME = "CampusShare"
APP_VERSION = "1.0.0"


def app_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=PRIMARY)