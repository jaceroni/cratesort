from __future__ import annotations

import subprocess
import sys as _sys
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QPointF, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
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
from cratesort.src.core.file_organizer import FileOrganizer
from cratesort.src.serato.crate_reader import CrateReader
from cratesort.src.utils.checkpoint import update_checkpoint_crates
from cratesort.src.utils.undo_manager import ConsolidationCommand
from cratesort.src.gui.overlays import (
    _ov_alert, _CrateSortDialog, _create_dialog_layout, _AnimatedStatCardWidget,
)

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
    ('true_duplicate', 'True Duplicates'),
    ('variant',        'Possible Variants'),
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

    # Larger file at same bitrate (better rip / more data) — but only when the
    # difference is big enough to actually mean something. A few-byte (or
    # even few-KB) gap is just ID3 tag padding, not a meaningfully different
    # encode, and citing it as "the reason" is technically true but
    # substantively misleading. Require the delta to clear 1% of the file
    # size before treating it as real; otherwise fall through to whatever
    # criterion actually differentiates these files.
    max_loser_size = max(l.file_size for l in losers)
    delta = winner.file_size - max_loser_size
    if delta > 0 and delta >= max_loser_size * 0.01:
        return f'larger file size (+{fmt_bytes(delta)})'

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


def _natural_join(fields: list[str]) -> str:
    """'comment' -> 'a comment'; 'artwork' -> 'artwork' (uncountable);
    multiple -> 'a comment and a year'. Used to avoid the stilted
    'also has: comment' colon-list phrasing."""
    worded = [f if f == 'artwork' else f'a {f}' for f in fields]
    if len(worded) == 1:
        return worded[0]
    return ', '.join(worded[:-1]) + f' and {worded[-1]}'


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


# Reasons in _winner_reason() that reflect real, objective audio/rip quality —
# as opposed to metadata completeness, crate count, or filename tidiness,
# none of which say anything about whether the audio itself is better. A
# track missing a YEAR tag (someone never filled it in, or entered it wrong)
# is not evidence of a worse rip, so a loser-row note must not claim "lower
# quality" on that basis alone — only when one of these genuinely fired.
_QUALITY_REASON_MARKERS = ('lossless format', 'higher quality (', 'larger file size (')


def _loser_note(copy: DuplicateCopy, winner: DuplicateCopy) -> str:
    """
    Plain-language note for a non-recommended copy explaining why it wasn't
    picked — or '' if nothing meaningfully differentiates it from the winner.
    Deliberately avoids asserting "lower quality" when the only difference is
    missing/incomplete metadata, since that's a data-entry gap, not evidence
    the audio itself is worse.
    """
    reason = _winner_reason(winner, [copy])
    if any(marker in reason for marker in _QUALITY_REASON_MARKERS):
        return f'Not the recommended copy — {reason}'
    advantages = _winner_metadata_advantages(winner, [copy])
    if advantages:
        return (
            f'Not the recommended copy — missing {_natural_join(advantages)}, '
            f'which doesn\'t necessarily mean lower quality'
        )
    return ''


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


