from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSettings, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
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

_ASSETS    = Path(__file__).parent.parent.parent / 'assets'
_LOGO_SVG  = _ASSETS / 'logo' / 'cs-logo-mascot-stacked.svg'
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
    def __init__(self, icon: str, target: int, suffix: str, label: str, parent=None):
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

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            'font-size: 16px; color: #7a6a55; background: transparent; border: none;'
        )
        col.addWidget(icon_lbl)

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
    def __init__(self, step: str, title: str, desc: str, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(130)
        self.setStyleSheet(
            'QFrame { background-color: #2F2F2F; border: 1px solid #3a3a3a; border-radius: 10px; }'
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        col = QVBoxLayout(self)
        col.setContentsMargins(18, 20, 18, 20)
        col.setSpacing(4)

        self._step_label = QLabel(step)
        self._step_label.setStyleSheet(
            'font-size: 32px; font-weight: 600; color: #3a3a3a; '
            'letter-spacing: -1px; background: transparent; border: none;'
        )
        col.addWidget(self._step_label)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            'font-size: 14px; font-weight: 500; color: #f1e3c8; '
            'background: transparent; border: none;'
        )
        col.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            'font-size: 11px; color: #7a6a55; background: transparent; border: none;'
        )
        desc_lbl.setWordWrap(True)
        col.addWidget(desc_lbl)

    def enterEvent(self, event):
        self._step_label.setStyleSheet(
            'font-size: 32px; font-weight: 600; color: #D17D34; '
            'letter-spacing: -1px; background: transparent; border: none;'
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._step_label.setStyleSheet(
            'font-size: 32px; font-weight: 600; color: #3a3a3a; '
            'letter-spacing: -1px; background: transparent; border: none;'
        )
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._callback:
            self._callback()


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
    status_message            = pyqtSignal(str, str)  # (message, state)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings      = QSettings(_ORG, _APP)
        self._library_path: Path | None = None
        self._worker: _ScanWorker | None = None
        self._inventory     = []
        self._summary       = None
        self._scan_start_ms = 0
        self._scan_cancelled = False

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        saved_path = Path(self._settings.value('library_path')) if self._settings.value('library_path') else None
        self._stack.addWidget(self._build_welcome(saved_path))  # 0
        self._stack.addWidget(self._build_scanning())           # 1
        self._stack.addWidget(self._build_dashboard())          # 2

        self._stack.setCurrentIndex(0)

    # ── Public API ────────────────────────────────────────────────────

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
        layout.setContentsMargins(60, 60, 60, 60)

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

        layout.addSpacing(8)

        if saved_path is None:
            instr = QLabel(
                'Select the root folder of your music library.\n'
                'CrateSort will scan all media files inside it, including subfolders.'
            )
            instr.setProperty('role', 'muted')
            instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            instr.setWordWrap(True)
            layout.addWidget(instr)

            btn = QPushButton('Select Music Library…')
            btn.setFixedWidth(220)
            btn.setMinimumHeight(42)
            btn.clicked.connect(self._on_select_library)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            last_lbl = QLabel('Last library:')
            last_lbl.setProperty('role', 'muted')
            last_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(last_lbl)

            path_text = QLabel(str(saved_path))
            path_text.setWordWrap(True)
            path_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            path_text.setStyleSheet('font-size: 12px; color: #f1e3c8;')
            layout.addWidget(path_text)

            load_btn = QPushButton('Load Library')
            load_btn.setMinimumHeight(42)

            choose_btn = QPushButton('Choose Different Library')
            choose_btn.setProperty('flat', 'true')
            choose_btn.setMinimumHeight(42)

            btns = QWidget()
            btns_layout = QVBoxLayout(btns)
            btns_layout.setContentsMargins(0, 0, 0, 0)
            btns_layout.setSpacing(8)
            btns_layout.addWidget(load_btn)
            btns_layout.addWidget(choose_btn)
            layout.addWidget(btns)

            always_cb = QCheckBox('Always load without asking')
            always_cb.setStyleSheet('font-size: 12px;')
            layout.addWidget(always_cb, alignment=Qt.AlignmentFlag.AlignCenter)

            def _on_load():
                self._settings.setValue('always_load_last', always_cb.isChecked())
                self._library_path = saved_path
                self.library_path_changed.emit(saved_path)
                self.start_scan(saved_path)

            load_btn.clicked.connect(_on_load)
            choose_btn.clicked.connect(self._on_select_library)

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
    _MUTED    = '#888888'
    _VMUTED   = '#555555'
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

        layout.addWidget(self._build_stat_cards_section(summary, inv))
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
        c0 = _AnimatedStatCard('♪', total_target, '', 'Total Tracks')
        row_layout.addWidget(c0)

        crate_target = 0
        if serato_dir and serato_dir.exists():
            subcrates = serato_dir / 'Subcrates'
            if subcrates.exists():
                crate_target = len(list(subcrates.rglob('*.crate')))
        c1 = _AnimatedStatCard('⊞', crate_target, '', 'Total Crates')
        row_layout.addWidget(c1)

        artists_target = len(summary.unique_artists) if summary else 0
        c2 = _AnimatedStatCard('♟', artists_target, '', 'Unique Artists')
        row_layout.addWidget(c2)

        hours_target = 0
        if inv:
            total_secs = sum(r.duration for r in inv if r.duration)
            hours_target = int(total_secs / 3600)
        c3 = _AnimatedStatCard('◷', hours_target, 'h', 'Hours of Music')
        row_layout.addWidget(c3)

        vbox.addWidget(row_widget)

        cards = [c0, c1, c2, c3]
        QTimer.singleShot(100, lambda: cards[0].start_animation(1600))
        QTimer.singleShot(220, lambda: cards[1].start_animation(1400))
        QTimer.singleShot(340, lambda: cards[2].start_animation(1500))
        QTimer.singleShot(460, lambda: cards[3].start_animation(1300))

        return outer

    def _build_action_cards_section(self) -> QWidget:
        _base_create = (
            'QFrame { background-color: #2a2218; border: 0.5px solid #4a3520; border-radius: 10px; }'
        )
        _hover_create = (
            f'QFrame {{ background-color: #2a2218; border: 0.5px solid {self._ORANGE}; '
            f'border-radius: 10px; }}'
        )

        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)

        goto_cards = [
            ('01', 'Change Library',   'Set active library path',          self._on_select_library),
            ('02', 'Classify Library', 'Reassign artists and genres',       self.classify_requested.emit),
            ('03', 'Manage Crates',    'Build crates and edit tracks',      self.crates_requested.emit),
            ('04', 'Organize Media',   'Manage folders and file locations', self.organize_requested.emit),
        ]

        goto_widget = QWidget()
        goto_grid = QGridLayout(goto_widget)
        goto_grid.setContentsMargins(0, 0, 0, 0)
        goto_grid.setSpacing(10)

        for col_idx, (step, title, desc, action) in enumerate(goto_cards):
            card = _WorkflowCard(step, title, desc, action)
            goto_grid.addWidget(card, 0, col_idx)

        vbox.addWidget(goto_widget)

        create_cards = [
            ('＋', 'New Crate',       'Start with a fresh crate',  self.new_crate_requested.emit),
            ('✦',  'New Smart Crate', 'Create a rule-based crate', self.new_smart_crate_requested.emit),
        ]

        create_widget = QWidget()
        create_grid = QGridLayout(create_widget)
        create_grid.setContentsMargins(0, 0, 0, 0)
        create_grid.setSpacing(10)

        for col_idx, (icon, title, desc, action) in enumerate(create_cards):
            card = _ClickableCard(action, _base_create, _hover_create)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 16, 14, 16)
            card_layout.setSpacing(4)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(
                f'font-size: 20px; color: {self._ORANGE}; background: transparent; border: none;'
            )
            card_layout.addWidget(icon_lbl)

            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                f'font-size: 13px; font-weight: 500; color: {self._CREAM}; '
                f'background: transparent; border: none;'
            )
            card_layout.addWidget(title_lbl)

            desc_lbl = QLabel(desc)
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
            current_crates: dict = {}
            subcrates = serato_dir / 'Subcrates'
            if subcrates.exists():
                for crate_file in subcrates.rglob('*.crate'):
                    try:
                        from cratesort.src.serato.crate_reader import CrateReader
                        reader = CrateReader(serato_dir)
                        tracks, _ = reader._read_tracks(crate_file)
                        current_crates[str(crate_file)] = len(tracks)
                    except Exception:
                        current_crates[str(crate_file)] = None

            checkpoint = load_checkpoint(serato_dir)
            changes = detect_changes(current_crates, checkpoint) if checkpoint else []
            save_checkpoint(serato_dir, current_crates)

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
                row_h = QHBoxLayout(row)
                row_h.setContentsMargins(0, 8, 0, 8)
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

        # Right: teal dot + synced text
        dot = QLabel('●')
        dot.setStyleSheet(
            f'color: {self._TEAL}; font-size: 9px; background: transparent; border: none;'
        )
        h.addWidget(dot)

        sync_lbl = QLabel('  Library synced')
        sync_lbl.setStyleSheet(
            f'color: {self._TEAL}; font-size: 11px; background: transparent; border: none;'
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

    def _show_dashboard(self) -> None:
        try:
            if self._scan_cancelled or self._summary is None:
                return
            self._populate_dashboard()
            self._stack.setCurrentIndex(2)
            self.scan_finished.emit()
            self.status_message.emit('Library synced. Ready.', 'green')
        except Exception as exc:
            import traceback
            print(f'[CrateSort] _show_dashboard error: {exc}\n{traceback.format_exc()}')

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

