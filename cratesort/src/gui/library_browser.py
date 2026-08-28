from __future__ import annotations

import json
import subprocess
import sys as _sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from cratesort.src.core.duplicate_consolidator import read_recent_merges

from PyQt6.QtCore import Qt, QByteArray, QEvent, QPoint, QRect, QSettings, QSize, QTimer, pyqtSignal

from cratesort.src.gui.overlays import (
    _CrateSortDialog, _ov_alert, _create_dialog_layout, _AnimatedStatCardWidget,
)
from cratesort.src.utils.undo_manager import (
    UndoManager, LibraryFieldEditCommand, LibraryTagsEditCommand,
    LibraryGenreChangeCommand, LibraryReassignArtistCommand,
)
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap

try:
    from PyQt6.QtSvgWidgets import QSvgWidget as _QSvgWidget  # noqa: F401 (defensive import)
except ImportError:
    pass
from PyQt6.QtWidgets import (
    QAbstractItemView, QAbstractScrollArea, QApplication, QDialog, QDialogButtonBox,
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

# The full fixed taxonomy, display order — shown in the "Why Only These
# Genres?" modal.
_LIBRARY_GENRES: list[str] = sorted(_VALID_GENRES_LOWER.values())

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


def _make_play_glyph_icon():
    """Hover-only play triangle shown in place of the note icon on track
    rows, signaling the row can be clicked (in this icon's hit zone) to
    start playback. 9×14 to match _make_note_icon()'s footprint."""
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPolygonF
    from PyQt6.QtCore import QPointF
    def _pm(color: str) -> QPixmap:
        pm = QPixmap(9, 14)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(QPolygonF([QPointF(1.5, 2), QPointF(1.5, 12), QPointF(8, 7)]))
        p.end()
        return pm
    icon = QIcon()
    icon.addPixmap(_pm('#D17D34'), QIcon.Mode.Normal)
    icon.addPixmap(_pm('#2F2F2F'), QIcon.Mode.Selected)
    return icon


_ARTIST_ICON = None
_TRACK_ICON  = None
_PLAY_GLYPH_ICON = None


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


def _get_play_glyph_icon():
    global _PLAY_GLYPH_ICON
    if _PLAY_GLYPH_ICON is None:
        _PLAY_GLYPH_ICON = _make_play_glyph_icon()
    return _PLAY_GLYPH_ICON

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
_FIELD_TO_COL = {field: col for col, field in _EDITABLE.items()}


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
        layout = _create_dialog_layout(self)

        headline = QLabel('Classifications Not Saved')
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        body = QLabel()
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setText('<div style="line-height: 145%;">You haven\'t accepted your classifications yet — your genre corrections won\'t be written to your files until you do. You can always come back and finish later.</div>')
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
            'QPushButton { background: #c35050; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background: #b03c3c; }'
            'QPushButton:pressed { background: #973434; }'
        )
        leave_btn.clicked.connect(self.accept)
        leave_btn.setAutoDefault(False)

        stay_btn = QPushButton('Stay && Finish')
        stay_btn.setFixedHeight(36)
        stay_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        stay_btn.clicked.connect(self.reject)
        stay_btn.setDefault(True)   # Return keeps you here; Escape does too

        btns.addWidget(leave_btn)
        btns.addStretch()
        btns.addWidget(stay_btn)
        layout.addLayout(btns)


class _GenreLogicDialog(_CrateSortDialog):
    """The record-shop rationale behind the fixed genre column: why the list
    is short, where subgenres go (style tags), and how it feeds the Organize
    folder tree. Opened from the "Why Only These Genres?" link under the
    genre sidebar."""

    # Lightened teal for the small section eyebrows + the inline link: the
    # app's #428175 fails AA at this size on the modal's #2F2F2F surface.
    # Still the interactive/teal family — not a new hue — just readable.
    _ACCENT = '#69A79A'

    _HEADLINE_GAP = 30   # headline → first section
    _SECTION_GAP  = 16   # between whole section groups (and before the button)
    _EYEBROW_GAP  = 8    # eyebrow → its own paragraph (grouped tight)

    def _eyebrow(self, text: str) -> QLabel:
        eb = QLabel(text)
        eb.setStyleSheet(
            f'color: {self._ACCENT}; font-size: 10px; font-weight: 700; '
            'letter-spacing: 0.12em; background: transparent; border: none;'
        )
        return eb

    def _body(self, html: str) -> QLabel:
        b = QLabel()
        b.setTextFormat(Qt.TextFormat.RichText)
        b.setText(f'<div style="line-height: 148%;">{html}</div>')
        b.setWordWrap(True)
        # Pin the wrap width to the real content width. Without this a
        # word-wrapped QLabel guesses a narrower width for sizeHint(), reports
        # too many lines, and the dialog's adjustSize() comes out too tall —
        # then QVBoxLayout spreads the surplus into the gaps between sections
        # (which is why they kept looking doubled).
        b.setFixedWidth(self._content_w)
        b.setStyleSheet(
            'color: #d5c7ad; font-size: 14px; background: transparent; border: none;'
        )
        return b

    def _section(self, eyebrow: str, body_html: str) -> QVBoxLayout:
        """One eyebrow + paragraph as a tight vertical group. The larger
        section gap lives on the parent layout, between whole groups."""
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(self._EYEBROW_GAP)
        box.addWidget(self._eyebrow(eyebrow))
        box.addWidget(self._body(body_html))
        return box

    def __init__(self, parent=None):
        super().__init__(parent)
        # Wide enough that the paragraphs run ~550px — keeps them to 2–3 lines
        # each so the modal stays short rather than tall-and-narrow.
        self.setFixedWidth(700)

        layout = _create_dialog_layout(self)
        self._inner = layout
        m = layout.contentsMargins()
        self._content_w = 700 - 2 - m.left() - m.right()   # dialog − frame border − inner margins
        # Every gap is placed explicitly below — no ambient layout spacing to
        # compound with them.
        layout.setSpacing(0)

        headline = QLabel('Why Only These Genres?')
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(self._HEADLINE_GAP)

        # ── Section 1: record-shop logic + collapsible genre list ──────────
        self._s1 = self._section(
            'RECORD SHOP LOGIC',
            'CrateSort works from a fixed list of genres — similar to how a '
            'record shop organizes its inventory. '
            # A stylesheet is active up the ancestry, so Qt ignores the
            # QPalette Link colour — the brand teal has to live in the markup
            # (inner <span>) or the link renders default system blue.
            f'<a href="#toggle" style="text-decoration:none;">'
            f'<span style="color:{self._ACCENT}; text-decoration:underline;">Click here</span></a> '
            'to see the full genre list.'
        )
        s1_body = self._s1.itemAt(1).widget()
        s1_body.setOpenExternalLinks(False)
        s1_body.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        s1_body.setCursor(Qt.CursorShape.PointingHandCursor)
        s1_body.linkActivated.connect(self._toggle_genre_list)

        self._genre_list_lbl = QLabel('\n'.join(_LIBRARY_GENRES))
        self._genre_list_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 13px; background: transparent; border: none; '
            'padding: 4px 0 0 18px;'
        )
        self._genre_list_lbl.setVisible(False)
        self._s1.addWidget(self._genre_list_lbl)
        layout.addLayout(self._s1)

        # ── Sections 2–4 ─────────────────────────────────────────────────
        for eyebrow, html in (
            ('OK, BUT WHY SO LIMITED?',
             'The whole concept here is to get your shit together. And as your '
             'library grows, the tighter we keep the genre list, the more '
             'organized your library will be — both as files on your drive and '
             'virtually in Serato.'),
            ('LEVERAGE STYLE TAGS',
             'Add style tags in addition to genre assignments to help organize '
             'obscure and alternative artists or tracks — “Funk Rock” and “Old '
             'School”. You can even filter by these tags to build deeper crates.'),
            ('GENRES BECOME FOLDERS',
             "When you run CrateSort's organize feature, each of these genres "
             'will become a top-level directory in your media folder — '
             'reorganizing folders and their files like a record shop would '
             'artists and their albums.'),
        ):
            layout.addSpacing(self._SECTION_GAP)
            layout.addLayout(self._section(eyebrow, html))

        layout.addSpacing(self._SECTION_GAP)

        back_btn = QPushButton('Back to Library')
        back_btn.setFixedHeight(36)
        back_btn.setMinimumWidth(140)
        back_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 0 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        back_btn.clicked.connect(self.accept)
        back_btn.setDefault(True)   # Return / Escape both just dismiss this
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(back_btn)
        layout.addLayout(row)
        # Absorbs the small cushion in _content_h() at the bottom rather than
        # letting the layout spread it into the section gaps.
        layout.addStretch(1)

    def _layout_h(self, lay) -> int:
        """Height of a box layout, summed from each child's OWN sizeHint
        (reliable for our pieces — fixed-px spacers, single-line eyebrows,
        fixed-width wrapped bodies, the plain genre list) rather than the
        layout's own sizeHint, which sticks at a stale value once any child
        has been shown (pyqt gotcha)."""
        m = lay.contentsMargins()
        parts: list[int] = []
        for i in range(lay.count()):
            it = lay.itemAt(i)
            if it.spacerItem() is not None:
                parts.append(it.spacerItem().sizeHint().height())   # addStretch → 0
            elif it.widget() is not None:
                if it.widget().isHidden():
                    continue
                parts.append(it.widget().sizeHint().height())
            elif it.layout() is not None:
                parts.append(self._layout_h(it.layout()))
        return (
            m.top() + m.bottom()
            + sum(parts)
            + lay.spacing() * max(0, len(parts) - 1)
        )

    def _content_h(self) -> int:
        return self._layout_h(self._inner) + 2 + 4   # + frame border + tiny cushion

    def showEvent(self, event) -> None:
        self.ensurePolished()
        for lbl in self.findChildren(QLabel):
            lbl.ensurePolished()
        self._apply_height()
        super().showEvent(event)

    def _apply_height(self) -> None:
        from PyQt6.QtWidgets import QLayout
        h = self._content_h()
        # The layout's minimumSize sticks at its largest-ever value after the
        # first show() (pyqt gotcha) and would clamp any shrink — drop the
        # constraint and force the exact height.
        self._inner.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.setMinimumHeight(0)
        self.setFixedHeight(h)

    def _toggle_genre_list(self, _href: str = '') -> None:
        self._genre_list_lbl.setVisible(not self._genre_list_lbl.isVisible())
        self._apply_height()
        h = self.height()
        if self._overlay is not None:
            pw = self._overlay._parent_window
            origin = pw.mapToGlobal(QPoint(0, 0))
            self.move(
                origin.x() + (pw.width() - self.width()) // 2,
                origin.y() + (pw.height() - h) // 2,
            )

