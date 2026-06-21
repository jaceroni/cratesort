from __future__ import annotations

import json
import logging
import sys
import time

logger = logging.getLogger(__name__)
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSettings, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter,
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
from cratesort.src.serato.database_reader import read_track_add_dates
from cratesort.src.gui.overlays import _CrateSortDialog, _ov_alert, _create_dialog_layout

_ASSETS         = Path(__file__).parent.parent.parent / 'assets'
_LOGO_SVG       = _ASSETS / 'logo' / 'cs-logo-mascot-stacked.svg'
_ICON_CHECKED   = str(_ASSETS / 'icons' / 'checkbox-checked.svg')
_ICON_UNCHECKED = str(_ASSETS / 'icons' / 'checkbox-unchecked.svg')
_ORG, _APP = 'JWBC', 'CrateSort'

# Minimum time the scanning UI stays visible (ms)
_MIN_SCAN_DISPLAY_MS = 1500

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


# ---------------------------------------------------------------------------
# Clickable card — full-surface click + hover border
# ---------------------------------------------------------------------------

class _ClickableCard(QFrame):
    def __init__(self, callback, base_style: str, hover_style: str, parent=None):
        super().__init__(parent)
        self._callback    = callback
        self._base_style  = base_style
        self._hover_style = hover_style
        self.setStyleSheet(base_style)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._callback()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(self._hover_style)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._base_style)
        super().leaveEvent(event)


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
    _STYLE_REST  = 'QFrame { background-color: #2F2F2F; border: 1px solid #3a3a3a; border-radius: 10px; }'
    _STYLE_HOVER = 'QFrame { background-color: #353028; border: 1px solid #D17D34; border-radius: 10px; }'
    _ICON_DIM    = '#2a2a2a'
    _ICON_ACTIVE = '#D17D34'

    def __init__(self, _step: str, title: str, desc: str, callback, icon_path=None, highlighted: bool = False, parent=None):
        super().__init__(parent)
        self._callback  = callback
        self._icon_path = icon_path
        self._icon_svg: QSvgWidget | None = None
        self._svg_bytes: bytes | None = None

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

        # Outer row: text on left, icon on right
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 14, 14, 14)
        row.setSpacing(0)

        col = QVBoxLayout()
        col.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            'font-size: 16px; font-weight: 500; color: #D17D34; '
            'background: transparent; border: none;'
        )
        col.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            'font-size: 11px; color: #a89b85; background: transparent; border: none;'
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

    def _load_icon_color(self, color: str) -> None:
        if self._icon_svg and self._svg_bytes:
            from PyQt6.QtCore import QByteArray
            colored = self._svg_bytes.decode('utf-8').replace(
                '#d17d34', color
            ).replace('#D17D34', color)
            self._icon_svg.load(QByteArray(colored.encode('utf-8')))

    def enterEvent(self, event):
        self.setStyleSheet(self._STYLE_HOVER)
        self._load_icon_color(self._ICON_ACTIVE)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.style_rest)
        self._load_icon_color(self.icon_dim)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._callback:
            self._callback()


# ---------------------------------------------------------------------------
# Change Review Dialog
# ---------------------------------------------------------------------------

