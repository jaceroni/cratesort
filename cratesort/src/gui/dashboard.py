from __future__ import annotations

import json
import logging
import re
import sys
import time

logger = logging.getLogger(__name__)
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QEasingCurve, QPointF, QPropertyAnimation, QRectF,
    QSettings, QThread, QTimer, QVariantAnimation, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFontMetrics, QLinearGradient, QPainter, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGraphicsOpacityEffect,
    QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem,
    QPushButton, QRadioButton, QScrollArea, QSizePolicy, QSplitter,
    QSplitterHandle, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

try:
    from PyQt6.QtSvgWidgets import QSvgWidget
    _SVG_AVAILABLE = True
except ImportError:
    _SVG_AVAILABLE = False

sys.path.insert(0, '/opt/homebrew/lib/python3.14/site-packages')

from cratesort.src.utils.checkpoint import save_checkpoint, load_checkpoint, detect_changes
from cratesort.src.serato.database_reader import read_track_add_dates, read_track_metadata, _normalize_pfil_keys
from cratesort.src.gui.overlays import (
    _CrateSortDialog, _ov_alert, _create_dialog_layout, _AnimatedStatCardWidget,
)
from cratesort.src.gui.yt_import_dialog import _YTImportDialog
from cratesort.src.gui.convert_dialog import _ConvertDialog

_ASSETS         = Path(__file__).parent.parent.parent / 'assets'
_LOGO_SVG       = _ASSETS / 'logo' / 'cs-logo-mascot-stacked.svg'
_MASCOT_SVG     = _ASSETS / 'logo' / 'cs-logo-mascot-only.svg'
_ICON_CHECKED   = str(_ASSETS / 'icons' / 'checkbox-checked.svg')
_ICON_UNCHECKED = str(_ASSETS / 'icons' / 'checkbox-unchecked.svg')
_ICON_RADIO_ON  = str(_ASSETS / 'icons' / 'radio-checked.svg')
_ICON_RADIO_OFF = str(_ASSETS / 'icons' / 'radio-unchecked.svg')
_ORG, _APP = 'JWBC', 'CrateSort'

# Minimum time the scanning UI stays visible (ms)
_MIN_SCAN_DISPLAY_MS = 1500

# Minimum time the classification-prep phase stays visible (ms) — this phase
# is pure in-memory work and can finish almost instantly on a small library,
# so a small floor keeps the stat cards visibly animating rather than flashing.
_MIN_CLASSIFY_DISPLAY_MS = 1000

_GRIP_COLOR       = '#a89b85'
_GRIP_COLOR_HOVER = '#d4c4ae'


# ---------------------------------------------------------------------------
# Custom splitter with visible grip handle (fixes 12 + 13)
# ---------------------------------------------------------------------------