class _UndoConsolidationWorker(QThread):
    finished = pyqtSignal(object)   # dict — rollback() result
    errored  = pyqtSignal(str)

    def __init__(
        self,
        log_path: Path,
        library_path: Path,
        serato_dir: Optional[Path],
        parent=None,
    ):
        super().__init__(parent)
        self._log_path     = log_path
        self._library_path = library_path
        self._serato_dir   = serato_dir

    def run(self) -> None:
        try:
            import json
            result = FileOrganizer(self._library_path, self._serato_dir).rollback(self._log_path)
            # Fold the just-restored crates back into the sync checkpoint, same
            # reasoning as DuplicateConsolidator.consolidate() — otherwise the
            # very next dashboard sync-check would misreport this undo itself
            # as a suspicious external change.
            if self._serato_dir:
                try:
                    with open(self._log_path, encoding='utf-8') as f:
                        log_data = json.load(f)
                    backup_paths = log_data.get('crate_backup_paths', [])
                    subcrates_dir = self._serato_dir / 'Subcrates'
                    reader = CrateReader(self._serato_dir)
                    updates: dict[str, list[str]] = {}
                    for bp in backup_paths:
                        # Backup lives under _CrateSort_Backups/<same relative
                        # path as under Subcrates>/<Name>_<timestamp>.crate.bak —
                        # map it back to the live crate file it restored.
                        backup_path = Path(bp)
                        try:
                            rel = backup_path.relative_to(self._serato_dir / '_CrateSort_Backups')
                        except ValueError:
                            continue
                        name = rel.name
                        # Strip the "_<14-digit timestamp>.crate.bak" suffix back to "<Name>.crate"
                        import re as _re
                        m = _re.match(r'^(.*)_\d{8}_\d{6}\.crate\.bak$', name)
                        if not m:
                            continue
                        live_path = subcrates_dir / rel.parent / f'{m.group(1)}.crate'
                        if live_path.exists():
                            tracks, _ = reader._read_tracks(live_path)
                            updates[str(live_path)] = tracks
                    update_checkpoint_crates(self._serato_dir, updates)
                except Exception:
                    pass   # checkpoint refresh is best-effort; the undo itself already succeeded
            self.finished.emit(result)
        except Exception as exc:
            self.errored.emit(str(exc))


def _round_unit(n: int) -> tuple[int, str]:
    """Whole-number value + unit for a byte count, same unit ladder as
    fmt_bytes() but rounded to an integer (the stat-card widget only animates
    whole numbers)."""
    val = float(n)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if val < 1024:
            return round(val), unit
        val /= 1024
    return round(val), 'TB'


class _ConsolidatePreviewDialog(_CrateSortDialog):
    """
    Replaces a dense paragraph of prose ("This will consolidate N extra
    copies into the ones you're keeping and free X...") with the same
    stat-card treatment used on the dashboard — Jace, reviewing the old
    version: "it looks like a paragraph, almost a warning... I want a more
    data-driven view." Reuses _AnimatedStatCardWidget (the one stat-card look
    used everywhere else in the app) rather than inventing a new one.
    """

    def __init__(
        self,
        parent: QWidget,
        groups_count: int,
        files_kept: int,
        copies_removed: int,
        space_freed: int,
    ):
        super().__init__(parent)
        self._elastic = False   # matches _ov_confirm(confirm_danger=True) — no bounce for a destructive action
        self.setMinimumWidth(640)

        layout = _create_dialog_layout(self)

        title_lbl = QLabel('Consolidate Duplicates')
        title_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(title_lbl)
        layout.addSpacing(4)

        lead_lbl = QLabel(
            f'Across {groups_count} group{"s" if groups_count != 1 else ""}, '
            f'here\'s what will happen:'
        )
        lead_lbl.setStyleSheet('color: #d5c7ad; font-size: 14px; background: transparent; border: none;')
        layout.addWidget(lead_lbl)

        stat_row = QHBoxLayout()
        stat_row.setSpacing(12)

        kept_card = _AnimatedStatCardWidget('FILES KEPT')
        stat_row.addWidget(kept_card, stretch=1)

        removed_card = _AnimatedStatCardWidget('COPIES REMOVED')
        stat_row.addWidget(removed_card, stretch=1)

        freed_value, freed_unit = _round_unit(space_freed)
        freed_card = _AnimatedStatCardWidget('SPACE FREED', suffix=f' {freed_unit}')
        stat_row.addWidget(freed_card, stretch=1)

        layout.addLayout(stat_row)

        note_lbl = QLabel()
        note_lbl.setTextFormat(Qt.TextFormat.RichText)
        note_lbl.setText(
            '<div style="line-height: 145%;">'
            'Your crates stay pointed at the copy you keep. An "Undo This '
            'Consolidation" option will be available right after, as long as '
            'nothing else touches these files in the meantime.'
            '</div>'
        )
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet('color: #a89b85; font-size: 12px; background: transparent; border: none;')
        layout.addWidget(note_lbl)

        yes_btn = QPushButton('Consolidate')
        yes_btn.setFixedHeight(36)
        yes_btn.setStyleSheet(
            'QPushButton { background-color: #c35050; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #b03c3c; }'
            'QPushButton:pressed { background-color: #973434; }'
        )
        yes_btn.clicked.connect(self.accept)
        yes_btn.setAutoDefault(False)

        no_btn = QPushButton('Cancel')
        no_btn.setFixedHeight(36)
        no_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
            'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
        )
        no_btn.clicked.connect(self.reject)
        no_btn.setDefault(True)   # destructive action — Return must stay the safe choice

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addWidget(no_btn)
        btn_row.addStretch()
        btn_row.addWidget(yes_btn)
        layout.addLayout(btn_row)

        kept_card.start_animation(files_kept, 700)
        removed_card.start_animation(copies_removed, 700)
        freed_card.start_animation(freed_value, 700)