class _ChangeReviewDialog(_CrateSortDialog):
    """
    Review Serato library changes detected since the last session.

    Each row shows the change description, when it happened, and a Revert
    button. Clicking Revert marks that change as pending revert (row grays out,
    button becomes Undo). Clicking Undo cancels the pending revert. No disk
    writes happen until the user clicks Sync & Proceed — at that point all
    pending reverts are executed and the checkpoint is saved. Clicking Cancel
    leaves the checkpoint unchanged and the sync banner remains.
    """

    _TEAL_TYPES   = {'crate_added', 'tracks_added', 'renamed', 'added'}
    _ORANGE_TYPES = {'crate_removed', 'tracks_removed', 'removed'}

    def __init__(
        self,
        changes: list[dict],
        serato_dir: Optional[Path],
        current_crates: dict,
        checkpoint_timestamp: Optional[datetime],
        parent=None,
    ):
        super().__init__(parent)
        self.setMinimumSize(540, 480)

        self._serato_dir         = serato_dir
        self._updated_crates     = dict(current_crates)
        self._pending_reverts:   set[int] = set()   # indices into self._changes
        self._changes            = list(changes)

        # Use the standard dialog layout builder with Orange accent (selection/confirm)
        layout = _create_dialog_layout(self, '#D17D34')

        title = QLabel('Serato Library Changes Detected')
        title.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(title)
        layout.addSpacing(6)

        if checkpoint_timestamp:
            day = checkpoint_timestamp.day
            since_str = checkpoint_timestamp.strftime(f'%B {day}, %Y at %I:%M %p')
            desc_text = (
                f'Changes detected since your last session on {since_str}. '
                'Mark any changes to revert before syncing.'
            )
        else:
            desc_text = (
                'Changes detected since your last CrateSort session. '
                'Mark any changes to revert before syncing.'
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
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        rows_container = QWidget()
        rows_container.setStyleSheet('background: transparent;')
        self._rows_layout = QVBoxLayout(rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        scroll.setWidget(rows_container)
        layout.addWidget(scroll, stretch=1)

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

        self._sync_btn = QPushButton('Sync & Proceed')
        self._sync_btn.setFixedHeight(36)
        self._sync_btn.setStyleSheet(
            'QPushButton { background-color: #D17D34; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #be6e2c; }'
            'QPushButton:pressed { background-color: #aa5d21; }'
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
        if can_revert:
            revert_btn = QPushButton('Revert')
            revert_btn.setFixedHeight(26)
            revert_btn.setStyleSheet(
                'QPushButton { background: #C75B5B; color: #ffffff; font-size: 11px; font-weight: 600; '
                'border: none; border-radius: 4px; padding: 2px 10px; }'
                'QPushButton:hover { background: #b24c4c; }'
                'QPushButton:pressed { background: #9c3b3b; }'
            )
            revert_btn.clicked.connect(
                lambda _, i=idx, f=frame, d=desc_lbl, t=time_lbl, b=revert_btn: self._on_revert(i, f, d, b)
            )
            h.addWidget(revert_btn)

        self._row_frames.append(frame)
        return frame

    # ── Revert interaction ────────────────────────────────────────────────────

    def _on_revert(
        self,
        idx: int,
        frame: QFrame,
        desc_lbl: QLabel,
        btn: QPushButton,
    ) -> None:
        if idx in self._pending_reverts:
            # Undo the pending revert
            self._pending_reverts.discard(idx)
            frame.setStyleSheet(
                'QFrame { background: #2a2a2a; border: none; border-radius: 4px; }'
            )
            desc_lbl.setStyleSheet(
                'color: #f1e3c8; font-size: 13px; background: transparent; border: none;'
            )
            btn.setText('Revert')
            btn.setStyleSheet(
                'QPushButton { background: #C75B5B; color: #ffffff; font-size: 11px; font-weight: 600; '
                'border: none; border-radius: 4px; padding: 2px 10px; }'
                'QPushButton:hover { background: #b24c4c; }'
                'QPushButton:pressed { background: #9c3b3b; }'
            )
        else:
            # Mark as pending revert
            self._pending_reverts.add(idx)
            frame.setStyleSheet(
                'QFrame { background: #222222; border: 1px solid #3a3a3a; border-radius: 4px; }'
            )
            desc_lbl.setStyleSheet(
                'color: #5a5a5a; font-size: 13px; text-decoration: line-through; '
                'background: transparent; border: none;'
            )
            btn.setText('Undo')
            btn.setStyleSheet(
                'QPushButton { background: #2a2a2a; color: #a89b85; font-size: 11px; font-weight: 600; '
                'border: 1px solid #444; border-radius: 4px; padding: 2px 10px; }'
                'QPushButton:hover { background: #383838; }'
            )

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
        if ctype == 'crate_added':
            return True   # just delete the file — no prev_tracks needed
        return bool(change.get('prev_tracks'))   # all other types need the old track list

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
    new_crate_requested       = pyqtSignal()
    new_smart_crate_requested = pyqtSignal()
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
        self._stack.addWidget(self._build_scanning())           # 1
        self._stack.addWidget(self._build_dashboard())          # 2

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
            self._check_serato_sync()
            self._populate_dashboard()

    def set_library_path(self, path: Path) -> None:
        self._library_path = path
        self.start_scan(path)

    def start_scan(self, library_path: Path) -> None:
        self._scan_cancelled = False
        self._library_path = library_path
        self._scan_label.setText('Scanning library…')
        self._scan_count.setText('Discovering files…')
        self._scan_bar.setValue(0)
        self._scan_start_ms = int(time.time() * 1000)
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
            logo.setFixedSize(240, 254)
            logo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
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
            instr = QLabel()
            instr.setTextFormat(Qt.TextFormat.RichText)
            instr.setText(
                '<div style="line-height: 145%; text-align: center;">'
                'Select the root folder of your music library.<br>'
                'CrateSort will scan all media files inside it, including subfolders.'
                '</div>'
            )
            instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            instr.setWordWrap(True)
            instr.setStyleSheet('color: #d5c7ad; font-size: 13px; background: transparent; border: none;')
            card_layout.addWidget(instr)

            btn = QPushButton('Select Music Library…')
            btn.setMinimumHeight(42)
            btn.setStyleSheet(
                'QPushButton { background-color: #D17D34; color: #ffffff; border: none; '
                'border-radius: 6px; font-size: 13px; font-weight: 600; }'
                'QPushButton:hover { background-color: #be6e2c; }'
                'QPushButton:pressed { background-color: #aa5d21; }'
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
                'color: #7a6a55; font-family: monospace; font-size: 12px; padding: 10px; }'
            )
            fm = QFontMetrics(path_text.font())
            elided_path = fm.elidedText(str(saved_path), Qt.TextElideMode.ElideMiddle, 360)
            path_text.setText(elided_path)
            path_text.setToolTip(str(saved_path))
            card_layout.addWidget(path_text)

            btn = QPushButton('Select Music Library…')
            btn.setMinimumHeight(42)
            btn.setStyleSheet(
                'QPushButton { background-color: #D17D34; color: #ffffff; border: none; '
                'border-radius: 6px; font-size: 13px; font-weight: 600; }'
                'QPushButton:hover { background-color: #be6e2c; }'
                'QPushButton:pressed { background-color: #aa5d21; }'
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
                'color: #f1e3c8; font-family: monospace; font-size: 12px; padding: 10px; }'
            )
            fm = QFontMetrics(path_text.font())
            elided_path = fm.elidedText(str(saved_path), Qt.TextElideMode.ElideMiddle, 360)
            path_text.setText(elided_path)
            path_text.setToolTip(str(saved_path))
            card_layout.addWidget(path_text)

            load_btn = QPushButton('Manage Last Library')
            load_btn.setMinimumHeight(42)
            load_btn.setStyleSheet(
                'QPushButton { background-color: #D17D34; color: #ffffff; border: none; '
                'border-radius: 6px; font-size: 13px; font-weight: 600; }'
                'QPushButton:hover { background-color: #be6e2c; }'
                'QPushButton:pressed { background-color: #aa5d21; }'
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

    # ── Scanning screen (state 1) ─────────────────────────────────────

    def _build_scanning(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(80, 80, 80, 80)

        self._scan_label = QLabel('Scanning library…')
        self._scan_label.setProperty('role', 'subheading')
        self._scan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._scan_count = QLabel('Discovering files…')
        self._scan_count.setProperty('role', 'muted')
        self._scan_count.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._scan_bar = QProgressBar()
        self._scan_bar.setRange(0, 0)   # indeterminate
        self._scan_bar.setFixedWidth(360)
        self._scan_bar.setFixedHeight(8)

        self._scan_cancel = QPushButton('Cancel')
        self._scan_cancel.setProperty('flat', 'true')
        self._scan_cancel.setFixedWidth(100)
        self._scan_cancel.setStyleSheet('QPushButton { color: #C75B5B; } QPushButton:hover { color: #b24c4c; }')
        self._scan_cancel.clicked.connect(self._on_cancel_scan)

        layout.addWidget(self._scan_label)
        layout.addWidget(self._scan_count)
        layout.addWidget(self._scan_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(self._scan_cancel, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

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

    def _populate_dashboard(self) -> None:
        layout = self._dashboard_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

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
            'QPushButton { background: #D17D34; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 0 18px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background: #be6e2c; }'
            'QPushButton:pressed { background: #aa5d21; }'
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

    def _build_action_cards_section(self) -> QWidget:
        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)

        _icons = _ASSETS / 'icons'
        goto_cards = [
            ('01', 'Manage Library',   'Browse and edit your track library', self.classify_requested.emit,    _icons / 'icon-library.svg'),
            ('02', 'Manage Crates',    'Build crates and edit tracks',       self.crates_requested.emit,      _icons / 'icon-crates.svg'),
            ('03', 'Organize Media',   'Manage folders and file locations',  self.organize_requested.emit,    _icons / 'icon-organize.svg'),
        ]

        goto_widget = QWidget()
        goto_grid = QGridLayout(goto_widget)
        goto_grid.setContentsMargins(0, 0, 0, 0)
        goto_grid.setSpacing(10)

        highlight_manage_library = not self._is_classification_complete()
        for col_idx, (step, title, desc, action, icon_path) in enumerate(goto_cards):
            card = _WorkflowCard(
                step, title, desc, action, icon_path=icon_path,
                highlighted=(highlight_manage_library and title == 'Manage Library'),
            )
            goto_grid.addWidget(card, 0, col_idx)

        vbox.addWidget(goto_widget)

        # Create cards — each has its own accent color
        create_defs = [
            {
                'icon': '＋', 'title': 'New Crate', 'desc': 'Start with a fresh crate',
                'action': self.new_crate_requested.emit,
                'accent': self._ORANGE,
                'base':  'QFrame { background-color: #2a2218; border: 0.5px solid #4a3520; border-radius: 10px; }',
                'hover': f'QFrame {{ background-color: #2e2519; border: 0.5px solid {self._ORANGE}; border-radius: 10px; }}',
            },
            {
                'icon': '✦', 'title': 'New Smart Crate', 'desc': 'Create a rule-based crate',
                'action': self.new_smart_crate_requested.emit,
                'accent': self._ORANGE,
                'base':  'QFrame { background-color: #2a2218; border: 0.5px solid #4a3520; border-radius: 10px; }',
                'hover': f'QFrame {{ background-color: #2e2519; border: 0.5px solid {self._ORANGE}; border-radius: 10px; }}',
            },
        ]

        create_widget = QWidget()
        create_grid = QGridLayout(create_widget)
        create_grid.setContentsMargins(0, 0, 0, 0)
        create_grid.setSpacing(10)

        for col_idx, defn in enumerate(create_defs):
            card = _ClickableCard(defn['action'], defn['base'], defn['hover'])
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 16, 14, 16)
            card_layout.setSpacing(4)

            icon_lbl = QLabel(defn['icon'])
            icon_lbl.setStyleSheet(
                f'font-size: 20px; color: {defn["accent"]}; background: transparent; border: none;'
            )
            card_layout.addWidget(icon_lbl)

            title_lbl = QLabel(defn['title'])
            title_lbl.setStyleSheet(
                f'font-size: 13px; font-weight: 500; color: {self._CREAM}; '
                f'background: transparent; border: none;'
            )
            card_layout.addWidget(title_lbl)

            desc_lbl = QLabel(defn['desc'])
            desc_lbl.setStyleSheet(
                'font-size: 11px; color: #7a6a55; background: transparent; border: none;'
            )
            desc_lbl.setWordWrap(True)
            card_layout.addWidget(desc_lbl)

            create_grid.addWidget(card, 0, col_idx)

        vbox.addWidget(create_widget)
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
        self._inventory = []
        self._summary = None
        self._library_path = None
        self._stack.setCurrentIndex(0)
        self.status_message.emit('', '')

    def _on_scan_progress(self, count: int, dir_name: str) -> None:
        self._scan_count.setText(f'{count:,} files found…  ({dir_name})')

    def _on_scan_finished(self, inventory, summary) -> None:
        if self._scan_cancelled:
            return
        self._inventory = inventory
        self._summary   = summary
        elapsed_ms = int(time.time() * 1000) - self._scan_start_ms
        delay = max(0, _MIN_SCAN_DISPLAY_MS - elapsed_ms)
        QTimer.singleShot(delay, self._show_dashboard)

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
            from cratesort.src.core.duplicate_detector import DuplicateDetector
            groups, summary = DuplicateDetector().detect(self._inventory)
            self._dup_groups  = groups
            self._dup_summary = summary
        except Exception:
            self._dup_groups  = []
            self._dup_summary = None

    def _show_dashboard(self) -> None:
        try:
            if self._scan_cancelled or self._summary is None:
                return
            self._check_serato_sync()
            self._run_duplicate_detection()
            self._populate_dashboard()
            self._stack.setCurrentIndex(2)
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
        
        btn = QPushButton('Review && Sync…')
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_review_sync_clicked)
        btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; border-radius: 4px; padding: 6px 14px; font-weight: 600; font-size: 12px; min-width: 170px; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        layout.addWidget(btn)
        
        return banner

    def _on_scan_error(self, message: str) -> None:
        self._scan_label.setText('Scan failed')
        self._scan_count.setText(message)
        self.status_message.emit(f'Scan error: {message}', 'error')

    def _run_scan(self, library_path: Path) -> None:
        self._worker = _ScanWorker(library_path)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.errored.connect(self._on_scan_error)
        self._worker.start()

