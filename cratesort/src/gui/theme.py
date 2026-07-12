from __future__ import annotations

from PyQt6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Color palette
# Inverted CrateView brand: dark shell, warm cream text, orange/teal accents.
# ---------------------------------------------------------------------------
C = {
    "bg":           "#1a1a1a",   # primary background
    "bg_panel":     "#2F2F2F",   # cards, panels, sidebar
    "bg_input":     "#383838",   # text inputs, combos
    "bg_hover":     "#252525",   # hover state on dark surfaces
    "bg_alt":       "#222222",   # alternating row tint
    "border":       "#444444",   # separators and borders
    "border_focus": "#D17D34",   # focused input border

    "text":         "#f1e3c8",   # primary (Vintage White)
    "text_sec":     "#f2dbb3",   # secondary (Parchment Cream)
    "text_muted":   "#a89b85",   # muted / labels
    "text_disabled":"#5a5248",   # disabled text

    "orange":       "#D17D34",   # primary accent (Satsuma Orange)
    "orange_hover": "#be6e2c",   # orange hover — darker, not lighter
    "orange_press": "#a35e24",   # orange pressed/active
    "teal":         "#428175",   # secondary accent (Retro Teal)
    "teal_hover":   "#38706a",   # teal hover — darker, not lighter

    "success":      "#6B9E78",   # soft warm green
    "warning":      "#D4A04A",   # warm gold
    "error":        "#C75B5B",   # muted red
    "info":         "#428175",   # same as teal

    "selection":    "#D17D34",   # selected items
    "selection_bg": "#3d2a18",   # selection background (subtle orange)
}

