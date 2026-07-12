from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from cratesort.src.gui.overlays import _ov_alert, _ov_confirm

logger = logging.getLogger(__name__)

_ASSETS = Path(__file__).parent.parent.parent / 'assets'
_ICON_CHECKED   = str(_ASSETS / 'icons' / 'checkbox-checked.svg')
_ICON_UNCHECKED = str(_ASSETS / 'icons' / 'checkbox-unchecked.svg')

_BG     = '#1a1a1a'
_PANEL  = '#2F2F2F'
_CREAM  = '#f1e3c8'
_MUTED  = '#a89b85'
_SEP    = '#383838'
_TEAL   = '#428175'
_ORANGE = '#D17D34'
_DANGER = '#C75B5B'


class SettingsView(QWidget):
    """Settings panel — library management, maintenance utilities, about."""

    library_changed  = pyqtSignal(Path)   # user picked a new library path
    repair_requested = pyqtSignal()        # replay reorg logs → fix stale crate paths

    def __init__(self, app_settings: QSettings, parent=None):
        super().__init__(parent)
        self._settings      = app_settings
        self._library_path: Optional[Path] = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        content = QWidget()
        content.setStyleSheet(f'background: {_BG};')
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(60, 48, 60, 48)
        vbox.setSpacing(32)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

        vbox.addWidget(self._build_library_section())
        vbox.addWidget(self._build_maintenance_section())
        vbox.addWidget(self._build_about_section())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── Public API ────────────────────────────────────────────────────

    def load(self, library_path: Optional[Path]) -> None:
        self._library_path = library_path
        path_str = str(library_path) if library_path else 'No library loaded'
        self._path_label.setText(path_str)
        self._path_label.setStyleSheet(
            f'color: {_CREAM if library_path else _MUTED}; font-size: 13px; '
            f'background: transparent; border: none;'
        )

    # ── Section builders ──────────────────────────────────────────────

    def _build_library_section(self) -> QWidget:
        section = QWidget()
        vbox = QVBoxLayout(section)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        vbox.addWidget(self._eyebrow('YOUR LIBRARY'))

        card = self._card()
        card_vbox = QVBoxLayout(card)
        card_vbox.setContentsMargins(20, 18, 20, 18)
        card_vbox.setSpacing(16)

        # Current path row
        path_row = QHBoxLayout()
        path_row.setSpacing(12)

        path_col = QVBoxLayout()
        path_col.setSpacing(4)
        lbl = QLabel('Library Path')
        lbl.setStyleSheet(f'color: {_CREAM}; font-size: 13px; font-weight: 500; background: transparent; border: none;')
        self._path_label = QLabel('No library loaded')
        self._path_label.setStyleSheet(f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;')
        self._path_label.setWordWrap(True)
        path_col.addWidget(lbl)
        path_col.addWidget(self._path_label)
        path_row.addLayout(path_col, stretch=1)

        change_btn = self._action_btn('Change Library', _ORANGE, '#b8682a', '#9c5520')
        change_btn.clicked.connect(self._on_change_library)
        path_row.addWidget(change_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        card_vbox.addLayout(path_row)

        # Separator
        card_vbox.addWidget(self._sep())

        # Auto-load checkbox
        self._autoload_cb = QCheckBox('Auto-load last library on startup')
        self._autoload_cb.setChecked(
            self._settings.value('always_load_last', False, type=bool)
        )
        self._autoload_cb.setStyleSheet(
            f'QCheckBox {{ color: {_CREAM}; font-size: 13px; background: transparent; spacing: 8px; }}'
            f'QCheckBox::indicator {{ width: 16px; height: 16px; }}'
            f'QCheckBox::indicator:unchecked {{ image: url("{_ICON_UNCHECKED}"); }}'
            f'QCheckBox::indicator:checked   {{ image: url("{_ICON_CHECKED}");   }}'
        )
        self._autoload_cb.toggled.connect(
            lambda on: self._settings.setValue('always_load_last', on)
        )
        card_vbox.addWidget(self._autoload_cb)
        vbox.addWidget(card)
        return section

    def _build_maintenance_section(self) -> QWidget:
        section = QWidget()
        vbox = QVBoxLayout(section)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        vbox.addWidget(self._eyebrow('MAINTENANCE'))

        card = self._card()
        card_vbox = QVBoxLayout(card)
        card_vbox.setContentsMargins(20, 18, 20, 18)
        card_vbox.setSpacing(0)

        # Repair crate paths
        card_vbox.addLayout(self._setting_row(
            'Repair Crate Paths',
            'Sync .crate files with current file locations after a reorganization.',
            self._action_btn('Repair Paths', _TEAL, '#38706a', '#2d6358'),
            self._on_repair_crate_paths,
        ))

        card_vbox.addWidget(self._sep())

        # Reset column widths
        card_vbox.addLayout(self._setting_row(
            'Reset Track Table Columns',
            'Restore default column widths in the Crates and Library tabs.',
            self._action_btn('Reset Columns', '#3a3a3a', '#4a4a4a', '#2a2a2a', text_color=_CREAM),
            self._on_reset_columns,
        ))


        vbox.addWidget(card)
        return section

    def _build_about_section(self) -> QWidget:
        section = QWidget()
        vbox = QVBoxLayout(section)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        vbox.addWidget(self._eyebrow('ABOUT'))

        card = self._card()
        card_vbox = QVBoxLayout(card)
        card_vbox.setContentsMargins(20, 20, 20, 20)
        card_vbox.setSpacing(16)

        # App identity
        name_lbl = QLabel('CrateSort  v0.1.0')
        name_lbl.setStyleSheet(
            f'color: {_CREAM}; font-size: 15px; font-weight: 600; background: transparent; border: none;'
        )
        tagline = QLabel('"Get your shit together."')
        tagline.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; font-style: italic; background: transparent; border: none;'
        )
        card_vbox.addWidget(name_lbl)
        card_vbox.addWidget(tagline)

        card_vbox.addWidget(self._sep())

        # Workflow walkthrough
        how_lbl = QLabel('HOW TO USE CRATESORT')
        how_lbl.setStyleSheet(
            f'font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em; background: transparent; border: none;'
        )
        card_vbox.addWidget(how_lbl)
        card_vbox.addSpacing(4)

        steps = [
            ('1  Point to your library',
             'Go to Settings and choose the root folder of your music drive — the folder that '
             'contains your media files AND your _Serato_ folder side by side.'),
            ('2  Classify',
             'Open the Classification tab. CrateSort groups your tracks by artist and proposes a '
             'genre for each group. Review, adjust, and approve. You only need to do this once — '
             'new tracks are picked up on subsequent runs.'),
            ('3  Organize',
             'Open the Organize tab and click Plan Reorganization. Review the proposed folder '
             'moves and renames. When satisfied, execute. CrateSort copies, verifies, then '
             'deletes originals — and updates every Serato crate automatically.'),
            ('4  Build your crates',
             'Use the Crates tab to create, rename, and populate crates. Drag tracks in from '
             'the track panel. Drag crates to reorder them. CrateSort writes directly to '
             'Serato\'s .crate files — Serato picks up every change on next launch.'),
            ('5  Repeat as needed',
             'As your library grows, re-run Classification to catch new tracks, then re-run '
             'Organize. CrateSort only processes what\'s changed — files already in the right '
             'place are left alone.'),
        ]

        for step_title, step_body in steps:
            step_title_lbl = QLabel(step_title)
            step_title_lbl.setStyleSheet(
                f'color: {_ORANGE}; font-size: 12px; font-weight: 600; '
                f'background: transparent; border: none;'
            )
            step_body_lbl = QLabel(step_body)
            step_body_lbl.setStyleSheet(
                f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;'
            )
            step_body_lbl.setWordWrap(True)
            card_vbox.addWidget(step_title_lbl)
            card_vbox.addWidget(step_body_lbl)
            card_vbox.addSpacing(6)

        vbox.addWidget(card)
        return section

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_change_library(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, 'Select Music Library', str(self._library_path or Path.home()),
        )
        if not folder:
            return
        new_path = Path(folder)
        self._settings.setValue('library_path', str(new_path))
        self._settings.setValue('always_load_last', False)
        self.load(new_path)
        self.library_changed.emit(new_path)

    def _on_repair_crate_paths(self) -> None:
        if not self._library_path:
            self._warn('No library loaded.')
            return
        self.repair_requested.emit()

    def _on_reset_columns(self) -> None:
        from cratesort.src.gui.crate_manager import _SETTINGS_KEY
        self._settings.remove(_SETTINGS_KEY)
        self._info('Column widths reset. Take effect on next Crates tab visit.')

    def _on_clear_library_edits(self) -> None:
        if not self._library_path:
            self._warn('No library loaded.')
            return
        if not self._confirm(
            'Clear Library Edits',
            'This removes all manual track title, artist, and genre overrides.\n\n'
            'This cannot be undone. Continue?',
        ):
            return
        edits_file = self._library_path / '_CrateSort' / 'library_edits.json'
        if edits_file.exists():
            edits_file.unlink()
            self._info('Library edits cleared.')
        else:
            self._info('No library edits file found.')

    def _on_reset_classification(self) -> None:
        if not self._library_path:
            self._warn('No library loaded.')
            return
        if not self._confirm(
            'Reset Classification',
            'This removes the entire classification session. You will need to\n'
            'reclassify your library before you can reorganize.\n\n'
            'This cannot be undone. Continue?',
        ):
            return
        session_file = self._library_path / '_CrateSort' / 'classification_session.json'
        if session_file.exists():
            session_file.unlink()
            self._info('Classification session cleared.')
        else:
            self._info('No classification session found.')

    # ── Helper widgets ────────────────────────────────────────────────

    def _eyebrow(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f'font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em; background: transparent;')
        return lbl

    def _card(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border: 0.5px solid {_SEP}; border-radius: 10px; }}'
        )
        return f

    def _sep(self) -> QFrame:
        s = QFrame()
        s.setFixedHeight(1)
        s.setStyleSheet(f'background: {_SEP}; border: none;')
        return s

    def _action_btn(
        self, text: str, bg: str, hover: str, pressed: str,
        text_color: str = '#ffffff',
    ) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            f'QPushButton {{ background: {bg}; color: {text_color}; font-size: 13px; '
            f'font-weight: 600; border: none; border-radius: 6px; padding: 0 16px; }}'
            f'QPushButton:hover {{ background: {hover}; }}'
            f'QPushButton:pressed {{ background: {pressed}; }}'
        )
        return btn

    def _setting_row(
        self,
        title: str,
        description: str,
        btn: QPushButton,
        slot,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f'color: {_CREAM}; font-size: 13px; font-weight: 500; background: transparent; border: none;'
        )
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
        desc_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)
        text_col.addWidget(desc_lbl)
        row.addLayout(text_col, stretch=1)

        btn.clicked.connect(slot)
        row.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        return row

    def _confirm(self, title: str, message: str) -> bool:
        return _ov_confirm(self, title, message, confirm_text='Continue', confirm_danger=True)

    def _warn(self, message: str) -> None:
        _ov_alert(self, 'Settings', message)

    def _info(self, message: str) -> None:
        _ov_alert(self, 'Settings', message)