# ---------------------------------------------------------------------------
# _AnalyzeLibraryModal — frameless modal shown during first-run classification
# ---------------------------------------------------------------------------

class _AnalyzeLibraryModal(_CrateSortDialog):
    """Frameless card displayed over the overlay during auto-classify."""

    review_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Wide enough for all 5 stat cards to hold their captions on one line
        # (the cards now refuse to wrap — see _AnimatedStatCardWidget).
        self.setFixedWidth(860)

        # Use standard Teal accent layout (safe action/progress)
        layout = _create_dialog_layout(self)

        headline = QLabel('Analyzing Library…')
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        subtitle = QLabel()
        subtitle.setTextFormat(Qt.TextFormat.RichText)
        subtitle.setText(
            '<div style="line-height: 145%; text-align: center;">'
            "If your library is big, this'll take a while. We're scanning all of "
            "your media files to see if the metadata is correct. You'll be able "
            'to approve, deny, and edit our suggested changes next.'
            '</div>'
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            'color: #d5c7ad; font-size: 13px; background: transparent; border: none;'
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(8)

        # Stat cards row — file-count story first (total, then its recognized/
        # unrecognized breakdown), then the artist/genre payoff that comes out
        # of it, so related numbers read as one connected block left to right.
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._card_files        = _AnimatedStatCardWidget('Files Analyzed',      self)
        self._card_recognized   = _AnimatedStatCardWidget('Files Recognized',    self)
        self._card_unrecognized = _AnimatedStatCardWidget('Files Unrecognized',  self)
        self._card_artists      = _AnimatedStatCardWidget('Artists Recognized',  self)
        self._card_genres       = _AnimatedStatCardWidget('Genres Recognized',   self)
        cards_row.addWidget(self._card_files)
        cards_row.addWidget(self._card_recognized)
        cards_row.addWidget(self._card_unrecognized)
        cards_row.addWidget(self._card_artists)
        cards_row.addWidget(self._card_genres)
        layout.addLayout(cards_row)
        layout.addSpacing(4)

        # Footer note — the "why this matters" payoff, always visible (not just
        # on completion) so it's read while people are still watching the cards.
        footer = QLabel()
        footer.setTextFormat(Qt.TextFormat.RichText)
        footer.setText(
            '<div style="line-height: 140%; text-align: center;">'
            'This stage not only helps you find and sort your files, but it will '
            'help determine where your files go during the Organize stage.'
            '</div>'
        )
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setWordWrap(True)
        footer.setStyleSheet('color: #a89b85; font-size: 11px; background: transparent; border: none;')
        # Small note, not full-width body text — cap it at half the dialog's
        # content width (same DPI-derived padding as _create_dialog_layout).
        screen = QApplication.primaryScreen()
        dpi = screen.physicalDotsPerInch() if screen else 96.0
        pad = int(round(dpi * 0.7 * 0.8))
        footer.setFixedWidth(int((720 - 2 * pad) * 0.68))
        layout.addWidget(footer, 0, Qt.AlignmentFlag.AlignHCenter)

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
        self._review_btn.setEnabled(False)
        self._review_btn.clicked.connect(self.review_requested.emit)
        btn_layout.addWidget(self._review_btn)
        self._action_stack.addWidget(btn_wrapper)  # index 1

        layout.addWidget(self._action_stack)

    def update_stats(
        self,
        files_analyzed: int,
        files_recognized: int,
        files_unrecognized: int,
        artists_recognized: int,
        genres_recognized: int,
    ) -> None:
        self._card_files.update_target(files_analyzed)
        self._card_recognized.update_target(files_recognized)
        self._card_unrecognized.update_target(files_unrecognized)
        self._card_artists.update_target(artists_recognized)
        self._card_genres.update_target(genres_recognized)

    def update_percent(self, percent: int) -> None:
        self._progress_bar.setValue(percent)

    def on_classification_complete(self) -> None:
        self._review_btn.setEnabled(True)
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
    track_selected       = pyqtSignal(str)   # file path
    album_art_requested  = pyqtSignal(str)
    # Emitted after an inline edit is committed (file_path, field, new_value)
    track_field_changed  = pyqtSignal(str, str, str)
    # Emitted when the hover play-icon on a track row is clicked
    play_requested       = pyqtSignal(object)  # TrackRecord

    def __init__(self, undo_manager: Optional['UndoManager'] = None, parent=None):
        super().__init__(parent)
        self._undo_manager = undo_manager
        self._session_genre: dict[str, tuple[str, str]] = {}  # artist → (genre, conf)
        self._session_artists: dict[str, str] = {}            # track_path → artist
        self._track_overrides: dict[str, str] = {}            # file_path → overridden genre
        self._has_classification = False
        self._library_path: Optional[Path] = None
        self._loaded_inv_id: Optional[int] = None
        self._inventory = []
        self._edits: dict[str, dict[str, str]] = {}
        self._confidence_backfilled = False
        self._settings = QSettings('JWBC', 'CrateSort')
        # Genre sidebar selection
        self._sidebar_genre: str = 'All'
        # Classify mode state
        self._classify_mode: bool = False
        self._classify_session = None
        self._classify_results: dict[str, tuple[str, str]] = {}  # artist → (genre, conf)
        self._classify_worker = None
        self._new_track_paths: set[str] = set()  # paths added via Add Tracks this session
        self._recent_merges: dict[str, dict] = {}  # normalized dest path → {count, most_recent}
        # Tracks the last genre edit for post-sidebar-rebuild navigation
        self._last_edited_artist:  Optional[str] = None
        self._last_assigned_genre: Optional[str] = None

        # Auto-classify modal state
        self._analyze_modal:          Optional[_AnalyzeLibraryModal] = None
        self._auto_classify_session                                   = None
        self._classify_tally = None  # ClassifyProgressTally, imported lazily

        # Inline editor state — at most one open at a time
        self._edit_item:     Optional[QTreeWidgetItem] = None
        self._edit_col:      int = -1
        self._edit_widget:   Optional[QLineEdit] = None
        self._edit_original: str = ''

        # Hover-play-icon state (mirrors CrateManagerView._crate_hover_item)
        self._hover_track_item: Optional[QTreeWidgetItem] = None
        # Path of the track currently loaded in the playback bar — its row
        # keeps the play-triangle icon even when unhovered, so you can see
        # which track is playing. Set via set_now_playing().
        self._now_playing_path: Optional[str] = None
        # True between a consumed hover-play-icon press and its release, so
        # the whole gesture is swallowed (see eventFilter).
        self._play_icon_press_active: bool = False
        # Session-lived tree state (expanded artists + current selection),
        # re-applied across tab switches so returning to Library doesn't
        # collapse everything or lose your place. Mirrors CrateManagerView's
        # _save_tree_state / _restore_tree_state. Reset only on library change
        # (and, implicitly, app restart).
        self._session_expanded_artists: set[str] = set()
        self._session_selected: Optional[tuple[str, str]] = None

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
        # A genuine library change invalidates the remembered tree state
        # (artist names won't carry over); a same-library reload (tab switch,
        # post-classify refresh) keeps it. Gate the save below on this.
        _lib_changed = (
            self._library_path is not None and self._library_path != library_path
        )

        self._library_path  = library_path
        self._loaded_inv_id = id(inventory)
        self._inventory     = list(inventory)
        self._new_track_paths.clear()
        self._recent_merges = read_recent_merges(library_path)

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
            except Exception as exc:
                import traceback
                print(f'[LibraryBrowser] Session load error: {exc}\n{traceback.format_exc()}')

        # Confidence and Status are both persistent columns — visible whenever
        # classification data exists, in or out of classify mode. Their
        # headers are never re-labeled (see HEADERS) since each only ever
        # holds its own single kind of value.
        self._tree.setColumnHidden(LC_CLS_CONF,   not self._has_classification)
        self._tree.setColumnHidden(LC_CLS_STATUS, not self._has_classification)

        self._edits = {}
        self._load_edits()

        # Capture the still-intact tree from the previous visit before it's
        # torn down, so expansion + selection survive the rebuild. Skip (and
        # clear) when the library itself changed — stale artist names must not
        # carry over.
        if _lib_changed:
            self._session_expanded_artists = set()
            self._session_selected = None
        else:
            expanded, selected = self._save_tree_state()
            if expanded:
                self._session_expanded_artists = expanded
            if selected:
                self._session_selected = selected

        self._rebuild_tree()
        self._populate_genre_sidebar()
        self._restore_tree_state(self._session_expanded_artists, self._session_selected)
        self._stack.setCurrentIndex(1)

        # Auto-open the classify review banner — no manual button click required —
        # whenever there's something to review: either nothing has ever been
        # accepted yet, or _count_unclassified_artists() found an artist that
        # was previously acknowledged Unclassified but now has a genuinely new,
        # real proposal (e.g. a style tag added since the last visit resolved
        # it). Artists with no real signal still stay silent forever, since
        # _count_unclassified_artists() only counts a *change*, not the mere
        # fact of being unclassified — a permanently-unresolvable track won't
        # re-pop this on every tab visit.
        if (not self._is_classification_complete() or self._count_unclassified_artists() > 0) \
                and self.isVisible():
            self._on_classify_clicked(auto_classify=True)

        self._refresh_classify_btn()

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
        self._tree.setMouseTracking(True)
        self._tree.viewport().setMouseTracking(True)
        self._tree.viewport().installEventFilter(self)

        # Hidden until a library with classification data is loaded. Proposed
        # Genre stays classify-mode-only after that; Confidence/Status become
        # permanent (see load()).
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
        footer.setStyleSheet('QFrame { background: #2F2F2F; border: none; }')
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

        msg = QLabel()
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            '<div style="line-height: 19px;">Here’s your library as we see it: sorted and '
            'grouped by artist. Double-click an artist row to reveal associated files. Right-click '
            'a file to approve or edit artist association. This step ensures that '
            'your files are classified correctly. All folders and filenames echo what is seen here. '
            "If you're unsure, mark it Unclassified. You can always come back and change it.</div>"
        )
        msg.setWordWrap(True)
        msg.setStyleSheet(
            'color: #7bbdad; font-size: 12px; background: transparent; border: none;'
        )
        row.addWidget(msg, stretch=1)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #7bbdad; '
            'border: 1px solid #2d4a44; border-radius: 6px; padding: 0 16px; font-size: 13px; }'
            'QPushButton:hover { background: rgba(45,74,68,0.4); }'
        )
        cancel_btn.clicked.connect(self._exit_classify_mode_cancel)
        row.addWidget(cancel_btn)

        accept_btn = QPushButton('Accept Reclassifications')
        accept_btn.setFixedHeight(36)
        accept_btn.setStyleSheet(
            'QPushButton { background: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 0 16px; font-size: 13px; font-weight: 600; }'
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
        row.setContentsMargins(12, 16, 12, 16)
        row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText('Search artist, title, album…')
        self._search.setMaximumWidth(260)
        self._search.setFixedHeight(36)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        row.addWidget(self._search)

        clear = QPushButton('Clear Filters')
        clear.setProperty('flat', 'true')
        clear.setFixedHeight(36)
        clear.clicked.connect(self._clear_filters)
        row.addWidget(clear)

        row.addStretch()

        self._classify_btn = QPushButton('Classify Library')
        self._classify_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; '
            'font-size: 13px; font-weight: 600; border: none; border-radius: 6px; '
            'padding: 0 16px; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
            'QPushButton:disabled { background-color: #2a3a37; color: #5a8a80; }'
        )
        self._classify_btn.setFixedHeight(36)
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
            'QPushButton { background-color: #428175; color: #ffffff; '
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
        """Count artists that still need classify-mode review: never touched,
        or previously acknowledged as Unclassified but the latest classify
        pass now has a real, different proposal (e.g. a newly-added style tag
        resolved it). A deliberate genre override (Change Genre/Reassign) is
        always considered handled and never re-surfaced.
        """
        _UC = {'', '—', 'Unclassified', 'Untagged'}
        count = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
            if genre not in _UC:
                continue
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            existing_genre = self._edits.get(f'__artist__{artist}', {}).get('genre')
            if existing_genre and existing_genre not in _UC:
                continue  # deliberate override — handled
            if existing_genre in _UC:
                proposed, _conf = self._session_genre.get(artist, ('', ''))
                if proposed in _UC:
                    continue  # acknowledged, and still nothing new to review
            count += 1
        return count

    def has_unsaved_classify_changes(self) -> bool:
        return self._classify_mode

    def _is_classification_complete(self) -> bool:
        if not self._library_path:
            return False
        flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
        return flag_path.exists()

    def _refresh_classify_btn(self) -> None:
        if self._classify_mode:
            return
        # Hidden entirely once nothing's left unclassified — not muted/disabled.
        # A standalone "Reclassify" button was tried and deliberately dropped
        # (classification already reruns automatically on every app launch).
        # That reasoning held as long as nothing could change the classifier's
        # own read of a track without a manual "Change Genre" override — but
        # Style Tags (see classifier.py Tier 2/4) broke that assumption: a
        # user can add a style tag with no genre override at all and get a
        # genuinely different proposal on the next launch. So this button
        # stays visible/reappears for artists acknowledged Unclassified whose
        # latest classify pass now has a real proposal — see
        # _count_unclassified_artists(). Deliberate genre overrides (Change
        # Genre/Reassign) are still always considered handled.
        self._classify_btn.setVisible(self._count_unclassified_artists() > 0)

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
        # Size the list to its own content so the link below can sit directly
        # under the last genre row instead of being pinned to the column
        # floor; it still scrolls internally if the window is too short.
        self._genre_sidebar_list.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        layout.addWidget(self._genre_sidebar_list)

        # Link sits right beneath the last genre. The ⓘ marks it as a note
        # rather than another genre row. At rest it's the same muted beige as
        # the genre rows above; hovering warms it to teal to signal it's
        # interactive.
        logic_link = QPushButton('ⓘ  Why Only These Genres?')
        logic_link.setObjectName('genre_logic_link')
        logic_link.setCursor(Qt.CursorShape.PointingHandCursor)
        logic_link.setStyleSheet(
            'QPushButton#genre_logic_link { color: #a89b85; font-size: 11px; '
            'font-weight: 600; letter-spacing: 0.02em; text-align: left; '
            'padding: 10px 14px; background: transparent; border: none; '
            'border-top: 1px solid #2a2a2a; }'
            'QPushButton#genre_logic_link:hover { color: #69A79A; }'
        )
        logic_link.clicked.connect(self._show_genre_logic)
        layout.addWidget(logic_link)
        layout.addStretch(1)   # leftover space goes below the link, not above it

        return frame

    def _show_genre_logic(self) -> None:
        _GenreLogicDialog(self.window()).exec()

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
        self._confidence_backfilled = False

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

        if self._confidence_backfilled:
            self._save_edits()

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
                # ResizeToContents only measures currently-rendered rows — in a large
                # library most artist rows are virtualized and never painted, so it
                # badly undersizes the column. Measure the real widest artist name
                # directly against the underlying data instead.
                fm = QFontMetrics(self._tree.font())
                widest = max(
                    (fm.horizontalAdvance(self._tree.topLevelItem(i).text(LC_ARTIST))
                     for i in range(self._tree.topLevelItemCount())),
                    default=0,
                )
                artist_w = widest + 50  # padding for tree expand-arrow/indent
                if artist_w > self._tree.columnWidth(LC_ARTIST):
                    self._tree.setColumnWidth(LC_ARTIST, artist_w)
            QTimer.singleShot(100, _resize_to_content)

        n = self._tree.topLevelItemCount()
        t = len(self._inventory)
        self._count_label.setText(f'{n:,} artists · {t:,} tracks')
        self._update_empty_state()

        # _rebuild_tree() only ever paints the persistent Status column
        # (LC_CLS_CONF via _derive_persistent_status in _make_top_level_item)
        # — it has no idea about classify-mode's own Proposed Genre/Confidence
        # columns. Instant-edit actions available from the tree's right-click
        # menu (Change Genre, Reassign Artist, Edit Style Tags, ...) all call
        # this method to refresh after writing an edit, and those menus are
        # reachable while the classify-mode review banner is still open — so
        # without this, a single manual edit mid-review would wipe every
        # other row's active review painting and leave LC_CLS_PROPOSED blank,
        # silently breaking "Accept Reclassifications" for the whole library
        # (it reads that now-blank text to decide what to apply).
        if self._classify_mode:
            self._populate_classify_columns()

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

        # Confidence (LC_CLS_CONF) and Status (LC_CLS_STATUS) are permanent,
        # single-purpose columns — always populated here, in and out of
        # classify mode, so their headers never need to lie about what's in
        # them (Confidence never shows a Status-type value like "Edited" or
        # vice versa). Confidence shows the classifier's raw tier for this
        # artist; Status shows the persistent Approved/Edited/Unclassified
        # state. Neither is touched by classify-mode's own review painting
        # (_populate_classify_columns, Proposed Genre only) — this is the
        # only place either column is ever written.
        #
        # Once an artist is settled (Approved or Edited), Confidence always
        # reads MATCHED — frozen in library_edits.json at decision time (see
        # _apply_library_genre / _exit_classify_mode_accept). Deliberate,
        # confirmed with Jace 2026-08-07: a library the user has already
        # reviewed shouldn't keep flashing the pre-decision LOW/NONE color
        # forever — that reads as "still needs attention" / an uncleaned
        # library even after they've explicitly signed off. The original
        # tier is only ever meaningful before a decision is made; a future
        # "reset classification" feature can surface it again on demand.
        _, confidence = self._classify_lookup(artist)
        frozen = self._frozen_confidence(artist)
        existing_override = self._edits.get(f'__artist__{artist}', {}).get('genre')
        if frozen != 'MATCHED' and existing_override and existing_override not in _UC_ARTIST:
            # Backfill/migrate: covers artists settled before Confidence-
            # freezing existed at all (frozen == '') and artists frozen by
            # an earlier build of this feature that froze the original tier
            # instead of always MATCHED (frozen == 'HIGH'/'LOW'/...). Either
            # way, once settled it should read MATCHED from here on.
            self._edits[f'__artist__{artist}']['confidence'] = 'MATCHED'
            self._confidence_backfilled = True
            frozen = 'MATCHED'
        confidence = frozen or confidence
        if confidence:
            item.setText(LC_CLS_CONF, confidence)
            item.setForeground(LC_CLS_CONF, QBrush(QColor(self._CONF_COLORS.get(confidence, '#a89b85'))))

        status_label, status_color = self._derive_persistent_status(artist)
        item.setText(LC_CLS_STATUS, status_label)
        item.setForeground(LC_CLS_STATUS, QBrush(QColor(status_color)) if status_color else QBrush())

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

        is_new = str(rec.path) in self._new_track_paths
        merge_info = self._recent_merges.get(unicodedata.normalize('NFC', str(rec.path)))
        child.setIcon(LC_ARTIST, self._resting_track_icon(str(rec.path)))
        prefix = '◆ ' if is_new else ('⟳ ' if merge_info else '')
        child.setText(LC_ARTIST, f'  {prefix}{title}')
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
            if merge_info:
                _merged_brush = QBrush(QColor('#D17D34'))
                for col in range(len(HEADERS)):
                    child.setForeground(col, _merged_brush)
                count = merge_info['count']
                try:
                    most_recent = datetime.fromisoformat(merge_info['most_recent']).strftime('%B %d, %Y')
                except Exception:
                    most_recent = merge_info['most_recent']
                child.setToolTip(
                    LC_ARTIST,
                    f'Absorbed {count} duplicate cop{"y" if count == 1 else "ies"} on {most_recent}',
                )
            elif is_new:
                _new_brush = QBrush(QColor('#5c9d94'))
                for col in range(len(HEADERS)):
                    child.setForeground(col, _new_brush)
                child.setToolTip(LC_ARTIST, 'Newly added — classify when ready')
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

    def _frozen_confidence(self, artist: str) -> str:
        """Confidence tier frozen at the moment this artist was last settled
        (Approved/Edited via Accept Reclassifications, right-click Approve, or
        Change Genre), or '' if never settled. See _apply_library_genre /
        _exit_classify_mode_accept for where this gets written."""
        return self._edits.get(f'__artist__{artist}', {}).get('confidence', '')

    # ── Lazy loading ──────────────────────────────────────────────────

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.parent():
            return  # only artist top-level items
        if item.childCount() == 1 and item.child(0).text(0) == _DUMMY:
            item.takeChild(0)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            for rec in data.get('tracks', []):
                self._make_track_child(item, rec)
        # Selection is intentionally left alone: an artist you double-click to
        # expand stays selected (your place marker) until you click elsewhere,
        # matching the crate tree.

    # ── Tree state (expanded artists + selection) across tab switches ──

    def _save_tree_state(self) -> tuple[set[str], Optional[tuple[str, str]]]:
        expanded: set[str] = set()
        selected: Optional[tuple[str, str]] = None
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist')
            if artist and top.isExpanded():
                expanded.add(artist)
        sel = self._tree.selectedItems()
        if sel:
            it = sel[0]
            if it.parent() is None:
                data = it.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
                if data.get('artist'):
                    selected = ('artist', data['artist'])
            else:
                rec = it.data(LC_PATH, Qt.ItemDataRole.UserRole)
                if rec is not None and hasattr(rec, 'path'):
                    selected = ('track', str(rec.path))
        return expanded, selected

    def _restore_tree_state(
        self, expanded: set[str], selected: Optional[tuple[str, str]]
    ) -> None:
        if not expanded and not selected:
            return
        target: Optional[QTreeWidgetItem] = None
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist')
            if artist and artist in expanded:
                top.setExpanded(True)  # fires _on_item_expanded → lazy-builds children
            if selected and selected[0] == 'artist' and artist == selected[1]:
                target = top
        if selected and selected[0] == 'track':
            target = self._find_track_item(selected[1])
        if target is not None:
            self._tree.setCurrentItem(target)
            target.setSelected(True)
            self._tree.scrollToItem(
                target, QAbstractItemView.ScrollHint.PositionAtCenter
            )

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

        if obj is self._tree.viewport():
            et = event.type()
            if et == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    # Arm BEFORE dispatching: _handle_play_icon_click emits
                    # play_requested, whose handler reads album art + primes
                    # QMediaPlayer and can pump the event queue — a mouse-move
                    # delivered reentrantly there must already be swallowed.
                    self._play_icon_press_active = True
                    if self._handle_play_icon_click(event.position().toPoint()):
                        # Swallow the WHOLE gesture (press + any drag +
                        # release). The hover-play icon must never touch the
                        # tree's selection — letting the move/release through
                        # after a consumed press lets QTreeView rubber-band
                        # the selection from its stale press anchor (the
                        # previously-selected row), highlighting every row in
                        # between.
                        return True
                self._play_icon_press_active = False
            elif et == QEvent.Type.MouseButtonRelease:
                if self._play_icon_press_active:
                    self._play_icon_press_active = False
                    return True
            elif et == QEvent.Type.MouseMove:
                if self._play_icon_press_active:
                    if event.buttons() & Qt.MouseButton.LeftButton:
                        return True  # still mid-gesture — don't let the tree drag-select
                    self._play_icon_press_active = False  # button already up: self-heal
                self._update_hover_play_icon(event.position().toPoint())
            elif et == QEvent.Type.Leave:
                self._play_icon_press_active = False
                self._clear_hover_play_icon()

        return super().eventFilter(obj, event)

    # ── Hover-play-icon (click to start playback) ───────────────────────

    _ICON_HIT_WIDTH = 28  # generous click target — indentation + icon + slop

    def _pos_in_icon_hit_zone(self, item: QTreeWidgetItem, pos) -> bool:
        index = self._tree.indexFromItem(item, LC_ARTIST)
        rect = self._tree.visualRect(index)
        hit = QRect(rect.left(), rect.top(), self._ICON_HIT_WIDTH, rect.height())
        return hit.contains(pos)

    def _handle_play_icon_click(self, pos) -> bool:
        item = self._tree.itemAt(pos)
        if item is None or item.parent() is None:
            return False  # not a track row
        if not self._pos_in_icon_hit_zone(item, pos):
            return False
        rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
        if not rec or not hasattr(rec, 'path'):
            return False
        self.play_requested.emit(rec)
        self.track_selected.emit(str(rec.path))
        self.album_art_requested.emit(str(rec.path))
        return True

    def _resting_track_icon(self, path_str: str):
        """The icon a track row shows when NOT hovered: the play triangle if
        it's the track currently loaded in the playback bar, else the note."""
        if path_str and path_str == self._now_playing_path:
            return _get_play_glyph_icon()
        return _get_track_icon()

    def _restore_row_icon(self, item: Optional[QTreeWidgetItem]) -> None:
        if item is None:
            return
        rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
        path_str = str(rec.path) if rec is not None and hasattr(rec, 'path') else ''
        item.setIcon(LC_ARTIST, self._resting_track_icon(path_str))

    def _update_hover_play_icon(self, pos) -> None:
        item = self._tree.itemAt(pos)
        target = item if (item is not None and item.parent() is not None) else None
        if target is self._hover_track_item:
            return
        self._restore_row_icon(self._hover_track_item)
        if target is not None:
            target.setIcon(LC_ARTIST, _get_play_glyph_icon())
        self._hover_track_item = target

    def _clear_hover_play_icon(self) -> None:
        if self._hover_track_item is not None:
            self._restore_row_icon(self._hover_track_item)
            self._hover_track_item = None

    def set_now_playing(self, path) -> None:
        """Mark the track loaded in the playback bar so its row keeps the
        play-triangle icon while unhovered. Called whenever playback starts
        on a new track."""
        new = str(path) if path else None
        if new == self._now_playing_path:
            return
        prev = self._now_playing_path
        self._now_playing_path = new
        for p in (prev, new):
            if not p:
                continue
            item = self._find_track_item(p)
            # The hovered row is owned by the hover logic (already a triangle);
            # it'll pick up the right resting icon when the cursor leaves.
            if item is not None and item is not self._hover_track_item:
                item.setIcon(LC_ARTIST, self._resting_track_icon(p))

    # ── Skip next/previous (playback bar) ────────────────────────────────
    # "Next/previous track across the whole currently-filtered library" —
    # walks the full per-artist track lists (stored on each top-level item's
    # data regardless of whether that artist has ever been expanded), so
    # skip continues through the entire visible/filtered library, not just
    # whatever rows happen to already be expanded. Respects the current
    # genre-sidebar/search filter (skips hidden top-level artist rows) but
    # not per-row expand state — the destination artist gets auto-expanded
    # and scrolled into view as a side effect of skipping to it.

    def next_track_after(self, current_path: str):
        return self._adjacent_track(current_path, forward=True)

    def previous_track_before(self, current_path: str):
        return self._adjacent_track(current_path, forward=False)

    def _full_filtered_tracks(self) -> list:
        """Tracks in the order actually shown in the tree — NOT the raw
        scan-order list stored on each artist's data. Those only happen to
        match when sorted A-Z by artist; under any other active column sort
        (genre, BPM, duration, whatever the user clicked) they diverge, which
        is exactly what made skip look random. Reading the real tree order is
        the only way to match what's on screen regardless of sort column.
        Artists never opened are transiently expanded just long enough to
        read their real (sorted) child order, then restored to how they were —
        this happens synchronously with no repaint in between, so it's not
        visible as a flicker."""
        tracks = []
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            if top.isHidden():
                continue
            was_expanded = top.isExpanded()
            if not was_expanded:
                top.setExpanded(True)
            for ci in range(top.childCount()):
                rec = top.child(ci).data(LC_PATH, Qt.ItemDataRole.UserRole)
                if rec is not None:
                    tracks.append(rec)
            if not was_expanded:
                top.setExpanded(False)
        return tracks

    def _adjacent_track(self, current_path: str, forward: bool):
        tracks = self._full_filtered_tracks()
        if not forward:
            tracks.reverse()
        found_current = False
        for rec in tracks:
            if found_current:
                self._reveal_track(rec)
                return rec
            if str(rec.path) == current_path:
                found_current = True
        self._set_status('No more tracks to skip to.')
        return None

    def _reveal_track(self, rec) -> None:
        """Expand the artist group containing rec (if needed) and scroll to
        it, so skip always shows you where playback moved to — even into a
        row you'd never opened."""
        path_str = str(rec.path)
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            if any(str(r.path) == path_str for r in data.get('tracks', [])):
                if not top.isExpanded():
                    top.setExpanded(True)
                item = self._find_track_item(path_str)
                if item:
                    self._tree.clearSelection()
                    item.setSelected(True)
                    self._tree.scrollToItem(item)
                break

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

        rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
        field = _EDITABLE.get(col)
        if not (rec and field):
            return

        if self._undo_manager:
            cmd = LibraryFieldEditCommand(self, str(rec.path), field, original, new_val)
            self._undo_manager.push(cmd)  # execute() updates cell + saves + writes disk
        else:
            self._apply_library_field(str(rec.path), field, new_val)

    def _flash_row_text(self, item: QTreeWidgetItem) -> None:
        """Flash all cells in the row to teal for 1.5s, then restore original colors."""
        n = self._tree.columnCount()
        original = [item.foreground(c) for c in range(n)]
        teal = QBrush(QColor('#428175'))
        for c in range(n):
            item.setForeground(c, teal)

        def _restore(it=item, colors=original) -> None:
            for c, brush in enumerate(colors):
                it.setForeground(c, brush)

        QTimer.singleShot(1500, _restore)

    # ── Undo/redo command support ────────────────────────────────────────

    def _resolve_track(self, path_str: str):
        for rec in self._inventory:
            if str(rec.path) == path_str:
                return rec
        return None

    def _find_track_item(self, path_str: str) -> Optional[QTreeWidgetItem]:
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            for ci in range(top.childCount()):
                child = top.child(ci)
                rec = child.data(LC_PATH, Qt.ItemDataRole.UserRole)
                if rec and str(rec.path) == path_str:
                    return child
        return None

    def _find_item_by_key(self, key: str) -> Optional[QTreeWidgetItem]:
        if key.startswith('__artist__'):
            artist = key[len('__artist__'):]
            for i in range(self._tree.topLevelItemCount()):
                top = self._tree.topLevelItem(i)
                data = top.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
                if data.get('artist', '') == artist:
                    return top
            return None
        return self._find_track_item(key)

    def _flash_disk_failure(self, message: Optional[str] = None) -> None:
        message = message or (
            '⚠ Could not write to file — check that the drive is connected '
            'and the file is not locked.'
        )
        saved_text = self._count_label.text()
        self._count_label.setText(message)
        QTimer.singleShot(5000, lambda t=saved_text: self._count_label.setText(t))

    def _set_status(self, text: str, teal: bool = False) -> None:
        """Transient status message reusing the count label — mirrors CrateManagerView._set_status."""
        if not text:
            return
        saved_text  = self._count_label.text()
        saved_style = self._count_label.styleSheet()
        if teal:
            self._count_label.setStyleSheet('color: #428175; font-size: 13px; font-weight: 600;')
        self._count_label.setText(text)

        def _restore(t=saved_text, s=saved_style) -> None:
            self._count_label.setStyleSheet(s)
            self._count_label.setText(t)

        QTimer.singleShot(4000, _restore)

    def _write_disk_field(self, rec, field: str, value: str) -> bool:
        from cratesort.src.core.file_organizer import write_file_metadata
        ok = write_file_metadata(rec.path, field, value)
        if ok:
            if field == 'title':
                rec.title = value
            elif field == 'album':
                rec.album = value
            elif field == 'bpm':
                try:
                    rec.bpm = float(value)
                except (ValueError, TypeError):
                    pass
            elif field == 'year':
                rec.year = value
            elif field == 'comment':
                rec.comment = value
            elif field == 'genre':
                rec.genre = value
            elif field == 'artist':
                rec.artist = value
        return ok

    def _apply_library_field(self, file_path: str, field: str, value: str) -> None:
        """Set a single track field to `value` — shared by execute() and undo()."""
        self._edits.setdefault(file_path, {})[field] = value
        self._save_edits()
        self.track_field_changed.emit(file_path, field, value)

        item = self._find_track_item(file_path)
        col = _FIELD_TO_COL.get(field)
        if item and col is not None:
            item.setText(col, f'  {value}' if col == LC_ARTIST else value)

        if field != 'tags':
            rec = self._resolve_track(file_path)
            if rec and not self._write_disk_field(rec, field, value):
                self._flash_disk_failure()
                return

        if item:
            parent = item.parent()
            if parent:
                parent.setExpanded(True)
            item.setSelected(False)
            self._tree.clearSelection()
            self._flash_row_text(item)
            self._tree.scrollToItem(item)

    def _apply_library_tags(self, key: str, tags_str: str) -> None:
        """Set the tags string on a track or artist key — shared by execute() and undo()."""
        if tags_str:
            self._edits.setdefault(key, {})['tags'] = tags_str
        else:
            self._edits.get(key, {}).pop('tags', None)
            if key in self._edits and not self._edits[key]:
                del self._edits[key]
        self._save_edits()
        item = self._find_item_by_key(key)
        if item:
            item.setText(LC_TAGS, tags_str)
            parent = item.parent()
            if parent:
                parent.setExpanded(True)
            item.setSelected(False)
            self._flash_row_text(item)
            self._tree.scrollToItem(item)

    def _apply_library_genre(self, edits_map: dict, disk_map: dict) -> None:
        """Set genre for one or more keys (track path or __artist__X) and write
        the affected files to disk — shared by execute() and undo()."""
        for key, genre in edits_map.items():
            if genre is None:
                self._edits.get(key, {}).pop('genre', None)
                self._edits.get(key, {}).pop('confidence', None)
                if key in self._edits and not self._edits[key]:
                    del self._edits[key]
            else:
                self._edits.setdefault(key, {})['genre'] = genre
                # Freeze Confidence to MATCHED the moment this artist is
                # settled (Approved or Edited) — a reviewed library shouldn't
                # keep flashing the pre-decision LOW/NONE color at the user
                # forever; that reads as "still needs attention" even after
                # they've explicitly signed off. See _frozen_confidence for
                # the read side.
                if key.startswith('__artist__'):
                    self._edits[key]['confidence'] = 'MATCHED'

        # Stage a per-track genre entry for anything that actually writes to
        # disk successfully — same "free-tier write-through" pattern used for
        # every other track field (title/album/comment/...). Without this,
        # the track row's displayed genre (_make_track_child) keeps reading
        # the stale self._track_overrides snapshot from classify-session-load
        # time instead of the value that was just written, even though
        # rec.genre itself is correctly updated by _write_disk_field.
        disk_failures = 0
        for path, genre in disk_map.items():
            rec = self._resolve_track(path)
            if rec:
                if self._write_disk_field(rec, 'genre', genre):
                    self._edits.setdefault(path, {})['genre'] = genre
                else:
                    disk_failures += 1
        self._save_edits()

        if disk_failures:
            self._flash_disk_failure(
                f'⚠ {disk_failures} track(s) could not be updated on disk — '
                f'check that the drive is connected and files are not locked.'
            )

        artist_changes = {
            k[len('__artist__'):]: v for k, v in edits_map.items()
            if k.startswith('__artist__') and v is not None
        }
        track_changes = {
            k: v for k, v in edits_map.items()
            if not k.startswith('__artist__') and v is not None
        }
        self._sync_genres_to_session(artist_changes, track_changes)

        self._rebuild_tree()

        # Follow the last-touched artist to wherever its genre bucket now lives
        # (execute AND undo both land here) so the sidebar filter + selection
        # return to it instead of falling back to "All".
        artist_keys = [k for k in edits_map if k.startswith('__artist__')]
        if artist_keys:
            artist = artist_keys[-1][len('__artist__'):]
            artist_item = self._find_item_by_key(f'__artist__{artist}')
            if artist_item:
                self._last_edited_artist  = artist
                self._last_assigned_genre = artist_item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''

        self._populate_genre_sidebar()
        self._update_empty_state()
        self._flash_keys(edits_map.keys())

    def _apply_library_reassign(self, edits_map: dict, disk_map: dict) -> None:
        """Replace each track's edit dict wholesale and write its artist tag to
        disk — shared by execute() and undo() of a reassignment."""
        for path, edit_dict in edits_map.items():
            if edit_dict:
                self._edits[path] = edit_dict
            else:
                self._edits.pop(path, None)
        self._save_edits()

        disk_failures = 0
        for path, artist in disk_map.items():
            rec = self._resolve_track(path)
            if rec and not self._write_disk_field(rec, 'artist', artist):
                disk_failures += 1
        if disk_failures:
            self._flash_disk_failure(
                f'⚠ {disk_failures} track(s) could not be updated on disk — '
                f'check that the drive is connected and files are not locked.'
            )

        self._rebuild_tree()
        self._populate_genre_sidebar()
        self._update_empty_state()

        for path in edits_map:
            item = self._find_track_item(path)
            if item:
                parent = item.parent()
                if parent:
                    parent.setExpanded(True)
                item.setSelected(False)
                self._flash_row_text(item)
                self._tree.scrollToItem(item)
        self._tree.clearSelection()

    def _flash_keys(self, keys) -> None:
        """After a full tree rebuild, re-find, scroll to, and flash each affected row."""
        found = [self._find_item_by_key(k) for k in keys]
        for item in found:
            if item:
                item.setSelected(False)
                self._flash_row_text(item)
                self._tree.scrollToItem(item)
        self._tree.clearSelection()

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

    def _apply_filter(self) -> None:
        search   = self._search.text().lower().strip()
        genre_f  = self._sidebar_genre if self._sidebar_genre != 'All' else ''

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
        if search or genre_f:
            self._count_label.setText(f'{visible_count:,} of {total:,} artists visible')
        else:
            t = len(self._inventory)
            self._count_label.setText(f'{total:,} artists · {t:,} tracks')

    def _clear_filters(self) -> None:
        self._search.clear()
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
        if not selected:
            return
        dlg = _ChangeGenreDialog(hint_label or f'{len(selected)} items', hint_genre, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_genre = dlg.selected_genre

        old_edits: dict[str, Optional[str]] = {}
        disk_old: dict[str, str] = {}
        for item in selected:
            if item.parent() is None:
                data   = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
                artist = data.get('artist', '')
                key = f'__artist__{artist}'
                for rec in data.get('tracks', []):
                    disk_old[str(rec.path)] = rec.genre or ''
            else:
                rec = item.data(LC_PATH, Qt.ItemDataRole.UserRole)
                if not rec:
                    continue
                key = str(rec.path)
                disk_old[str(rec.path)] = rec.genre or ''
            old_edits[key] = self._edits.get(key, {}).get('genre')
        if not old_edits:
            return

        label = hint_label or f'{len(selected)} items'
        if self._undo_manager:
            cmd = LibraryGenreChangeCommand(self, old_edits, new_genre, disk_old, label)
            self._undo_manager.push(cmd)
        else:
            self._apply_library_genre(
                {k: new_genre for k in old_edits},
                {p: new_genre for p in disk_old},
            )

    def _artist_menu(self, item: QTreeWidgetItem, pos) -> None:
        data  = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
        artist = data.get('artist', '')
        menu   = QMenu(self)
        approve   = menu.addAction('✓ Approve')
        chg       = menu.addAction('↕ Change Genre…')
        edit_tags = menu.addAction('✏ Edit Style Tags…')
        action = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if action == approve:
            self._approve_artist(item, artist)
        elif action == chg:
            self._change_genre_for_selection(artist, item.text(LC_GENRE))
        elif action == edit_tags:
            self._edit_artist_tags(item, artist)

    def _approve_artist(self, item: QTreeWidgetItem, artist: str) -> None:
        """Right-click 'Approve' — accept the classifier's current proposal
        for just this one artist. Same write path as _change_genre_for_selection
        (real per-track disk write + library_edits.json staging, undoable),
        just sourcing the genre from the classifier's proposal instead of a
        user-picked value from the Change Genre dialog."""
        proposed, _confidence = self._classify_lookup(artist)
        _UC = {'', '—', 'Unclassified', 'Untagged'}
        if not proposed or proposed in _UC:
            return  # nothing real proposed for this artist to approve
        key = f'__artist__{artist}'
        old_genre = self._edits.get(key, {}).get('genre')

        artist_data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
        disk_old = {str(rec.path): (rec.genre or '') for rec in artist_data.get('tracks', [])}

        if self._undo_manager:
            cmd = LibraryGenreChangeCommand(self, {key: old_genre}, proposed, disk_old, artist)
            self._undo_manager.push(cmd)
        else:
            self._apply_library_genre({key: proposed}, {p: proposed for p in disk_old})

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

        # 4. Snapshot prior per-track state (for undo) before applying the move
        moves: dict[str, dict] = {}
        for _, track_rec, parent_item in tracks_to_move:
            parent_data = parent_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            path = str(track_rec.path)
            moves[path] = {
                'prior_edit':        dict(self._edits.get(path, {})),
                'prior_disk_artist': track_rec.artist or '',
                'group_artist':      parent_data.get('artist', ''),
            }

        label = tracks_to_move[0][1].filename if len(moves) == 1 else ''
        if self._undo_manager:
            cmd = LibraryReassignArtistCommand(self, moves, new_artist, label)
            self._undo_manager.push(cmd)
        else:
            edits_map = {
                path: {**info['prior_edit'], 'reassign_artist': new_artist, 'original_artist': info['group_artist']}
                for path, info in moves.items()
            }
            disk_map = {path: new_artist for path in moves}
            self._apply_library_reassign(edits_map, disk_map)

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
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        tags_str = ', '.join(dlg._track.tags)
        if self._undo_manager:
            cmd = LibraryTagsEditCommand(self, key, artist, current_tags_str, tags_str)
            self._undo_manager.push(cmd)
        else:
            self._apply_library_tags(key, tags_str)

    def _edit_style_tags(self, item: QTreeWidgetItem, rec) -> None:
        from cratesort.src.gui.classifier_view import _EditTagsDialog
        old_tags_str = self._edits.get(str(rec.path), {}).get('tags', '')
        dlg = _EditTagsDialog(
            # Build a minimal TrackInfo proxy
            type('T', (), {
                'filename': rec.filename,
                'title': rec.title,
                'genre_tag': rec.genre,
                'tags': old_tags_str.split(','),
                'comment': rec.comment,
            })(),
            self
        )
        dlg.setWindowTitle(f'Edit Style Tags — {rec.filename}')
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        tags_str = ', '.join(dlg._track.tags)
        if self._undo_manager:
            cmd = LibraryTagsEditCommand(self, str(rec.path), rec.filename, old_tags_str, tags_str)
            self._undo_manager.push(cmd)
        else:
            self._apply_library_tags(str(rec.path), tags_str)

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
        from cratesort.src.gui.classifier_view import (
            ClassificationSession, ClassifyProgressTally, _ClassifyWorker,
        )

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
            self._classify_tally = ClassifyProgressTally()

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
        self._refresh_classify_btn()
        self._enter_classify_mode(session)

    def _on_classify_error(self, message: str) -> None:
        self._refresh_classify_btn()
        _show_dark_alert(self.window(), 'Classification Failed', message[:500])

    # ── Auto-classify modal slots ──────────────────────────────────────

    def _on_auto_classify_progress(self, done: int, total: int, info: dict) -> None:
        if self._analyze_modal is None or self._classify_tally is None:
            return
        tally = self._classify_tally.add(info)
        self._analyze_modal.update_stats(
            files_analyzed=tally['files_analyzed'],
            files_recognized=tally['files_recognized'],
            files_unrecognized=tally['files_unrecognized'],
            artists_recognized=tally['artists_recognized'],
            genres_recognized=tally['genres_recognized'],
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
            # _CrateSortDialog.done() defers the real close (and the overlay-scrim
            # cleanup tied to `finished`) until its exit animation completes —
            # deleteLater() right after close() used to race that animation and
            # win, tearing down `_exit_anim` before `finished` ever fired and
            # leaving the modal scrim stuck on screen. Deleting only once
            # `finished` actually arrives lets the animation and overlay cleanup
            # run to completion first.
            modal.finished.connect(modal.deleteLater)
            modal.close()
        self._auto_classify_session   = None
        self._classify_tally          = None

    def _enter_classify_mode(self, session) -> None:
        # load() re-triggers auto-classify on every visit to Library while
        # anything's still unclassified, so this can be re-entered while
        # classify mode is already active. Only snapshot/reorder on the
        # actual first entry — otherwise the snapshot below would capture
        # the already-classify-reordered layout (or a user's manual drag
        # made *during* classify mode) as the "pre-classify" baseline,
        # corrupting the state that exit restores.
        already_active = self._classify_mode
        self._classify_mode = True
        self._classify_session = session
        self._classify_results = {
            entry.artist: (entry.display_genre, entry.confidence)
            for entry in session.entries
        }

        # Confidence/Status are already visible (permanent columns — see
        # load()); only Proposed Genre is classify-mode-exclusive.
        self._tree.setColumnHidden(LC_CLS_PROPOSED, False)
        self._tree.setColumnWidth(LC_CLS_PROPOSED, 120)

        if not already_active:
            # Snapshot header state so exit can restore it exactly
            self._pre_classify_header_state = self._tree.header().saveState()

            # Defer visual reorder until the tree has registered visibility changes
            def _reorder_cls_cols():
                hdr = self._tree.header()
                genre_vis = hdr.visualIndex(LC_GENRE)
                hdr.moveSection(hdr.visualIndex(LC_CLS_PROPOSED), genre_vis + 1)
                hdr.moveSection(hdr.visualIndex(LC_CLS_CONF),     genre_vis + 2)
                hdr.moveSection(hdr.visualIndex(LC_CLS_STATUS),   genre_vis + 3)
                self._tree.resizeColumnToContents(LC_CLS_PROPOSED)
                if self._tree.columnWidth(LC_CLS_PROPOSED) < 60:
                    self._tree.setColumnWidth(LC_CLS_PROPOSED, 60)

            QTimer.singleShot(0, _reorder_cls_cols)

        # Only the classify-mode-exclusive column gets the teal review-mode
        # tint — Confidence/Status are permanent and keep their default color.
        self._tree.headerItem().setForeground(LC_CLS_PROPOSED, QBrush(QColor('#428175')))
        self._populate_classify_columns()
        self._update_empty_state()
        self._classify_banner_frame.setVisible(True)
        self._classify_btn.setVisible(False)

    def _derive_persistent_status(self, artist: str) -> tuple[str, str]:
        """
        Persistent (always-visible, not just during classify-mode review)
        status for an artist — deliberately NOT sourced from ArtistEntry.state,
        which is unreliable in practice: the 'approved' transition only exists
        in dead code (_ClassifierViewLegacy, never instantiated), "Accept
        Reclassifications" never re-saves it, and "Reassign Artist" silently
        fails to persist it.

        Ground truth is library_edits.json (self._edits) — NOT a comparison
        of two genre strings. _rebuild_tree()'s displayed genre is pre-filled
        from the classifier's own raw proposal for anything not yet accepted,
        so comparing it against that same proposal is trivially true before
        any real decision has ever been made (this used to render "✓ Approved"
        on a fresh library before Accept was ever clicked once). Checking
        whether an explicit accepted-genre edit actually exists is the only
        way to tell "genuinely approved" apart from "not yet reviewed, but
        the preview happens to agree."

        Returns (label, hex_color), or ('', '') if this artist has no
        classification data at all yet.
        """
        if artist not in self._session_genre:
            return '', ''
        proposed_genre, confidence = self._session_genre[artist]
        _UC = {'', '—', 'Unclassified', 'Untagged'}

        # NOT self._frozen_confidence() here — that answers "what does the
        # Confidence column show" (always 'MATCHED' once settled, see
        # _apply_library_genre), which is a display-only decision. Status
        # needs the classifier's live, natural confidence to detect the one
        # case Accept never writes an edit for (raw tag already valid) —
        # conflating the two collapses Edited into Approved for every
        # settled artist, since a frozen 'MATCHED' would short-circuit here
        # before the existing_genre/proposed_genre comparison below runs.
        if confidence == 'MATCHED':
            # The file's own tag already IS the taxonomy genre — Accept
            # deliberately never writes an edit for these (nothing to
            # accept), so there was never anything pending.
            return '✓ Approved', '#6B9E78'

        existing_genre = self._edits.get(f'__artist__{artist}', {}).get('genre')
        if existing_genre is None:
            return '◔ Pending', '#a89b85'
        if existing_genre in _UC:
            return '△ Unclassified', '#C75B5B'
        if existing_genre == proposed_genre:
            return '✓ Approved', '#6B9E78'
        return '✎ Edited', '#D4A04A'

    _CONF_COLORS = {
        'MATCHED': '#f1e3c8',
        'HIGH':    '#428175',
        'MEDIUM':  '#9fa4c7',
        'LOW':     '#D17D34',
        'NONE':    '#C75B5B',
    }

    def _populate_classify_columns(self) -> None:
        """Paint Proposed Genre for rows still pending review. Confidence and
        Status are permanent columns maintained solely by _rebuild_tree() /
        _make_top_level_item() — never touched here — so this never needs to
        worry about mixing a Status-type value into the Confidence column or
        vice versa; each column only ever holds its own one kind of value.
        """
        _BG_NORMAL = '#1c2825'
        _BG_UC     = '#221a1a'
        _UC        = {'Unclassified', 'Untagged', ''}

        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            current_genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''

            # Artists already settled (approved or manually edited to a real
            # genre) are not part of this review pass — but Proposed Genre
            # still gets painted to match the settled value (same neutral
            # treatment MATCHED rows already use) instead of going blank.
            # A cell going empty reads as "something was deleted" to a user
            # watching it happen live (e.g. right-click Approve); showing
            # agreement between Genre and Proposed Genre is the correct,
            # reassuring signal that nothing is pending here anymore.
            #
            # "Settled" must be judged from library_edits.json — an explicit,
            # real accepted genre — never from current_genre/LC_GENRE itself:
            # _rebuild_tree() pre-fills the displayed genre from the raw
            # classifier proposal (_classify_lookup) for anything not yet
            # accepted, so on a never-reviewed artist current_genre already
            # looks like a real genre even though nothing was ever accepted.
            proposed, confidence = self._classify_results.get(
                artist, ('Unclassified', 'NONE')
            )

            existing_genre = self._edits.get(f'__artist__{artist}', {}).get('genre')
            if existing_genre and existing_genre not in _UC:
                item.setText(LC_CLS_PROPOSED, existing_genre)
                item.setBackground(LC_CLS_PROPOSED, QBrush(QColor(_BG_NORMAL)))
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor('#f1e3c8')))
                continue
            # MATCHED artists never get a library_edits.json entry — Accept
            # deliberately skips writing one for them, since the file's own
            # tag already IS the taxonomy genre, nothing to accept. Same
            # "settled" treatment applies once the library has already been
            # through a full accept cycle before (_is_classification_
            # complete()) — on the very first-ever review nothing has an
            # edits entry yet either, so this check would otherwise fire
            # immediately, before the user has seen a first pass at all.
            if confidence == 'MATCHED' and proposed == current_genre \
                    and self._is_classification_complete():
                item.setText(LC_CLS_PROPOSED, current_genre)
                item.setBackground(LC_CLS_PROPOSED, QBrush(QColor(_BG_NORMAL)))
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor('#f1e3c8')))
                continue

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
                item.setForeground(LC_CLS_PROPOSED, QBrush(QColor(self._CONF_COLORS.get(confidence, '#a89b85'))))

    def _exit_classify_mode_cancel(self) -> None:
        self._classify_mode = False
        self._classify_session = None
        self._classify_results = {}
        # Only Proposed Genre needs clearing/hiding — Confidence and Status
        # are permanent columns that were never touched by classify-mode's
        # own painting in the first place (see _populate_classify_columns),
        # so there's nothing stale in them to repopulate here.
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            item.setText(LC_CLS_PROPOSED, '')
            item.setData(LC_CLS_PROPOSED, Qt.ItemDataRole.BackgroundRole, None)
        if getattr(self, '_pre_classify_header_state', None):
            self._tree.header().restoreState(self._pre_classify_header_state)
            self._pre_classify_header_state = None
        self._tree.headerItem().setForeground(LC_CLS_PROPOSED, QBrush(QColor('#a89b85')))
        self._tree.setColumnHidden(LC_CLS_PROPOSED, True)

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
            existing_genre = edits.get(artist_key, {}).get('genre')
            if existing_genre and existing_genre not in _UC:
                continue  # user-set override — don't overwrite with classifier's proposal
            # existing_genre == 'Unclassified' is only an acknowledgment (see the
            # pass below), not a deliberate choice — fall through so a fresh,
            # real proposal (e.g. a newly-added style tag resolving it) still applies.
            confidence = item.text(LC_CLS_CONF)
            if confidence == 'MATCHED' and proposed == current_genre:
                continue  # ID3 tag already matches taxonomy — no override needed
            # NOT "and proposed != current_genre" — current_genre is the tree's
            # displayed genre, which _rebuild_tree() pre-fills from this same
            # classifier proposal (_classify_lookup) for anything not yet
            # accepted. That means proposed == current_genre trivially on the
            # very first Accept ever, for every artist, before anything is
            # actually written — which silently no-op'd Accept for the entire
            # library (no library_edits.json entry, no disk write, no
            # _accepted_tracks) while the row still displayed "✓ Approved"
            # (itself the same illusion, in _derive_persistent_status). The
            # existing_genre guard above already protects real prior
            # acceptances/overrides, so nothing further is needed here.
            if proposed and proposed not in _UC:
                edits.setdefault(artist_key, {})['genre'] = proposed
                # Freeze Confidence to MATCHED at accept time — same rule as
                # _apply_library_genre, see _frozen_confidence for the read side.
                edits[artist_key]['confidence'] = 'MATCHED'
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

        # Acknowledge any remaining Unclassified artists that have no existing edit entry.
        # This records "seen and accepted as Unclassified" so the Classify button can disable.
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            data = item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
            artist = data.get('artist', '')
            artist_key = f'__artist__{artist}'
            if artist_key not in edits:
                current_genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
                if current_genre in _UC:
                    edits[artist_key] = {'genre': 'Unclassified'}

        # Write accepted genre proposals to track files on disk (free-tier write-through),
        # and — for anything that actually succeeded — also stage a per-track genre
        # entry in library_edits.json, same as every other track-level edit field
        # (title/album/comment/etc.). Without this, the Library tree's track rows
        # read from self._track_overrides (a snapshot from when the classify
        # session was last loaded) and would keep showing the pre-accept genre
        # until the next full relaunch+rescan, even though the file itself and
        # the artist-level status both already reflect the real, accepted genre.
        from cratesort.src.core.file_organizer import write_file_metadata
        disk_failures = 0
        for rec, genre in _accepted_tracks:
            if write_file_metadata(rec.path, 'genre', genre):
                rec.genre = genre
                edits.setdefault(str(rec.path), {})['genre'] = genre
            else:
                disk_failures += 1

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

        if _last_accept_artist:
            self._last_edited_artist  = _last_accept_artist
            self._last_assigned_genre = _last_accept_genre

        self._exit_classify_mode_cancel()
        if self._inventory and self._library_path:
            self.load(self._inventory, self._library_path)

        n = self._tree.topLevelItemCount()
        t = len(self._inventory)
        norm = f'{n:,} artists · {t:,} tracks'
        if disk_failures:
            self._count_label.setText(
                f'⚠ Classification accepted. {disk_failures} file(s) could not be '
                f'updated on disk — check that the drive is connected and files are not locked.'
            )
            QTimer.singleShot(7000, lambda s=norm: self._count_label.setText(s))
        else:
            self._count_label.setText(
                '✓ Metadata clean — run Organize to also rename your files on disk.'
            )
            QTimer.singleShot(8000, lambda s=norm: self._count_label.setText(s))

    # ── Persistence ───────────────────────────────────────────────────

    def save_state(self) -> None:
        """Call before hiding/destroying the view to persist column order."""
        self._settings.setValue(_SETTINGS_KEY, self._tree.header().saveState())
