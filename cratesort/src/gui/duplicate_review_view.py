from __future__ import annotations

import subprocess
import sys as _sys
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPointF, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QRadioButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

_ASSETS          = Path(__file__).parent.parent.parent / 'assets'
_ICON_RADIO_ON   = str(_ASSETS / 'icons' / 'radio-checked.svg')
_ICON_RADIO_OFF  = str(_ASSETS / 'icons' / 'radio-unchecked.svg')

from cratesort.src.core.duplicate_detector import (
    DuplicateGroup, DuplicateCopy, DuplicateSummary, fmt_bytes, group_fingerprint,
)
from cratesort.src.core.duplicate_consolidator import (
    DuplicateConsolidator, ConsolidationResult,
)
from cratesort.src.core.duplicate_dismissals import add_dismissed, remove_dismissed
from cratesort.src.gui.overlays import _ov_alert, _ov_confirm

# ── Colors ────────────────────────────────────────────────────────────────────

_BG     = '#1a1a1a'
_PANEL  = '#2F2F2F'
_CREAM  = '#f1e3c8'
_MUTED  = '#a89b85'
_ORANGE = '#D17D34'
_TEAL   = '#428175'
_RED    = '#C75B5B'
_SEP    = '#383838'
_ROW    = '#242424'
_ROW2   = '#2a2a2a'
_DIM    = '#666666'

# Stack indices
_STATE_RESULTS      = 0
_STATE_PROGRESS     = 1
_STATE_CELEBRATION  = 2

# Filter modes for the results screen
_FILTERS = (
    ('all',            'All'),
    ('true_duplicate', 'True duplicates'),
    ('variant',        'Possible variants'),
    ('needs_review',   'Needs review'),
    ('accepted',       'Accepted'),
)

_FILTER_PILL_QSS = (
    f'QPushButton {{ background: transparent; color: {_MUTED}; border: 1px solid #4a4a4a; '
    f'border-radius: 6px; padding: 5px 14px; font-size: 12px; }}'
    f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
    f'QPushButton:checked {{ background: {_TEAL}; color: #ffffff; border-color: {_TEAL}; }}'
)


def _show_in_finder(file_path: str) -> None:
    """Reveal (and select) a file in the OS file browser. Mirrors the helper
    already used in library_browser.py / crate_manager.py / classifier_view.py."""
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
# Winner reason helper
# ---------------------------------------------------------------------------

import re as _re

_TRACK_NUM_RE = _re.compile(r'^\d+[\s.\-]')


def _winner_reason(winner: DuplicateCopy, losers: list[DuplicateCopy]) -> str:
    """
    Return a plain-language phrase explaining why this copy was chosen.
    Checks criteria in priority order; reports the first one that actually
    differentiates the winner from the losers.
    """
    if not losers:
        return 'best available copy'

    # Lossless format beats lossy
    if winner.format in ('FLAC', 'WAV', 'AIFF'):
        if any(l.format not in ('FLAC', 'WAV', 'AIFF') for l in losers):
            return f'{winner.format} — lossless format'

    # Higher bitrate
    max_loser_br = max((l.bitrate or 0) for l in losers)
    if (winner.bitrate or 0) > max_loser_br:
        return f'higher quality ({winner.bitrate} kbps)'

    # Larger file at same bitrate (better rip / more data)
    max_loser_size = max(l.file_size for l in losers)
    if winner.file_size > max_loser_size:
        return 'larger file size'

    # More metadata filled in
    winner_meta = sum(1 for v in [winner.genre_tag, winner.year_tag, winner.bpm] if v)
    max_loser_meta = max(sum(1 for v in [l.genre_tag, l.year_tag, l.bpm] if v) for l in losers)
    if winner_meta > max_loser_meta:
        return 'more complete metadata'

    # More crates
    max_loser_crates = max(l.crate_count for l in losers)
    if winner.crate_count > max_loser_crates:
        n = winner.crate_count
        return f'in {n} crate{"s" if n != 1 else ""}'

    # Cleaner filename (no leading track number like "02 Title.mp3")
    winner_clean  = not bool(_TRACK_NUM_RE.match(winner.file_path.stem))
    any_loser_messy = any(bool(_TRACK_NUM_RE.match(l.file_path.stem)) for l in losers)
    if winner_clean and any_loser_messy:
        return 'cleaner filename'

    return 'best available copy'


def _winner_metadata_advantages(winner: DuplicateCopy, losers: list[DuplicateCopy]) -> list[str]:
    """
    Return field names where the winner has data that at least one loser is missing.
    Only reports fields where the winner has an exclusive advantage — both sides
    having the same field doesn't count.
    """
    adv = []
    if winner.comment    and any(not l.comment    for l in losers): adv.append('comment')
    if winner.genre_tag  and any(not l.genre_tag  for l in losers): adv.append('genre')
    if winner.bpm        and any(not l.bpm        for l in losers): adv.append('BPM')
    if winner.year_tag   and any(not l.year_tag   for l in losers): adv.append('year')
    if winner.has_artwork and any(not l.has_artwork for l in losers): adv.append('artwork')
    return adv


def _comment_merge_note(winner: DuplicateCopy, losers: list[DuplicateCopy]) -> str:
    """
    Return a plain-language note about comment merging, or '' if nothing to say.
    """
    loser_comments = [l.comment for l in losers if l.comment]
    if not loser_comments:
        return ''
    if winner.comment:
        if any(c != winner.comment for c in loser_comments):
            return 'comments from both copies will be merged'
        return ''
    else:
        return 'comment from other copy will carry over'


# ---------------------------------------------------------------------------
# Disclosure (expand / collapse) control
# ---------------------------------------------------------------------------