class _GripHandle(QSplitterHandle):
    """Splitter handle that paints three horizontal lines as a drag grip."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self._hovered = False
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(_GRIP_COLOR_HOVER if self._hovered else _GRIP_COLOR)
        pen = QPen(color)
        pen.setWidthF(1.5)
        painter.setPen(pen)
        cx = self.width() // 2
        cy = self.height() // 2
        for y_off in (-4, 0, 4):
            painter.drawLine(cx - 14, cy + y_off, cx + 14, cy + y_off)
        painter.end()


class _GripSplitter(QSplitter):
    """QSplitter that uses _GripHandle and exposes a taller drag target."""

    def __init__(self, orientation=Qt.Orientation.Vertical, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(18)   # comfortable drag area height
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return _GripHandle(self.orientation(), self)


class _ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _ScanWorker(QThread):
    progress = pyqtSignal(int, str)    # (files_found, current_dir_name)
    finished = pyqtSignal(object, object)  # (inventory, summary)
    errored  = pyqtSignal(str)

    def __init__(self, library_path: Path, parent=None):
        super().__init__(parent)
        self._path = library_path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            from cratesort.src.core.scanner import LibraryScanner
            scanner = LibraryScanner(
                self._path,
                progress_callback=self._on_progress,
            )
            inventory, summary = scanner.scan()
            if not self._cancelled:
                self.finished.emit(inventory, summary)
        except Exception as exc:
            if not self._cancelled:
                self.errored.emit(str(exc))

    def _on_progress(self, count: int, dir_name: str) -> None:
        if not self._cancelled:
            self.progress.emit(count, dir_name)


_SVG_VIEWBOX_RE = re.compile(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"')


def _svg_aspect_ratio(svg_bytes: bytes) -> float:
    """Width/height ratio from an SVG's viewBox, so icons can be scaled to a
    fixed height without stretching/squishing non-square artwork. Falls back
    to 1.0 (square) if no viewBox is found."""
    match = _SVG_VIEWBOX_RE.search(svg_bytes.decode('utf-8', errors='ignore'))
    if not match:
        return 1.0
    w, h = float(match.group(1)), float(match.group(2))
    return w / h if h else 1.0


# ---------------------------------------------------------------------------
# Icon action card — text top-left, large muted icon top-right that lights up
# on hover. Same treatment as _WorkflowCard, sized for a compact row.
# ---------------------------------------------------------------------------

class _IconActionCard(QFrame):
    _ICON_DIM    = '#2a2a2a'
    _ICON_ACTIVE = '#D17D34'

    def __init__(
        self, title: str, desc: str, callback, icon_path,
        rest_style: str, hover_style: str, icon_size: int = 60, parent=None,
    ):
        super().__init__(parent)
        self._callback    = callback
        self._rest_style  = rest_style
        self._hover_style = hover_style
        self._icon_svg: QSvgWidget | None = None
        self._svg_bytes: bytes | None = None

        self.setStyleSheet(rest_style)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 14, 14)
        row.setSpacing(8)

        col = QVBoxLayout()
        col.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            'font-size: 13px; font-weight: 500; color: #D17D34; '
            'background: transparent; border: none;'
        )
        col.addWidget(title_lbl)

        desc_lbl = QLabel()
        desc_lbl.setTextFormat(Qt.TextFormat.RichText)
        desc_lbl.setText(f'<div style="line-height: 16.5px;">{desc}</div>')
        desc_lbl.setStyleSheet(
            'font-size: 12px; color: #a89b85; background: transparent; border: none;'
        )
        desc_lbl.setWordWrap(True)
        col.addWidget(desc_lbl)
        col.addStretch()

        row.addLayout(col, stretch=1)

        if _SVG_AVAILABLE and icon_path and Path(icon_path).exists():
            try:
                self._svg_bytes = Path(icon_path).read_bytes()
                aspect = _svg_aspect_ratio(self._svg_bytes)
                self._icon_svg = QSvgWidget()
                # Lock height across all cards; derive width from each icon's own
                # aspect ratio so nothing gets stretched/squished to fit a square.
                self._icon_svg.setFixedSize(round(icon_size * aspect), icon_size)
                self._icon_svg.setStyleSheet('background: transparent;')
                self._icon_svg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self._load_icon_color(self._ICON_DIM)
                row.addWidget(self._icon_svg, alignment=Qt.AlignmentFlag.AlignTop)
            except Exception:
                pass

    def _load_icon_color(self, color: str) -> None:
        if self._icon_svg and self._svg_bytes:
            from PyQt6.QtCore import QByteArray
            colored = self._svg_bytes.decode('utf-8').replace(
                '#d17d34', color
            ).replace('#D17D34', color)
            self._icon_svg.load(QByteArray(colored.encode('utf-8')))

    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)
        self._load_icon_color(self._ICON_ACTIVE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._rest_style)
        self._load_icon_color(self._ICON_DIM)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._callback:
            self._callback()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Animated stat card — count-up on load, click to replay
# ---------------------------------------------------------------------------

class _AnimatedStatCard(QFrame):
    def __init__(self, target: int, suffix: str, label: str, parent=None):
        super().__init__(parent)
        self._target   = target
        self._suffix   = suffix
        self._current  = 0.0
        self._elapsed  = 0
        self._duration = 1400

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(
            'QFrame { background-color: #2F2F2F; border: 1px solid #3a3a3a; border-radius: 10px; }'
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        col = QVBoxLayout(self)
        col.setContentsMargins(14, 16, 14, 16)
        col.setSpacing(4)

        self._num_label = QLabel('0' + suffix)
        self._num_label.setStyleSheet(
            'font-size: 26px; font-weight: 500; color: #f1e3c8; '
            'background: transparent; border: none;'
        )
        col.addWidget(self._num_label)

        stat_lbl = QLabel(label.upper())
        stat_lbl.setStyleSheet(
            'font-size: 11px; color: #7a6a55; letter-spacing: 0.08em; '
            'background: transparent; border: none;'
        )
        col.addWidget(stat_lbl)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start_animation(self, duration_ms: int = 1400):
        self._duration = duration_ms
        self._elapsed  = 0
        self._current  = 0.0
        self._num_label.setText('0' + self._suffix)
        self._timer.start()

    def _tick(self):
        self._elapsed += 16
        t = min(self._elapsed / self._duration, 1.0)
        eased = 1.0 - (1.0 - t) ** 3
        self._current = eased * self._target
        self._num_label.setText(f'{int(self._current):,}{self._suffix}')
        if t >= 1.0:
            self._timer.stop()
            self._num_label.setText(f'{self._target:,}{self._suffix}')

    def mousePressEvent(self, event):
        self.start_animation(1400)


# ---------------------------------------------------------------------------
# Workflow card — step number turns orange on hover
# ---------------------------------------------------------------------------

class _WorkflowCard(QFrame):
    _STYLE_REST     = 'QFrame { background-color: #2F2F2F; border: 1px solid #3a3a3a; border-radius: 10px; }'
    _STYLE_HOVER    = 'QFrame { background-color: #353028; border: 1px solid #D17D34; border-radius: 10px; }'
    _STYLE_DISABLED = 'QFrame { background-color: #262626; border: 1px solid #333333; border-radius: 10px; }'
    _ICON_DIM      = '#2a2a2a'
    _ICON_ACTIVE   = '#D17D34'
    _ICON_DISABLED = '#3a3a3a'

    def __init__(self, _step: str, title: str, desc: str, callback, icon_path=None, highlighted: bool = False, footer: str = None, parent=None):
        super().__init__(parent)
        self._callback  = callback
        self._icon_path = icon_path
        self._icon_svg: QSvgWidget | None = None
        self._svg_bytes: bytes | None = None
        self._disabled  = False

        if highlighted:
            self.style_rest = 'QFrame { background-color: #1a2e2b; border: 2px solid #428175; border-radius: 10px; }'
            self.icon_dim   = '#428175'
        else:
            self.style_rest = self._STYLE_REST
            self.icon_dim   = self._ICON_DIM

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(230)
        self.setStyleSheet(self.style_rest)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Outer column: text/icon row on top, full-width footer at the bottom
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 14, 14, 14)
        outer_layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(0)

        col = QVBoxLayout()
        col.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            'font-size: 16px; font-weight: 500; color: #D17D34; '
            'background: transparent; border: none;'
        )
        col.addWidget(title_lbl)

        desc_lbl = QLabel()
        desc_lbl.setTextFormat(Qt.TextFormat.RichText)
        desc_lbl.setText(f'<div style="line-height: 16.5px;">{desc}</div>')
        desc_lbl.setStyleSheet(
            'font-size: 12px; color: #a89b85; background: transparent; border: none;'
        )
        desc_lbl.setWordWrap(True)
        col.addWidget(desc_lbl)
        col.addStretch()

        row.addLayout(col, stretch=1)

        # Large icon — anchored top-right, dimmed at rest, orange on hover
        if _SVG_AVAILABLE and icon_path and Path(icon_path).exists():
            try:
                self._svg_bytes = Path(icon_path).read_bytes()
                self._icon_svg = QSvgWidget()
                self._icon_svg.setFixedSize(100, 100)
                self._icon_svg.setStyleSheet('background: transparent;')
                self._icon_svg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self._load_icon_color(self.icon_dim)
                row.addWidget(self._icon_svg, alignment=Qt.AlignmentFlag.AlignTop)
            except Exception:
                pass

        outer_layout.addLayout(row)
        outer_layout.addStretch()

        if footer:
            footer_lbl = QLabel()
            footer_lbl.setTextFormat(Qt.TextFormat.RichText)
            footer_lbl.setText(f'<div style="line-height: 16.5px;">{footer}</div>')
            footer_lbl.setStyleSheet(
                'font-size: 12px; color: #5a5a5a; background: transparent; border: none;'
            )
            footer_lbl.setWordWrap(True)
            outer_layout.addWidget(footer_lbl)

    def _load_icon_color(self, color: str) -> None:
        if self._icon_svg and self._svg_bytes:
            from PyQt6.QtCore import QByteArray
            colored = self._svg_bytes.decode('utf-8').replace(
                '#d17d34', color
            ).replace('#D17D34', color)
            self._icon_svg.load(QByteArray(colored.encode('utf-8')))

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = disabled
        if disabled:
            self.setStyleSheet(self._STYLE_DISABLED)
            self._load_icon_color(self._ICON_DISABLED)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setStyleSheet(self.style_rest)
            self._load_icon_color(self.icon_dim)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        if not self._disabled:
            self.setStyleSheet(self._STYLE_HOVER)
            self._load_icon_color(self._ICON_ACTIVE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._disabled:
            self.setStyleSheet(self.style_rest)
            self._load_icon_color(self.icon_dim)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._disabled:
            return
        if self._callback:
            self._callback()


# ---------------------------------------------------------------------------
# Change Review Dialog
# ---------------------------------------------------------------------------

class _ChangeReviewDialog(_CrateSortDialog):
    """
    Review Serato library changes detected since the last session.

    Each row shows the change description, when it happened, and a
    two-option radio pair — exactly one is selected per row, first
    option selected by default. The option text is per-change-type
    (see _RADIO_LABELS) and states the concrete resulting outcome for
    the crate/tracks themselves — e.g. "Leave Removed" / "Restore
    Crate" for a crate removal — rather than a generic "Keep"/"Undo"
    (which reads ambiguously: keep the *crate*, or keep the *removal*?)
    or "Approve"/"Remove" (which both sound destructive next to a
    removal-type change). Selecting the second option marks that change
    as pending revert. No disk writes happen until the user clicks
    Apply & Continue — at that point all pending reverts are executed
    and the checkpoint is saved. Clicking Cancel leaves the checkpoint
    unchanged and the sync banner remains.
    """

    _TEAL_TYPES   = {'crate_added', 'tracks_added', 'renamed', 'added'}
    _ORANGE_TYPES = {'crate_removed', 'tracks_removed', 'removed'}

    # Per-row option text describing the actual resulting state, not an
    # abstract "keep/undo the change" — "Keep"/"Undo" alone read as
    # ambiguous next to a *removal* ("keep the removal, or keep the
    # crate?"). Each pair below states outcomes directly: what happens
    # to the crate/tracks themselves if this option is selected.
    _RADIO_LABELS: dict[str, tuple[str, str]] = {
        'crate_added':    ('Keep Crate',    'Delete Crate'),
        'crate_removed':  ('Leave Removed', 'Restore Crate'),
        'renamed':        ('Keep New Name', 'Revert Name'),
        'tracks_added':   ('Keep Tracks',   'Remove Tracks'),
        'tracks_removed': ('Leave Removed', 'Restore Tracks'),
    }
    _DEFAULT_RADIO_LABELS = ('Keep', 'Undo')

    def __init__(
        self,
        changes: list[dict],
        serato_dir: Optional[Path],
        current_crates: dict,
        checkpoint_timestamp: Optional[datetime],
        parent=None,
    ):
        super().__init__(parent)
        self.setMinimumWidth(540)

        self._serato_dir         = serato_dir
        self._updated_crates     = dict(current_crates)
        self._pending_reverts:   set[int] = set()   # indices into self._changes marked for removal
        self._changes            = list(changes)

        # Use the standard dialog layout builder with Orange accent (selection/confirm)
        layout = _create_dialog_layout(self)

        title = QLabel('Serato Crate Changes Detected')
        title.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(title)
        layout.addSpacing(6)

        if checkpoint_timestamp:
            date_str = checkpoint_timestamp.strftime('%m/%d/%y')
            time_str = checkpoint_timestamp.strftime('%I:%M %p').lstrip('0')
            desc_text = (
                f'Things have changed since your last session on {date_str} at {time_str}. '
                'Please review the changes below before your next session:'
            )
        else:
            desc_text = (
                'Things have changed since your last CrateSort session. '
                'Please review the changes below before your next session:'
            )
        desc = QLabel()
        desc.setTextFormat(Qt.TextFormat.RichText)
        desc.setText(f'<div style="line-height: 145%;">{desc_text}</div>')
        desc.setStyleSheet('color: #d5c7ad; font-size: 13px; background: transparent; border: none;')
        desc.setWordWrap(True)
        layout.addWidget(desc)
        layout.addSpacing(12)

        # ── Change rows ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        rows_container = QWidget()
        rows_container.setStyleSheet('background: transparent;')
        self._rows_layout = QVBoxLayout(rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        scroll.setWidget(rows_container)
        # Cap the visible list so it scrolls past ~6 rows instead of forcing
        # the dialog to grow unbounded; below the cap, the dialog shrinks to
        # fit the actual number of changes (no leftover blank space).
        scroll.setMaximumHeight(300)
        layout.addWidget(scroll)

        self._row_frames: list[QFrame] = []
        for i, change in enumerate(self._changes):
            self._rows_layout.addWidget(self._build_row(i, change))

        self._rows_layout.addStretch()

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._cancel_btn = QPushButton('Cancel')
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
            'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
        )
        self._cancel_btn.clicked.connect(self.reject)

        self._sync_btn = QPushButton('Apply && Continue')
        self._sync_btn.setFixedHeight(36)
        self._sync_btn.setStyleSheet(
            'QPushButton { background-color: #aa6326; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #925521; }'
            'QPushButton:pressed { background-color: #7e491c; }'
        )
        self._sync_btn.clicked.connect(self._on_sync)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._sync_btn)
        layout.addLayout(btn_row)

    # ── Row builder ───────────────────────────────────────────────────────────

    def _build_row(self, idx: int, change: dict) -> QFrame:
        ctype = change.get('type', '')
        dot_color = (
            '#428175' if ctype in self._TEAL_TYPES
            else '#D17D34' if ctype in self._ORANGE_TYPES
            else '#a89b85'
        )

        frame = QFrame()
        frame.setStyleSheet(
            'QFrame { background: #2a2a2a; border: none; border-radius: 4px; }'
        )
        h = QHBoxLayout(frame)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(10)

        dot = QLabel('●')
        dot.setStyleSheet(
            f'color: {dot_color}; font-size: 8px; background: transparent; border: none;'
        )
        dot.setFixedWidth(14)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(dot)

        desc_lbl = QLabel(change.get('description', ''))
        desc_lbl.setStyleSheet('color: #f1e3c8; font-size: 13px; background: transparent; border: none;')
        desc_lbl.setWordWrap(False)
        h.addWidget(desc_lbl, stretch=1)

        mtime: Optional[datetime] = change.get('mtime')
        time_lbl = QLabel(self._fmt_time(mtime))
        time_lbl.setStyleSheet('color: #5a5a5a; font-size: 11px; background: transparent; border: none;')
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(time_lbl)

        can_revert = self._can_revert(change)
        keep_text, undo_text = self._RADIO_LABELS.get(ctype, self._DEFAULT_RADIO_LABELS)

        radio_group = QButtonGroup(frame)
        radio_group.setExclusive(True)

        keep_radio = QRadioButton(keep_text)
        keep_radio.setCursor(Qt.CursorShape.PointingHandCursor)
        keep_radio.setStyleSheet(self._RADIO_STYLE)
        radio_group.addButton(keep_radio)
        h.addWidget(keep_radio)

        undo_radio: Optional[QRadioButton] = None
        if can_revert:
            undo_radio = QRadioButton(undo_text)
            undo_radio.setCursor(Qt.CursorShape.PointingHandCursor)
            undo_radio.setStyleSheet(self._RADIO_STYLE)
            radio_group.addButton(undo_radio)
            h.addWidget(undo_radio)
        else:
            keep_radio.setEnabled(False)

        keep_radio.setChecked(True)

        if undo_radio is not None:
            undo_radio.toggled.connect(lambda checked, i=idx: self._on_undo_toggled(i, checked))

        self._row_frames.append(frame)
        return frame

    # ── Keep / Undo interaction ──────────────────────────────────────────────

    _RADIO_STYLE = (
        'QRadioButton { color: #a89b85; font-size: 12px; font-weight: 600; '
        'background: transparent; border: none; spacing: 6px; padding: 0 4px; }'
        'QRadioButton::indicator { width: 16px; height: 16px; }'
        f'QRadioButton::indicator:unchecked {{ image: url("{_ICON_RADIO_OFF}"); }}'
        f'QRadioButton::indicator:checked   {{ image: url("{_ICON_RADIO_ON}");  }}'
        'QRadioButton:checked { color: #f1e3c8; }'
        'QRadioButton:disabled { color: #5a5a5a; }'
    )

    def _on_undo_toggled(self, idx: int, checked: bool) -> None:
        if checked:
            self._pending_reverts.add(idx)
        else:
            self._pending_reverts.discard(idx)

    # ── Sync action ───────────────────────────────────────────────────────────

    def _on_sync(self) -> None:
        failed: list[str] = []
        for idx in self._pending_reverts:
            change = self._changes[idx]
            try:
                self._execute_revert(change)
            except Exception as exc:
                logger.warning("Revert failed for %s: %s", change.get('type'), exc)
                failed.append(f'• {change.get("description", "unknown")} — {exc}')

        if failed:
            _ov_alert(
                self,
                'Revert Failed',
                'The following changes could not be reverted:\n\n'
                + '\n'.join(failed)
                + '\n\nThe sync was not saved. Please try again or contact support.',
            )
            return  # don't save checkpoint — user can retry

        if self._serato_dir:
            save_checkpoint(str(self._serato_dir), self._updated_crates)

        self.accept()

    def _execute_revert(self, change: dict) -> None:
        ctype      = change.get('type', '')
        crate_path = change.get('crate_path', '')
        prev_tracks = change.get('prev_tracks', [])

        if ctype == 'crate_added':
            p = Path(crate_path)
            if p.exists():
                p.unlink()
            self._updated_crates.pop(crate_path, None)

        elif ctype == 'crate_removed':
            self._write_crate(crate_path, prev_tracks)
            self._updated_crates[crate_path] = prev_tracks

        elif ctype == 'renamed':
            # Delete the new (renamed) file, restore the old name with old tracks
            new_path = Path(crate_path)
            if new_path.exists():
                new_path.unlink()
            self._updated_crates.pop(crate_path, None)
            old_path = change.get('old_crate_path', '')
            if old_path:
                self._write_crate(old_path, prev_tracks)
                self._updated_crates[old_path] = prev_tracks

        elif ctype in ('tracks_added', 'tracks_removed'):
            self._write_crate(crate_path, prev_tracks)
            self._updated_crates[crate_path] = prev_tracks

    def _write_crate(self, crate_path_str: str, track_paths: list[str]) -> None:
        import sys as _sys
        _sys.path.insert(0, '/opt/homebrew/lib/python3.14/site-packages')
        from serato_crate.crate_file import write_crate_file
        p = Path(crate_path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [('otrk', [('ptrk', t)]) for t in track_paths]
        tmp = p.with_suffix(p.suffix + '.tmp')
        write_crate_file(tmp, data)
        tmp.replace(p)
        logger.info("Reverted crate: %s (%d tracks)", p.name, len(track_paths))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _can_revert(self, change: dict) -> bool:
        """Return True if this change type can be reverted."""
        ctype = change.get('type', '')
        if ctype in ('crate_added', 'crate_removed'):
            return True   # crate_added: delete the file; crate_removed: recreate (even if empty)
        return bool(change.get('prev_tracks'))   # track changes need the old track list to restore

    @staticmethod
    def _fmt_time(dt: Optional[datetime]) -> str:
        if dt is None:
            return ''
        now = datetime.now()
        if dt.date() == now.date():
            return f'Today at {dt.strftime("%I:%M %p").lstrip("0")}'
        if dt.year == now.year:
            return f'{dt.strftime("%b")} {dt.day} at {dt.strftime("%I:%M %p").lstrip("0")}'
        return f'{dt.strftime("%b")} {dt.day}, {dt.year}'


# ---------------------------------------------------------------------------
# _ScanActivityBeam — bounded sweeping "still working" cue for the scan banner
# ---------------------------------------------------------------------------

class _ScanActivityBeam(QWidget):
    """A soft comet of light that bounces back and forth in a fixed-width
    track, drawn as a plain symmetric teal->gold->teal gradient — no image
    asset, no directional head/tail, no off-screen phases.

    NOT a progress bar and must never be read as one: it never grows, never
    reaches 100%, and always returns to where it started. That's what keeps
    it compliant with the no-fake-progress rule — a real progress bar claims
    to measure completion (`setRange(0, total)`); this only claims "still
    alive," the same job the pulsing mascot already does, just filling the
    dead horizontal space next to it. Track height (12px) and motion are
    deliberately distinct from the locked determinate-progress-bar spec
    (8px, hard-edged teal fill) so it can never be mistaken for one.

    Deliberately simple: one continuous ping-pong animation, comet always
    fully within the track, symmetric coloring so there's no "head" or
    "tail" whose orientation could look wrong on either pass.
    """

    _TRACK_H = 6    # halved again per feedback (was 12)
    _WIDGET_H = 10  # halved again per feedback (was 20)
    _CYCLE_MS = 1800

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self._WIDGET_H)
        self._pos = 0.0

        curve = QEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(self._CYCLE_MS)
        self._anim.setStartValue(0.0)
        self._anim.setKeyValueAt(0.5, 1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(curve)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._on_value_changed)

    def start(self) -> None:
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()

    def _on_value_changed(self, value: float) -> None:
        self._pos = value
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        track_y = (self._WIDGET_H - self._TRACK_H) / 2
        track_rect = rect.adjusted(0, int(track_y), 0, -int(track_y))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#383838'))
        painter.drawRoundedRect(track_rect, 1.5, 1.5)

        w = rect.width()
        if w <= 0:
            painter.end()
            return
        comet_w = max(16, int(w * 0.17))   # halved per feedback (was 32 / 0.34)
        cx = self._pos * max(0, w - comet_w)

        # Dims toward each end, brightest at center — a parabola in `_pos`
        # (0 at both ends, 1 at pos=0.5) applied as overall opacity to just
        # the comet + glow, not the track background beneath them.
        fade = 4.0 * self._pos * (1.0 - self._pos)
        painter.setOpacity(max(0.0, min(1.0, fade)))

        gradient = QLinearGradient(cx, 0, cx + comet_w, 0)
        gradient.setColorAt(0.00, QColor(66, 129, 117, 0))
        gradient.setColorAt(0.18, QColor(80, 158, 143, 190))
        gradient.setColorAt(0.35, QColor(120, 178, 150, 235))
        gradient.setColorAt(0.5,  QColor(255, 221, 158, 255))
        gradient.setColorAt(0.65, QColor(120, 178, 150, 235))
        gradient.setColorAt(0.82, QColor(80, 158, 143, 190))
        gradient.setColorAt(1.00, QColor(66, 129, 117, 0))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(QRectF(cx, track_y, comet_w, self._TRACK_H), 1.5, 1.5)

        cy = self._WIDGET_H / 2.0
        peak_x = cx + comet_w / 2.0
        # Hard-capped so the glow's DIAMETER can never exceed the widget's
        # own height — a prior version scaled this off track height alone
        # (`_TRACK_H * 0.9`) and still came out taller than the widget
        # (21.6px circle in a 20px-tall widget), so it was still getting a
        # hard horizontal cutoff top and bottom, just a smaller one. This
        # cap makes that geometrically impossible regardless of what
        # _TRACK_H/_WIDGET_H get tuned to later.
        glow_r = min(self._TRACK_H * 0.9, self._WIDGET_H / 2.0 - 1.0)
        glow = QRadialGradient(peak_x, cy, glow_r)
        glow.setColorAt(0.00, QColor(255, 232, 185, 130))
        glow.setColorAt(0.25, QColor(255, 220, 170, 90))
        glow.setColorAt(0.5,  QColor(255, 210, 155, 50))
        glow.setColorAt(0.75, QColor(255, 205, 150, 20))
        glow.setColorAt(1.00, QColor(255, 205, 150, 0))
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(peak_x, cy), glow_r, glow_r)
        painter.end()


# ---------------------------------------------------------------------------
# Dashboard widget
# ---------------------------------------------------------------------------

class DashboardWidget(QWidget):
    """
    Three-state widget:
      0 — No library configured  (welcome / directory picker)
      1 — Scanning               (progress + background thread)
      2 — Scan complete          (stats dashboard)
    """

    library_path_changed      = pyqtSignal(Path)
    scan_started              = pyqtSignal()
    scan_finished             = pyqtSignal()
    classify_requested        = pyqtSignal()
    crates_requested          = pyqtSignal()
    organize_requested        = pyqtSignal()
    duplicates_requested      = pyqtSignal()   # user clicked the duplicate banner
    status_message            = pyqtSignal(str, str)  # (message, state)

    def __init__(self, parent=None, saved_path: Optional[Path] = None):
        super().__init__(parent)
        self._settings      = QSettings(_ORG, _APP)
        self._library_path: Path | None = None
        self._worker: _ScanWorker | None = None
        self._inventory     = []
        self._summary       = None
        self._scan_start_ms = 0
        self._scan_cancelled = False
        self._classify_worker = None  # _ClassifyWorker, imported lazily like LibraryScanner
        self._classify_tally = None
        self._classify_start_ms = 0
        self._classifying = False
        self._sync_pending = False
        self._detected_changes = []
        self._current_crates = {}
        self._dup_groups: list = []
        self._dup_summary = None
        self._dup_banner_widget = None

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        if saved_path is None:
            _raw = self._settings.value('library_path')
            saved_path = Path(_raw) if _raw else None
        self._stack.addWidget(self._build_welcome(saved_path))  # 0
        self._stack.addWidget(self._build_dashboard())          # 1 — shown both while scanning and once ready

        self._stack.setCurrentIndex(0)

    # ── Public API ────────────────────────────────────────────────────

    def is_sync_pending(self) -> bool:
        return self._sync_pending

    def _is_classification_complete(self) -> bool:
        if not self._library_path:
            return False
        flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
        return flag_path.exists()

    def refresh(self) -> None:
        if self._library_path and self._summary is not None:
            self._run_duplicate_detection()
            self._populate_dashboard()

    def set_library_path(self, path: Path) -> None:
        self._library_path = path
        self.start_scan(path)

    def start_scan(self, library_path: Path) -> None:
        logo = getattr(self, '_welcome_logo', None)
        if logo is not None and self._stack.currentIndex() == 0:
            self._play_logo_exit(lambda: self._start_scan_now(library_path))
        else:
            self._start_scan_now(library_path)

    def _play_logo_exit(self, on_finished) -> None:
        """Shrink the welcome logo away — mirrors its grow-in (same InBack/overshoot
        recipe as the dialog exit bounce) — before switching to the scan screen."""
        logo = self._welcome_logo
        curve = QEasingCurve(QEasingCurve.Type.InBack)
        curve.setOvershoot(3.0)
        anim = QVariantAnimation(logo)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(384)  # matches the 20%-slowed dialog exit duration
        anim.setEasingCurve(curve)
        anim.valueChanged.connect(
            lambda factor: logo.setFixedSize(
                max(1, int(self._LOGO_W * factor)), max(1, int(self._LOGO_H * factor))
            )
        )
        anim.finished.connect(on_finished)
        self._logo_exit_anim = anim
        anim.start()

    def _start_scan_now(self, library_path: Path) -> None:
        self._scan_cancelled = False
        self._library_path = library_path
        self._summary   = None
        self._inventory = []
        self._scan_start_ms = int(time.time() * 1000)
        self._populate_dashboard(scanning=True)
        self._stack.setCurrentIndex(1)
        self.scan_started.emit()
        self.status_message.emit('Scanning library…', 'amber')
        self._run_scan(library_path)

    # ── Welcome screen (state 0) ──────────────────────────────────────

    def _build_welcome(self, saved_path: Path | None = None) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(60, 60, 60, 100) # bottom headroom for media player

        if _SVG_AVAILABLE and _LOGO_SVG.exists():
            logo = QSvgWidget(str(_LOGO_SVG))
            logo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

            # Fun elastic grow-in on first launch — same OutBack/overshoot recipe
            # as the dialog bounce (_CrateSortDialog.run_bounce_animation), just
            # applied to the logo's size instead of a window's geometry.
            self._welcome_logo = logo
            self._LOGO_W, self._LOGO_H = 240, 254
            logo.setFixedSize(int(self._LOGO_W * 0.55), int(self._LOGO_H * 0.55))
            grow_curve = QEasingCurve(QEasingCurve.Type.OutBack)
            grow_curve.setOvershoot(3.0)
            self._logo_grow_anim = QVariantAnimation(w)
            self._logo_grow_anim.setStartValue(0.55)
            self._logo_grow_anim.setEndValue(1.0)
            self._logo_grow_anim.setDuration(320)
            self._logo_grow_anim.setEasingCurve(grow_curve)
            self._logo_grow_anim.valueChanged.connect(
                lambda factor: logo.setFixedSize(int(self._LOGO_W * factor), int(self._LOGO_H * factor))
            )
            self._logo_grow_anim.start()
        else:
            lbl = QLabel('CrateSort')
            lbl.setProperty('role', 'heading')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)

        tagline = QLabel('Get your shit together.')
        tagline.setProperty('role', 'tagline')
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)

        beta_badge = QLabel('BETA')
        beta_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        beta_badge.setStyleSheet(
            'color: #D17D34; font-size: 10px; font-weight: 700; letter-spacing: 2px; '
            'border: 1px solid #D17D34; border-radius: 4px; padding: 2px 8px; '
            'background: transparent;'
        )
        layout.addWidget(beta_badge, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        # Welcome Card wrapping all action controls
        welcome_card = QFrame()
        welcome_card.setObjectName('welcome_card')
        welcome_card.setFixedWidth(440)
        welcome_card.setStyleSheet(
            'QFrame#welcome_card { background-color: #2F2F2F; border: 1px solid #444444; border-radius: 12px; }'
        )
        card_layout = QVBoxLayout(welcome_card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(16)

        if saved_path is None:
            heading = QLabel('Point CrateSort to your _Serato_ folder and media files.')
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading.setWordWrap(True)
            heading.setStyleSheet(
                'color: #f1e3c8; font-size: 14px; font-weight: 600; background: transparent; border: none;'
            )
            card_layout.addWidget(heading)

            subtext = QLabel()
            subtext.setTextFormat(Qt.TextFormat.RichText)
            subtext.setText(
                '<div style="line-height: 125%;">'
                "If they're in different locations you'll need to move them into the "
                'same folder to enable crate management and export features.'
                '</div>'
            )
            subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtext.setWordWrap(True)
            subtext.setStyleSheet('color: #a89b85; font-size: 12px; background: transparent; border: none;')
            card_layout.addWidget(subtext)

            btn = QPushButton('Select Your Serato && Media Folder')
            btn.setMinimumHeight(42)
            btn.setStyleSheet(
                'QPushButton { background-color: #aa6326; color: #ffffff; border: none; '
                'border-radius: 6px; font-size: 13px; font-weight: 600; }'
                'QPushButton:hover { background-color: #925521; }'
                'QPushButton:pressed { background-color: #7e491c; }'
            )
            btn.clicked.connect(self._on_select_library)
            card_layout.addWidget(btn)

        elif not saved_path.exists():
            not_found = QLabel('Your previous library could not be found.')
            not_found.setStyleSheet('font-size: 14px; font-weight: 500; color: #f1e3c8; background: transparent; border: none;')
            not_found.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(not_found)

            path_text = QLabel()
            path_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            path_text.setStyleSheet(
                'QLabel { background-color: #1a1a1a; border: 1px solid #383838; border-radius: 6px; '
                'color: #7a6a55; font-family: Menlo, Monaco, "Courier New", monospace; font-size: 12px; padding: 10px; }'
            )
            fm = QFontMetrics(path_text.font())
            elided_path = fm.elidedText(str(saved_path), Qt.TextElideMode.ElideMiddle, 360)
            path_text.setText(elided_path)
            path_text.setToolTip(str(saved_path))
            card_layout.addWidget(path_text)

            btn = QPushButton('Select Music Library…')
            btn.setMinimumHeight(42)
            btn.setStyleSheet(
                'QPushButton { background-color: #aa6326; color: #ffffff; border: none; '
                'border-radius: 6px; font-size: 13px; font-weight: 600; }'
                'QPushButton:hover { background-color: #925521; }'
                'QPushButton:pressed { background-color: #7e491c; }'
            )
            btn.clicked.connect(self._on_select_library)
            card_layout.addWidget(btn)

        else:
            last_lbl = QLabel('Last library:')
            last_lbl.setStyleSheet('color: #a89b85; font-size: 12px; background: transparent; border: none;')
            last_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(last_lbl)

            path_text = QLabel()
            path_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            path_text.setStyleSheet(
                'QLabel { background-color: #1a1a1a; border: 1px solid #383838; border-radius: 6px; '
                'color: #f1e3c8; font-family: Menlo, Monaco, "Courier New", monospace; font-size: 12px; padding: 10px; }'
            )
            fm = QFontMetrics(path_text.font())
            elided_path = fm.elidedText(str(saved_path), Qt.TextElideMode.ElideMiddle, 360)
            path_text.setText(elided_path)
            path_text.setToolTip(str(saved_path))
            card_layout.addWidget(path_text)

            load_btn = QPushButton('Manage Last Library')
            load_btn.setMinimumHeight(42)
            load_btn.setStyleSheet(
                'QPushButton { background-color: #aa6326; color: #ffffff; border: none; '
                'border-radius: 6px; font-size: 13px; font-weight: 600; }'
                'QPushButton:hover { background-color: #925521; }'
                'QPushButton:pressed { background-color: #7e491c; }'
            )

            choose_btn = QPushButton('Choose Different Library')
            choose_btn.setMinimumHeight(42)
            choose_btn.setStyleSheet(
                'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
                'border-radius: 6px; font-size: 13px; font-weight: 500; }'
                'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
                'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
            )

            card_layout.addWidget(load_btn)
            card_layout.addWidget(choose_btn)

            always_cb = QCheckBox('Always load without asking')
            always_cb.setStyleSheet(
                f'QCheckBox {{ color: #f1e3c8; font-size: 12px; background: transparent; spacing: 8px; }}'
                f'QCheckBox::indicator {{ width: 16px; height: 16px; }}'
                f'QCheckBox::indicator:unchecked {{ image: url("{_ICON_UNCHECKED}"); }}'
                f'QCheckBox::indicator:checked   {{ image: url("{_ICON_CHECKED}");   }}'
            )
            card_layout.addWidget(always_cb, alignment=Qt.AlignmentFlag.AlignCenter)

            def _on_load():
                self._settings.setValue('always_load_last', always_cb.isChecked())
                self._library_path = saved_path
                self.library_path_changed.emit(saved_path)
                self.start_scan(saved_path)

            load_btn.clicked.connect(_on_load)
            choose_btn.clicked.connect(self._on_select_library)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('background: #383838; border: none; max-height: 1px;')
        card_layout.addWidget(sep)

        backup_warning = QLabel('⚠  Beta build — back up your library before scanning.')
        backup_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        backup_warning.setWordWrap(True)
        backup_warning.setStyleSheet(
            'color: #a89b85; font-size: 11px; background: transparent; border: none;'
        )
        card_layout.addWidget(backup_warning)

        layout.addWidget(welcome_card, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── Scanning banner (shown inline in the dashboard while a scan runs) ──

    def _build_scanning_banner(self) -> QWidget:
        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        eyebrow = QLabel('SCANNING YOUR LIBRARY')
        eyebrow.setStyleSheet('font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em;')
        vbox.addWidget(eyebrow)

        panel = QFrame()
        panel.setStyleSheet(
            f'QFrame {{ background-color: {self._PANEL}; border: 0.5px solid {self._SEP}; '
            f'border-radius: 10px; }}'
        )
        panel_v = QVBoxLayout(panel)
        panel_v.setContentsMargins(18, 16, 18, 17)
        panel_v.setSpacing(10)

        # Left column is fixed-width so the mascot (top) and status text
        # (bottom) share one column, and the cards/beam/cancel column to its
        # right stays aligned across both rows regardless of mascot presence.
        LEFT_COL_WIDTH = 132

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self._mascot: Optional[QSvgWidget] = None
        self._mascot_anim: Optional[QPropertyAnimation] = None
        if _SVG_AVAILABLE and _MASCOT_SVG.exists():
            mascot = QSvgWidget(str(_MASCOT_SVG))
            # Mascot SVG's viewBox is 1063.39x1262.43 (not square); QSvgWidget
            # stretches to fill its box with no aspect-ratio preservation, so
            # the fixed size must match that ratio or the art looks squashed.
            mascot.setFixedSize(84, 100)
            mascot.setStyleSheet('background: transparent;')
            mascot.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            effect = QGraphicsOpacityEffect(mascot)
            mascot.setGraphicsEffect(effect)
            curve = QEasingCurve(QEasingCurve.Type.InOutSine)
            anim = QPropertyAnimation(effect, b'opacity', mascot)
            anim.setDuration(1100)
            anim.setKeyValueAt(0.0, 0.3)
            anim.setKeyValueAt(0.5, 1.0)
            anim.setKeyValueAt(1.0, 0.3)
            anim.setEasingCurve(curve)
            anim.setLoopCount(-1)
            self._mascot = mascot
            self._mascot_anim = anim
            mascot_container = QWidget()
            mascot_container.setFixedWidth(LEFT_COL_WIDTH)
            mascot_container.setStyleSheet('background: transparent;')
            mascot_col = QHBoxLayout(mascot_container)
            mascot_col.setContentsMargins(0, 0, 0, 0)
            mascot_col.addWidget(mascot, alignment=Qt.AlignmentFlag.AlignHCenter)
            top_row.addWidget(mascot_container)
            top_row.setAlignment(mascot_container, Qt.AlignmentFlag.AlignBottom)
            anim.start()
        else:
            top_row.addSpacing(LEFT_COL_WIDTH + 14)

        # Live stats — the same 5-card row the Library tab's "Analyze Library"
        # modal used to show on its own, separate popup. Classification now
        # runs automatically right after the file scan, still on this same
        # scanning screen, so scanning and classifying read as one continuous
        # progress story instead of two back-to-back "scanning" experiences.
        # Files Analyzed climbs during phase 1 (file scan); the other 4 stay
        # at 0 until phase 2 (classification) starts populating them.
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        self._scan_card_analyzed     = _AnimatedStatCardWidget('Files Analyzed')
        self._scan_card_recognized   = _AnimatedStatCardWidget('Files Recognized')
        self._scan_card_unrecognized = _AnimatedStatCardWidget('Files Unrecognized')
        self._scan_card_artists      = _AnimatedStatCardWidget('Artists Recognized')
        self._scan_card_genres       = _AnimatedStatCardWidget('Genres Recognized')
        for card in (
            self._scan_card_analyzed, self._scan_card_recognized,
            self._scan_card_unrecognized, self._scan_card_artists, self._scan_card_genres,
        ):
            cards_row.addWidget(card)
        top_row.addLayout(cards_row, stretch=1)
        panel_v.addLayout(top_row)

        # Bottom row: status text sits under the mascot, then the comet beam
        # picks up at the same left edge as the first stat card and runs to
        # the Cancel button, which lines up with the last card's right edge.
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)

        status_container = QWidget()
        status_container.setFixedWidth(LEFT_COL_WIDTH)
        status_container.setStyleSheet('background: transparent;')
        status_v = QVBoxLayout(status_container)
        status_v.setContentsMargins(0, 0, 0, 0)
        self._scan_count = QLabel('Discovering files…')
        self._scan_count.setWordWrap(True)
        self._scan_count.setStyleSheet(
            'font-size: 11px; color: #7a6a55; letter-spacing: 0.02em; background: transparent; border: none;'
        )
        status_v.addWidget(self._scan_count)
        bottom_row.addWidget(status_container)

        self._scan_beam = _ScanActivityBeam()
        bottom_row.addWidget(self._scan_beam, stretch=1)
        self._scan_beam.start()

        self._scan_cancel = QPushButton('Cancel')
        self._scan_cancel.setFixedHeight(32)
        self._scan_cancel.setStyleSheet(
            'QPushButton { background: transparent; color: #C75B5B; border: 1px solid #444444; '
            'border-radius: 6px; padding: 0 16px; font-size: 12px; font-weight: 500; }'
            'QPushButton:hover { color: #ff7a7a; border-color: #C75B5B; }'
        )
        self._scan_cancel.clicked.connect(self._on_cancel_scan)
        bottom_row.addWidget(self._scan_cancel, alignment=Qt.AlignmentFlag.AlignVCenter)

        panel_v.addLayout(bottom_row)

        vbox.addWidget(panel)
        return outer

    # ── Dashboard container (state 2) ────────────────────────────────

    def _build_dashboard(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._dashboard_scroll = scroll

        inner = QWidget()
        self._dashboard_layout = QVBoxLayout(inner)
        self._dashboard_layout.setContentsMargins(28, 24, 28, 28)
        self._dashboard_layout.setSpacing(16)
        scroll.setWidget(inner)

        return scroll

    # ── Dashboard style constants ────────────────────────────────────
    _BG       = '#1a1a1a'
    _PANEL    = '#2F2F2F'
    _SEP      = '#383838'
    _CREAM    = '#f1e3c8'
    _MUTED    = '#a89b85'
    _VMUTED   = '#a89b85'
    _ORANGE   = '#D17D34'
    _TEAL     = '#428175'
    _ROW_ALT  = '#222222'
    _ROW_BASE = '#242424'

    def _populate_dashboard(self, scanning: bool = False) -> None:
        layout = self._dashboard_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        # The mascot/animation (if any) belonged to the widget just cleared above —
        # drop the references so nothing holds onto a soon-to-be-deleted QObject.
        self._mascot = None
        self._mascot_anim = None

        if scanning:
            # Library data isn't ready yet — show scan status where the stat
            # cards normally go, keep the YouTube/conversion tools live, and
            # leave out the activity feed/footer (both depend on the scan).
            layout.addWidget(self._build_scanning_banner())
            layout.addWidget(self._make_divider())
            layout.addWidget(self._build_action_cards_section(scanning=True))
            layout.addStretch()
            return

        summary    = self._summary
        inv        = self._inventory
        serato_dir = self._library_path / '_Serato_' if self._library_path else None

        if self._sync_pending:
            layout.addWidget(self._build_sync_warning_banner())

        layout.addWidget(self._build_stat_cards_section(summary, inv))
        if self._dup_groups:
            self._dup_banner_widget = self._build_dup_banner()
            layout.addWidget(self._dup_banner_widget)
        else:
            self._dup_banner_widget = None
        layout.addWidget(self._make_divider())
        layout.addWidget(self._build_action_cards_section())
        layout.addWidget(self._make_divider())
        layout.addWidget(self._build_activity_section(serato_dir))
        layout.addWidget(self._make_divider())
        layout.addWidget(self._build_footer_bar(serato_dir))
        layout.addStretch()

    # ── Section builders ─────────────────────────────────────────────

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet('background-color: #2a2a2a; border: none;')
        return line

    def _build_stat_cards_section(self, summary, inv: list) -> QWidget:
        serato_dir = self._library_path / '_Serato_' if self._library_path else None

        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        eyebrow = QLabel('YOUR LIBRARY')
        eyebrow.setStyleSheet('font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em;')
        vbox.addWidget(eyebrow)

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        total_target = summary.total_files if summary else 0
        c0 = _AnimatedStatCard(total_target, '', 'Total Tracks')
        row_layout.addWidget(c0)

        crate_target = 0
        if serato_dir and serato_dir.exists():
            subcrates = serato_dir / 'Subcrates'
            if subcrates.exists():
                crate_target = len(list(subcrates.rglob('*.crate')))
        c1 = _AnimatedStatCard(crate_target, '', 'Total Crates')
        row_layout.addWidget(c1)

        artists_target = len(summary.unique_artists) if summary else 0
        c2 = _AnimatedStatCard(artists_target, '', 'Unique Artists')
        row_layout.addWidget(c2)

        hours_target = 0
        if inv:
            total_secs = sum(r.duration for r in inv if r.duration)
            hours_target = int(total_secs / 3600)
        c3 = _AnimatedStatCard(hours_target, 'h', 'Hours of Music')
        row_layout.addWidget(c3)

        vbox.addWidget(row_widget)

        cards = [c0, c1, c2, c3]
        QTimer.singleShot(100, lambda: cards[0].start_animation(1600))
        QTimer.singleShot(220, lambda: cards[1].start_animation(1400))
        QTimer.singleShot(340, lambda: cards[2].start_animation(1500))
        QTimer.singleShot(460, lambda: cards[3].start_animation(1300))

        return outer

    def _build_dup_banner(self) -> QFrame:
        from cratesort.src.core.duplicate_detector import fmt_bytes
        summary = self._dup_summary
        n       = summary.total_groups if summary else len(self._dup_groups)
        space   = fmt_bytes(summary.space_recoverable) if summary else ''

        banner = QFrame()
        banner.setStyleSheet(
            'QFrame { background: #2a1a00; border: 1px solid #D17D34; border-radius: 8px; }'
        )
        row = QHBoxLayout(banner)
        row.setContentsMargins(20, 14, 20, 14)

        txt_col = QVBoxLayout()
        title = QLabel(f'{n:,} Potential Duplicate{"s" if n != 1 else ""} Found')
        title.setStyleSheet('color: #D17D34; font-size: 14px; font-weight: 700; background: transparent; border: none;')
        txt_col.addWidget(title)

        sub_parts = []
        if space:
            sub_parts.append(f'{space} could be reclaimed')
        if summary and summary.skipped_count > 0:
            s = summary.skipped_count
            sub_parts.append(
                f'{s:,} track{"s" if s != 1 else ""} skipped — no metadata'
            )
        sub_parts.append('Review before you classify.')
        sub = QLabel('  ·  '.join(sub_parts))
        sub.setStyleSheet('color: #a89b85; font-size: 12px; background: transparent; border: none;')
        txt_col.addWidget(sub)

        row.addLayout(txt_col, stretch=1)

        btn = QPushButton('Review Duplicates')
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            'QPushButton { background: #aa6326; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 0 18px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background: #925521; }'
            'QPushButton:pressed { background: #7e491c; }'
        )
        btn.clicked.connect(self.duplicates_requested.emit)
        row.addWidget(btn)

        return banner

    def clear_duplicates(self) -> None:
        """Called after a successful Rinse — removes the duplicate banner immediately."""
        self._dup_groups = []
        self._dup_summary = None
        if self._dup_banner_widget is not None:
            self._dup_banner_widget.hide()
            self._dup_banner_widget.deleteLater()
            self._dup_banner_widget = None

    def _build_action_cards_section(self, scanning: bool = False) -> QWidget:
        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)

        _icons = _ASSETS / 'icons'
        goto_cards = [
            ('01', 'Manage Library', 'Start here to clean all of your media files by reviewing '
                                      'and updating metadata and filenames.',
             self.classify_requested.emit, _icons / 'icon-library.svg', None),
            ('02', 'Manage Crates',  'Once your media has been cleaned, come here to browse, '
                                      'create, edit, and export your Serato crates.',
             self.crates_requested.emit, _icons / 'icon-crates.svg', None),
            ('03', 'Organize Media', 'Consolidate duplicates and reorganize all of your media '
                                      'files without affecting your Serato crates.',
             self.organize_requested.emit, _icons / 'icon-organize.svg',
             'CrateSort’s Organization Logic:<br>Your Library Folder > Media > Genre > Artist > Files'),
        ]

        goto_widget = QWidget()
        goto_grid = QGridLayout(goto_widget)
        goto_grid.setContentsMargins(0, 0, 0, 0)
        goto_grid.setSpacing(10)

        highlight_manage_library = not self._is_classification_complete()
        for col_idx, (step, title, desc, action, icon_path, footer) in enumerate(goto_cards):
            card = _WorkflowCard(
                step, title, desc, action, icon_path=icon_path,
                highlighted=(highlight_manage_library and title == 'Manage Library' and not scanning),
                footer=footer,
            )
            if scanning:
                card.set_disabled(True)
            goto_grid.addWidget(card, 0, col_idx)

        vbox.addWidget(goto_widget)

        # Extra 6px on each side on top of vbox's uniform 10px spacing, matching
        # the 16px gap the outer dashboard layout uses around its own divider
        # (between the stat cards and this section) — otherwise this divider
        # reads noticeably more cramped than the one above it.
        vbox.addSpacing(6)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet('background-color: #2a2a2a; border: none;')
        vbox.addWidget(divider)
        vbox.addSpacing(6)

        # ── YouTube import cards ──────────────────────────────────────────
        yt_defs = [
            {
                'icon_path': _icons / 'icon-mp3-2.svg', 'title': 'YouTube to MP3',
                'desc': 'Convert URL to audio file  ·  VBR',
                'action': lambda: self._open_yt_import('mp3'),
                'base':  _WorkflowCard._STYLE_REST,
                'hover': _WorkflowCard._STYLE_HOVER,
            },
            {
                'icon_path': _icons / 'icon-mp4-2.svg', 'title': 'YouTube to MP4',
                'desc': 'Convert URL to video file  ·  VBR',
                'action': lambda: self._open_yt_import('mp4'),
                'base':  _WorkflowCard._STYLE_REST,
                'hover': _WorkflowCard._STYLE_HOVER,
            },
        ]

        yt_widget = QWidget()
        yt_grid = QGridLayout(yt_widget)
        yt_grid.setContentsMargins(0, 0, 0, 0)
        yt_grid.setSpacing(10)

        for col_idx, defn in enumerate(yt_defs):
            card = _IconActionCard(
                defn['title'], defn['desc'], defn['action'], defn['icon_path'],
                defn['base'], defn['hover'],
            )
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            yt_grid.addWidget(card, 0, col_idx)

        vbox.addWidget(yt_widget)

        # ── Local conversion cards ────────────────────────────────────────
        convert_defs = [
            {
                'icon_path': _icons / 'icon-convert.svg', 'title': 'Audio to MP3',
                'desc': 'Convert existing audio file  ·  320kbps',
                'action': lambda: self._open_convert('wav_mp3'),
                'base':  _WorkflowCard._STYLE_REST,
                'hover': _WorkflowCard._STYLE_HOVER,
            },
            {
                'icon_path': _icons / 'icon-convert.svg', 'title': 'Video to MP4',
                'desc': 'Convert existing video file  ·  H.264',
                'action': lambda: self._open_convert('video_mp4'),
                'base':  _WorkflowCard._STYLE_REST,
                'hover': _WorkflowCard._STYLE_HOVER,
            },
        ]

        convert_widget = QWidget()
        convert_grid = QGridLayout(convert_widget)
        convert_grid.setContentsMargins(0, 0, 0, 0)
        convert_grid.setSpacing(10)

        for col_idx, defn in enumerate(convert_defs):
            card = _IconActionCard(
                defn['title'], defn['desc'], defn['action'], defn['icon_path'],
                defn['base'], defn['hover'],
            )
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            convert_grid.addWidget(card, 0, col_idx)

        vbox.addWidget(convert_widget)
        return outer

    def _build_activity_section(self, serato_dir: Optional[Path]) -> QWidget:
        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(8)

        eyebrow = QLabel('RECENT ACTIVITY — LAST 30 DAYS')
        eyebrow.setStyleSheet('font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em;')
        vbox.addWidget(eyebrow)

        panel = QFrame()
        panel.setStyleSheet(
            f'QFrame {{ background-color: {self._PANEL}; border: 0.5px solid {self._SEP}; '
            f'border-radius: 10px; }}'
        )
        panel_vbox = QVBoxLayout(panel)
        panel_vbox.setContentsMargins(18, 16, 18, 16)
        panel_vbox.setSpacing(0)

        now = datetime.now()
        items = []

        if serato_dir and serato_dir.exists():
            changes = list(self._detected_changes)

            _teal_types   = {'crate_added', 'tracks_added', 'renamed', 'added'}
            _orange_types = {'crate_removed', 'tracks_removed', 'removed'}
            for change in changes:
                ctype = change.get('type', '')
                dot_color = (
                    self._TEAL if ctype in _teal_types
                    else self._ORANGE if ctype in _orange_types
                    else self._MUTED
                )
                items.append({
                    'dot_color': dot_color,
                    'text': change['description'].replace('.crate', ''),
                    'time_str': 'Today',
                    '_dt': now,
                })

            try:
                add_dates = read_track_add_dates(serato_dir)
                cutoff = now - timedelta(days=30)
                recent = [(p, dt) for p, dt in add_dates.items() if dt >= cutoff]
                recent.sort(key=lambda x: x[1], reverse=True)
                for path, dt in recent[:10]:
                    time_str = 'Today' if dt.date() == now.date() else dt.strftime('%b %d')
                    items.append({
                        'dot_color': self._TEAL,
                        'text': Path(path).name,
                        'time_str': time_str,
                        '_dt': dt,
                    })
            except Exception:
                pass

            # Reorganization log entries
            crate_sort_dir = serato_dir.parent / '_CrateSort'
            cutoff = now - timedelta(days=30)
            for log_file in sorted(crate_sort_dir.glob('reorganization_log_*.json'), reverse=True):
                try:
                    with open(log_file, encoding='utf-8') as f:
                        log = json.load(f)
                    exec_str = log.get('executed_at', '')
                    if not exec_str:
                        continue
                    dt = datetime.fromisoformat(exec_str)
                    if dt >= cutoff:
                        moved = sum(1 for m in log.get('moves', []) if m.get('status') == 'completed')
                        time_str = 'Today' if dt.date() == now.date() else dt.strftime('%b %d')
                        items.append({
                            'dot_color': self._TEAL,
                            'text': f'Library Reorganized — {moved:,} file{"s" if moved != 1 else ""} moved',
                            'time_str': time_str,
                            '_dt': dt,
                        })
                    rb_str = log.get('rolled_back_at', '')
                    if rb_str:
                        dt_rb = datetime.fromisoformat(rb_str)
                        if dt_rb >= cutoff:
                            moved = sum(1 for m in log.get('moves', []) if m.get('status') == 'completed')
                            time_str_rb = 'Today' if dt_rb.date() == now.date() else dt_rb.strftime('%b %d')
                            items.append({
                                'dot_color': self._ORANGE,
                                'text': f'Reorganization Rolled Back — {moved:,} file{"s" if moved != 1 else ""} restored',
                                'time_str': time_str_rb,
                                '_dt': dt_rb,
                            })
                except Exception:
                    continue

        items.sort(key=lambda x: x['_dt'], reverse=True)
        items = items[:10]

        if not items:
            empty = QLabel('No activity in the last 30 days.')
            empty.setStyleSheet(
                f'color: {self._MUTED}; font-size: 13px; background: transparent; border: none;'
            )
            panel_vbox.addWidget(empty)
        else:
            for i, item in enumerate(items):
                if i > 0:
                    sep = QFrame()
                    sep.setFixedHeight(1)
                    sep.setStyleSheet(f'background-color: {self._SEP}; border: none;')
                    panel_vbox.addWidget(sep)

                row = QWidget()
                row.setStyleSheet("background: transparent; border: none;")
                row_h = QHBoxLayout(row)
                row_h.setContentsMargins(8, 8, 8, 8)
                row_h.setSpacing(10)

                dot = QLabel('●')
                dot.setStyleSheet(
                    f'color: {item["dot_color"]}; font-size: 6px; '
                    f'background: transparent; border: none;'
                )
                dot.setFixedWidth(14)
                dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row_h.addWidget(dot)

                text_lbl = QLabel(item['text'])
                text_lbl.setStyleSheet(
                    'font-size: 13px; color: #c9b89a; background: transparent; border: none;'
                )
                text_lbl.setWordWrap(True)
                row_h.addWidget(text_lbl, stretch=1)

                time_lbl = QLabel(item['time_str'])
                time_lbl.setStyleSheet(
                    'font-size: 11px; color: #5a5a5a; background: transparent; border: none;'
                )
                time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                row_h.addWidget(time_lbl)

                panel_vbox.addWidget(row)

        vbox.addWidget(panel)
        return outer

    def _build_footer_bar(self, serato_dir: Optional[Path]) -> QFrame:
        """Footer bar with last-session timestamp and sync status."""
        footer = QFrame()
        footer.setStyleSheet(
            f'QFrame {{ background-color: {self._PANEL}; border: 1px solid {self._SEP}; '
            f'border-radius: 4px; }}'
        )
        footer.setFixedHeight(34)

        h = QHBoxLayout(footer)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(0)

        # Left: last session timestamp
        timestamp_text = 'First session'
        if serato_dir:
            cp = load_checkpoint(serato_dir)
            if cp and cp.get('timestamp'):
                try:
                    dt = datetime.fromisoformat(cp['timestamp'])
                    timestamp_text = f'Last session: {dt.strftime("%Y-%m-%d %H:%M")}'
                except Exception:
                    pass

        ts_lbl = QLabel(timestamp_text)
        ts_lbl.setStyleSheet(
            f'color: {self._VMUTED}; font-size: 11px; background: transparent; border: none;'
        )
        h.addWidget(ts_lbl)
        h.addStretch()

        # Right: dot + sync text (Amber if pending, Teal if synced)
        dot_color = self._ORANGE if self._sync_pending else self._TEAL
        status_text = '  Review Serato changes' if self._sync_pending else '  Library synced'

        dot = QLabel('●')
        dot.setStyleSheet(
            f'color: {dot_color}; font-size: 9px; background: transparent; border: none;'
        )
        h.addWidget(dot)

        if self._sync_pending:
            sync_lbl = _ClickableLabel(status_text)
            sync_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            sync_lbl.clicked.connect(self._on_review_sync_clicked)
        else:
            sync_lbl = QLabel(status_text)

        sync_lbl.setStyleSheet(
            f'color: {dot_color}; font-size: 11px; background: transparent; border: none;'
        )
        h.addWidget(sync_lbl)

        return footer

    # ── Slots ─────────────────────────────────────────────────────────

    def _open_yt_import(self, fmt: str) -> None:
        from cratesort.src.gui.classifier_view import ALL_GENRES
        library_genres: set[str] = set()
        if self._summary is not None:
            library_genres = {g for g in self._summary.unique_genres if g}
        genres = sorted(library_genres | set(ALL_GENRES), key=str.lower)
        artists = sorted(
            {tr.artist for tr in self._inventory if getattr(tr, 'artist', None)},
            key=str.lower,
        )
        dlg = _YTImportDialog(fmt, self._library_path, genres, artists, self)
        dlg.exec()

    def _open_convert(self, mode: str) -> None:
        dlg = _ConvertDialog(mode, self)
        dlg.exec()

    def _on_select_library(self) -> None:
        # Reset always_load_last so the dialog appears on next startup
        self._settings.setValue('always_load_last', False)
        start_dir = (
            str(self._library_path.parent)
            if self._library_path and self._library_path.parent.exists()
            else str(Path.home())
        )
        path = QFileDialog.getExistingDirectory(
            self,
            'Select the folder containing your media files — '
            'CrateSort will scan everything inside it',
            start_dir,
        )
        if path:
            library_path = Path(path)
            self._library_path = library_path
            self.library_path_changed.emit(library_path)
            self.start_scan(library_path)

    def _on_cancel_scan(self) -> None:
        self._scan_cancelled = True   # set BEFORE clearing state — timer callbacks check this
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            try:
                self._worker.finished.disconnect()
            except Exception:
                pass
            self._worker.wait(3000)
        if self._classify_worker and self._classify_worker.isRunning():
            self._classify_worker.cancel()
            try:
                self._classify_worker.finished.disconnect()
            except Exception:
                pass
            self._classify_worker.wait(3000)
        self._classifying = False
        if getattr(self, '_mascot_anim', None) is not None:
            self._mascot_anim.stop()
        self._inventory = []
        self._summary = None
        self._library_path = None
        # start_scan()'s _play_logo_exit() shrinks the welcome logo to ~0px
        # on the way out; restore it to resting size or it stays invisible
        # when we land back on the welcome screen here.
        logo = getattr(self, '_welcome_logo', None)
        if logo is not None:
            logo.setFixedSize(self._LOGO_W, self._LOGO_H)
        self._stack.setCurrentIndex(0)
        self.status_message.emit('', '')

    def _on_scan_progress(self, count: int, dir_name: str) -> None:
        self._scan_card_analyzed.update_target(count)
        self._scan_count.setText(f'Scanning “{dir_name}”…')

    def _on_scan_finished(self, inventory, summary) -> None:
        if self._scan_cancelled:
            return
        self._apply_serato_overlay(inventory)
        self._inventory = inventory
        self._summary   = summary
        elapsed_ms = int(time.time() * 1000) - self._scan_start_ms
        delay = max(0, _MIN_SCAN_DISPLAY_MS - elapsed_ms)
        QTimer.singleShot(delay, self._start_classification_phase)

    def _start_classification_phase(self) -> None:
        """
        Run library classification automatically right after the file scan,
        still on this same scanning screen — this is what used to be a
        separate "Analyzing Library" popup the first time the user opened
        Library. By the time that tab is opened, classification_session.json
        already exists, so the existing skip-logic in
        LibraryBrowserView._on_classify_clicked opens straight into the
        classified view with no second "scanning" experience. The modal
        remains as a fallback for the (rare) case this phase never ran or
        failed — see _on_classify_phase_error.

        Copy here must never imply classification is "done" — the library
        isn't classified in any meaningful sense until the user reviews and
        accepts on the Library screen. This phase only proposes associations.
        """
        if self._scan_cancelled:
            return
        from cratesort.src.gui.classifier_view import ClassifyProgressTally, _ClassifyWorker

        # Files Analyzed is frozen at its final scan total rather than fed
        # from the classifier's own tally: both converge to the same number
        # (every scanned track), but the classifier counts it by accumulating
        # per-artist-group as it goes, starting from 0 — re-feeding that into
        # the same animated card would visibly count it back DOWN before
        # climbing back up. The other 4 cards are genuinely phase-2-only
        # concepts with nothing from phase 1 to conflict with.
        self._scan_card_analyzed.update_target(len(self._inventory))
        self._scan_count.setText('Preparing artist & genre associations…')

        self._classify_tally    = ClassifyProgressTally()
        self._classify_start_ms = int(time.time() * 1000)
        self._classifying       = True

        self._classify_worker = _ClassifyWorker(self._inventory, self._library_path)
        self._classify_worker.progress.connect(self._on_classify_progress)
        self._classify_worker.finished.connect(self._on_classify_phase_finished)
        self._classify_worker.errored.connect(self._on_classify_phase_error)
        self._classify_worker.start()

    def _on_classify_progress(self, done: int, total: int, info: dict) -> None:
        if self._scan_cancelled or self._classify_tally is None:
            return
        tally = self._classify_tally.add(info)
        self._scan_card_recognized.update_target(tally['files_recognized'])
        self._scan_card_unrecognized.update_target(tally['files_unrecognized'])
        self._scan_card_artists.update_target(tally['artists_recognized'])
        self._scan_card_genres.update_target(tally['genres_recognized'])

    def _on_classify_phase_finished(self, session) -> None:
        self._classifying = False
        if self._scan_cancelled:
            return
        try:
            session.save()
            session.apply_library_edits()
        except Exception as exc:
            logger.warning('[Classify] Failed to save dashboard-phase session: %s', exc)
        elapsed_ms = int(time.time() * 1000) - self._classify_start_ms
        delay = max(0, _MIN_CLASSIFY_DISPLAY_MS - elapsed_ms)
        QTimer.singleShot(delay, self._show_dashboard)

    def _on_classify_phase_error(self, message: str) -> None:
        self._classifying = False
        logger.warning('[Classify] Dashboard-phase classification failed: %s', message)
        # No session file was written, so the existing _AnalyzeLibraryModal
        # fallback in LibraryBrowserView._on_classify_clicked will naturally
        # retry when the user opens the Library tab — proceed to the
        # dashboard rather than blocking on a failure here.
        if not self._scan_cancelled:
            self._show_dashboard()

    def _apply_serato_overlay(self, inventory: list) -> None:
        """
        Overlay Serato's own BPM/comment onto matching tracks. These fields
        can be edited live in Serato (e.g. mid-set) without ever touching
        the audio file itself, so a file-mtime-based scan cache alone would
        never see the change. Serato's `database V2` is one small binary
        file, cheap to parse fresh on every launch regardless of library
        size or scan-cache state.

        Deliberately does NOT overlay genre. Genre is different from
        BPM/comment: CrateSort has its own dedicated classification/Accept
        workflow that owns genre authoritatively (Serato has no equivalent
        "edit genre live mid-set" feature the way it does for BPM/comment).
        A real bug was found and fixed here: overlaying Serato's genre
        unconditionally meant every classification a user accepted got
        silently reverted on the next launch — Accept writes the new genre
        to the audio file itself, but never touches Serato's own database,
        so Serato's database still had the pre-classification genre, and
        this overlay was overwriting the correct, freshly-written file tag
        with that stale value every time. Confirmed empirically: a track
        classified "FX" → "Specialty" and correctly written to disk by
        Accept reverted straight back to "FX" the moment this overlay ran
        on the next scan, before this fix.

        Matches by trying every candidate key `_normalize_pfil_keys()` would
        derive from a track's own path (not just a direct absolute-path
        lookup) — Serato's stored paths only agree with `rec.path` when the
        library's root hasn't moved since Serato last wrote them, and this
        overlay needs to keep matching across a renamed folder or remounted
        drive for the feature to be reliable.
        """
        if not self._library_path:
            return
        serato_dir = self._library_path / '_Serato_'
        if not serato_dir.exists():
            return
        db_metadata = read_track_metadata(serato_dir)
        if not db_metadata:
            return
        for rec in inventory:
            entry = None
            for key in _normalize_pfil_keys(rec.path.as_posix()):
                entry = db_metadata.get(key)
                if entry:
                    break
            if entry is None:
                continue
            if entry.bpm is not None:
                rec.bpm = entry.bpm
            if entry.comment is not None:
                rec.comment = entry.comment

    def _check_serato_sync(self) -> None:
        serato_dir = self._library_path / '_Serato_' if self._library_path else None
        self._sync_pending = False
        self._detected_changes = []
        self._current_crates = {}
        self._checkpoint_timestamp: Optional[datetime] = None

        if serato_dir and serato_dir.exists():
            # Gather current crates — store full track lists for revert support
            subcrates = serato_dir / 'Subcrates'
            if subcrates.exists():
                for crate_file in subcrates.rglob('*.crate'):
                    try:
                        from cratesort.src.serato.crate_reader import CrateReader
                        reader = CrateReader(serato_dir)
                        tracks, _ = reader._read_tracks(crate_file)
                        self._current_crates[str(crate_file)] = tracks
                    except Exception:
                        self._current_crates[str(crate_file)] = None

            checkpoint = load_checkpoint(serato_dir)
            if checkpoint is None:
                save_checkpoint(serato_dir, self._current_crates)
            else:
                try:
                    self._checkpoint_timestamp = datetime.fromisoformat(
                        checkpoint.get('timestamp', '')
                    )
                except Exception:
                    pass
                self._detected_changes = detect_changes(self._current_crates, checkpoint)
                # Attach mtime of each changed .crate file so the dialog can show it
                for change in self._detected_changes:
                    crate_path = Path(change.get('crate_path', ''))
                    if crate_path.exists():
                        try:
                            change['mtime'] = datetime.fromtimestamp(
                                crate_path.stat().st_mtime
                            )
                        except Exception:
                            change['mtime'] = None
                    else:
                        # Removed crate — fall back to checkpoint timestamp
                        change['mtime'] = self._checkpoint_timestamp
                if self._detected_changes:
                    self._sync_pending = True
                else:
                    save_checkpoint(serato_dir, self._current_crates)

    def _run_duplicate_detection(self) -> None:
        if not self._inventory:
            return
        try:
            from collections import defaultdict
            from cratesort.src.core.duplicate_detector import (
                DuplicateDetector, group_fingerprint, summarize_groups,
            )
            from cratesort.src.core.duplicate_dismissals import load_dismissed
            from cratesort.src.serato.database_reader import read_track_play_counts

            counts: dict[str, int] = defaultdict(int)
            for tracks in self._current_crates.values():
                if tracks:
                    for track in tracks:
                        counts[track] += 1
            crate_count_map = dict(counts)

            serato_dir     = self._library_path / '_Serato_' if self._library_path else None
            play_count_map = read_track_play_counts(serato_dir) if serato_dir and serato_dir.exists() else {}

            groups, summary = DuplicateDetector().detect(
                self._inventory,
                crate_count_map=crate_count_map,
                play_count_map=play_count_map,
            )

            # Drop groups the user previously said to always keep — they never
            # reach the banner count or the review screen.
            dismissed = load_dismissed(self._library_path) if self._library_path else set()
            if dismissed:
                groups  = [g for g in groups if group_fingerprint(g) not in dismissed]
                summary = summarize_groups(groups, skipped_count=summary.skipped_count)

            self._dup_groups  = groups
            self._dup_summary = summary
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('[DupDetect] Detection failed: %s', exc, exc_info=True)
            self._dup_groups  = []
            self._dup_summary = None

    def _show_dashboard(self) -> None:
        try:
            if self._scan_cancelled or self._summary is None:
                return
            self._check_serato_sync()
            self._run_duplicate_detection()
            self._populate_dashboard(scanning=False)
            self.scan_finished.emit()
            if self._sync_pending:
                self.status_message.emit('Serato library changes detected. Review required.', 'amber')
            else:
                self.status_message.emit('Library synced. Ready.', 'green')
        except Exception as exc:
            import traceback
            print(f'[CrateSort] _show_dashboard error: {exc}\n{traceback.format_exc()}')

    def _on_review_sync_clicked(self) -> None:
        serato_dir = self._library_path / '_Serato_' if self._library_path else None
        dialog = _ChangeReviewDialog(
            self._detected_changes,
            serato_dir,
            self._current_crates,
            self._checkpoint_timestamp,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Dialog handled checkpoint save internally after executing reverts.
            # Re-scan so the inventory and Crates tab reflect any reverted crate files.
            self._sync_pending = False
            if self._library_path:
                self.start_scan(self._library_path)
            else:
                self._populate_dashboard()
            self.status_message.emit('Library synced. Ready.', 'green')

    def _build_sync_warning_banner(self) -> QWidget:
        banner = QFrame()
        banner.setStyleSheet(
            'QFrame { background-color: #2a2218; border: 1px solid #D17D34; border-radius: 8px; }'
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        icon_lbl = QLabel('⚠️')
        icon_lbl.setStyleSheet('font-size: 16px; border: none; background: transparent;')
        layout.addWidget(icon_lbl)
        
        msg_lbl = QLabel(
            'Changes detected in Serato library since last CrateSort session. '
            'Please review and sync to continue.'
        )
        msg_lbl.setStyleSheet('color: #f1e3c8; font-size: 13px; font-weight: 500; border: none; background: transparent;')
        layout.addWidget(msg_lbl)
        
        layout.addStretch()
        
        btn = QPushButton('Review && Sync')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_review_sync_clicked)
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; border-radius: 6px; padding: 0 16px; font-weight: 600; font-size: 13px; min-width: 170px; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        layout.addWidget(btn)

        return banner

    def _on_scan_error(self, message: str) -> None:
        self._scan_count.setText(f'Scan failed — {message}')
        self.status_message.emit(f'Scan error: {message}', 'error')

    def _run_scan(self, library_path: Path) -> None:
        self._worker = _ScanWorker(library_path)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.errored.connect(self._on_scan_error)
        self._worker.start()

