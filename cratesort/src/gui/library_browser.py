from __future__ import annotations

import json
import subprocess
import sys as _sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QEvent, QSettings, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMenu, QPushButton, QSplitter, QStackedWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
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

HEADERS = [
    'Artist', 'Tracks', 'Album', 'Genre', 'Style Tags',
    'Duration', 'Format', 'BPM', 'Year', 'Bitrate', 'Comments', 'File Path',
]

_MUTED   = '#a89b85'
_DUMMY   = '__LAZY__'

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_genre: dict[str, tuple[str, str]] = {}  # artist → (genre, conf)
        self._track_overrides: dict[str, str] = {}            # file_path → overridden genre
        self._has_classification = False
        self._library_path: Optional[Path] = None
        self._loaded_inv_id: Optional[int] = None
        self._inventory = []
        # In-memory edits: {file_path: {field: value}}
        self._edits: dict[str, dict[str, str]] = {}
        self._settings = QSettings('JWBC', 'CrateSort')
        # Inline editor state — at most one open at a time
        self._edit_item:     Optional[QTreeWidgetItem] = None
        self._edit_col:      int = -1
        self._edit_widget:   Optional[QLineEdit] = None
        self._edit_original: str = ''   # original text for Escape-cancel

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_empty())    # 0
        self._stack.addWidget(self._build_browser())  # 1
        self._stack.setCurrentIndex(0)

    # ── Public ────────────────────────────────────────────────────────

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
                    # Fix 4: artist-level enrichment keyed by sort-form name
                    self._session_genre[entry.artist] = (entry.display_genre, entry.confidence)
                    # Fix 2: per-track genre overrides from session TrackInfo
                    for track in entry.tracks:
                        if track.genre_tag:
                            self._track_overrides[track.path] = track.genre_tag
                self._has_classification = bool(self._session_genre)
                print(f'[LibraryBrowser] _track_overrides ({len(self._track_overrides)} entries):')
                for p, g in list(self._track_overrides.items())[:10]:
                    print(f'  {Path(p).name} → {g}')
            except Exception as exc:
                import traceback
                print(f'[LibraryBrowser] Session load error: {exc}\n{traceback.format_exc()}')

        self._no_class_banner.setVisible(not self._has_classification)
        self._populate_filters()
        self._edits = {}
        self._load_edits()
        self._rebuild_tree()
        self._stack.setCurrentIndex(1)

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
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._no_class_banner = self._build_banner()
        layout.addWidget(self._no_class_banner)
        layout.addWidget(self._build_toolbar())

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

        # Restore column order from QSettings
        saved = self._settings.value(_SETTINGS_KEY)
        if saved:
            self._tree.header().restoreState(saved)

        layout.addWidget(self._tree, stretch=1)

        footer = QFrame()
        footer.setStyleSheet('QFrame { background: #2F2F2F; border-top: 1px solid #444; }')
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 6, 16, 6)
        self._count_label = QLabel()
        self._count_label.setStyleSheet('color: #a89b85; font-size: 12px;')
        fl.addWidget(self._count_label)
        fl.addStretch()
        layout.addWidget(footer)

        return w

    def _build_banner(self) -> QFrame:
        frame = QFrame()
        frame.setVisible(False)
        frame.setStyleSheet('QFrame { background: #2a2520; border-bottom: 1px solid #D4A04A; }')
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 10, 16, 10)
        msg = QLabel(
            '⚠  Classification has not been run. '
            'Genres shown are from file metadata only. '
            'Run classification from the Dashboard.'
        )
        msg.setWordWrap(True)
        msg.setStyleSheet('color: #D4A04A; font-size: 13px;')
        row.addWidget(msg)
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

        self._genre_cb = QComboBox()
        self._genre_cb.setMinimumWidth(140)
        self._genre_cb.currentTextChanged.connect(self._apply_filter)
        row.addWidget(self._genre_cb)

        self._format_cb = QComboBox()
        self._format_cb.setMinimumWidth(110)
        self._format_cb.currentTextChanged.connect(self._apply_filter)
        row.addWidget(self._format_cb)

        row.addStretch()

        clear = QPushButton('Clear Filters')
        clear.setProperty('flat', 'true')
        clear.clicked.connect(self._clear_filters)
        row.addWidget(clear)

        return tb

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
            else:
                primary, _ = _extract_primary_artist(rec.artist or 'Unknown Artist')
                canonical  = _canonical_artist(primary)
            artist_tracks[canonical].append(rec)

        genres: set[str] = set()
        formats: set[str] = set()

        for artist, tracks in sorted(artist_tracks.items()):
            genre, _ = self._classify_lookup(artist)
            artist_edits = self._edits.get(f'__artist__{artist}', {})
            if 'genre' in artist_edits:
                genre = artist_edits['genre']
            item = self._make_artist_item(artist, tracks, genre)
            self._tree.addTopLevelItem(item)
            if genre:
                genres.add(genre)
            for rec in tracks:
                if rec.extension:
                    formats.add(rec.extension.lstrip('.').upper())

        # Column widths (only set on fresh load to respect QSettings restoreState)
        if not self._settings.value(_SETTINGS_KEY):
            widths = [200, 60, 150, 130, 100, 70, 65, 55, 55, 80, 150, 220]
            for col, w in enumerate(widths):
                self._tree.setColumnWidth(col, w)

        self._tree.setSortingEnabled(True)

        # Fix 4: default A-Z on first load (no saved header state)
        if not self._settings.value(_SETTINGS_KEY):
            self._tree.sortByColumn(LC_ARTIST, Qt.SortOrder.AscendingOrder)

        # Fix 3: enforce min col widths AFTER layout pass (100ms delay)
        QTimer.singleShot(100, self._enforce_min_col_widths)

        n = self._tree.topLevelItemCount()
        t = len(self._inventory)
        self._count_label.setText(f'{n:,} artists · {t:,} tracks')

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

        item.setIcon(LC_ARTIST, _get_artist_icon())
        item.setText(LC_ARTIST, artist)
        item.setText(LC_TRACKS, str(len(tracks)))
        item.setText(LC_GENRE,  genre or '—')
        item.setText(LC_TAGS,   tags)
        item.setText(LC_PATH,   common)

        muted = QBrush(QColor(_MUTED))
        item.setForeground(LC_TRACKS, muted)

        if not genre:
            item.setForeground(LC_GENRE, muted)
            f = item.font(LC_GENRE)
            f.setItalic(True)
            item.setFont(LC_GENRE, f)

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
        if rec and col in _EDITABLE:
            self._edits.setdefault(str(rec.path), {})[_EDITABLE[col]] = new_val
        self._save_edits()

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
        genres = set()
        formats = set()
        for rec in self._inventory:
            if rec.extension:
                formats.add(rec.extension.lstrip('.').upper())

        if self._has_classification:
            for g, _ in self._session_genre.values():
                if g and g not in ('Not classified', 'Unclassified'):
                    genres.add(g)

        self._genre_cb.blockSignals(True)
        self._genre_cb.clear()
        self._genre_cb.addItem('All Genres')
        self._genre_cb.addItems(sorted(genres))
        if not self._has_classification or any(
            not g for g, _ in self._session_genre.values()
        ):
            self._genre_cb.addItem('Unclassified')
        self._genre_cb.blockSignals(False)

        self._format_cb.blockSignals(True)
        self._format_cb.clear()
        self._format_cb.addItem('All Formats')
        self._format_cb.addItems(sorted(formats))
        self._format_cb.blockSignals(False)

    def _apply_filter(self) -> None:
        search   = self._search.text().lower().strip()
        genre_f  = self._genre_cb.currentText()
        format_f = self._format_cb.currentText()

        if genre_f in ('All Genres', ''):
            genre_f = ''
        if format_f in ('All Formats', ''):
            format_f = ''

        visible_count = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            tracks = data.get('tracks', [])
            item_genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''

            # Genre filter
            if genre_f:
                if genre_f == 'Unclassified':
                    if item_genre:
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
        self._genre_cb.setCurrentIndex(0)
        self._format_cb.setCurrentIndex(0)

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
        for item in selected:
            if item.parent() is None:
                data   = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
                artist = data.get('artist', '')
                item.setText(LC_GENRE, new_genre)
                item.setData(LC_GENRE, Qt.ItemDataRole.UserRole + 1, new_genre)
                item.setForeground(LC_GENRE, QBrush(QColor('#f1e3c8')))
                f = item.font(LC_GENRE)
                f.setItalic(False)
                item.setFont(LC_GENRE, f)
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
            self._reassign_track(item, rec)
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

    def _reassign_track(self, child: QTreeWidgetItem, rec) -> None:
        """Move a track to a different (existing or new) artist group."""
        from cratesort.src.gui.classifier_view import _ReassignArtistDialog

        # Collect existing artist names from top-level tree items
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

        parent_item = child.parent()
        parent_data = parent_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
        parent_tracks = parent_data.get('tracks', [])

        # Remove rec from source group
        try:
            parent_tracks.remove(rec)
        except ValueError:
            pass
        parent_item.setText(LC_TRACKS, str(len(parent_tracks)))
        idx = parent_item.indexOfChild(child)
        parent_item.takeChild(idx)

        # Remove source artist group if now empty
        if not parent_tracks:
            top_idx = self._tree.indexOfTopLevelItem(parent_item)
            self._tree.takeTopLevelItem(top_idx)

        # Find or create destination artist group
        dest_item = None
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            top_data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            if top_data.get('artist', '') == new_artist:
                dest_item = top
                break

        if dest_item is not None:
            dest_data = dest_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            dest_tracks = dest_data.get('tracks', [])
            dest_tracks.append(rec)
            dest_item.setText(LC_TRACKS, str(len(dest_tracks)))
            # Ensure children are loaded then add the track
            if dest_item.childCount() == 1 and dest_item.child(0).text(0) == _DUMMY:
                dest_item.takeChild(0)
                for t in dest_tracks:
                    self._make_track_child(dest_item, t)
            else:
                self._make_track_child(dest_item, rec)
        else:
            # Create new artist group for this track
            genre, _ = self._classify_lookup(new_artist)
            dest_item = self._make_artist_item(new_artist, [rec], genre)
            self._tree.addTopLevelItem(dest_item)

        dest_item.setExpanded(True)
        dest_item.setSelected(False)
        self._flash_row_text(dest_item)

        # Persist reassignment so it survives app restart
        original_artist = parent_data.get('artist', '')
        self._edits.setdefault(str(rec.path), {})['reassign_artist'] = new_artist
        self._edits.setdefault(str(rec.path), {})['original_artist'] = original_artist
        self._save_edits()

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

    def save_state(self) -> None:
        """Call before hiding/destroying the view to persist column order."""
        self._settings.setValue(_SETTINGS_KEY, self._tree.header().saveState())