class _DisclosureButton(QPushButton):
    """Self-painted expand/collapse chevron. A glyph char (⌄ / ⌃) does not
    render in the app font, so the chevron is drawn directly."""

    def __init__(self, expanded: bool, on_toggle: Callable[[], None], parent=None):
        super().__init__(parent)
        self._expanded = expanded
        self._hover = False
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet('QPushButton { background: transparent; border: none; }')
        self.setToolTip('Collapse' if expanded else 'Expand')
        self.clicked.connect(lambda: on_toggle())

    def enterEvent(self, e):  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(_CREAM if self._hover else _MUTED), 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        half, amp = 4.5, 2.4
        if self._expanded:  # chevron points up
            pts = [QPointF(cx - half, cy + amp), QPointF(cx, cy - amp), QPointF(cx + half, cy + amp)]
        else:               # chevron points down
            pts = [QPointF(cx - half, cy - amp), QPointF(cx, cy + amp), QPointF(cx + half, cy - amp)]
        p.drawPolyline(QPolygonF(pts))
        p.end()


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _ConsolidationWorker(QThread):
    progress = pyqtSignal(int, int, str)   # (done, total, label)
    finished = pyqtSignal(object)          # ConsolidationResult
    errored  = pyqtSignal(str)

    def __init__(
        self,
        approved: list,                    # list of (group, winner, losers) triples
        library_path: Path,
        serato_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._approved      = approved
        self._library_path  = library_path
        self._serato_dir    = serato_dir
        self._cancelled     = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            consolidator = DuplicateConsolidator(self._library_path, self._serato_dir)
            result = consolidator.consolidate(
                self._approved,
                commit=True,
                progress_callback=lambda d, t, l: self.progress.emit(d, t, l)
                if not self._cancelled else None,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as exc:
            import traceback
            self.errored.emit(f'{exc}\n{traceback.format_exc()}')


# ---------------------------------------------------------------------------
# Duplicate Review View
# ---------------------------------------------------------------------------

class DuplicateReviewView(QWidget):
    """
    Full-screen duplicate review launched from the dashboard stat card.

    States:
      0 — Results: Tier 1 (true dupes) + Tier 2 (variants) review lists
      1 — Progress: consolidation in progress (% complete bar)
      2 — Celebration: "Rinsed. X files cleaned up, Y GB freed."

    Review model (opt-in, per-group):
      * Every group is a cheap collapsed strip; click it to open the full card.
      * In an open card, one radio picks the copy to keep — every other copy is
        consolidated into it.
      * "Accept This Group" locks that group in and moves you to the next one;
        no other group is touched until "Consolidate Accepted Groups".

    Emits `done` when the user dismisses the celebration or skips entirely.
    """

    done           = pyqtSignal()    # user finished — return to dashboard
    track_selected = pyqtSignal(str) # file path → populate sidebar artwork

    def __init__(self, parent=None):
        super().__init__(parent)

        self._library_path: Optional[Path] = None
        self._serato_dir:   Optional[Path] = None
        self._groups:       list[DuplicateGroup] = []
        self._summary:      Optional[DuplicateSummary] = None
        self._worker:       Optional[_ConsolidationWorker] = None

        # Per-group winner overrides: group index → DuplicateCopy
        self._winner_overrides: dict[int, DuplicateCopy] = {}
        # Groups the user has accepted (locked in, collapsed)
        self._accepted:  set[int] = set()
        # Groups the user chose to keep in full ("don't ask again")
        self._dismissed: set[int] = set()
        # Groups whose full card body is currently rendered. Everything else is a
        # cheap strip — building 700+ full cards up front freezes the app.
        self._expanded: set[int] = set()

        self._filter_mode = 'all'
        self._card_widgets: dict[int, QWidget] = {}
        self._filter_btns:  dict[str, QPushButton] = {}

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_results())     # 0
        self._stack.addWidget(self._build_progress())    # 1
        self._stack.addWidget(self._build_celebration()) # 2
        self._stack.setCurrentIndex(_STATE_RESULTS)

    # ── Public API ─────────────────────────────────────────────────────────

    def load(
        self,
        groups: list[DuplicateGroup],
        summary: DuplicateSummary,
        library_path: Path,
        serato_dir: Path,
    ) -> None:
        self._groups       = groups
        self._summary      = summary
        self._library_path = library_path
        self._serato_dir   = serato_dir
        self._winner_overrides.clear()
        self._accepted.clear()
        self._dismissed.clear()
        self._expanded.clear()
        self._filter_mode = 'all'
        if 'all' in self._filter_btns:
            self._filter_btns['all'].setChecked(True)
        self._populate_results()
        self._stack.setCurrentIndex(_STATE_RESULTS)

    # ── Off-stage teardown ────────────────────────────────────────────────
    # A big library can produce 700+ group rows. Keeping them all alive while
    # the user is on another screen weighs on the whole app (and makes the
    # screen-switch snapshot slow). Free them on hide; rebuild from the same
    # review state on show. State (accepted / expanded / winner overrides)
    # lives in plain dicts on self and is never touched here.

    def _clear_result_widgets(self) -> None:
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._card_widgets.clear()

    def hideEvent(self, event):  # noqa: N802
        super().hideEvent(event)
        if self._card_widgets:
            self._clear_result_widgets()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if (self._groups and not self._card_widgets
                and self._stack.currentIndex() == _STATE_RESULTS):
            self._populate_results()

    # ── Results screen (State 0) ────────────────────────────────────────────

    def _build_results(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {_BG};')
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        hdr = QFrame()
        hdr.setStyleSheet(f'background: {_PANEL}; border: none;')
        hdr_col = QVBoxLayout(hdr)
        hdr_col.setContentsMargins(32, 20, 32, 20)
        hdr_col.setSpacing(12)

        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title_lbl = QLabel('Rinse Your Library')
        title_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 20px; font-weight: 700; background: transparent;')
        subtitle = QLabel('Review potential duplicates before you classify.')
        subtitle.setStyleSheet(f'color: {_MUTED}; font-size: 13px; background: transparent;')
        title_col.addWidget(title_lbl)
        title_col.addWidget(subtitle)
        hdr_row.addLayout(title_col, stretch=1)

        self._skip_btn = QPushButton('Cancel — Don\'t Consolidate')
        self._skip_btn.setFixedHeight(36)
        self._skip_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {_MUTED}; '
            f'border: 1px solid #444444; border-radius: 6px; padding: 0 16px; }}'
            f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
        )
        self._skip_btn.clicked.connect(self.done.emit)
        hdr_row.addWidget(self._skip_btn)

        self._consolidate_btn = QPushButton('Consolidate Accepted Groups')
        self._consolidate_btn.setFixedHeight(36)
        self._consolidate_btn.setStyleSheet(
            f'QPushButton {{ background: {_TEAL}; color: #ffffff; border: none; '
            f'border-radius: 6px; padding: 0 20px; font-weight: 600; }}'
            f'QPushButton:hover {{ background: #38706a; }}'
            f'QPushButton:pressed {{ background: #2d6358; }}'
            f'QPushButton:disabled {{ background: #3a3a3a; color: {_DIM}; }}'
        )
        self._consolidate_btn.clicked.connect(self._on_consolidate)
        hdr_row.addWidget(self._consolidate_btn)
        hdr_col.addLayout(hdr_row)

        # Progress anchor — "X of Y groups reviewed"
        self._progress_row_w = QWidget()
        self._progress_row_w.setStyleSheet('background: transparent;')
        prog_row = QHBoxLayout(self._progress_row_w)
        prog_row.setContentsMargins(0, 2, 0, 2)
        prog_row.setSpacing(12)
        self._review_progress_lbl = QLabel()
        self._review_progress_lbl.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;'
        )
        self._review_progress_bar = QProgressBar()
        self._review_progress_bar.setTextVisible(False)
        self._review_progress_bar.setFixedHeight(8)
        self._review_progress_bar.setStyleSheet(
            f'QProgressBar {{ background: {_SEP}; border: none; border-radius: 4px; }}'
            f'QProgressBar::chunk {{ background: {_TEAL}; border-radius: 4px; }}'
        )
        prog_row.addWidget(self._review_progress_lbl)
        prog_row.addWidget(self._review_progress_bar, stretch=1)
        hdr_col.addWidget(self._progress_row_w)

        # Filter bar
        self._filter_row_w = QWidget()
        self._filter_row_w.setStyleSheet('background: transparent;')
        filt_row = QHBoxLayout(self._filter_row_w)
        filt_row.setContentsMargins(0, 4, 0, 6)
        filt_row.setSpacing(8)
        self._filter_group = QButtonGroup(w)
        self._filter_group.setExclusive(True)
        for mode, base_label in _FILTERS:
            b = QPushButton(base_label)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(30)
            b.setStyleSheet(_FILTER_PILL_QSS)
            b._base_label = base_label  # type: ignore[attr-defined]
            if mode == 'all':
                b.setChecked(True)
            b.clicked.connect(lambda _c=False, m=mode: self._on_filter_changed(m))
            self._filter_group.addButton(b)
            self._filter_btns[mode] = b
            filt_row.addWidget(b)
        filt_row.addStretch()
        hdr_col.addWidget(self._filter_row_w)

        outer.addWidget(hdr)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f'QScrollArea {{ background: {_BG}; border: none; }}')
        self._results_scroll = scroll

        self._results_content = QWidget()
        self._results_content.setStyleSheet(f'background: {_BG};')
        self._results_layout = QVBoxLayout(self._results_content)
        self._results_layout.setContentsMargins(32, 24, 32, 32)
        self._results_layout.setSpacing(14)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_content)
        outer.addWidget(scroll, stretch=1)

        return w

    # ── Filtering ──────────────────────────────────────────────────────────

    def _on_filter_changed(self, mode: str) -> None:
        self._filter_mode = mode
        self._populate_results()
        self._results_scroll.verticalScrollBar().setValue(0)

    def _passes_filter(self, idx: int, group: DuplicateGroup) -> bool:
        m = self._filter_mode
        if m == 'all':
            return True
        if m in ('true_duplicate', 'variant'):
            return group.tier == m
        if m == 'needs_review':
            return idx not in self._accepted and idx not in self._dismissed
        if m == 'accepted':
            return idx in self._accepted
        return True

    def _ensure_one_expanded(self) -> Optional[int]:
        """Keep exactly one reviewable group open to work on. Returns the index
        newly expanded, or None if one was already open / nothing to open."""
        reviewable = [
            i for i, g in enumerate(self._groups)
            if i not in self._accepted and i not in self._dismissed
            and self._passes_filter(i, g)
        ]
        if reviewable and not (self._expanded & set(reviewable)):
            self._expanded.add(reviewable[0])
            return reviewable[0]
        return None

    # ── Results population ─────────────────────────────────────────────────

    def _populate_results(self) -> None:
        # Clear old content (keep the trailing stretch)
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._card_widgets.clear()

        def insert(wdg: QWidget) -> None:
            self._results_layout.insertWidget(self._results_layout.count() - 1, wdg)

        skipped = self._summary.skipped_count if self._summary else 0
        if skipped > 0 and self._filter_mode == 'all':
            n = skipped
            notice = QLabel(
                f'{n:,} untagged track{"s" if n != 1 else ""} '
                f'{"were" if n != 1 else "was"} skipped and may still contain duplicates.'
            )
            notice.setWordWrap(True)
            notice.setStyleSheet(
                f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;'
            )
            insert(notice)

        tier1 = [(i, g) for i, g in enumerate(self._groups) if g.tier == 'true_duplicate']
        tier2 = [(i, g) for i, g in enumerate(self._groups) if g.tier == 'variant']

        self._ensure_one_expanded()

        def render_section(
            title_base: str, subtitle: str, accent: str,
            entries: list[tuple[int, DuplicateGroup]], is_true: bool,
        ) -> None:
            visible = [(i, g) for i, g in entries if self._passes_filter(i, g)]
            if not visible:
                return
            action: Optional[tuple[str, Callable[[], None]]] = None
            if is_true and self._filter_mode != 'accepted':
                remaining = [
                    i for i, _g in entries
                    if i not in self._accepted and i not in self._dismissed
                ]
                if remaining:
                    action = (
                        'Accept all remaining true duplicates',
                        lambda r=remaining: self._on_accept_all_true(r),
                    )
            n = len(entries)
            insert(self._build_section_header(
                f'{title_base} — {n} group{"s" if n != 1 else ""}',
                subtitle, accent, action=action,
            ))
            for i, g in visible:
                card = self._build_group_card(i, g)
                self._card_widgets[i] = card
                insert(card)

        render_section(
            'True Duplicates',
            'Same file found in multiple locations. '
            'We\'ve selected the best copy — confirm or choose a different one.',
            _RED, tier1, True,
        )
        render_section(
            'Possible Variants',
            'Looks like different versions of the same song. '
            'Confirm if any are actual duplicates you want to consolidate.',
            _ORANGE, tier2, False,
        )

        # Empty states
        if not tier1 and not tier2:
            if skipped > 0:
                headline = QLabel('Nothing to review.')
                headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
                headline.setStyleSheet(
                    f'color: {_CREAM}; font-size: 16px; font-weight: 600; '
                    f'background: transparent; border: none;'
                )
                body = QLabel(
                    'No tracks had enough metadata to compare.\n'
                    'Add artist and title tags to your tracks, then rescan.'
                )
                body.setAlignment(Qt.AlignmentFlag.AlignCenter)
                body.setWordWrap(True)
                body.setStyleSheet(
                    f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;'
                )
                insert(headline)
                insert(body)
            else:
                empty = QLabel('No duplicates found. Your library is clean.')
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setStyleSheet(
                    f'color: {_MUTED}; font-size: 14px; background: transparent; border: none;'
                )
                insert(empty)
        elif not self._card_widgets:
            msg = {
                'accepted':      'No groups accepted yet. Open a group and choose "Accept This Group".',
                'needs_review':  'Every group has been reviewed. Consolidate when you\'re ready.',
                'true_duplicate': 'No true duplicates.',
                'variant':       'No possible variants.',
            }.get(self._filter_mode, 'Nothing matches this filter.')
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;'
            )
            insert(lbl)

        self._refresh_progress_and_filters()
        self._refresh_consolidate_btn()

    def _apply_card_change(self, idx: int, refresh: bool = True) -> None:
        """Rebuild just one group's widget in place. Avoids re-rendering every
        strip (700+) on each expand / accept / collapse."""
        old = self._card_widgets.get(idx)
        if old is None:
            if refresh:
                self._refresh_progress_and_filters()
                self._refresh_consolidate_btn()
            return
        pos = self._results_layout.indexOf(old)
        self._results_layout.removeWidget(old)
        old.deleteLater()
        group = self._groups[idx]
        if pos >= 0 and self._passes_filter(idx, group):
            new = self._build_group_card(idx, group)
            self._results_layout.insertWidget(pos, new)
            self._card_widgets[idx] = new
        else:
            self._card_widgets.pop(idx, None)
        if refresh:
            self._refresh_progress_and_filters()
            self._refresh_consolidate_btn()

    def _refresh_progress_and_filters(self) -> None:
        total = len(self._groups)
        reviewed = len(self._accepted | self._dismissed)
        self._review_progress_bar.setRange(0, max(total, 1))
        self._review_progress_bar.setValue(reviewed)
        self._review_progress_lbl.setText(
            f'{reviewed} of {total} group{"s" if total != 1 else ""} reviewed'
        )
        has_groups = total > 0
        self._progress_row_w.setVisible(has_groups)
        self._filter_row_w.setVisible(has_groups)

        counts = {
            'all':            total,
            'true_duplicate': sum(1 for g in self._groups if g.tier == 'true_duplicate'),
            'variant':        sum(1 for g in self._groups if g.tier == 'variant'),
            'needs_review':   sum(
                1 for i in range(total)
                if i not in self._accepted and i not in self._dismissed
            ),
            'accepted':       len(self._accepted),
        }
        for mode, btn in self._filter_btns.items():
            base = getattr(btn, '_base_label', btn.text())
            btn.setText(f'{base} ({counts[mode]})')

    def _refresh_consolidate_btn(self) -> None:
        n = len(self._accepted)
        actionable = any(self._selected_losers_for(i) for i in self._accepted)
        self._consolidate_btn.setVisible(n > 0)
        self._consolidate_btn.setEnabled(actionable)
        label = f'Consolidate Accepted Group{"s" if n != 1 else ""}'
        if n:
            label += f' ({n})'
        self._consolidate_btn.setText(label)

    # ── Selection helpers ──────────────────────────────────────────────────

    def _winner_for(self, idx: int) -> Optional[DuplicateCopy]:
        g = self._groups[idx]
        return self._winner_overrides.get(idx, g.recommended_winner)

    def _selected_losers_for(self, idx: int) -> list[DuplicateCopy]:
        """Every copy in the group except the one being kept."""
        g = self._groups[idx]
        winner = self._winner_for(idx)
        return [c for c in g.copies if c is not winner]

    # ── Section header ─────────────────────────────────────────────────────

    def _build_section_header(
        self, title: str, subtitle: str, accent: str,
        action: Optional[tuple[str, Callable[[], None]]] = None,
    ) -> QFrame:
        f = QFrame()
        f.setStyleSheet('background: transparent; border: none;')
        outer = QVBoxLayout(f)
        outer.setContentsMargins(0, 22, 0, 6)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f'background: {accent}; border: none; border-radius: 2px;')
        row.addWidget(bar)  # no alignment= → stretches to full row height

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(6)

        t = QLabel(title)
        t.setStyleSheet(f'color: {_CREAM}; font-size: 15px; font-weight: 700; background: transparent; border: none;')
        text_col.addWidget(t)

        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setStyleSheet(f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;')
        text_col.addWidget(s)

        row.addLayout(text_col, stretch=1)

        if action is not None:
            label, handler = action
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setStyleSheet(
                f'QPushButton {{ background: transparent; color: {_TEAL}; '
                f'border: 1px solid {_TEAL}; border-radius: 6px; padding: 0 14px; font-size: 12px; }}'
                f'QPushButton:hover {{ background: rgba(66, 129, 117, 0.15); }}'
            )
            btn.clicked.connect(lambda _c=False, h=handler: h())
            row.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        outer.addLayout(row)
        return f

    # ── Group card: collapsed strip ────────────────────────────────────────

    def _disclosure_btn(self, idx: int, expanded: bool) -> QPushButton:
        """The single alternating expand/collapse affordance — no words.
        Chevron down = click to open, chevron up = click to close. Always the
        far-right item on a group's title line."""
        if expanded:
            return _DisclosureButton(True, lambda i=idx: self._on_collapse(i))
        return _DisclosureButton(False, lambda i=idx: self._on_expand(i))

    def _build_collapsed_card(self, idx: int, group: DuplicateGroup) -> QFrame:
        """Cheap one-line strip. Click anywhere to open the full card."""
        losers = self._selected_losers_for(idx)
        freed  = sum(c.file_size for c in losers)
        accent = _RED if group.tier == 'true_duplicate' else _ORANGE

        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border: 1px solid #383838; border-radius: 8px; }}'
            f'QFrame:hover {{ border-color: #5a5a5a; }}'
        )
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 12, 16, 12)
        row.setSpacing(12)

        dot = QLabel('●')
        dot.setStyleSheet(f'color: {accent}; font-size: 11px; background: transparent; border: none;')
        row.addWidget(dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        song_lbl = QLabel(f'{group.canonical_artist}  —  {group.canonical_title}')
        song_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 13px; font-weight: 600; background: transparent; border: none;')
        row.addWidget(song_lbl, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        n = len(group.copies)
        meta = f'{n} copies'
        if freed:
            meta += f'  ·  frees {fmt_bytes(freed)}'
        meta_lbl = QLabel(meta)
        meta_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
        row.addWidget(meta_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(self._disclosure_btn(idx, expanded=False),
                      alignment=Qt.AlignmentFlag.AlignVCenter)

        card.mousePressEvent = lambda _e, i=idx: self._on_expand(i)
        return card

    def _on_expand(self, idx: int) -> None:
        if idx in self._expanded:
            return
        self._expanded.add(idx)
        self._apply_card_change(idx)
        self._scroll_to_card(idx)

    def _on_collapse(self, idx: int) -> None:
        self._expanded.discard(idx)
        self._apply_card_change(idx)
        self._scroll_to_card(idx)

    # ── Group card: full body ──────────────────────────────────────────────

    def _build_group_card(self, idx: int, group: DuplicateGroup) -> QFrame:
        if idx in self._dismissed:
            return self._build_dismissed_card(idx, group)
        if idx in self._accepted:
            return self._build_accepted_card(idx, group)
        if idx not in self._expanded:
            return self._build_collapsed_card(idx, group)

        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border: 1px solid #444444; border-radius: 8px; }}'
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        winner = self._winner_for(idx)

        # Title bar — its own row with real height so the title, savings figure
        # and controls all sit centred on one line without the buttons clipping.
        title_bar = QWidget()
        title_bar.setMinimumHeight(34)
        title_bar.setStyleSheet('background: transparent;')
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        _vc = Qt.AlignmentFlag.AlignVCenter

        song_lbl = QLabel(f'{group.canonical_artist}  —  {group.canonical_title}')
        song_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | _vc)
        song_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 14px; font-weight: 600; background: transparent; border: none;')
        title_row.addWidget(song_lbl, stretch=1)

        savings_lbl = QLabel(
            f'frees {fmt_bytes(sum(c.file_size for c in group.copies if c is not winner))}'
        )
        savings_lbl.setStyleSheet(f'color: {_TEAL}; font-size: 12px; background: transparent; border: none;')
        title_row.addWidget(savings_lbl, alignment=_vc)

        keep_all_btn = QPushButton('Keep All — Don\'t Ask Again')
        keep_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        keep_all_btn.setMinimumHeight(28)
        keep_all_btn.setToolTip('Keep every copy in this group and never flag this exact set again')
        keep_all_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {_MUTED}; '
            f'border: 1px solid #444444; border-radius: 6px; padding: 4px 12px; font-size: 11px; }}'
            f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
        )
        keep_all_btn.clicked.connect(lambda _checked=False, i=idx: self._on_keep_all(i))
        title_row.addWidget(keep_all_btn, alignment=_vc)

        title_row.addWidget(self._disclosure_btn(idx, expanded=True), alignment=_vc)

        layout.addWidget(title_bar)

        # Copy rows — one radio picks the keeper; every other copy is consolidated.
        btn_group = QButtonGroup(card)
        btn_group.setExclusive(True)
        copy_rows: list[tuple] = []  # (radio, row_frame, copy)

        for copy in group.copies:
            is_winner = (copy is winner)
            radio, row = self._build_copy_row(copy, is_winner, winner, group.copies)
            btn_group.addButton(radio)
            if is_winner:
                radio.setChecked(True)
            copy_rows.append((radio, row, copy))
            layout.addWidget(row)

        # Footer: live summary + Accept
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        summary_lbl = QLabel()
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
        footer.addWidget(summary_lbl, stretch=1)

        accept_btn = QPushButton('Accept This Group')
        accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        accept_btn.setFixedHeight(32)
        accept_btn.setStyleSheet(
            f'QPushButton {{ background: {_TEAL}; color: #ffffff; border: none; '
            f'border-radius: 6px; padding: 0 16px; font-size: 12px; font-weight: 600; }}'
            f'QPushButton:hover {{ background: #38706a; }}'
        )
        accept_btn.clicked.connect(lambda _checked=False, i=idx: self._on_accept_group(i))
        footer.addWidget(accept_btn)

        def _refresh_footer(cur_winner: DuplicateCopy) -> None:
            n = len(group.copies) - 1
            summary_lbl.setText(
                f'Keeping {cur_winner.file_path.name}  ·  {n} other '
                f'cop{"ies" if n != 1 else "y"} consolidated into it'
            )
            savings_lbl.setText(
                f'frees {fmt_bytes(sum(c.file_size for c in group.copies if c is not cur_winner))}'
            )

        def _on_winner_toggled(_btn, checked: bool) -> None:
            if not checked:
                return
            cur = next((c for r, rf, c in copy_rows if r.isChecked()), winner)
            self._winner_overrides[idx] = cur
            for r, rf, c in copy_rows:
                is_w = r.isChecked()
                bg     = _ROW if is_w else _ROW2
                border = f'2px solid {_TEAL}' if is_w else f'1px solid {_SEP}'
                rf.setStyleSheet(
                    f'QFrame {{ background: {bg}; border: {border}; border-radius: 6px; }}'
                )
            _refresh_footer(cur)

        btn_group.buttonToggled.connect(_on_winner_toggled)

        # Bottom note — different messaging for variants vs true duplicates
        if group.tier == 'variant':
            durations = [c.duration for c in group.copies if c.duration]
            sizes     = [c.file_size for c in group.copies if c.file_size]
            hints: list[str] = []
            if len(durations) >= 2 and max(durations) - min(durations) > 2.0:
                def _fmt_dur(s: float) -> str:
                    return f'{int(s // 60)}:{int(s % 60):02d}'
                hints.append(
                    f'durations differ ({_fmt_dur(min(durations))} vs {_fmt_dur(max(durations))})'
                )
            if len(sizes) >= 2 and max(sizes) / max(min(sizes), 1) > 1.5:
                hints.append(
                    f'file sizes differ ({fmt_bytes(min(sizes))} vs {fmt_bytes(max(sizes))})'
                )
            if hints:
                note_text = (
                    f'These files have different {" and ".join(hints)} — they are likely '
                    f'different recordings that share the same track name. '
                    f'Only consolidate if you are certain they are the same file.'
                )
            else:
                note_text = (
                    'These may be different versions of the same song. '
                    'Only consolidate if you are certain they are actual duplicates.'
                )
            note = QLabel(note_text)
            note.setWordWrap(True)
            note.setStyleSheet(
                f'color: {_ORANGE}; font-size: 11px; background: transparent; border: none;'
            )
            layout.addWidget(note)

        elif group.metadata_conflicts:
            conflicting = [c.field.upper() for c in group.metadata_conflicts]
            if len(conflicting) == 1:
                conflict_str = conflicting[0]
            elif len(conflicting) == 2:
                conflict_str = f'{conflicting[0]} and {conflicting[1]}'
            else:
                conflict_str = ', '.join(conflicting[:-1]) + f', and {conflicting[-1]}'
            warn = QLabel(
                f'{conflict_str} {"differs" if len(conflicting) == 1 else "differ"} '
                f'between copies — the winner\'s '
                f'{"value" if len(conflicting) == 1 else "values"} will be kept.'
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;'
            )
            layout.addWidget(warn)

        layout.addLayout(footer)
        _refresh_footer(winner)
        return card

    def _build_dismissed_card(self, idx: int, group: DuplicateGroup) -> QFrame:
        """Collapsed state for a group the user chose to keep in full."""
        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border: 1px solid #383838; border-radius: 8px; }}'
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        song_lbl = QLabel(f'{group.canonical_artist}  —  {group.canonical_title}')
        song_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 13px; font-weight: 600; background: transparent; border: none;')
        text_col.addWidget(song_lbl)

        note_lbl = QLabel(
            f'Keeping all {len(group.copies)} copies — won\'t ask about this set again.'
        )
        note_lbl.setStyleSheet(f'color: {_DIM}; font-size: 12px; background: transparent; border: none;')
        text_col.addWidget(note_lbl)
        row.addLayout(text_col, stretch=1)

        undo_btn = QPushButton('Undo')
        undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        undo_btn.setFixedHeight(30)
        undo_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {_MUTED}; '
            f'border: 1px solid #444444; border-radius: 6px; padding: 0 14px; font-size: 12px; }}'
            f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
        )
        undo_btn.clicked.connect(lambda _checked=False, i=idx: self._on_undo_dismiss(i))
        row.addWidget(undo_btn)

        return card

    def _build_accepted_card(self, idx: int, group: DuplicateGroup) -> QFrame:
        """Collapsed state for a group whose consolidation is locked in.
        Nothing touches disk until 'Consolidate Accepted Groups'."""
        winner = self._winner_for(idx)
        n = len(self._selected_losers_for(idx))

        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border: 1px solid {_TEAL}; border-radius: 8px; }}'
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(12)

        check = QLabel('✓')
        check.setStyleSheet(f'color: {_TEAL}; font-size: 16px; font-weight: 700; background: transparent; border: none;')
        row.addWidget(check, alignment=Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        song_lbl = QLabel(f'{group.canonical_artist}  —  {group.canonical_title}')
        song_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 13px; font-weight: 600; background: transparent; border: none;')
        text_col.addWidget(song_lbl)

        note_lbl = QLabel(
            f'Keeping {winner.file_path.name}  ·  {n} cop{"ies" if n != 1 else "y"} consolidated in'
        )
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;')
        text_col.addWidget(note_lbl)
        row.addLayout(text_col, stretch=1)

        edit_btn = QPushButton('Edit')
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedHeight(30)
        edit_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {_MUTED}; '
            f'border: 1px solid #444444; border-radius: 6px; padding: 0 14px; font-size: 12px; }}'
            f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
        )
        edit_btn.clicked.connect(lambda _checked=False, i=idx: self._on_edit_accepted(i))
        row.addWidget(edit_btn)

        return card

    # ── Per-group actions ──────────────────────────────────────────────────

    def _on_keep_all(self, idx: int) -> None:
        group = self._groups[idx]
        self._dismissed.add(idx)
        self._accepted.discard(idx)
        self._expanded.discard(idx)
        self._winner_overrides.pop(idx, None)
        if self._library_path is not None:
            add_dismissed(self._library_path, group_fingerprint(group))
        self._apply_card_change(idx)

    def _on_undo_dismiss(self, idx: int) -> None:
        group = self._groups[idx]
        self._dismissed.discard(idx)
        if self._library_path is not None:
            remove_dismissed(self._library_path, group_fingerprint(group))
        self._apply_card_change(idx)

    def _on_accept_group(self, idx: int) -> None:
        if not self._selected_losers_for(idx):
            return
        self._accepted.add(idx)
        self._dismissed.discard(idx)
        self._expanded.discard(idx)
        # Collapse in place only — never auto-jump to another group. The user
        # decides what to open next.
        self._apply_card_change(idx)

    def _on_edit_accepted(self, idx: int) -> None:
        self._accepted.discard(idx)
        self._expanded.add(idx)
        self._apply_card_change(idx)
        self._scroll_to_card(idx)

    def _on_accept_all_true(self, indices: list[int]) -> None:
        for i in indices:
            if i not in self._dismissed:
                self._accepted.add(i)
                self._expanded.discard(i)
        for i in indices:
            self._apply_card_change(i, refresh=False)
        self._refresh_progress_and_filters()
        self._refresh_consolidate_btn()

    # ── Navigation helpers ─────────────────────────────────────────────────

    def _scroll_to_card(self, idx: int) -> None:
        w = self._card_widgets.get(idx)
        if w is not None:
            QTimer.singleShot(0, lambda: self._results_scroll.ensureWidgetVisible(w, 0, 40))

    # ── Copy row ───────────────────────────────────────────────────────────

    def _build_copy_row(
        self,
        copy:       DuplicateCopy,
        is_winner:  bool,
        winner:     Optional[DuplicateCopy] = None,
        all_copies: Optional[list]          = None,
    ) -> tuple:
        row = QFrame()
        bg     = _ROW  if is_winner else _ROW2
        border = f'2px solid {_TEAL}' if is_winner else f'1px solid {_SEP}'
        row.setStyleSheet(
            f'QFrame {{ background: {bg}; border: {border}; border-radius: 6px; }}'
        )
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 12, 12, 12)
        h.setSpacing(14)

        radio = QRadioButton()
        radio.setStyleSheet(
            f'QRadioButton {{ background: transparent; border: none; spacing: 0; }}'
            f'QRadioButton::indicator {{ width: 16px; height: 16px; }}'
            f'QRadioButton::indicator:unchecked {{ image: url("{_ICON_RADIO_OFF}"); }}'
            f'QRadioButton::indicator:checked   {{ image: url("{_ICON_RADIO_ON}");  }}'
        )
        radio.setToolTip('Keep this copy')
        h.addWidget(radio, alignment=Qt.AlignmentFlag.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        name_lbl = QLabel(copy.file_path.name)
        name_lbl.setStyleSheet(
            f'color: {_CREAM}; font-size: 13px; font-weight: 600; background: transparent; border: none;'
        )
        info_col.addWidget(name_lbl)

        fmt_str = copy.format
        if copy.bitrate:
            fmt_str += f'  ·  {copy.bitrate} kbps'
        if copy.duration:
            mins = int(copy.duration // 60)
            secs = int(copy.duration % 60)
            fmt_str += f'  ·  {mins}:{secs:02d}'
        fmt_str += f'  ·  {fmt_bytes(copy.file_size)}'

        fmt_lbl = QLabel(fmt_str)
        fmt_lbl.setStyleSheet(f'color: {_DIM}; font-size: 12px; background: transparent; border: none;')
        info_col.addWidget(fmt_lbl)

        path_lbl = QLabel(f'LOCATION: {copy.folder_context.replace("/", " > ").replace(" : ", " / ")}')
        path_lbl.setStyleSheet(
            f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;'
        )
        info_col.addWidget(path_lbl)

        others = [c for c in (all_copies or []) if c != copy]

        def _detail(text: str, color: str = _MUTED) -> QLabel:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f'color: {color}; font-size: 12px; background: transparent; border: none;')
            return lbl

        if copy.crate_count > 0:
            info_col.addWidget(_detail(f'CRATES: {copy.crate_count}'))
        if copy.play_count and copy.play_count > 0:
            info_col.addWidget(_detail(f'PLAYS: {copy.play_count}'))
        info_col.addWidget(_detail(
            f'COMMENT: "{copy.comment[:60]}"' if copy.comment else 'COMMENT: N/A'
        ))
        info_col.addWidget(_detail(
            f'GENRE: {copy.genre_tag}' if copy.genre_tag else 'GENRE: N/A'
        ))
        info_col.addWidget(_detail(
            f'BPM: {int(copy.bpm)}' if copy.bpm else 'BPM: N/A'
        ))
        info_col.addWidget(_detail(
            'ARTWORK: Yes' if copy.has_artwork else 'ARTWORK: No'
        ))

        if is_winner:
            reason = _winner_reason(copy, others)
            advantages = _winner_metadata_advantages(copy, others)
            comment_note = _comment_merge_note(copy, others)
            label_text = f'✳  Keeping this one — {reason}'
            if advantages:
                label_text += f' — also has: {", ".join(advantages)}'
            if comment_note:
                label_text += f' — {comment_note}'
            rec_lbl = QLabel(label_text)
            rec_lbl.setWordWrap(True)
            rec_lbl.setStyleSheet(
                f'color: {_TEAL}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
            info_col.addWidget(rec_lbl)

        elif winner is not None:
            if copy.play_count and copy.play_count > (winner.play_count or 0):
                warn = QLabel('Play count from this copy will be added to the winner')
                warn.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
                info_col.addWidget(warn)
            if copy.crate_count > winner.crate_count:
                warn = QLabel(
                    f'⚠  Keeping the other copy loses {copy.crate_count} crate{"s" if copy.crate_count != 1 else ""}'
                )
                warn.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
                info_col.addWidget(warn)

        h.addLayout(info_col, stretch=1)

        finder_btn = QPushButton('Show in Finder')
        finder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        finder_btn.setFixedHeight(24)
        finder_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {_MUTED}; '
            f'border: 1px solid #444444; border-radius: 6px; padding: 2px 10px; font-size: 11px; }}'
            f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
        )
        finder_btn.clicked.connect(
            lambda _checked=False, p=str(copy.file_path): _show_in_finder(p)
        )
        h.addWidget(finder_btn, alignment=Qt.AlignmentFlag.AlignTop)

        _r  = radio
        _fp = str(copy.file_path)

        def _on_row_press(_event, _radio=_r, _path=_fp) -> None:
            _radio.setChecked(True)
            self.track_selected.emit(_path)

        row.mousePressEvent = _on_row_press

        return radio, row

    # ── Progress screen (State 1) ───────────────────────────────────────────

    def _build_progress(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {_BG};')
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        title = QLabel('Rinsing…')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f'color: {_CREAM}; font-size: 20px; font-weight: 700; background: transparent;')
        layout.addWidget(title)

        self._progress_label = QLabel('Preparing…')
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setStyleSheet(f'color: {_MUTED}; font-size: 13px; background: transparent;')
        layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedWidth(400)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f'QProgressBar {{ background: {_SEP}; border: none; border-radius: 4px; }}'
            f'QProgressBar::chunk {{ background: {_TEAL}; border-radius: 4px; }}'
        )
        layout.addWidget(self._progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        self._progress_count = QLabel()
        self._progress_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_count.setStyleSheet(f'color: {_MUTED}; font-size: 12px; background: transparent;')
        layout.addWidget(self._progress_count)

        return w

    # ── Celebration screen (State 2) ───────────────────────────────────────

    def _build_celebration(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f'background: {_BG};')

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        inner_w = QWidget()
        inner_w.setFixedWidth(560)
        inner_w.setStyleSheet('background: transparent;')
        layout = QVBoxLayout(inner_w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        check = QLabel('✓')
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check.setStyleSheet(f'color: {_TEAL}; font-size: 56px; background: transparent; border: none;')
        layout.addWidget(check)

        self._celeb_headline = QLabel('Rinsed.')
        self._celeb_headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._celeb_headline.setStyleSheet(
            f'color: {_CREAM}; font-size: 28px; font-weight: 700; background: transparent; border: none;'
        )
        layout.addWidget(self._celeb_headline)

        self._celeb_stat = QLabel()
        self._celeb_stat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._celeb_stat.setWordWrap(True)
        self._celeb_stat.setStyleSheet(
            f'color: {_TEAL}; font-size: 16px; background: transparent; border: none;'
        )
        layout.addWidget(self._celeb_stat)

        self._celeb_tip = QLabel()
        self._celeb_tip.setTextFormat(Qt.TextFormat.RichText)
        self._celeb_tip.setText(
            '<div style="line-height: 145%; text-align: center;">'
            'Don\'t worry, the duplicate tracks that were in multiple folders will be rerouted '
            'by CrateSort so your crates will still work in your DJ software.'
            '</div>'
        )
        self._celeb_tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._celeb_tip.setWordWrap(True)
        self._celeb_tip.setStyleSheet(
            f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;'
        )
        layout.addWidget(self._celeb_tip)

        self._celeb_skipped_lbl = QLabel()
        self._celeb_skipped_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._celeb_skipped_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._celeb_skipped_lbl.setWordWrap(True)
        self._celeb_skipped_lbl.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;'
        )
        self._celeb_skipped_lbl.hide()
        layout.addWidget(self._celeb_skipped_lbl)

        self._celeb_errors_lbl = QLabel()
        self._celeb_errors_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._celeb_errors_lbl.setWordWrap(True)
        self._celeb_errors_lbl.setStyleSheet(
            f'color: {_ORANGE}; font-size: 11px; background: transparent; border: none;'
        )
        self._celeb_errors_lbl.hide()
        layout.addWidget(self._celeb_errors_lbl)

        classify_btn = QPushButton('Go Back to Dashboard')
        classify_btn.setFixedHeight(44)
        classify_btn.setFixedWidth(260)
        classify_btn.setStyleSheet(
            f'QPushButton {{ background: {_TEAL}; color: #ffffff; border: none; '
            f'border-radius: 6px; font-size: 14px; font-weight: 600; }}'
            f'QPushButton:hover {{ background: #38706a; }}'
            f'QPushButton:pressed {{ background: #2d6358; }}'
        )
        classify_btn.clicked.connect(self.done.emit)
        layout.addWidget(classify_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        h_row = QHBoxLayout()
        h_row.addStretch()
        h_row.addWidget(inner_w)
        h_row.addStretch()
        outer.addLayout(h_row)
        outer.addStretch()

        return w

    # ── Consolidation flow ──────────────────────────────────────────────────

    def _on_consolidate(self) -> None:
        approved: list[tuple] = []
        for i in sorted(self._accepted):
            group  = self._groups[i]
            winner = self._winner_for(i)
            losers = self._selected_losers_for(i)
            if winner and losers:
                approved.append((group, winner, losers))

        if not approved:
            self.done.emit()
            return

        files_removed = sum(len(losers) for _g, _w, losers in approved)
        space_freed   = sum(c.file_size for _g, _w, losers in approved for c in losers)
        if not _ov_confirm(
            self,
            'Consolidate Duplicates',
            f'This will consolidate {files_removed} extra '
            f'cop{"ies" if files_removed != 1 else "y"} into the ones you\'re keeping '
            f'and free {fmt_bytes(space_freed)}.\n\n'
            'Your crates stay pointed at the copy you keep. '
            'This can\'t be reversed from inside CrateSort.',
            confirm_text='Consolidate',
            confirm_danger=True,
        ):
            return

        total = len(approved)
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(0)
        self._progress_count.setText(f'0 of {total:,}')
        self._stack.setCurrentIndex(_STATE_PROGRESS)

        self._worker = _ConsolidationWorker(
            approved=approved,
            library_path=self._library_path,
            serato_dir=self._serato_dir,
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.errored.connect(self._on_errored)
        self._worker.start()

    def _on_progress(self, done: int, total: int, label: str) -> None:
        self._progress_bar.setValue(done)
        self._progress_count.setText(f'{done:,} of {total:,}')
        self._progress_label.setText(label)

    def _on_finished(self, result: ConsolidationResult) -> None:
        self._worker = None

        n = result.files_removed
        s = fmt_bytes(result.space_freed)
        self._celeb_stat.setText(
            f'{n:,} duplicate{"s" if n != 1 else ""} cleaned up  ·  {s} freed'
        )

        if result.errors:
            self._celeb_errors_lbl.setText(
                f'⚠ {len(result.errors)} file{"s" if len(result.errors) != 1 else ""} '
                f'could not be removed — check the log.'
            )
            self._celeb_errors_lbl.show()
        else:
            self._celeb_errors_lbl.hide()

        skipped = self._summary.skipped_count if self._summary else 0
        if skipped > 0:
            self._celeb_skipped_lbl.setText(
                f'<div style="line-height: 145%; text-align: center;">'
                f'{skipped:,} untagged track{"s" if skipped != 1 else ""} '
                f'{"weren\'t" if skipped != 1 else "wasn\'t"} evaluated. '
                f'Fix the tags and rescan to cover your full library.'
                f'</div>'
            )
            self._celeb_skipped_lbl.show()
        else:
            self._celeb_skipped_lbl.hide()

        self._stack.setCurrentIndex(_STATE_CELEBRATION)

    def _on_errored(self, msg: str) -> None:
        self._worker = None
        self._stack.setCurrentIndex(_STATE_RESULTS)
        _ov_alert(self, 'Consolidation Failed', f'Something went wrong:\n{msg[:400]}')