# ---------------------------------------------------------------------------
# Stylesheet
# Charter is a macOS system font — referenced directly (no WOFF loading needed).
# Falls back to Georgia then generic serif.
# ---------------------------------------------------------------------------
STYLESHEET = f"""

/* ── Base ─────────────────────────────────────────────────────────── */
QMainWindow, QWidget, QDialog {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: "Helvetica Neue", Arial, Helvetica, sans-serif;
    font-size: 14px;
}}

/* ── Menu bar ─────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    border-bottom: 1px solid {C['border']};
    padding: 2px 0;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 3px;
}}
QMenuBar::item:selected {{
    background-color: {C['bg_hover']};
}}
QMenuBar::item:pressed {{
    background-color: {C['orange']};
    color: #fff;
}}
QMenu {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 24px 6px 16px;
}}
QMenu::item:selected {{
    background-color: {C['orange']};
    color: #fff;
    border-radius: 2px;
}}
QMenu::separator {{
    height: 1px;
    background: {C['border']};
    margin: 4px 8px;
}}

/* ── Status bar ───────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {C['bg_panel']};
    color: {C['text_muted']};
    border-top: 1px solid {C['border']};
    font-size: 11px;
    padding: 2px 16px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── Buttons ──────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {C['orange']};
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 0 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
    margin: 0px;
}}
QPushButton:hover {{
    background-color: {C['orange_hover']};
}}
QPushButton:pressed {{
    background-color: {C['orange_press']};
}}
QPushButton:disabled {{
    background-color: #2a2a2a;
    color: #666666;
}}

/* Secondary button — teal */
QPushButton[secondary="true"] {{
    background-color: {C['teal']};
    color: #ffffff;
    font-weight: 400;
    border-radius: 6px;
    border: 1px solid transparent;
    min-height: 36px;
    margin: 0px;
}}
QPushButton[secondary="true"]:hover {{
    background-color: {C['teal_hover']};
}}
QPushButton[secondary="true"]:pressed {{
    background-color: #2d6358;
}}
QPushButton[secondary="true"]:disabled {{
    background-color: #2a2a2a;
    color: #666666;
}}

/* Ghost / flat button */
QPushButton[flat="true"],
QPushButton[flat=true] {{
    background-color: transparent;
    color: {C['text']};
    border: 1px solid {C['border']};
    font-weight: 400;
    min-height: 36px;
    margin: 0px;
}}
QPushButton[flat="true"]:hover,
QPushButton[flat=true]:hover {{
    background-color: {C['bg_hover']};
    border-color: {C['text_muted']};
}}

/* Danger button */
QPushButton[danger="true"] {{
    background-color: {C['error']};
}}
QPushButton[danger="true"]:hover {{
    background-color: #b24c4c;
}}
QPushButton[danger="true"]:pressed {{
    background-color: #9c3b3b;
}}

/* ── Sidebar nav buttons ──────────────────────────────────────────── */
QPushButton#nav_btn {{
    background: transparent;
    color: {C['text_muted']};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    text-align: left;
    padding: 11px 16px;
    font-size: 14px;
    font-weight: 400;
    min-height: 40px;
}}
QPushButton#nav_btn:hover {{
    background-color: {C['bg_hover']};
    color: {C['text']};
}}
QPushButton#nav_btn:checked {{
    background-color: {C['bg_hover']};
    color: {C['text']};
    border-left: 6px solid {C['orange']};
    font-weight: 600;
}}

/* ── Input fields ─────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {C['bg_input']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {C['orange']};
    selection-color: #fff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {C['border_focus']};
    outline: none;
}}
QLineEdit:disabled {{
    color: {C['text_disabled']};
    background-color: {C['bg_panel']};
}}

/* ── Combo box ────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {C['bg_input']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 28px;
}}
QComboBox:focus {{
    border-color: {C['border_focus']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C['text_muted']};
    width: 0;
    height: 0;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    border: 1px solid {C['border']};
    selection-background-color: {C['orange']};
    selection-color: #fff;
    border-radius: 4px;
}}

/* ── Spin box ─────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {C['bg_input']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 5px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {C['border_focus']};
}}

/* ── Labels ───────────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {C['text']};
}}
QLabel[role="heading"] {{
    font-size: 20px;
    font-weight: 700;
    color: {C['text']};
    font-family: "Charter", "Georgia", serif;
}}
QLabel[role="subheading"] {{
    font-size: 14px;
    font-weight: 600;
    color: {C['text_sec']};
}}
QLabel[role="muted"] {{
    color: {C['text_muted']};
    font-size: 12px;
}}
QLabel[role="tagline"] {{
    color: {C['text_muted']};
    font-size: 15px;
    font-style: italic;
    font-family: "Charter", "Georgia", serif;
}}
QLabel[role="stat"] {{
    color: {C['orange']};
    font-size: 22px;
    font-weight: 700;
}}
QLabel[role="stat_label"] {{
    color: {C['text_muted']};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
QLabel[role="success"] {{
    color: {C['success']};
}}
QLabel[role="warning"] {{
    color: {C['warning']};
}}
QLabel[role="error"] {{
    color: {C['error']};
}}

/* ── Group box ────────────────────────────────────────────────────── */
QGroupBox {{
    background-color: {C['bg_panel']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px;
    font-weight: 600;
    color: {C['text_muted']};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: {C['text_muted']};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}

/* ── Frame / card ─────────────────────────────────────────────────── */
QFrame[role="card"] {{
    background-color: {C['bg_panel']};
    border: 1px solid {C['border']};
    border-radius: 6px;
}}
QFrame[role="sidebar"] {{
    background-color: {C['bg_panel']};
    border-right: 1px solid {C['border']};
    border-radius: 0px;
}}

/* ── Tables ───────────────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    gridline-color: {C['border']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    alternate-background-color: {C['bg_alt']};
    selection-background-color: {C['orange']};
    selection-color: #2F2F2F;
    outline: none;
}}
QTableWidget::item:selected,
QTableView::item:selected,
QTableWidget::item:selected:active,
QTableView::item:selected:active,
QTableWidget::item:selected:!active,
QTableView::item:selected:!active {{
    background-color: {C['orange']};
    color: #2F2F2F;
    border: none;
    outline: none;
}}
QTableWidget::item:hover:!selected,
QTableView::item:hover:!selected {{
    background-color: {C['bg_input']};
}}
QTableWidget::item:hover:selected,
QTableView::item:hover:selected {{
    background-color: {C['orange']};
    color: #2F2F2F;
}}

/* ── Tree / list ──────────────────────────────────────────────────── */
QTreeWidget, QTreeView, QListWidget, QListView {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    alternate-background-color: {C['bg_alt']};
    outline: none;
    /* Item 10: selection color at widget level */
    selection-background-color: {C['orange']};
    selection-color: #2F2F2F;
}}
QTreeWidget::item, QTreeView::item,
QListWidget::item, QListView::item {{
    padding: 4px 4px 4px 2px;
    border-radius: 0;
}}
QTreeWidget::item:selected, QTreeView::item:selected,
QListWidget::item:selected, QListView::item:selected {{
    border-radius: 0;
}}
/* Kill ALL system blue — every selection state. No border-left (item 2). */
QTreeWidget::item:selected,
QTreeView::item:selected,
QListWidget::item:selected,
QListView::item:selected,
QTreeWidget::item:selected:active,
QTreeView::item:selected:active,
QListWidget::item:selected:active,
QListView::item:selected:active,
QTreeWidget::item:selected:!active,
QTreeView::item:selected:!active,
QListWidget::item:selected:!active,
QListView::item:selected:!active {{
    background-color: {C['orange']};
    color: #2F2F2F;
    border: none;
    outline: none;
}}
QTreeWidget::item:hover:!selected,
QTreeView::item:hover:!selected,
QListWidget::item:hover:!selected,
QListView::item:hover:!selected {{
    background-color: {C['bg_input']};
}}
QTreeWidget::item:hover:selected,
QTreeView::item:hover:selected,
QListWidget::item:hover:selected,
QListView::item:hover:selected {{
    background-color: {C['orange']};
    color: #2F2F2F;
}}
/* Item 10: prevent blue on focus + branch indicators */
QTreeWidget:focus, QTreeView:focus {{
    outline: none;
    border: 1px solid {C['border']};
}}
QTreeWidget::item:focus, QTreeView::item:focus {{
    outline: none;
    border: none;
}}
QTreeView::branch, QTreeWidget::branch {{
    background: transparent;
    width: 14px;    /* constrain branch width to reduce dead space */
}}
QTreeView::branch:selected, QTreeWidget::branch:selected {{
    background: {C['orange']};
}}
QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings,
QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings {{
    background: transparent;
}}

/* ── Header ───────────────────────────────────────────────────────── */
QHeaderView {{
    background-color: {C['bg']};
}}
QHeaderView::section {{
    background-color: {C['bg']};
    color: {C['text_muted']};
    border: none;
    border-bottom: 1px solid {C['border']};
    border-right: 1px solid {C['border']};
    padding: 5px 8px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ── Tabs ─────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 4px;
    background-color: {C['bg_panel']};
}}
QTabBar::tab {{
    background-color: {C['bg']};
    color: {C['text_muted']};
    border: 1px solid {C['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 16px;
    margin-right: 2px;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    border-bottom: 2px solid {C['orange']};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background-color: {C['bg_hover']};
    color: {C['text']};
}}

/* ── Progress bar ─────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {C['bg_input']};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {C['orange']};
    border-radius: 4px;
}}

/* ── Scroll bars ──────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {C['bg']};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {C['bg']};
    height: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {C['border']};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {C['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Splitter ─────────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {C['border']};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── Check box / radio ────────────────────────────────────────────── */
QCheckBox, QRadioButton {{
    color: {C['text']};
    spacing: 8px;
    font-size: 14px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {C['border']};
    border-radius: 3px;
    background-color: {C['bg_input']};
}}
QCheckBox::indicator:checked {{
    background-color: {C['orange']};
    border-color: {C['orange']};
    /* Cream inner square as checkmark substitute (no image needed) */
    image: none;
}}
QCheckBox::indicator:hover {{
    border-color: {C['orange']};
}}
/* Tree widget item checkboxes — item 4: visible on BOTH dark and orange rows.
   Use neutral #666 border + cream fill so it contrasts against any background. */
QTreeWidget::indicator {{
    width: 15px;
    height: 15px;
    border: 1.5px solid #666666;
    border-radius: 3px;
    background: transparent;
}}
QTreeWidget::indicator:checked {{
    background-color: {C['text']};
    border-color: #666666;
}}
/* Fix 3: hover must NOT change indicator style — stays constant on any row bg */
QTreeWidget::indicator:hover,
QTreeWidget::indicator:checked:hover {{
    border: 1.5px solid #666666;
}}
QTreeWidget::indicator:checked:hover {{
    background-color: {C['text']};
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1.5px solid #666666;
    border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background-color: {C['orange']};
    border-color: {C['orange']};
}}
QCheckBox::indicator:hover {{
    border-color: {C['orange']};
}}
/* Remove focus rectangle — no blue outline anywhere */
QAbstractItemView::item:focus {{
    outline: none;
    border: none;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {C['border']};
    border-radius: 8px;
    background-color: {C['bg_input']};
}}
QRadioButton::indicator:checked {{
    background-color: {C['orange']};
    border-color: {C['orange']};
}}

/* ── Tool tip ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {C['bg_panel']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
}}

/* ── Message box / dialogs ────────────────────────────────────────── */
QMessageBox {{
    background-color: {C['bg']};
}}
QMessageBox QLabel {{
    color: {C['text']};
    font-size: 14px;
}}
QDialog {{
    background-color: {C['bg']};
}}

/* ── Stacked widget ───────────────────────────────────────────────── */
QStackedWidget {{
    background-color: {C['bg']};
}}

"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(STYLESHEET)
