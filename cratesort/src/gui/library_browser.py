from __future__ import annotations

import json
import subprocess
import sys as _sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QByteArray, QEvent, QRect, QSettings, QSize, QTimer, pyqtSignal

from cratesort.src.gui.overlays import _CrateSortDialog, _ov_alert, _create_dialog_layout
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap

try:
    from PyQt6.QtSvgWidgets import QSvgWidget as _QSvgWidget  # noqa: F401 (defensive import)
except ImportError:
    pass
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem,
    QMenu, QProgressBar, QPushButton, QSplitter, QStackedWidget,
    QStyle, QStyledItemDelegate,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

# ---------------------------------------------------------------------------
# Column indices
# ---------------------------------------------------------------------------
LC_ARTIST   = 0   # Artist name | Track title
LC_TRACKS   = 1   # Track count | (blank)
LC_ALBUM    = 2   # (blank)     | Album
LC_GENRE    = 3   # Genre (classified or raw)
LC_TAGS     = 4   # Style tags
LC_DURATION = 5   # (blank)     | M:SS
LC_FORMAT   = 6   # (blank)     | MP3/WAV…
LC_BPM      = 7   # (blank)     | BPM
LC_YEAR     = 8   # (blank)     | Year
LC_BITRATE  = 9   # (blank)     | kbps
LC_COMMENT  = 10  # (blank)     | Comments
LC_PATH     = 11  # Common path | Full path
# Classify mode columns — appended at end, hidden outside classify mode
LC_CLS_PROPOSED = 12
LC_CLS_CONF     = 13
LC_CLS_STATUS   = 14

HEADERS = [
    'Artist', 'Tracks', 'Album', 'Genre', 'Style Tags',
    'Duration', 'Format', 'BPM', 'Year', 'Bitrate', 'Comments', 'File Path',
    'Proposed Genre', 'Confidence', 'Status',
]

_MUTED   = '#a89b85'
_DUMMY   = '__LAZY__'

# Taxonomy-validated genres — only these 13 are accepted for ID3 fallback bucketing.
# Keys are lowercase for case-insensitive matching; values are the canonical forms.
_VALID_GENRES_LOWER: dict[str, str] = {g.lower(): g for g in {
    'Blues', 'Country', 'Electronic', 'Funk/Soul', 'Hip-Hop/Rap',
    'House', 'Jazz', 'R&B', 'Reggae', 'Rock', 'Seasonal',
    'Specialty', 'Traditional',
}}

_SETTINGS_KEY = 'library_browser_header_state'


def _make_person_icon():
    """Painted person silhouette — circle head + shoulder ellipse, dual-state.
    18×14 pixmap: drawing occupies left 14px, right 4px is transparent padding."""
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
    def _pm(color: str) -> QPixmap:
        px = QPixmap(18, 14)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(4, 0, 6, 6)    # head
        p.drawEllipse(1, 7, 12, 10)  # shoulders
        p.end()
        return px
    icon = QIcon()
    icon.addPixmap(_pm(_MUTED),    QIcon.Mode.Normal)
    icon.addPixmap(_pm('#2F2F2F'), QIcon.Mode.Selected)
    return icon


def _make_note_icon():
    """Music note ♪ dual-state: cream normal, dark on selection. 11×14 (tighter gap)."""
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
    def _pm(color: str) -> QPixmap:
        pm = QPixmap(9, 14)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        f = p.font()
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, '♪')
        p.end()
        return pm
    icon = QIcon()
    icon.addPixmap(_pm(_MUTED),    QIcon.Mode.Normal)
    icon.addPixmap(_pm('#2F2F2F'), QIcon.Mode.Selected)
    return icon


_ARTIST_ICON = None
_TRACK_ICON  = None


def _get_artist_icon():
    global _ARTIST_ICON
    if _ARTIST_ICON is None:
        _ARTIST_ICON = _make_person_icon()
    return _ARTIST_ICON


def _get_track_icon():
    global _TRACK_ICON
    if _TRACK_ICON is None:
        _TRACK_ICON = _make_note_icon()
    return _TRACK_ICON

# Editable track columns (field name for storage).
# LC_GENRE and LC_ARTIST (as artist) are NOT here — use right-click menus only.
# LC_ARTIST on a track row shows the title, which IS editable.
_EDITABLE = {
    LC_ARTIST:  'title',    # track rows show title in this col
    LC_ALBUM:   'album',
    # LC_GENRE omitted — right-click "Change Genre..." only
    LC_TAGS:    'tags',
    LC_BPM:     'bpm',
    LC_YEAR:    'year',
    LC_COMMENT: 'comment',
}


# SVG icon path for the classify-mode banner
_BANNER_ICON_PATH = Path(__file__).resolve().parent.parent.parent / 'assets' / 'icons' / 'icon-banner.svg'


def _tint_svg_icon(icon_path: Path, size: int, color: str) -> QPixmap:
    """Load an SVG as a QPixmap, tint it to the given hex color, and return it."""
    px = QPixmap(str(icon_path)).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if px.isNull():
        return px
    tinted = QPixmap(px.size())
    tinted.fill(Qt.GlobalColor.transparent)
    p = QPainter(tinted)
    p.drawPixmap(0, 0, px)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(tinted.rect(), QColor(color))
    p.end()
    return tinted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_dur(seconds: Optional[float]) -> str:
    if not seconds:
        return '—'
    return f'{int(seconds // 60)}:{int(seconds % 60):02d}'