def _show_consolidate_preview(
    parent: QWidget, groups_count: int, files_kept: int, copies_removed: int, space_freed: int,
) -> bool:
    dlg = _ConsolidatePreviewDialog(parent, groups_count, files_kept, copies_removed, space_freed)
    return dlg.exec() == QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# Duplicate Review View
# ---------------------------------------------------------------------------

class DuplicateReviewView(QWidget):
    """
    Full-screen duplicate review launched from the dashboard stat card.

    States:
      0 — Results: Tier 1 (true dupes) + Tier 2 (variants) review lists
      1 — Progress: "Consolidating…" (% complete bar)
      2 — Celebration: "Consolidation Successful"

    Review model (opt-in, per-group):
      * Every group is a cheap collapsed strip; click it to open the full card.
      * In an open card, one radio picks the copy to keep — every other copy is
        consolidated into it.
      * "Accept This Group" locks that group in and moves you to the next one;
        no other group is touched until "Consolidate Accepted Groups".

    Emits `done` when the user dismisses the celebration or skips entirely.
    """

    done              = pyqtSignal()      # user finished — return to dashboard
    track_selected    = pyqtSignal(str)   # file path → populate sidebar artwork
    # winner file path (str) → merged comment. Fired the moment a real
    # consolidation commits — independent of `done`, which also fires from
    # Skip/Classify and carries nothing. The caller's in-memory TrackRecords
    # (dashboard._inventory) were loaded at the last scan and have no other
    # way to learn their .comment is now stale on disk.
    comments_updated  = pyqtSignal(dict)

    def __init__(self, undo_manager=None, parent=None):
        super().__init__(parent)

        self._library_path: Optional[Path] = None
        self._serato_dir:   Optional[Path] = None
        self._groups:       list[DuplicateGroup] = []
        self._summary:      Optional[DuplicateSummary] = None
        self._worker:       Optional[_ConsolidationWorker] = None
        # Undo/redo for a completed consolidation now lives on the shared
        # sidebar Undo/Redo stack (see ConsolidationCommand in
        # undo_manager.py) rather than a screen-local button that vanished
        # the moment you navigated away — which is exactly what happened in
        # practice. _cmd_workers keeps the async undo/redo QThreads alive
        # while in flight (nothing else would hold a reference to them).
        self._undo_manager = undo_manager
        self._cmd_workers:  set = set()

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

        # Chunked-population bookkeeping (see _populate_results /
        # _continue_populate) — large libraries build their result rows
        # across several event-loop ticks instead of freezing on one huge
        # synchronous pass. _populate_gen invalidates a stale in-flight run;
        # _populating_in_progress distinguishes "progress screen showing
        # because we're still building the list" from "showing because a real
        # consolidation is running" (same stack page, different reason).
        self._populate_gen = 0
        self._populating_in_progress = False

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
        # Invalidate any in-flight chunked population (see _populate_results)
        # — its stale continuation would otherwise keep firing timers and
        # inserting widgets into a screen that's being torn down.
        self._populate_gen += 1
        if self._populating_in_progress:
            self._populating_in_progress = False
            self._stack.setCurrentIndex(_STATE_RESULTS)
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
        title_lbl = QLabel('Duplicate Consolidation')
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

        filt_by_lbl = QLabel('Filter by')
        filt_by_lbl.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; font-weight: 600; '
            f'background: transparent; border: none;'
        )
        filt_row.addWidget(filt_by_lbl)

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
        return group.tier == m

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

    # Below this many groups, one synchronous pass is fast enough that a
    # progress screen would just be an unnecessary flash. Above it — confirmed
    # on a real 75k-track library that produced 16,000 duplicate groups —
    # building every row's widget synchronously froze the app for close to a
    # minute, with a system-level "spinning wheel of death," not just a slow
    # render. The original review-screen design already avoids the *worst*
    # case (a full interactive card per group) by rendering everything but the
    # expanded group as a cheap collapsed strip — see _ensure_one_expanded —
    # but at 16,000 items even the cheap strip's widget-construction cost adds
    # up to a real, user-visible freeze.
    _CHUNK_THRESHOLD = 800
    _CHUNK_SIZE = 200

    def _populate_results(self) -> None:
        # Clear old content (keep the trailing stretch)
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._card_widgets.clear()
        self._ensure_one_expanded()

        # Bump before building the plan so a stale in-flight chunked run (from
        # a rapid double filter-click, say) recognizes itself as superseded
        # and stops instead of racing this one.
        self._populate_gen += 1
        gen = self._populate_gen
        steps = self._build_populate_plan()

        if len(self._groups) < self._CHUNK_THRESHOLD:
            self._run_populate_steps(steps)
            self._refresh_progress_and_filters()
            self._refresh_consolidate_btn()
            return

        # Large library: build entirely off-screen (the progress stack page,
        # not the results page) so nothing half-renders in front of the user,
        # with real, calculable progress — the total is always known up
        # front, so this is a real percentage, never a fake/pulsing one.
        self._populating_in_progress = True
        self._progress_bar.setRange(0, max(len(steps), 1))
        self._progress_bar.setValue(0)
        self._progress_label.setText('Preparing duplicate review…')
        self._progress_count.setText(f'0 of {len(self._groups):,} groups')
        self._stack.setCurrentIndex(_STATE_PROGRESS)
        self._continue_populate(steps, gen, 0, len(steps))

    def _continue_populate(self, steps: list, gen: int, done: int, total: int) -> None:
        if gen != self._populate_gen:
            return  # superseded by a newer load()/filter change — drop this run
        batch, rest = steps[:self._CHUNK_SIZE], steps[self._CHUNK_SIZE:]
        self._run_populate_steps(batch)
        done += len(batch)
        self._progress_bar.setValue(done)
        self._progress_count.setText(f'{done:,} of {total:,}')
        if rest:
            QTimer.singleShot(0, lambda: self._continue_populate(rest, gen, done, total))
            return
        self._populating_in_progress = False
        self._refresh_progress_and_filters()
        self._refresh_consolidate_btn()
        if self._stack.currentIndex() == _STATE_PROGRESS:
            self._stack.setCurrentIndex(_STATE_RESULTS)

    def _run_populate_steps(self, steps: list) -> None:
        """Execute a batch of plan steps from _build_populate_plan — either
        insert an already-built widget, or build+insert one group's card
        (the expensive part, which is why this is called in chunks)."""
        for step in steps:
            if step[0] == 'w':
                self._insert_result_widget(step[1])
            else:
                _, i, g = step
                card = self._build_group_card(i, g)
                self._card_widgets[i] = card
                self._insert_result_widget(card)

    def _insert_result_widget(self, wdg: QWidget) -> None:
        self._results_layout.insertWidget(self._results_layout.count() - 1, wdg)

    def _build_populate_plan(self) -> list:
        """Decide everything about what the results screen should show —
        section headers, empty states, which groups get a card — using only
        the cheap per-group bookkeeping (tier/filter checks). Building the
        group-card widgets themselves is deferred: each is represented here
        as a ('c', idx, group) step for _run_populate_steps to execute later,
        in chunks."""
        steps: list = []

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
            steps.append(('w', notice))

        tier1 = [(i, g) for i, g in enumerate(self._groups) if g.tier == 'true_duplicate']
        tier2 = [(i, g) for i, g in enumerate(self._groups) if g.tier == 'variant']

        def plan_section(
            title_base: str, subtitle: str, accent: str,
            entries: list[tuple[int, DuplicateGroup]], is_true: bool,
        ) -> None:
            visible = [(i, g) for i, g in entries if self._passes_filter(i, g)]
            if not visible:
                return
            # Accepted groups render as a collapsed strip already (see
            # _build_group_card) — sorting them after the still-pending ones
            # keeps what you're actively working on at the top, without
            # needing a dedicated "hide accepted" filter button for it.
            visible.sort(key=lambda ig: ig[0] in self._accepted)
            action: Optional[tuple[str, Callable[[], None]]] = None
            if is_true:
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
            steps.append(('w', self._build_section_header(
                f'{title_base} — {n} group{"s" if n != 1 else ""}',
                subtitle, accent, action=action,
            )))
            for i, g in visible:
                steps.append(('c', i, g))

        plan_section(
            'True Duplicates',
            'Same file found in multiple locations. '
            'We\'ve selected the best copy — confirm or choose a different one.',
            _RED, tier1, True,
        )
        plan_section(
            'Possible Variants',
            'Looks like different versions of the same song. '
            'Confirm if any are actual duplicates you want to consolidate.',
            _ORANGE, tier2, False,
        )

        has_visible_card = any(step[0] == 'c' for step in steps)

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
                steps.append(('w', headline))
                steps.append(('w', body))
            else:
                empty = QLabel('No duplicates found. Your library is clean.')
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setStyleSheet(
                    f'color: {_MUTED}; font-size: 14px; background: transparent; border: none;'
                )
                steps.append(('w', empty))
        elif not has_visible_card:
            msg = {
                'true_duplicate': 'No true duplicates.',
                'variant':        'No possible variants.',
            }.get(self._filter_mode, 'Nothing matches this filter.')
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;'
            )
            steps.append(('w', lbl))

        return steps

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
        song_lbl.setWordWrap(True)  # same overflow risk/fix as the expanded card's title — see there
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
        song_lbl.setWordWrap(True)
        song_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | _vc)
        song_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 14px; font-weight: 600; background: transparent; border: none;')
        title_row.addWidget(song_lbl, stretch=1)

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

        conflict_fields = [c.field.upper() for c in group.metadata_conflicts]
        for copy in group.copies:
            is_winner = (copy is winner)
            radio, row = self._build_copy_row(copy, is_winner, winner, group.copies, conflict_fields)
            btn_group.addButton(radio)
            if is_winner:
                radio.setChecked(True)
            copy_rows.append((radio, row, copy))
            layout.addWidget(row)

        # Footer: the call-to-action sentence sits directly beside its own
        # button now, rather than up in the title bar competing for space
        # with the song title and Keep All — it's the same "select a file,
        # then confirm" action, so it reads as one connected unit.
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 4, 0, 0)
        footer.addStretch(1)

        savings_lbl = QLabel(
            f'Select the file you\'d like to keep — the unselected duplicates will be '
            f'deleted to free-up {fmt_bytes(sum(c.file_size for c in group.copies if c is not winner))}'
        )
        # _MUTED (not the brighter _CREAM) — matches the LOCATION/COMMENT/etc.
        # detail text already used elsewhere in this card. padding-top nudges
        # the label's own font-metrics baseline down to align with the
        # button's vertically-centered text next to it.
        savings_lbl.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; background: transparent; border: none; padding-top: 5px;'
        )
        footer.addWidget(savings_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        footer.addSpacing(16)

        accept_btn = QPushButton('Confirm Selection')
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
            savings_lbl.setText(
                f'Select the file you\'d like to keep — the unselected duplicates will be '
                f'deleted to free-up {fmt_bytes(sum(c.file_size for c in group.copies if c is not cur_winner))}'
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

        # Metadata-conflict disclosure (which fields disagree between copies)
        # now lives in the winner's teal "Keeping this one" line inside
        # _build_copy_row, in the same place as the win-reason explanation —
        # previously it was a separate line here that could disagree with
        # (or omit fields from) the teal text above it.

        layout.addLayout(footer)
        _refresh_footer(winner)

        # Symmetric with _build_collapsed_card's "click anywhere to open" —
        # click anywhere on the card that isn't a real control (a copy row,
        # a button, the disclosure chevron) collapses it back. Those controls
        # all accept their own mouse press, so this only fires on the card's
        # own background/label surface, which Qt bubbles unhandled mouse
        # events up to.
        card.mousePressEvent = lambda _e, i=idx: self._on_collapse(i)
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

        # Same freeze this loop hit at real-library scale as _populate_results
        # — rebuilding one card at a time is already about as cheap as it
        # gets per item, but at thousands of accepted groups the total add up
        # to a real, multi-second-to-multi-minute synchronous stretch. Same
        # chunked-with-progress treatment; see _populate_results for why.
        if len(indices) < self._CHUNK_THRESHOLD:
            for i in indices:
                self._apply_card_change(i, refresh=False)
            self._refresh_progress_and_filters()
            self._refresh_consolidate_btn()
            return

        self._populate_gen += 1
        gen = self._populate_gen
        self._populating_in_progress = True
        self._progress_bar.setRange(0, len(indices))
        self._progress_bar.setValue(0)
        self._progress_label.setText('Accepting duplicate groups…')
        self._progress_count.setText(f'0 of {len(indices):,}')
        self._stack.setCurrentIndex(_STATE_PROGRESS)
        self._continue_accept_all(list(indices), gen, 0, len(indices))

    def _continue_accept_all(self, remaining: list[int], gen: int, done: int, total: int) -> None:
        if gen != self._populate_gen:
            return  # superseded — a filter change or new load() dropped this run
        batch, rest = remaining[:self._CHUNK_SIZE], remaining[self._CHUNK_SIZE:]
        for i in batch:
            self._apply_card_change(i, refresh=False)
        done += len(batch)
        self._progress_bar.setValue(done)
        self._progress_count.setText(f'{done:,} of {total:,}')
        if rest:
            QTimer.singleShot(0, lambda: self._continue_accept_all(rest, gen, done, total))
            return
        self._populating_in_progress = False
        self._refresh_progress_and_filters()
        self._refresh_consolidate_btn()
        if self._stack.currentIndex() == _STATE_PROGRESS:
            self._stack.setCurrentIndex(_STATE_RESULTS)

    # ── Navigation helpers ─────────────────────────────────────────────────

    def _scroll_to_card(self, idx: int) -> None:
        w = self._card_widgets.get(idx)
        if w is not None:
            QTimer.singleShot(0, lambda: self._results_scroll.ensureWidgetVisible(w, 0, 40))

    # ── Copy row ───────────────────────────────────────────────────────────

    def _build_copy_row(
        self,
        copy:            DuplicateCopy,
        is_winner:       bool,
        winner:          Optional[DuplicateCopy] = None,
        all_copies:      Optional[list]          = None,
        conflict_fields: Optional[list[str]]     = None,
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
        name_lbl.setWordWrap(True)
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

        # No wordWrap here used to mean a genuinely deep folder path could
        # report an unbounded sizeHint width, and since this label sits in a
        # stretch=1 column, that dragged the whole card (and the scroll
        # area's content widget, via setWidgetResizable) wider than the
        # window — a real horizontal-scrollbar bug at real-library depth,
        # confirmed on a 75k-track library where it pushed the per-group
        # Accept button off-screen entirely. Wrapping instead of a single
        # unbounded line means this can never force the row wider than
        # whatever width the layout actually gives it.
        path_lbl = QLabel(f'LOCATION: {copy.folder_context.replace("/", " > ").replace(" : ", " / ")}')
        path_lbl.setWordWrap(True)
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
            f'YEAR: {copy.year_tag}' if copy.year_tag else 'YEAR: N/A'
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
            # 'best available copy' is a content-free fallback for when
            # nothing in _winner_reason's own criteria differs — don't show
            # it as filler when a real differentiator (extra metadata, a
            # richer comment) is about to be stated right after it anyway.
            if reason == 'best available copy' and (advantages or comment_note):
                label_text = '❤  Keep this file'
            else:
                label_text = f'❤  Keep this file — {reason}'
            if advantages:
                label_text += f' — has {_natural_join(advantages)}'
            if comment_note:
                label_text += f' — {comment_note}'
            if conflict_fields:
                # All differing-value fields (both copies have a value, but
                # disagree) surface here, in the one place that already
                # explains the winner decision — previously this lived only
                # in a separate line below both copies, and could silently
                # omit fields (e.g. YEAR) that the teal line never mentioned
                # at all, which read as the two texts contradicting each other.
                plural = len(conflict_fields) != 1
                fields_str = (
                    conflict_fields[0] if len(conflict_fields) == 1
                    else ', '.join(conflict_fields[:-1]) + f' and {conflict_fields[-1]}'
                )
                label_text += (
                    f' — {fields_str} also {"differ" if plural else "differs"}, '
                    f'winner\'s value{"s" if plural else ""} kept'
                )
            info_col.addSpacing(8)   # extra breathing room above this block
            rec_lbl = QLabel(label_text)
            rec_lbl.setWordWrap(True)
            rec_lbl.setStyleSheet(
                f'color: {_TEAL}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
            info_col.addWidget(rec_lbl)

            info_col.addSpacing(6)   # extra breathing room between the two lines
            # Crate-safety reassurance is universally true for every
            # consolidation (not evidence-based like the line above), so it's
            # fixed text rather than something computed per group. Same gray
            # as the format/bitrate/duration/size line (_DIM), not teal —
            # it's a supporting note, not part of the decision claim above it.
            crates_lbl = QLabel(
                'Any crates that were using the unselected files will be '
                'automatically rerouted to the file you keep.'
            )
            crates_lbl.setWordWrap(True)
            crates_lbl.setStyleSheet(
                f'color: {_DIM}; font-size: 11px; background: transparent; border: none;'
            )
            info_col.addWidget(crates_lbl)

        elif winner is not None:
            loser_note = _loser_note(copy, winner)
            if loser_note:
                note_lbl = QLabel(loser_note)
                note_lbl.setWordWrap(True)
                note_lbl.setStyleSheet(f'color: {_DIM}; font-size: 11px; background: transparent; border: none;')
                info_col.addWidget(note_lbl)
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

        title = QLabel('Consolidating…')
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

        self._celeb_headline = QLabel('Consolidation Successful')
        self._celeb_headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._celeb_headline.setStyleSheet(
            f'color: {_CREAM}; font-size: 28px; font-weight: 700; background: transparent; border: none;'
        )
        layout.addWidget(self._celeb_headline)

        # Same stat-card treatment as the pre-consolidation confirm dialog
        # (_ConsolidatePreviewDialog) — one consistent "here are the numbers"
        # look across both the before and after screens of this same action.
        stat_row = QHBoxLayout()
        stat_row.setSpacing(12)
        self._celeb_removed_card = _AnimatedStatCardWidget('DUPLICATES REMOVED')
        stat_row.addWidget(self._celeb_removed_card, stretch=1)
        self._celeb_freed_card = _AnimatedStatCardWidget('SPACE FREED')
        stat_row.addWidget(self._celeb_freed_card, stretch=1)
        layout.addLayout(stat_row)

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

        # Undo now lives on the sidebar Undo/Redo stack (ConsolidationCommand),
        # not a button on this screen — see __init__ and _on_finished.

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
        if not _show_consolidate_preview(
            self,
            groups_count=len(approved),
            files_kept=len(approved),
            copies_removed=files_removed,
            space_freed=space_freed,
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
        approved   = getattr(self._worker, '_approved', None)
        self._worker = None
        if result.comment_updates:
            self.comments_updated.emit(result.comment_updates)

        if (
            self._undo_manager is not None
            and result.rollback_log_path
            and result.files_removed > 0
            and approved
        ):
            n = result.files_removed
            cmd = ConsolidationCommand(
                description=f'Consolidated {n} duplicate file{"s" if n != 1 else ""}',
                log_path=result.rollback_log_path,
                approved=approved,
                do_undo=self._run_consolidation_undo,
                do_redo=self._run_consolidation_redo,
            )
            self._undo_manager.push_completed(cmd)

        n = result.files_removed
        freed_value, freed_unit = _round_unit(result.space_freed)
        self._celeb_removed_card.start_animation(n, 700)
        self._celeb_freed_card.set_suffix(f' {freed_unit}')
        self._celeb_freed_card.start_animation(freed_value, 700)

        if result.errors:
            n_err = len(result.errors)
            shown = result.errors[:3]
            more = n_err - len(shown)
            detail = '\n'.join(f'⚠ {e}' for e in shown)
            if more > 0:
                detail += f'\n…and {more} more.'
            self._celeb_errors_lbl.setText(detail)
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

    # ── Undo / Redo (via the sidebar's shared UndoManager) ──────────────────
    # These are the do_undo/do_redo callables ConsolidationCommand invokes —
    # see undo_manager.py. Each keeps its worker alive in self._cmd_workers
    # until it reports back, since nothing else holds a reference to it.

    def _run_consolidation_undo(self, cmd: ConsolidationCommand, on_done: Callable[[str], None]) -> None:
        worker = _UndoConsolidationWorker(
            log_path=cmd.log_path,
            library_path=self._library_path,
            serato_dir=self._serato_dir,
            parent=self,
        )
        self._cmd_workers.add(worker)

        def _finished(result: dict) -> None:
            self._cmd_workers.discard(worker)
            restored = result.get('restored', 0)
            failed   = result.get('failed', 0)
            if failed:
                errors = '\n'.join(result.get('errors', [])[:10])
                _ov_alert(
                    self, 'Some Files Could Not Be Restored',
                    f'{restored} file{"s" if restored != 1 else ""} restored, '
                    f'{failed} failed:\n\n{errors}',
                )
            on_done(f'Restored {restored} file{"s" if restored != 1 else ""}')

        def _errored(msg: str) -> None:
            self._cmd_workers.discard(worker)
            _ov_alert(self, 'Undo Failed', f'Something went wrong:\n{msg[:400]}')
            on_done('Undo failed')

        worker.finished.connect(_finished)
        worker.errored.connect(_errored)
        worker.start()

    def _run_consolidation_redo(self, cmd: ConsolidationCommand, on_done: Callable[[str], None]) -> None:
        worker = _ConsolidationWorker(
            approved=cmd.approved,
            library_path=self._library_path,
            serato_dir=self._serato_dir,
            parent=self,
        )
        self._cmd_workers.add(worker)

        def _finished(result: ConsolidationResult) -> None:
            self._cmd_workers.discard(worker)
            # A redo produces a fresh rollback log — the next undo must
            # target this one, not the original run's (already-consumed) log.
            cmd.log_path = result.rollback_log_path
            if result.comment_updates:
                self.comments_updated.emit(result.comment_updates)
            n = result.files_removed
            on_done(f'Consolidated {n} file{"s" if n != 1 else ""}')

        def _errored(msg: str) -> None:
            self._cmd_workers.discard(worker)
            _ov_alert(self, 'Redo Failed', f'Something went wrong:\n{msg[:400]}')
            on_done('Redo failed')

        worker.finished.connect(_finished)
        worker.errored.connect(_errored)
        worker.start()