def _show_in_finder(file_path: str) -> None:
    try:
        if _sys.platform == 'darwin':
            subprocess.run(['open', '-R', file_path], check=False)
        elif _sys.platform == 'win32':
            subprocess.run(['explorer', f'/select,{file_path}'], check=False)
        else:
            subprocess.run(['xdg-open', str(Path(file_path).parent)], check=False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Genre Sidebar Delegate
# ---------------------------------------------------------------------------

class GenreSidebarDelegate(QStyledItemDelegate):
    """
    Custom-painted delegate for the genre sidebar list.
    Paints two-line genre items (name + artist/track subline) with correct
    selection/hover states, orange left bar, and red tint for Unclassified.
    """

    _HEIGHTS = {'all': 36, 'genre': 48, 'unclassified': 56}

    def sizeHint(self, option, index) -> QSize:
        item_type = index.data(Qt.ItemDataRole.UserRole + 4) or 'genre'
        return QSize(0, self._HEIGHTS.get(item_type, 48))

    def paint(self, painter, option, index) -> None:
        painter.save()
        try:
            self._do_paint(painter, option, index)
        finally:
            painter.restore()

    def _do_paint(self, painter, option, index) -> None:
        item_type = index.data(Qt.ItemDataRole.UserRole + 4) or 'genre'
        name      = index.data(Qt.ItemDataRole.UserRole + 1) or ''
        artists   = index.data(Qt.ItemDataRole.UserRole + 2) or 0
        tracks    = index.data(Qt.ItemDataRole.UserRole + 3) or 0
        is_uc  = item_type == 'unclassified'
        is_all = item_type == 'all'
        is_sel = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hov = bool(option.state & QStyle.StateFlag.State_MouseOver)

        rect = QRect(option.rect)

        # Separator line for unclassified (1px at top+4, then shift rect down 8px)
        if is_uc:
            painter.setPen(QPen(QColor('#2a2a2a'), 1))
            painter.drawLine(rect.left(), rect.top() + 4, rect.right(), rect.top() + 4)
            rect = rect.adjusted(0, 8, 0, 0)

        # Background
        if is_sel:
            bg = '#2a1515' if is_uc else '#573d26'
        elif is_hov:
            bg = '#251a1a' if is_uc else '#252525'
        elif is_uc:
            bg = '#1f1a1a'
        else:
            bg = None
        if bg:
            painter.fillRect(rect, QColor(bg))

        # Left border bar (selected only)
        if is_sel:
            bar_color = '#C75B5B' if is_uc else '#D17D34'
            painter.fillRect(QRect(rect.left(), rect.top(), 5, rect.height()), QColor(bar_color))

        # Text colours
        if is_sel or is_hov:
            name_color = '#f1e3c8'
        elif is_uc:
            name_color = '#C75B5B'
        else:
            name_color = '#a89b85'

        if is_uc:
            sub_color = '#C75B5B'
        elif is_sel:
            sub_color = '#a07850'
        else:
            sub_color = '#a89b85'

        left_pad  = 14
        right_pad = 10
        text_x = rect.left() + left_pad
        text_w = max(1, rect.width() - left_pad - right_pad)

        name_y_off = 4 if is_all else 8
        sub_y_off  = 18 if is_all else 26

        # Name
        name_font = QFont()
        name_font.setPixelSize(11 if is_all else 12)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor(name_color))
        painter.drawText(
            QRect(text_x, rect.top() + name_y_off, text_w, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            name,
        )

        # Subline
        sub_font = QFont()
        sub_font.setPixelSize(10)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        painter.setPen(QColor(sub_color))
        painter.drawText(
            QRect(text_x, rect.top() + sub_y_off, text_w, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f'{artists:,} artists · {tracks:,} tracks',
        )


# ---------------------------------------------------------------------------
# Unsaved classify-mode changes dialog
# ---------------------------------------------------------------------------

class _UnsavedChangesDialog(_CrateSortDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._elastic = False
        self.setMinimumWidth(480)

        # Use standard Red accent layout (warning/danger/discard)
        layout = _create_dialog_layout(self, '#C75B5B')

        headline = QLabel('Unsaved Classification Changes')
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        body = QLabel()
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setText('<div style="line-height: 145%;">You have unsaved changes in Classify mode. If you leave now, your corrections will be lost.</div>')
        body.setWordWrap(True)
        body.setStyleSheet(
            'color: #d5c7ad; font-size: 14px; background: transparent; border: none;'
        )
        layout.addWidget(body)
        layout.addSpacing(12)

        btns = QHBoxLayout()
        btns.setSpacing(12)

        leave_btn = QPushButton('Leave Anyway')
        leave_btn.setFixedHeight(36)
        leave_btn.setStyleSheet(
            'QPushButton { background: #C75B5B; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background: #b24c4c; }'
            'QPushButton:pressed { background: #9c3b3b; }'
        )
        leave_btn.clicked.connect(self.accept)

        stay_btn = QPushButton('Stay and Finish')
        stay_btn.setFixedHeight(36)
        stay_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        stay_btn.clicked.connect(self.reject)

        btns.addWidget(leave_btn)
        btns.addStretch()
        btns.addWidget(stay_btn)
        layout.addLayout(btns)

# ---------------------------------------------------------------------------
# _AnimatedStatCardWidget — count-up stat card for the Analyze Library modal
# ---------------------------------------------------------------------------

class _AnimatedStatCardWidget(QFrame):
    """Smoothly animates a numeric value towards a moving target at 60 fps."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._current_value = 0
        self._target_value  = 0

        self.setStyleSheet(
            'QFrame { background-color: #1a1a1a; border: 1px solid #444444; '
            'border-radius: 8px; }'
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value_label = QLabel('0')
        self._value_label.setProperty('role', 'stat')
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(
            'font-size: 22px; font-weight: 600; color: #f1e3c8; '
            'background: transparent; border: none;'
        )
        layout.addWidget(self._value_label)

        self._title_label = QLabel(title)
        self._title_label.setProperty('role', 'stat_label')
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            'font-size: 10px; color: #a89b85; letter-spacing: 0.06em; '
            'background: transparent; border: none;'
        )
        layout.addWidget(self._title_label)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def update_target(self, target: int) -> None:
        self._target_value = target
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        diff = self._target_value - self._current_value
        if diff == 0:
            self._timer.stop()
            return
        if diff > 0:
            step = max(1, int(diff * 0.15))
            self._current_value = min(self._target_value, self._current_value + step)
        else:
            step = min(-1, int(diff * 0.15))
            self._current_value = max(self._target_value, self._current_value + step)
        self._value_label.setText(f'{self._current_value:,}')


# ---------------------------------------------------------------------------
# _AnalyzeLibraryModal — frameless modal shown during first-run classification
# ---------------------------------------------------------------------------

class _AnalyzeLibraryModal(_CrateSortDialog):
    """Frameless 520×280 card displayed over the overlay during auto-classify."""

    review_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(520, 320)

        # Use standard Teal accent layout (safe action/progress)
        layout = _create_dialog_layout(self, '#428175')

        headline = QLabel('Analyzing Library')
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        subtitle = QLabel()
        subtitle.setTextFormat(Qt.TextFormat.RichText)
        subtitle.setText('<div style="line-height: 145%; text-align: center;">Analyzing your DJ library and media files – validating artists and genres...</div>')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            'color: #d5c7ad; font-size: 13px; background: transparent; border: none;'
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        # Stat cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._card_tracks  = _AnimatedStatCardWidget('Tracks Analyzed',   self)
        self._card_artists = _AnimatedStatCardWidget('Artists Classified', self)
        self._card_fixes   = _AnimatedStatCardWidget('Corrections Made',   self)
        cards_row.addWidget(self._card_tracks)
        cards_row.addWidget(self._card_artists)
        cards_row.addWidget(self._card_fixes)
        layout.addLayout(cards_row)

        # Action stack — fixed height keeps modal dimensions stable on transition
        self._action_stack = QStackedWidget()
        self._action_stack.setFixedHeight(45)
        self._action_stack.setStyleSheet('background: transparent;')

        # Page 0: progress bar
        pb_wrapper = QWidget()
        pb_layout  = QVBoxLayout(pb_wrapper)
        pb_layout.setContentsMargins(0, 16, 0, 0)
        pb_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            'QProgressBar { background-color: #383838; border: none; border-radius: 2px; }'
            'QProgressBar::chunk { background-color: #428175; border-radius: 2px; }'
        )
        pb_layout.addWidget(self._progress_bar)
        self._action_stack.addWidget(pb_wrapper)   # index 0

        # Page 1: Review Results button
        btn_wrapper = QWidget()
        btn_layout  = QHBoxLayout(btn_wrapper)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._review_btn = QPushButton('Review Results')
        self._review_btn.setFixedSize(180, 36)
        self._review_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; '
            'border: none; border-radius: 6px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        self._review_btn.clicked.connect(self.review_requested.emit)
        btn_layout.addWidget(self._review_btn)
        self._action_stack.addWidget(btn_wrapper)  # index 1

        layout.addWidget(self._action_stack)

    def update_stats(self, tracks_count: int, artists_count: int) -> None:
        self._card_tracks.update_target(tracks_count)
        self._card_artists.update_target(artists_count)
        # TODO: Corrections Made — real-time comparison signal not yet available

    def update_percent(self, percent: int) -> None:
        self._progress_bar.setValue(percent)

    def on_classification_complete(self) -> None:
        self._action_stack.setCurrentIndex(1)


def _show_dark_alert(parent_window: QWidget, title: str, body: str) -> None:
    """Thin wrapper — delegates to the canonical _ov_alert from overlays."""
    _ov_alert(parent_window, title, body)


# ---------------------------------------------------------------------------
# Library Browser view
# ---------------------------------------------------------------------------

class LibraryBrowserView(QWidget):
    """
    Artist-nested library browser.
    Artist rows expand to show track children (lazy-loaded on first expand).
    """

    # Emitted when a track is selected (for album art panel)
    track_selected   = pyqtSignal(str)   # file path
    album_art_requested = pyqtSignal(str)
    # Emitted after an inline edit is committed (file_path, field, new_value)
    track_field_changed = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_genre: dict[str, tuple[str, str]] = {}  # artist → (genre, conf)
        self._session_artists: dict[str, str] = {}            # track_path → artist
        self._track_overrides: dict[str, str] = {}            # file_path → overridden genre
        self._has_classification = False
        self._library_path: Optional[Path] = None
        self._loaded_inv_id: Optional[int] = None
        self._inventory = []
        self._edits: dict[str, dict[str, str]] = {}
        self._settings = QSettings('JWBC', 'CrateSort')
        # Genre sidebar selection
        self._sidebar_genre: str = 'All'
        # Classify mode state
        self._classify_mode: bool = False
        self._classify_session = None
        self._classify_results: dict[str, tuple[str, str]] = {}  # artist → (genre, conf)
        self._classify_worker = None
        # Tracks the last genre edit for post-sidebar-rebuild navigation
        self._last_edited_artist:  Optional[str] = None
        self._last_assigned_genre: Optional[str] = None

        # Auto-classify modal state
        self._analyze_modal:          Optional[_AnalyzeLibraryModal] = None
        self._auto_classify_session                                   = None
        self._processed_artists:      set                            = set()
        self._processed_tracks_count: int                            = 0
        self._auto_artist_tracks_map: dict                           = {}
        self._auto_dj_tools_count:    int                            = 0

        # Inline editor state — at most one open at a time
        self._edit_item:     Optional[QTreeWidgetItem] = None
        self._edit_col:      int = -1
        self._edit_widget:   Optional[QLineEdit] = None
        self._edit_original: str = ''

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_empty())    # 0
        self._stack.addWidget(self._build_browser())  # 1
        self._stack.setCurrentIndex(0)

    # ── Public ────────────────────────────────────────────────────────

    def on_scan_finished(self, inventory, library_path: Path) -> None:
        """Called by MainWindow after a background scan completes.
        Routes through load() so session variables are always fully initialized."""
        self.load(inventory, library_path)

    def load(self, inventory, library_path: Path) -> None:
        """
        Load (or refresh) from scanner inventory + optional classification session.

        The early-return cache has been removed intentionally: after the user runs
        classification and navigates here, the same inventory object is reused (same
        id()) but the session file on disk has changed.  Always reload the session.
        """
        self._library_path  = library_path
        self._loaded_inv_id = id(inventory)
        self._inventory     = list(inventory)

        # Load classification session
        self._session_genre = {}
        self._session_artists = {}   # track_path (str) → entry.artist (str)
        self._track_overrides = {}
        self._has_classification = False
        session_file = library_path / '_CrateSort' / 'classification_session.json'
        if session_file.exists():
            try:
                from cratesort.src.gui.classifier_view import (
                    ClassificationSession, _extract_primary_artist, _canonical_artist,
                )
                session = ClassificationSession.load(session_file)
                for entry in session.entries:
                    self._session_genre[entry.artist] = (entry.display_genre, entry.confidence)
                    for track in entry.tracks:
                        self._session_artists[track.path] = entry.artist
                        if track.genre_tag:
                            self._track_overrides[track.path] = track.genre_tag
                self._has_classification = bool(self._session_genre)
                print(f'[LibraryBrowser] _track_overrides ({len(self._track_overrides)} entries):')
                for p, g in list(self._track_overrides.items())[:10]:
                    print(f'  {Path(p).name} → {g}')
            except Exception as exc:
                import traceback
                print(f'[LibraryBrowser] Session load error: {exc}\n{traceback.format_exc()}')

        self._populate_filters()
        self._edits = {}
        self._load_edits()
        self._rebuild_tree()
        self._populate_genre_sidebar()
        self._stack.setCurrentIndex(1)

        # Auto-classify if the user has not yet confirmed any genre assignments
        if not self._is_classification_complete() and self.isVisible():
            self._on_classify_clicked(auto_classify=True)

    # ── Empty state ───────────────────────────────────────────────────

    def _build_empty(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h = QLabel('Library Browser')
        h.setProperty('role', 'heading')
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s = QLabel('Load a library from the Dashboard to browse your tracks.')
        s.setProperty('role', 'muted')
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(h)
        layout.addSpacing(8)
        layout.addWidget(s)
        return w

    # ── Browser layout ────────────────────────────────────────────────

    def _build_browser(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Classify mode banner (hidden outside classify mode)
        self._classify_banner_frame = self._build_classify_banner()
        outer.addWidget(self._classify_banner_frame)

        # Toolbar
        outer.addWidget(self._build_toolbar())

        # Content row: resizable genre sidebar + tree via splitter
        self._sidebar_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._sidebar_splitter.setHandleWidth(4)
        self._sidebar_splitter.setStyleSheet(
            'QSplitter::handle { background-color: #2a2a2a; }'
        )
        self._sidebar_splitter.addWidget(self._build_genre_sidebar())

        # Tree — 15 columns; classify mode columns hidden until needed
        self._tree = QTreeWidget()
        self._tree.setColumnCount(len(HEADERS))
        self._tree.setHeaderLabels(HEADERS)
        self._tree.header().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._tree.header().setSectionsMovable(True)
        self._tree.header().setSectionsClickable(True)
        self._tree.header().setSortIndicatorShown(True)
        self._tree.header().setStretchLastSection(False)
        self._tree.setSortingEnabled(True)
        self._tree.setAlternatingRowColors(True)
        from PyQt6.QtGui import QPalette as _QPalette
        _lb_pal = self._tree.palette()
        _lb_pal.setColor(_QPalette.ColorRole.Base,          QColor('#242424'))
        _lb_pal.setColor(_QPalette.ColorRole.AlternateBase, QColor('#2a2a2a'))
        self._tree.setPalette(_lb_pal)
        self._tree.setStyleSheet(
            'QTreeWidget { gridline-color: #383838; }'
            'QTreeWidget::item { padding: 4px 4px 4px 2px; border-radius: 0;'
            ' border-right: 1px solid #383838; border-bottom: 1px solid #383838; }'
            'QTreeWidget::item:selected { border-right: 1px solid #383838;'
            ' border-bottom: 1px solid #383838; }'
            'QTreeWidget::branch { border-bottom: 1px solid #383838; background: transparent; }'
            'QTreeWidget::branch:hover { background: #383838; }'
            'QTreeWidget::branch:selected { background: #D17D34; }'
        )
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(12)
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.viewport().installEventFilter(self)

        # Hide classify mode columns until classify mode is active
        self._tree.setColumnHidden(LC_CLS_PROPOSED, True)
        self._tree.setColumnHidden(LC_CLS_CONF,     True)
        self._tree.setColumnHidden(LC_CLS_STATUS,   True)

        # Restore column order from QSettings
        saved = self._settings.value(_SETTINGS_KEY)
        if saved:
            self._tree.header().restoreState(saved)

        # Wrap tree in a stack so we can show an empty state over it
        self._track_stack = QStackedWidget()
        self._track_stack.addWidget(self._build_library_empty_state())  # index 0
        self._track_stack.addWidget(self._tree)                          # index 1
        self._track_stack.setCurrentIndex(1)

        self._sidebar_splitter.addWidget(self._track_stack)
        self._sidebar_splitter.setStretchFactor(0, 0)
        self._sidebar_splitter.setStretchFactor(1, 1)
        _saved_w = self._settings.value('library/sidebar_width', 200, type=int)
        self._sidebar_splitter.setSizes([_saved_w, 100000])
        self._sidebar_splitter.splitterMoved.connect(
            lambda: self._settings.setValue(
                'library/sidebar_width', self._sidebar_splitter.sizes()[0]
            )
        )
        outer.addWidget(self._sidebar_splitter, stretch=1)

        footer = QFrame()
        footer.setStyleSheet('QFrame { background: #2F2F2F; border-top: 1px solid #444; }')
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 6, 16, 6)
        self._count_label = QLabel()
        self._count_label.setStyleSheet('color: #a89b85; font-size: 12px;')
        fl.addWidget(self._count_label)
        fl.addStretch()
        outer.addWidget(footer)

        return w

    def _build_classify_banner(self) -> QFrame:
        """Teal banner visible only while classify mode is active."""
        frame = QFrame()
        frame.setVisible(False)
        frame.setStyleSheet(
            'QFrame { background: #1a3530; border-left: 3px solid #428175; border-bottom: 1px solid #2d4a44; }'
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)

        icon_px = _tint_svg_icon(_BANNER_ICON_PATH, 16, '#f1e3c8')
        if not icon_px.isNull():
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon_px)
            icon_lbl.setFixedSize(16, 16)
            icon_lbl.setStyleSheet('background: transparent; border: none;')
            row.addWidget(icon_lbl)

        msg = QLabel("This is your library how we see it — review the artists and their nested files. Right-click/double-click an artist or their tracks to correct anything that looks off. Not sure about something? Change its genre to 'Unclassified' and move on. Your files are not touched until you reorganize.")
        msg.setWordWrap(True)
        msg.setStyleSheet(
            'color: #7bbdad; font-size: 12px; background: transparent; border: none;'
        )
        row.addWidget(msg, stretch=1)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #7bbdad; '
            'border: 1px solid #2d4a44; border-radius: 4px; padding: 4px 12px; font-size: 11px; }'
            'QPushButton:hover { background: rgba(45,74,68,0.4); }'
        )
        cancel_btn.clicked.connect(self._exit_classify_mode_cancel)
        row.addWidget(cancel_btn)

        accept_btn = QPushButton('Accept Reclassifications')
        accept_btn.setStyleSheet(
            'QPushButton { background: #428175; color: #f1e3c8; border: none; '
            'border-radius: 4px; padding: 4px 14px; font-size: 11px; font-weight: 500; }'
            'QPushButton:hover { background: #38706a; }'
            'QPushButton:pressed { background: #2d6358; }'
        )
        accept_btn.clicked.connect(self._exit_classify_mode_accept)
        row.addWidget(accept_btn)

        return frame

    def _build_toolbar(self) -> QFrame:
        tb = QFrame()
        tb.setStyleSheet('QFrame { background: #252525; border-bottom: 1px solid #444; }')
        row = QHBoxLayout(tb)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText('Search artist, title, album…')
        self._search.setMaximumWidth(260)
        self._search.textChanged.connect(self._apply_filter)
        row.addWidget(self._search)

        self._format_cb = QComboBox()
        self._format_cb.setMinimumWidth(110)
        self._format_cb.currentTextChanged.connect(self._apply_filter)
        row.addWidget(self._format_cb)

        row.addStretch()

        clear = QPushButton('Clear Filters')
        clear.setProperty('flat', 'true')
        clear.clicked.connect(self._clear_filters)
        row.addWidget(clear)

        self._classify_btn = QPushButton('Classify Library')
        self._classify_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #f1e3c8; '
            'font-size: 11px; font-weight: 500; border: none; border-radius: 4px; '
            'padding: 6px 12px; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
            'QPushButton:disabled { background-color: #2a3a37; color: #5a8a80; }'
        )
        self._classify_btn.clicked.connect(self._on_classify_clicked)
        row.addWidget(self._classify_btn)

        return tb

    def _build_library_empty_state(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 40, 40, 40)

        icon_lbl = QLabel('♪')
        icon_lbl.setStyleSheet('font-size: 48px; color: #a89b85; background: transparent;')
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        heading = QLabel("Your library hasn't been classified yet.")
        heading.setStyleSheet(
            'font-size: 14px; font-weight: 500; color: #f1e3c8; background: transparent;'
        )
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setWordWrap(True)
        layout.addWidget(heading)

        subline = QLabel(
            'Hit Classify Library to assign genres, clean up filenames, '
            'and get your library organized.'
        )
        subline.setStyleSheet('font-size: 12px; color: #a89b85; background: transparent;')
        subline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subline.setWordWrap(True)
        subline.setMaximumWidth(380)
        layout.addWidget(subline, alignment=Qt.AlignmentFlag.AlignCenter)

        classify_btn = QPushButton('Classify Library')
        classify_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #f1e3c8; '
            'font-size: 11px; font-weight: 500; border: none; border-radius: 4px; '
            'padding: 8px 20px; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        classify_btn.clicked.connect(self._on_classify_clicked)
        layout.addWidget(classify_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    def _update_empty_state(self) -> None:
        """Show the empty state when no genres are classified, tree otherwise."""
        if not hasattr(self, '_track_stack'):
            return
        if self._classify_mode:
            self._track_stack.setCurrentIndex(1)
            return
        _UC = {'', '—', 'Unclassified', 'Untagged'}
        has_genres = any(
            (self._tree.topLevelItem(i).data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or '')
            not in _UC
            for i in range(self._tree.topLevelItemCount())
        )
        self._track_stack.setCurrentIndex(1 if has_genres else 0)

    def _count_unclassified_artists(self) -> int:
        _UC = {'', '—', 'Unclassified', 'Untagged'}
        count = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
            if genre in _UC:
                count += 1
        return count

    def has_unsaved_classify_changes(self) -> bool:
        return self._classify_mode

    def _is_classification_complete(self) -> bool:
        if not self._library_path:
            return False
        flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
        return flag_path.exists()

    def _build_genre_sidebar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('genre_sidebar')
        frame.setMinimumWidth(160)
        frame.setMaximumWidth(320)
        frame.setStyleSheet(
            'QFrame#genre_sidebar { background-color: #1e1e1e; border: none; }'
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel('GENRES')
        header.setStyleSheet(
            'color: #a89b85; font-size: 9px; letter-spacing: 1px; '
            'padding: 12px 14px 8px; background: transparent; border: none;'
        )
        layout.addWidget(header)

        self._genre_sidebar_list = QListWidget()
        self._genre_sidebar_list.setStyleSheet(
            'QListWidget { background: transparent; border: none; outline: none; }'
            'QListWidget::item { padding: 0; border: none; }'
        )
        self._genre_sidebar_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self._genre_sidebar_list.setItemDelegate(
            GenreSidebarDelegate(self._genre_sidebar_list)
        )
        self._genre_sidebar_list.setMouseTracking(True)
        self._genre_sidebar_list.viewport().setMouseTracking(True)
        self._genre_sidebar_list.currentItemChanged.connect(
            self._on_sidebar_genre_changed
        )
        layout.addWidget(self._genre_sidebar_list, stretch=1)

        return frame

    def _populate_genre_sidebar(self) -> None:
        self._genre_sidebar_list.blockSignals(True)
        self._genre_sidebar_list.clear()

        genre_artist_count: dict[str, int] = {}
        genre_track_count: dict[str, int] = {}
        unclassified_artists = 0
        unclassified_tracks = 0

        _UC = {'', '—', 'Unclassified', 'Untagged'}
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            tracks = data.get('tracks', [])
            genre = top.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
            if genre in _UC:
                unclassified_artists += 1
                unclassified_tracks += len(tracks)
            else:
                genre_artist_count[genre] = genre_artist_count.get(genre, 0) + 1
                genre_track_count[genre] = genre_track_count.get(genre, 0) + len(tracks)

        total_artists = self._tree.topLevelItemCount()
        total_tracks = len(self._inventory)

        def _make_item(key: str, name: str, artist_c: int, track_c: int, itype: str) -> QListWidgetItem:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole,     key)
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            item.setData(Qt.ItemDataRole.UserRole + 2, artist_c)
            item.setData(Qt.ItemDataRole.UserRole + 3, track_c)
            item.setData(Qt.ItemDataRole.UserRole + 4, itype)
            return item

        self._genre_sidebar_list.addItem(
            _make_item('All', 'All', total_artists, total_tracks, 'all')
        )

        for genre in sorted(genre_artist_count.keys()):
            self._genre_sidebar_list.addItem(
                _make_item(genre, genre, genre_artist_count[genre], genre_track_count[genre], 'genre')
            )

        if unclassified_artists > 0:
            self._genre_sidebar_list.addItem(
                _make_item('Unclassified', 'Unclassified', unclassified_artists, unclassified_tracks, 'unclassified')
            )

        # Restore current selection
        for i in range(self._genre_sidebar_list.count()):
            it = self._genre_sidebar_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == self._sidebar_genre:
                self._genre_sidebar_list.setCurrentItem(it)
                break
        else:
            self._genre_sidebar_list.setCurrentRow(0)

        self._genre_sidebar_list.blockSignals(False)

        # Post-edit navigation: follow the artist to its new genre bucket if applicable.
        dest_genre  = self._last_assigned_genre
        dest_artist = self._last_edited_artist
        if dest_genre is not None and dest_artist is not None:
            self._last_edited_artist  = None
            self._last_assigned_genre = None

            # Navigate when the user is viewing a specific bucket that is no longer
            # the destination (skip navigation when viewing "All").
            navigate = (
                self._sidebar_genre != 'All'
                and self._sidebar_genre != dest_genre
            )

            if navigate:
                self._sidebar_genre = dest_genre
                self._genre_sidebar_list.blockSignals(True)
                for i in range(self._genre_sidebar_list.count()):
                    it = self._genre_sidebar_list.item(i)
                    if it.data(Qt.ItemDataRole.UserRole) == dest_genre:
                        self._genre_sidebar_list.setCurrentItem(it)
                        break
                self._genre_sidebar_list.blockSignals(False)

            # Always re-apply filter so row visibilities and status counts are current.
            self._apply_filter()

            if navigate:
                for i in range(self._tree.topLevelItemCount()):
                    top = self._tree.topLevelItem(i)
                    top_data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
                    if top_data.get('artist', '') == dest_artist:
                        self._tree.clearSelection()
                        top.setSelected(True)
                        self._tree.setCurrentItem(top)
                        self._tree.scrollToItem(top)
                        break

    def _on_sidebar_genre_changed(
        self, current: QListWidgetItem, _previous: QListWidgetItem
    ) -> None:
        if current:
            self._sidebar_genre = current.data(Qt.ItemDataRole.UserRole) or 'All'
            self._apply_filter()

    # ── Tree population ───────────────────────────────────────────────

    def _rebuild_tree(self) -> None:
        self._tree.setSortingEnabled(False)
        self._tree.clear()

        # Group tracks by canonical artist
        artist_tracks: dict[str, list] = defaultdict(list)
        try:
            from cratesort.src.gui.classifier_view import (
                _extract_primary_artist, _canonical_artist,
            )
        except ImportError:
            def _extract_primary_artist(a): return (a, False)
            def _canonical_artist(a): return a

        for rec in self._inventory:
            edits = self._edits.get(str(rec.path), {})
            if 'reassign_artist' in edits:
                canonical = edits['reassign_artist']
            elif str(rec.path) in self._session_artists:
                canonical = self._session_artists[str(rec.path)]
            else:
                primary, _ = _extract_primary_artist(rec.artist or 'Unknown Artist')
                canonical  = _canonical_artist(primary)
            artist_tracks[canonical].append(rec)

        genres: set[str] = set()
        formats: set[str] = set()

        for artist, tracks in sorted(artist_tracks.items()):
            artist_edits = self._edits.get(f'__artist__{artist}', {})
            if 'genre' in artist_edits:
                genre = artist_edits['genre']
            else:
                genre, _ = self._classify_lookup(artist)
                if not genre:
                    # Step 3: taxonomy-validated ID3 majority vote (exact case-insensitive match only)
                    _tag_counts: Counter = Counter()
                    for rec in tracks:
                        t_edits = self._edits.get(str(rec.path), {})
                        raw_tag = (
                            t_edits.get('genre')
                            or self._track_overrides.get(str(rec.path))
                            or rec.genre
                            or ''
                        )
                        canonical = _VALID_GENRES_LOWER.get(raw_tag.strip().lower())
                        if canonical:
                            _tag_counts[canonical] += 1
                    genre = _tag_counts.most_common(1)[0][0] if _tag_counts else ''
            item = self._make_artist_item(artist, tracks, genre)
            self._tree.addTopLevelItem(item)
            if genre:
                genres.add(genre)
            for rec in tracks:
                if rec.extension:
                    formats.add(rec.extension.lstrip('.').upper())

        # Column widths (only set on fresh load to respect QSettings restoreState)
        if not self._settings.value(_SETTINGS_KEY):
            widths = [220, 60, 180, 120, 140, 80, 80, 70, 70, 80, 160, 200]
            for col, w in enumerate(widths):
                self._tree.setColumnWidth(col, w)

        self._tree.setSortingEnabled(True)

        # Fix 4: default A-Z on first load (no saved header state)
        if not self._settings.value(_SETTINGS_KEY):
            self._tree.sortByColumn(LC_ARTIST, Qt.SortOrder.AscendingOrder)

        # Resize columns to content on first load; user-adjusted widths persist via QSettings
        if not self._settings.value(_SETTINGS_KEY):
            def _resize_to_content():
                self._tree.header().resizeSections(QHeaderView.ResizeMode.ResizeToContents)
                _min = 60
                for i in range(self._tree.columnCount()):
                    if self._tree.columnWidth(i) < _min:
                        self._tree.setColumnWidth(i, _min)
            QTimer.singleShot(100, _resize_to_content)

        n = self._tree.topLevelItemCount()
        t = len(self._inventory)
        self._count_label.setText(f'{n:,} artists · {t:,} tracks')
        self._update_empty_state()

    def _make_artist_item(self, artist: str, tracks: list, genre: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setData(LC_ARTIST, Qt.ItemDataRole.UserRole, {'artist': artist, 'tracks': tracks})
        item.setData(LC_GENRE,  Qt.ItemDataRole.UserRole + 1, genre)  # for filtering

        # Common path
        paths = [rec.path for rec in tracks]
        if len(paths) == 1 or all(p.parent == paths[0].parent for p in paths):
            common = str(paths[0].parent)
        else:
            common = 'Multiple locations'

        # Artist-level tags only — track tags are independent and stored separately
        tags = self._edits.get(f'__artist__{artist}', {}).get('tags', '')

        _UC_ARTIST = {'', '—', 'Unclassified', 'Untagged'}

        item.setIcon(LC_ARTIST, _get_artist_icon())
        item.setText(LC_ARTIST, artist)
        item.setText(LC_TRACKS, str(len(tracks)))
        item.setText(LC_GENRE,  'Unclassified' if genre in _UC_ARTIST else genre)
        item.setText(LC_TAGS,   tags)
        item.setText(LC_PATH,   common)

        muted = QBrush(QColor(_MUTED))
        item.setForeground(LC_TRACKS, muted)

        if genre in _UC_ARTIST:
            _red = QBrush(QColor('#C75B5B'))
            item.setForeground(LC_ARTIST, _red)
            item.setForeground(LC_GENRE, _red)
            item.setToolTip(LC_ARTIST, 'Classify this artist to move all tracks out of Unclassified.')

        # Lazy-load placeholder
        dummy = QTreeWidgetItem(item)
        dummy.setText(0, _DUMMY)

        return item

    def _make_track_child(self, parent: QTreeWidgetItem, rec) -> QTreeWidgetItem:
        child = QTreeWidgetItem(parent)
        edits = self._edits.get(str(rec.path), {})

        title   = edits.get('title',   rec.title   or '')
        album   = edits.get('album',   rec.album   or '')
        # Fix 2: per-track genre override > inline edit > raw file tag
        genre   = edits.get('genre',
                    self._track_overrides.get(str(rec.path), rec.genre or '—'))
        tags    = edits.get('tags',    '')
        bpm     = edits.get('bpm',     str(round(rec.bpm)) if rec.bpm else '—')
        year    = edits.get('year',    rec.year    or '—')
        comment = edits.get('comment', rec.comment or '')

        child.setIcon(LC_ARTIST, _get_track_icon())
        child.setText(LC_ARTIST,   f'  {title}')
        child.setText(LC_TRACKS,   '')
        child.setText(LC_ALBUM,    album)
        child.setText(LC_GENRE,    genre)
        child.setText(LC_TAGS,     tags)
        child.setText(LC_DURATION, _fmt_dur(rec.duration))
        child.setText(LC_FORMAT,   rec.extension.lstrip('.').upper())
        child.setText(LC_BPM,      bpm)
        child.setText(LC_YEAR,     year)
        child.setText(LC_BITRATE,  f'{rec.bitrate} kbps' if rec.bitrate else '—')
        child.setText(LC_COMMENT,  (comment[:50] + '…') if len(comment) > 50 else comment)
        child.setText(LC_PATH,     str(rec.path))

        child.setData(LC_PATH, Qt.ItemDataRole.UserRole, rec)  # store TrackRecord
        if comment:
            child.setToolTip(LC_COMMENT, comment)

        _UC_T = {'', '—', 'Unclassified', 'Untagged'}
        parent_genre = parent.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
        if parent_genre in _UC_T:
            track_genre_raw = genre.strip() if genre else ''
            if track_genre_raw and track_genre_raw not in _UC_T:
                # Case B: track has a genre tag but artist is unclassified → amber
                _amber = QBrush(QColor('#c9a87a'))
                for col in range(len(HEADERS)):
                    child.setForeground(col, _amber)
                child.setText(LC_GENRE, f'{track_genre_raw} ⚠ Artist unclassified')
                child.setForeground(LC_GENRE, _amber)
                child.setToolTip(LC_ARTIST, 'This track has a genre tag but will remain in Unclassified until its artist is classified.')
            else:
                # Case A: track has no genre → red (same as artist)
                _red = QBrush(QColor('#C75B5B'))
                for col in range(len(HEADERS)):
                    child.setForeground(col, _red)
                child.setForeground(LC_GENRE, _red)
        else:
            muted = QBrush(QColor(_MUTED))
            for col in range(len(HEADERS)):
                child.setForeground(col, muted)
        return child

    def _classify_lookup(self, artist: str) -> tuple[str, str]:
        """
        Return (genre, confidence) for an artist from the session.
        Tries canonical (sort-form) name, then primary extracted name, then raw.
        The session keys are stored in sort form (e.g. 'Gap Band, The').
        """
        if not self._has_classification or not artist:
            return '', ''
        # 1. Direct match (most common — artist is already in sort form)
        result = self._session_genre.get(artist)
        if result:
            return result
        # 2. Apply canonical/sort-form transformation
        try:
            from cratesort.src.gui.classifier_view import (
                _extract_primary_artist, _canonical_artist,
            )
            primary, _ = _extract_primary_artist(artist)
            canonical   = _canonical_artist(primary)
            result = self._session_genre.get(canonical) or self._session_genre.get(primary)
            if result:
                return result
        except Exception:
            pass
        return '', ''

    # ── Lazy loading ──────────────────────────────────────────────────

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.parent():
            return  # only artist top-level items
        if item.childCount() == 1 and item.child(0).text(0) == _DUMMY:
            item.takeChild(0)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            for rec in data.get('tracks', []):
                self._make_track_child(item, rec)
        # Deselect parent on expand to avoid permanent orange
        if item.isSelected():
            item.setSelected(False)

    # ── Selection + album art ──────────────────────────────────────────

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.parent():  # track child
            rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
            if rec and hasattr(rec, 'path'):
                self.track_selected.emit(str(rec.path))
                self.album_art_requested.emit(str(rec.path))
        # Artist row: single click highlights only — expand/collapse on double click

    # ── Event filter (click-away editor close) ────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if (event.type() == QEvent.Type.MouseButtonPress
                and self._edit_widget is not None
                and obj is self._tree.viewport()):
            click_pos = event.position().toPoint()
            if not self._edit_widget.geometry().contains(click_pos):
                self._commit_active_editor()
                return False
        return super().eventFilter(obj, event)

    # ── Inline editing ────────────────────────────────────────────────

    def _commit_active_editor(self) -> None:
        """
        Commit the open editor.
        - If text unchanged: close quietly, no flash.
        - If text changed: save, close, flash row text teal for 1.5s.
        """
        if self._edit_widget is None or self._edit_item is None:
            return
        item, col, widget, original = (
            self._edit_item, self._edit_col,
            self._edit_widget, self._edit_original,
        )
        new_val = widget.text()

        # Clear state BEFORE removeItemWidget — prevents editingFinished re-entry
        self._edit_widget   = None
        self._edit_item     = None
        self._edit_col      = -1
        self._edit_original = ''

        try:
            self._tree.removeItemWidget(item, col)
        except Exception:
            pass

        # Fix 1: only commit + flash when the value actually changed
        if new_val == original:
            return  # no change — close quietly, no flash, no save

        display = f'  {new_val}' if col == LC_ARTIST else new_val
        item.setText(col, display)

        rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
        field = _EDITABLE.get(col)
        if rec and field:
            self._edits.setdefault(str(rec.path), {})[field] = new_val
            self.track_field_changed.emit(str(rec.path), field, new_val)
        self._save_edits()

        # Write field to disk immediately (free-tier metadata write-through).
        # 'tags' is virtual-only — skip disk write. _save_edits() staging always stands.
        disk_ok = True
        if rec and field and field != 'tags':
            from cratesort.src.core.file_organizer import write_file_metadata
            disk_ok = write_file_metadata(rec.path, field, new_val)
            if disk_ok:
                if field == 'title':
                    rec.title = new_val
                elif field == 'album':
                    rec.album = new_val
                elif field == 'bpm':
                    try:
                        rec.bpm = float(new_val)
                    except (ValueError, TypeError):
                        pass
                elif field == 'year':
                    rec.year = new_val
                elif field == 'comment':
                    rec.comment = new_val

        if not disk_ok:
            item.setText(col, f'  {original}' if col == LC_ARTIST else original)
            saved_label = self._count_label.text()
            self._count_label.setText(
                '⚠ Could not write to file — check that the drive is connected '
                'and the file is not locked.'
            )
            QTimer.singleShot(5000, lambda t=saved_label: self._count_label.setText(t))
            return

        # Deselect the row before flashing: selected state applies dark text on
        # orange background, hiding the teal text flash entirely.
        item.setSelected(False)
        self._tree.clearSelection()
        self._flash_row_text(item)

    def _flash_row_text(self, item: QTreeWidgetItem) -> None:
        """Flash all cells in the row to teal for 1.5s, then restore cream."""
        n    = self._tree.columnCount()
        teal = QBrush(QColor('#428175'))
        cream = QBrush(QColor('#f1e3c8'))
        for c in range(n):
            item.setForeground(c, teal)
        QTimer.singleShot(1500, lambda it=item: [
            it.setForeground(c, cream) for c in range(n)
        ])

    def _cancel_active_editor(self) -> None:
        """Cancel the open editor: close without saving, no flash (Escape key)."""
        if self._edit_widget is None or self._edit_item is None:
            return
        item, col = self._edit_item, self._edit_col
        self._edit_widget  = None
        self._edit_item    = None
        self._edit_col     = -1
        self._edit_original = ''
        # Original text is already in item — just remove the editor widget
        try:
            self._tree.removeItemWidget(item, col)
        except Exception:
            pass

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if not item.parent():
            item.setExpanded(not item.isExpanded())
            return
        if column not in _EDITABLE:
            return  # non-editable: genre, duration, format, bitrate, path

        rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
        if not rec:
            return

        # Commit any existing editor first before opening a new one
        self._commit_active_editor()

        current = item.text(column).lstrip()
        editor  = QLineEdit(current)
        editor.selectAll()
        editor.setMinimumHeight(26)  # prevent descender clipping

        self._edit_widget  = editor
        self._edit_item    = item
        self._edit_col     = column
        self._edit_original = current

        # Escape → cancel (patch keyPressEvent on the instance)
        _orig_kp = editor.keyPressEvent
        def _handle_key(event):
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_active_editor()
            else:
                _orig_kp(event)
        editor.keyPressEvent = _handle_key  # type: ignore[method-assign]

        # Enter → commit+flash
        editor.returnPressed.connect(self._commit_active_editor)
        # Focus lost (click-away) → commit+flash; safe if already committed
        editor.editingFinished.connect(self._commit_active_editor)

        self._tree.setItemWidget(item, column, editor)
        editor.setFocus()

    # ── Filtering ─────────────────────────────────────────────────────

    def _populate_filters(self) -> None:
        formats: set[str] = set()
        for rec in self._inventory:
            if rec.extension:
                formats.add(rec.extension.lstrip('.').upper())
        self._format_cb.blockSignals(True)
        self._format_cb.clear()
        self._format_cb.addItem('All Formats')
        self._format_cb.addItems(sorted(formats))
        self._format_cb.blockSignals(False)

    def _apply_filter(self) -> None:
        search   = self._search.text().lower().strip()
        genre_f  = self._sidebar_genre if self._sidebar_genre != 'All' else ''
        format_f = self._format_cb.currentText()
        if format_f in ('All Formats', ''):
            format_f = ''

        _UC_GENRES = {'', '—', 'Unclassified', 'Untagged'}

        visible_count = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            tracks = data.get('tracks', [])
            item_genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''

            # Genre filter (driven by sidebar selection)
            if genre_f:
                if genre_f == 'Unclassified':
                    if item_genre not in _UC_GENRES:
                        item.setHidden(True)
                        continue
                elif item_genre != genre_f:
                    item.setHidden(True)
                    continue

            # Format filter — show artist if any track matches
            if format_f:
                has_fmt = any(
                    rec.extension.lstrip('.').upper() == format_f
                    for rec in tracks
                )
                if not has_fmt:
                    item.setHidden(True)
                    continue

            # Search filter
            if search:
                artist_match = search in artist.lower()
                track_match  = any(
                    search in (rec.title or '').lower()
                    or search in (rec.album or '').lower()
                    or search in rec.filename.lower()
                    for rec in tracks
                )
                if not artist_match and not track_match:
                    item.setHidden(True)
                    continue

            item.setHidden(False)
            visible_count += 1

        total = self._tree.topLevelItemCount()
        if search or genre_f or format_f:
            self._count_label.setText(f'{visible_count:,} of {total:,} artists visible')
        else:
            t = len(self._inventory)
            self._count_label.setText(f'{total:,} artists · {t:,} tracks')

    def _clear_filters(self) -> None:
        self._search.clear()
        self._format_cb.setCurrentIndex(0)
        self._sidebar_genre = 'All'
        if self._genre_sidebar_list.count() > 0:
            self._genre_sidebar_list.setCurrentRow(0)

    # ── Context menus ─────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if not item:
            return
        if not item.isSelected():
            self._tree.clearSelection()
            item.setSelected(True)
        self._context_selection: list[QTreeWidgetItem] = list(self._tree.selectedItems())
        if item.parent():
            self._track_menu(item, pos)
        else:
            self._artist_menu(item, pos)

    def _sync_genres_to_session(self, artist_changes: dict, track_changes: dict) -> None:
        """Write genre changes back to classification_session.json for cross-view sync."""
        if not self._library_path or (not artist_changes and not track_changes):
            return
        session_file = self._library_path / '_CrateSort' / 'classification_session.json'
        if not session_file.exists():
            return
        try:
            from cratesort.src.gui.classifier_view import ClassificationSession
            session = ClassificationSession.load(session_file)
            for entry in session.entries:
                if entry.artist in artist_changes:
                    entry.final_genre = artist_changes[entry.artist]
                    if entry.state in ('pending', 'flagged'):
                        entry.state = 'edited'
                for track in entry.tracks:
                    if track.path in track_changes:
                        track.genre_tag = track_changes[track.path]
            session.save()
        except Exception as exc:
            print(f'[LibraryBrowser] Failed to sync to session: {exc}')

    def _change_genre_for_selection(self, hint_label: str = '', hint_genre: str = '') -> None:
        """Apply a single genre change to every currently selected item (artist or track)."""
        from cratesort.src.gui.classifier_view import _ChangeGenreDialog
        selected = getattr(self, '_context_selection', None) or list(self._tree.selectedItems())
        print(f'[DEBUG LibraryBrowser] _change_genre_for_selection: {len(selected)} items')
        for dbg in selected:
            print(f'  {"ARTIST" if dbg.parent() is None else "TRACK"}: {dbg.text(0)!r}')
        if not selected:
            return
        dlg = _ChangeGenreDialog(hint_label or f'{len(selected)} items', hint_genre, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_genre = dlg.selected_genre
        artist_changes: dict[str, str] = {}
        track_changes:  dict[str, str] = {}
        _UC_GENRES = {'', '—', 'Unclassified', 'Untagged'}
        for item in selected:
            if item.parent() is None:
                data   = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
                artist = data.get('artist', '')
                display_genre = 'Unclassified' if new_genre in _UC_GENRES else new_genre
                item.setText(LC_GENRE, display_genre)
                item.setData(LC_GENRE, Qt.ItemDataRole.UserRole + 1, new_genre)
                f = item.font(LC_GENRE)
                f.setItalic(False)
                item.setFont(LC_GENRE, f)
                if new_genre in _UC_GENRES:
                    _red = QBrush(QColor('#C75B5B'))
                    item.setForeground(LC_ARTIST, _red)
                    item.setForeground(LC_GENRE, _red)
                    item.setToolTip(LC_ARTIST, 'Classify this artist to move all tracks out of Unclassified.')
                else:
                    _cream = QBrush(QColor('#f1e3c8'))
                    item.setForeground(LC_ARTIST, _cream)
                    item.setForeground(LC_GENRE, _cream)
                    item.setToolTip(LC_ARTIST, '')
                # Propagate color to any already-expanded child track items
                for ci in range(item.childCount()):
                    ch = item.child(ci)
                    if ch.text(0) == _DUMMY:
                        continue
                    rec = ch.data(LC_PATH, Qt.ItemDataRole.UserRole)
                    if not rec:
                        continue
                    t_edits = self._edits.get(str(rec.path), {})
                    t_genre = (
                        t_edits.get('genre')
                        or self._track_overrides.get(str(rec.path))
                        or rec.genre
                        or ''
                    )
                    if new_genre in _UC_GENRES:
                        if t_genre and t_genre not in _UC_GENRES:
                            _amber = QBrush(QColor('#c9a87a'))
                            for col in range(self._tree.columnCount()):
                                ch.setForeground(col, _amber)
                            ch.setText(LC_GENRE, f'{t_genre} ⚠ Artist unclassified')
                            ch.setForeground(LC_GENRE, _amber)
                            ch.setToolTip(LC_ARTIST, 'This track has a genre tag but will remain in Unclassified until its artist is classified.')
                        else:
                            _red = QBrush(QColor('#C75B5B'))
                            for col in range(self._tree.columnCount()):
                                ch.setForeground(col, _red)
                            ch.setForeground(LC_GENRE, _red)
                            ch.setToolTip(LC_ARTIST, '')
                    else:
                        _muted = QBrush(QColor(_MUTED))
                        for col in range(self._tree.columnCount()):
                            ch.setForeground(col, _muted)
                        ch.setText(LC_GENRE, t_genre or '—')
                        ch.setToolTip(LC_ARTIST, '')
                self._edits.setdefault(f'__artist__{artist}', {})['genre'] = new_genre
                artist_changes[artist] = new_genre
                item.setSelected(False)
                self._flash_row_text(item)
            else:
                rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
                if rec:
                    item.setText(LC_GENRE, new_genre)
                    self._edits.setdefault(str(rec.path), {})['genre'] = new_genre
                    track_changes[str(rec.path)] = new_genre
        self._save_edits()
        self._sync_genres_to_session(artist_changes, track_changes)
        if artist_changes:
            self._last_edited_artist  = next(reversed(artist_changes))
            self._last_assigned_genre = new_genre
        self._populate_genre_sidebar()
        self._update_empty_state()

    def _artist_menu(self, item: QTreeWidgetItem, pos) -> None:
        data  = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
        artist = data.get('artist', '')
        menu   = QMenu(self)
        menu.addAction('✓ Approve')
        chg       = menu.addAction('↕ Change Genre…')
        edit_tags = menu.addAction('✏ Edit Style Tags…')
        menu.addAction('⚑ Mark for Review')
        action = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if action == chg:
            self._change_genre_for_selection(artist, item.text(LC_GENRE))
        elif action == edit_tags:
            self._edit_artist_tags(item, artist)

    def _track_menu(self, item: QTreeWidgetItem, pos) -> None:
        rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
        if not rec:
            return
        menu   = QMenu(self)
        reassign = menu.addAction('↪ Reassign Artist…')
        chg_g    = menu.addAction('↕ Change Genre…')
        edit_t   = menu.addAction('✏ Edit Style Tags…')
        menu.addSeparator()
        finder   = menu.addAction('📂 Show in Finder')
        menu.addSeparator()
        cp_a     = menu.addAction('Copy Artist')
        cp_t     = menu.addAction('Copy Title')
        cp_p     = menu.addAction('Copy File Path')

        action = menu.exec(self._tree.viewport().mapToGlobal(pos))
        path = str(rec.path)
        if action == reassign:
            self._reassign_track(item)
        elif action == chg_g:
            self._change_genre_for_selection(rec.filename, rec.genre or '')
        elif action == edit_t:
            self._edit_style_tags(item, rec)
        elif action == finder:
            _show_in_finder(path)
        elif action == cp_a:
            QApplication.clipboard().setText(rec.artist or '')
        elif action == cp_t:
            QApplication.clipboard().setText(rec.title or '')
        elif action == cp_p:
            QApplication.clipboard().setText(path)

    def _change_track_genre(self, child: QTreeWidgetItem, rec) -> None:
        """Change genre on the right-clicked track and any other selected tracks."""
        from cratesort.src.gui.classifier_view import _ChangeGenreDialog
        current = rec.genre or ''
        dlg = _ChangeGenreDialog(rec.filename, current, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_genre = dlg.selected_genre
        selected = [item for item in self._tree.selectedItems() if item.parent()]
        if child not in selected:
            selected = [child]
        for sel in selected:
            sel_rec = sel.data(LC_PATH, Qt.ItemDataRole.UserRole)
            if sel_rec:
                sel.setText(LC_GENRE, new_genre)
                self._edits.setdefault(str(sel_rec.path), {})['genre'] = new_genre
        self._save_edits()
        child.setSelected(False)
        self._flash_row_text(child)

    def _reassign_track(self, child: QTreeWidgetItem) -> None:
        """Move one or more selected tracks to a different (existing or new) artist group."""
        from cratesort.src.gui.classifier_view import _ReassignArtistDialog

        # 1. Collect all selected track items; fall back to right-clicked item only
        selected = [item for item in self._tree.selectedItems() if item.parent()]
        if child not in selected:
            selected = [child]

        # 2. Gather (child_item, track_rec, parent_item) — drop rows with no record
        tracks_to_move = [
            (item, item.data(LC_PATH, Qt.ItemDataRole.UserRole), item.parent())
            for item in selected
        ]
        tracks_to_move = [(ci, tr, pi) for ci, tr, pi in tracks_to_move if tr is not None]
        if not tracks_to_move:
            return

        # 3. Show artist-picker dialog once
        existing_artists = []
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            existing_artists.append(data.get('artist', ''))

        dlg = _ReassignArtistDialog(existing_artists, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_artist = dlg.artist_name.strip()
        if not new_artist:
            return

        # 4. Find or create destination artist group
        dest_item = None
        dest_tracks: list = []
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            top_data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            if top_data.get('artist', '') == new_artist:
                dest_item = top
                dest_tracks = top_data.get('tracks', [])
                break

        # 5. Move each track: tree removal + path-based list removal + edit persistence
        modified_parents: list[QTreeWidgetItem] = []
        for child_item, track_rec, parent_item in tracks_to_move:
            parent_data = parent_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            parent_tracks = parent_data.get('tracks', [])
            original_artist = parent_data.get('artist', '')

            # Remove child from tree
            parent_item.takeChild(parent_item.indexOfChild(child_item))

            # Path-based removal — avoids ValueError when dataclass fields have changed
            for r in list(parent_tracks):
                if str(r.path) == str(track_rec.path):
                    parent_tracks.remove(r)
                    break

            parent_item.setText(LC_TRACKS, str(len(parent_tracks)))
            parent_data['tracks'] = parent_tracks
            parent_item.setData(LC_ARTIST, Qt.ItemDataRole.UserRole, parent_data)

            if parent_item not in modified_parents:
                modified_parents.append(parent_item)

            # Persist edit
            self._edits.setdefault(str(track_rec.path), {})['reassign_artist'] = new_artist
            self._edits.setdefault(str(track_rec.path), {})['original_artist'] = original_artist

            dest_tracks.append(track_rec)

        # 6. Update or create the destination group
        if dest_item is None:
            genre, _ = self._classify_lookup(new_artist)
            dest_item = self._make_artist_item(new_artist, dest_tracks, genre)
            self._tree.addTopLevelItem(dest_item)
        else:
            dest_item.setText(LC_TRACKS, str(len(dest_tracks)))
            dest_data = dest_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            dest_data['tracks'] = dest_tracks
            dest_item.setData(LC_ARTIST, Qt.ItemDataRole.UserRole, dest_data)

            if dest_item.childCount() == 1 and dest_item.child(0).text(0) == _DUMMY:
                dest_item.takeChild(0)
                for t in dest_tracks:
                    self._make_track_child(dest_item, t)
            else:
                for _, track_rec, _ in tracks_to_move:
                    self._make_track_child(dest_item, track_rec)

        # 7. Remove any parent groups that are now empty
        for parent_item in modified_parents:
            parent_data = parent_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            if not parent_data.get('tracks', []):
                top_idx = self._tree.indexOfTopLevelItem(parent_item)
                if top_idx >= 0:
                    self._tree.takeTopLevelItem(top_idx)

        dest_item.setExpanded(True)
        dest_item.setSelected(False)
        self._flash_row_text(dest_item)
        self._save_edits()
        self._populate_genre_sidebar()
        self._update_empty_state()

        # Write artist tag to disk for each reassigned track (free-tier write-through)
        from cratesort.src.core.file_organizer import write_file_metadata
        disk_failures = 0
        for _, track_rec, _ in tracks_to_move:
            if write_file_metadata(track_rec.path, 'artist', new_artist):
                track_rec.artist = new_artist
            else:
                disk_failures += 1
        if disk_failures:
            n = self._tree.topLevelItemCount()
            t = len(self._inventory)
            norm = f'{n:,} artists · {t:,} tracks'
            self._count_label.setText(
                f'⚠ {disk_failures} track(s) could not be updated on disk — '
                f'check that the drive is connected and files are not locked.'
            )
            QTimer.singleShot(6000, lambda s=norm: self._count_label.setText(s))

    def _change_artist_genre(self, item: QTreeWidgetItem, artist: str) -> None:
        from cratesort.src.gui.classifier_view import _ChangeGenreDialog
        current = item.text(LC_GENRE)
        dlg = _ChangeGenreDialog(artist, current, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_genre = dlg.selected_genre
            item.setText(LC_GENRE, new_genre)
            item.setData(LC_GENRE, Qt.ItemDataRole.UserRole + 1, new_genre)
            item.setForeground(LC_GENRE, QBrush(QColor('#f1e3c8')))
            f = item.font(LC_GENRE)
            f.setItalic(False)
            item.setFont(LC_GENRE, f)
            self._edits.setdefault(f'__artist__{artist}', {})['genre'] = new_genre
            self._save_edits()
            item.setSelected(False)
            self._flash_row_text(item)

            # Write genre to all tracks for this artist (free-tier write-through)
            from cratesort.src.core.file_organizer import write_file_metadata
            artist_data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            disk_failures = 0
            for rec in artist_data.get('tracks', []):
                if write_file_metadata(rec.path, 'genre', new_genre):
                    rec.genre = new_genre
                else:
                    disk_failures += 1
            if disk_failures:
                n = self._tree.topLevelItemCount()
                t = len(self._inventory)
                norm = f'{n:,} artists · {t:,} tracks'
                self._count_label.setText(
                    f'⚠ {disk_failures} track(s) could not be updated on disk — '
                    f'check that the drive is connected and files are not locked.'
                )
                QTimer.singleShot(6000, lambda s=norm: self._count_label.setText(s))

    def _edit_artist_tags(self, item: QTreeWidgetItem, artist: str) -> None:
        from cratesort.src.gui.classifier_view import _EditTagsDialog
        key = f'__artist__{artist}'
        current_tags_str = self._edits.get(key, {}).get('tags', '')
        current_tags = [t.strip() for t in current_tags_str.split(',') if t.strip()]
        dlg = _EditTagsDialog(
            type('T', (), {
                'filename': artist,
                'title':    artist,
                'genre_tag': item.text(LC_GENRE),
                'tags':     current_tags,
                'comment':  '',
            })(),
            self
        )
        dlg.setWindowTitle(f'Edit Style Tags — {artist}')
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tags_str = ', '.join(dlg._track.tags)
            self._edits.setdefault(key, {})['tags'] = tags_str
            self._save_edits()
            item.setText(LC_TAGS, tags_str)

    def _edit_style_tags(self, item: QTreeWidgetItem, rec) -> None:
        from cratesort.src.gui.classifier_view import _EditTagsDialog
        dlg = _EditTagsDialog(
            # Build a minimal TrackInfo proxy
            type('T', (), {
                'filename': rec.filename,
                'title': rec.title,
                'genre_tag': rec.genre,
                'tags': self._edits.get(str(rec.path), {}).get('tags', '').split(','),
                'comment': rec.comment,
            })(),
            self
        )
        dlg.setWindowTitle(f'Edit Style Tags — {rec.filename}')
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tags_str = ', '.join(dlg._track.tags)
            self._edits.setdefault(str(rec.path), {})['tags'] = tags_str
            self._save_edits()
            item.setText(LC_TAGS, tags_str)

    # ── Persistence ───────────────────────────────────────────────────

    def _edits_file(self) -> Optional[Path]:
        if not self._library_path:
            return None
        return self._library_path / '_CrateSort' / 'library_edits.json'

    def _load_edits(self) -> None:
        p = self._edits_file()
        if p and p.exists():
            try:
                with open(p, encoding='utf-8') as f:
                    self._edits = json.load(f)
            except Exception:
                self._edits = {}

    def _save_edits(self) -> None:
        p = self._edits_file()
        if not p or not self._edits:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(self._edits, f, indent=2)

    def _enforce_min_col_widths(self) -> None:
        """Ensure every column header is fully visible (never clipped)."""
        fm = self._tree.header().fontMetrics()
        for col in range(self._tree.columnCount()):
            text    = self._tree.headerItem().text(col)
            min_w   = fm.horizontalAdvance(text) + 40   # 40px generous padding
            current = self._tree.columnWidth(col)
            if current < min_w:
                self._tree.setColumnWidth(col, min_w)

    # ── Classify mode ─────────────────────────────────────────────────

    def _on_classify_clicked(self, checked: bool = False, auto_classify: bool = False) -> None:
        if not self._inventory or not self._library_path:
            return
        from cratesort.src.gui.classifier_view import ClassificationSession, _ClassifyWorker

        session_file = self._library_path / '_CrateSort' / 'classification_session.json'

        if auto_classify:
            # Session already on disk — load and enter classify mode immediately
            if session_file.exists():
                try:
                    session = ClassificationSession.load(session_file)
                    session.apply_library_edits()
                    self._enter_classify_mode(session)
                    return
                except Exception:
                    pass

            # No session yet — show the Analyze Library modal and run the worker
            from cratesort.src.gui.classifier_view import (
                _extract_primary_artist, _canonical_artist,
                DJ_TOOLS_LABEL, _DJ_TOOLS_FOLDER_PATTERNS,
            )
            _VIDEO_PURPOSE = frozenset({
                'movie clips', '_movie clips', 'commercials', '_commercials',
                'clips', 'films', 'visuals', '_visuals',
            })

            # Pre-compile artist → track_count map (mirrors _ClassifyWorker grouping)
            artist_tracks_map: dict[str, int] = {}
            dj_tools_count = 0
            for rec in self._inventory:
                raw_artist = rec.artist or ''
                no_artist  = (
                    not raw_artist
                    or raw_artist.lower() in ('unknown artist', 'various', 'fx')
                )
                if rec.is_video:
                    if any(p in str(rec.path).lower() for p in _VIDEO_PURPOSE):
                        dj_tools_count += 1
                        continue
                if no_artist and rec.duration and rec.duration < 60:
                    if any(p in str(rec.path).lower() for p in _DJ_TOOLS_FOLDER_PATTERNS):
                        dj_tools_count += 1
                        continue
                primary, _ = _extract_primary_artist(raw_artist or 'Unknown Artist')
                canonical  = _canonical_artist(primary)
                artist_tracks_map[canonical] = artist_tracks_map.get(canonical, 0) + 1

            self._auto_artist_tracks_map = artist_tracks_map
            self._auto_dj_tools_count    = dj_tools_count
            self._processed_artists      = set()
            self._processed_tracks_count = 0

            main_window = self.window()
            self._analyze_modal = _AnalyzeLibraryModal(main_window)
            self._analyze_modal.review_requested.connect(self._on_review_results_clicked)
            self._analyze_modal.show()
            self._analyze_modal.raise_()

            self._classify_worker = _ClassifyWorker(self._inventory, self._library_path)
            self._classify_worker.progress.connect(self._on_auto_classify_progress)
            self._classify_worker.finished.connect(self._on_auto_classify_finished)
            self._classify_worker.errored.connect(self._on_auto_classify_error)
            self._classify_worker.start()

        else:
            # Manual toolbar trigger — existing behaviour
            if session_file.exists():
                try:
                    session = ClassificationSession.load(session_file)
                    session.apply_library_edits()
                    self._enter_classify_mode(session)
                    return
                except Exception:
                    pass

            self._classify_btn.setEnabled(False)
            self._classify_btn.setText('Classifying…')
            self._classify_worker = _ClassifyWorker(self._inventory, self._library_path)
            self._classify_worker.finished.connect(self._on_classify_finished)
            self._classify_worker.errored.connect(self._on_classify_error)
            self._classify_worker.start()

    def _on_classify_finished(self, session) -> None:
        session.save()
        session.apply_library_edits()
        self._classify_btn.setEnabled(True)
        self._classify_btn.setText('Classify Library')
        self._enter_classify_mode(session)

    def _on_classify_error(self, message: str) -> None:
        self._classify_btn.setEnabled(True)
        self._classify_btn.setText('Classify Library')
        _show_dark_alert(self.window(), 'Classification Failed', message[:500])

    # ── Auto-classify modal slots ──────────────────────────────────────

    def _on_auto_classify_progress(self, done: int, total: int, artist_name: str) -> None:
        from cratesort.src.gui.classifier_view import DJ_TOOLS_LABEL
        if self._analyze_modal is None:
            return
        if artist_name not in self._processed_artists:
            self._processed_artists.add(artist_name)
            if artist_name == DJ_TOOLS_LABEL:
                self._processed_tracks_count += self._auto_dj_tools_count
            else:
                self._processed_tracks_count += self._auto_artist_tracks_map.get(artist_name, 0)
        self._analyze_modal.update_stats(
            self._processed_tracks_count, len(self._processed_artists)
        )
        if total > 0:
            self._analyze_modal.update_percent(int((done / total) * 100))

    def _on_auto_classify_finished(self, session) -> None:
        session.save()
        session.apply_library_edits()
        self._auto_classify_session = session
        if self._analyze_modal is not None:
            self._analyze_modal.on_classification_complete()

    def _on_auto_classify_error(self, message: str) -> None:
        self._cleanup_auto_classify_ui()
        _show_dark_alert(self.window(), 'Classification Failed', message[:500])

    def _on_review_results_clicked(self) -> None:
        session = self._auto_classify_session
        self._cleanup_auto_classify_ui()
        if session is not None:
            self._enter_classify_mode(session)

    def _cleanup_auto_classify_ui(self) -> None:
        if self._analyze_modal is not None:
            modal = self._analyze_modal
            self._analyze_modal = None
            modal.close()       # emits finished → _CrateSortDialog._cleanup_overlay handles scrim
            modal.deleteLater()
        self._auto_classify_session  = None
        self._processed_artists      = set()
        self._processed_tracks_count = 0
        self._auto_artist_tracks_map = {}
        self._auto_dj_tools_count    = 0

    def _enter_classify_mode(self, session) -> None:
        self._classify_mode = True
        self._classify_session = session
        self._classify_results = {
            entry.artist: (entry.display_genre, entry.confidence)
            for entry in session.entries
        }
        # Snapshot header state so exit can restore it exactly
        self._pre_classify_header_state = self._tree.header().saveState()

        # Show classify columns with target widths
        self._tree.setColumnHidden(LC_CLS_PROPOSED, False)
        self._tree.setColumnHidden(LC_CLS_CONF,     False)
        self._tree.setColumnHidden(LC_CLS_STATUS,   False)
        self._tree.setColumnWidth(LC_CLS_PROPOSED, 120)
        self._tree.setColumnWidth(LC_CLS_CONF,      80)
        self._tree.setColumnWidth(LC_CLS_STATUS,    80)

        # Defer visual reorder until the tree has registered visibility changes
        def _reorder_cls_cols():
            hdr = self._tree.header()
            genre_vis = hdr.visualIndex(LC_GENRE)
            hdr.moveSection(hdr.visualIndex(LC_CLS_PROPOSED), genre_vis + 1)
            hdr.moveSection(hdr.visualIndex(LC_CLS_CONF),     genre_vis + 2)
            hdr.moveSection(hdr.visualIndex(LC_CLS_STATUS),   genre_vis + 3)
            for col in (LC_CLS_PROPOSED, LC_CLS_CONF, LC_CLS_STATUS):
                self._tree.resizeColumnToContents(col)
                if self._tree.columnWidth(col) < 60:
                    self._tree.setColumnWidth(col, 60)

        QTimer.singleShot(0, _reorder_cls_cols)

        # Teal-tinted column headers
        for col in (LC_CLS_PROPOSED, LC_CLS_CONF, LC_CLS_STATUS):
            self._tree.headerItem().setForeground(col, QBrush(QColor('#428175')))
        self._populate_classify_columns()
        self._update_empty_state()
        self._classify_banner_frame.setVisible(True)
        self._classify_btn.setVisible(False)

    def _populate_classify_columns(self) -> None:
        _BG_NORMAL = '#1c2825'
        _BG_UC     = '#221a1a'
        _UC        = {'Unclassified', 'Untagged', ''}

        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            current_genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
            proposed, confidence = self._classify_results.get(
                artist, ('Unclassified', 'NONE')
            )
            is_uc = proposed in _UC
            changed = not is_uc and proposed != current_genre

            # Proposed Genre
            item.setText(LC_CLS_PROPOSED, proposed)
            item.setBackground(LC_CLS_PROPOSED, QBrush(QColor(_BG_UC if is_uc else _BG_NORMAL)))
            if is_uc:
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor('#C75B5B')))
            elif confidence == 'MATCHED':
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor('#f1e3c8')))
            elif changed:
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor('#D17D34')))
            else:
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor('#7bbdad')))

            # Confidence
            item.setText(LC_CLS_CONF, confidence)
            item.setBackground(LC_CLS_CONF, QBrush(QColor(_BG_UC if is_uc else _BG_NORMAL)))
            conf_color = {
                'MATCHED': '#f1e3c8',
                'HIGH':    '#428175',
                'MEDIUM':  '#9fa4c7',
                'LOW':     '#D17D34',
                'NONE':    '#C75B5B',
            }.get(confidence, '#a89b85')
            item.setForeground(LC_CLS_CONF, QBrush(QColor(conf_color)))

            # Status
            status = '' if confidence == 'MATCHED' else ('Modified' if changed else '')
            item.setText(LC_CLS_STATUS, status)
            item.setBackground(LC_CLS_STATUS, QBrush(QColor(_BG_UC if is_uc else _BG_NORMAL)))
            if status:
                item.setForeground(LC_CLS_STATUS, QBrush(QColor('#D17D34')))

    def _exit_classify_mode_cancel(self) -> None:
        self._classify_mode = False
        self._classify_session = None
        self._classify_results = {}
        # Clear classify column text
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            for col in (LC_CLS_PROPOSED, LC_CLS_CONF, LC_CLS_STATUS):
                item.setText(col, '')
                item.setData(col, Qt.ItemDataRole.BackgroundRole, None)
        # Restore pre-classify header state (column order + widths), then hide columns
        if getattr(self, '_pre_classify_header_state', None):
            self._tree.header().restoreState(self._pre_classify_header_state)
            self._pre_classify_header_state = None
        for col in (LC_CLS_PROPOSED, LC_CLS_CONF, LC_CLS_STATUS):
            self._tree.headerItem().setForeground(col, QBrush(QColor('#a89b85')))
            self._tree.setColumnHidden(col, True)
        self._update_empty_state()
        self._classify_banner_frame.setVisible(False)
        self._classify_btn.setVisible(True)

    def _exit_classify_mode_accept(self) -> None:
        if not self._classify_results or not self._library_path:
            self._exit_classify_mode_cancel()
            return
        edits_path = self._library_path / '_CrateSort' / 'library_edits.json'
        edits: dict = {}
        if edits_path.exists():
            try:
                with open(edits_path, encoding='utf-8') as f:
                    edits = json.load(f)
            except Exception:
                pass

        _UC = {'Unclassified', 'Untagged', ''}
        _last_accept_artist: Optional[str] = None
        _last_accept_genre:  Optional[str] = None
        _accepted_tracks: list = []   # (rec, proposed_genre) collected for disk writes
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            current_genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
            proposed = item.text(LC_CLS_PROPOSED)
            artist_key = f'__artist__{artist}'
            if artist_key in edits and 'genre' in edits[artist_key]:
                continue  # user-set override — don't overwrite with classifier's proposal
            confidence = item.text(LC_CLS_CONF)
            if confidence == 'MATCHED' and proposed == current_genre:
                continue  # ID3 tag already matches taxonomy — no override needed
            if proposed and proposed not in _UC and proposed != current_genre:
                edits.setdefault(artist_key, {})['genre'] = proposed
                item.setText(LC_GENRE, proposed)
                item.setData(LC_GENRE, Qt.ItemDataRole.UserRole + 1, proposed)
                item.setForeground(LC_GENRE, QBrush(QColor('#f1e3c8')))
                f = item.font(LC_GENRE)
                f.setItalic(False)
                item.setFont(LC_GENRE, f)
                _last_accept_artist = artist
                _last_accept_genre  = proposed
                for rec in data.get('tracks', []):
                    _accepted_tracks.append((rec, proposed))

        edits_path.parent.mkdir(parents=True, exist_ok=True)
        save_success = False
        try:
            with open(edits_path, 'w', encoding='utf-8') as f:
                json.dump(edits, f, indent=2)
            save_success = True
        except Exception as exc:
            print(f'[LibraryBrowser] Failed to save accepted classifications: {exc}')

        if save_success:
            try:
                flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
                flag_path.parent.mkdir(parents=True, exist_ok=True)
                flag_path.touch()
            except Exception as exc:
                print(f'[LibraryBrowser] Warning: Failed to write classification accepted flag: {exc}')

        # Write accepted genre proposals to track files on disk (free-tier write-through).
        # library_edits.json staging already stands as an Organize fallback for any failures.
        from cratesort.src.core.file_organizer import write_file_metadata
        disk_failures = 0
        for rec, genre in _accepted_tracks:
            if write_file_metadata(rec.path, 'genre', genre):
                rec.genre = genre
            else:
                disk_failures += 1

        if _last_accept_artist:
            self._last_edited_artist  = _last_accept_artist
            self._last_assigned_genre = _last_accept_genre

        self._exit_classify_mode_cancel()
        if self._inventory and self._library_path:
            self.load(self._inventory, self._library_path)

        if disk_failures:
            n = self._tree.topLevelItemCount()
            t = len(self._inventory)
            norm = f'{n:,} artists · {t:,} tracks'
            self._count_label.setText(
                f'⚠ Classification accepted. {disk_failures} file(s) could not be '
                f'updated on disk — check that the drive is connected and files are not locked.'
            )
            QTimer.singleShot(7000, lambda s=norm: self._count_label.setText(s))

    # ── Persistence ───────────────────────────────────────────────────

    def save_state(self) -> None:
        """Call before hiding/destroying the view to persist column order."""
        self._settings.setValue(_SETTINGS_KEY, self._tree.header().saveState())
