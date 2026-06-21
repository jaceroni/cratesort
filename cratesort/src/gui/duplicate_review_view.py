from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

_ASSETS        = Path(__file__).parent.parent.parent / 'assets'
_ICON_CHECKED  = str(_ASSETS / 'icons' / 'checkbox-checked.svg')
_ICON_UNCHECKED = str(_ASSETS / 'icons' / 'checkbox-unchecked.svg')

from cratesort.src.core.duplicate_detector import (
    DuplicateGroup, DuplicateCopy, DuplicateSummary, fmt_bytes,
)
from cratesort.src.core.duplicate_consolidator import (
    DuplicateConsolidator, ConsolidationResult,
)
from cratesort.src.gui.overlays import _ov_alert

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

# Stack indices
_STATE_RESULTS      = 0
_STATE_PROGRESS     = 1
_STATE_CELEBRATION  = 2


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _ConsolidationWorker(QThread):
    progress = pyqtSignal(int, int, str)   # (done, total, label)
    finished = pyqtSignal(object)          # ConsolidationResult
    errored  = pyqtSignal(str)

    def __init__(
        self,
        approved: list,
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

    Emits `done` when the user dismisses the celebration or skips entirely.
    """

    done = pyqtSignal()   # user finished — return to dashboard

    def __init__(self, parent=None):
        super().__init__(parent)

        self._library_path: Optional[Path] = None
        self._serato_dir:   Optional[Path] = None
        self._groups:       list[DuplicateGroup] = []
        self._summary:      Optional[DuplicateSummary] = None
        self._worker:       Optional[_ConsolidationWorker] = None

        # Per-group winner overrides: group index → DuplicateCopy
        self._winner_overrides: dict[int, DuplicateCopy] = {}
        # Per-group dismissed flags for Tier 2
        self._dismissed: set[int] = set()

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
        self._dismissed.clear()
        self._populate_results()
        self._stack.setCurrentIndex(_STATE_RESULTS)

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
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(32, 20, 32, 20)

        title_col = QVBoxLayout()
        title_lbl = QLabel('Rinse Your Library')
        title_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 20px; font-weight: 700; background: transparent;')
        subtitle = QLabel('Review potential duplicates before you classify.')
        subtitle.setStyleSheet(f'color: {_MUTED}; font-size: 13px; background: transparent;')
        title_col.addWidget(title_lbl)
        title_col.addWidget(subtitle)
        hdr_row.addLayout(title_col, stretch=1)

        self._skip_btn = QPushButton('Skip for Now')
        self._skip_btn.setFixedHeight(36)
        self._skip_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {_MUTED}; '
            f'border: 1px solid #444444; border-radius: 6px; padding: 0 16px; }}'
            f'QPushButton:hover {{ color: {_CREAM}; border-color: {_CREAM}; }}'
        )
        self._skip_btn.clicked.connect(self.done.emit)
        hdr_row.addWidget(self._skip_btn)

        self._consolidate_btn = QPushButton('Consolidate Checked')
        self._consolidate_btn.setFixedHeight(36)
        self._consolidate_btn.setStyleSheet(
            f'QPushButton {{ background: {_TEAL}; color: {_CREAM}; border: none; '
            f'border-radius: 6px; padding: 0 20px; font-weight: 600; }}'
            f'QPushButton:hover {{ background: #38706a; }}'
            f'QPushButton:pressed {{ background: #2d6358; }}'
        )
        self._consolidate_btn.clicked.connect(self._on_consolidate)
        hdr_row.addWidget(self._consolidate_btn)

        outer.addWidget(hdr)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f'QScrollArea {{ background: {_BG}; border: none; }}')

        self._results_content = QWidget()
        self._results_content.setStyleSheet(f'background: {_BG};')
        self._results_layout = QVBoxLayout(self._results_content)
        self._results_layout.setContentsMargins(32, 24, 32, 32)
        self._results_layout.setSpacing(24)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_content)
        outer.addWidget(scroll, stretch=1)

        return w

    def _populate_results(self) -> None:
        # Clear old content (keep the trailing stretch)
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Skipped-track disclosure — shown before any results, every time
        skipped = self._summary.skipped_count if self._summary else 0
        if skipped > 0:
            n = skipped
            notice = QLabel(
                f'{n:,} untagged track{"s" if n != 1 else ""} '
                f'{"were" if n != 1 else "was"} skipped and may still contain duplicates.'
            )
            notice.setWordWrap(True)
            notice.setStyleSheet(
                f'color: {_MUTED}; font-size: 13px; background: transparent; border: none;'
            )
            self._results_layout.insertWidget(0, notice)

        tier1 = [g for g in self._groups if g.tier == 'true_duplicate']
        tier2 = [g for g in self._groups if g.tier == 'variant']

        if tier1:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1,
                self._build_section_header(
                    f'True Duplicates — {len(tier1)} group{"s" if len(tier1) != 1 else ""}',
                    'Same file found in multiple locations. '
                    'We\'ve selected the best copy — confirm or choose a different one.',
                    _RED,
                )
            )
            for i, g in enumerate(self._groups):
                if g.tier == 'true_duplicate':
                    self._results_layout.insertWidget(
                        self._results_layout.count() - 1,
                        self._build_group_card(i, g),
                    )

        if tier2:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1,
                self._build_section_header(
                    f'Possible Variants — {len(tier2)} group{"s" if len(tier2) != 1 else ""}',
                    'Looks like different versions of the same song. '
                    'Confirm if any are actual duplicates you want to consolidate.',
                    _ORANGE,
                )
            )
            for i, g in enumerate(self._groups):
                if g.tier == 'variant':
                    self._results_layout.insertWidget(
                        self._results_layout.count() - 1,
                        self._build_group_card(i, g),
                    )

        if not tier1 and not tier2:
            self._consolidate_btn.setEnabled(False)
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
                self._results_layout.insertWidget(
                    self._results_layout.count() - 1, headline
                )
                self._results_layout.insertWidget(
                    self._results_layout.count() - 1, body
                )
            else:
                empty = QLabel('No duplicates found. Your library is clean.')
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setStyleSheet(
                    f'color: {_MUTED}; font-size: 14px; background: transparent; border: none;'
                )
                self._results_layout.insertWidget(0, empty)

    def _build_section_header(self, title: str, subtitle: str, accent: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet('background: transparent; border: none;')
        outer = QVBoxLayout(f)
        outer.setContentsMargins(0, 36, 0, 14)
        outer.setSpacing(0)

        # Accent bar spans the full height of title + subtitle
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
        outer.addLayout(row)

        return f

    def _build_group_card(self, idx: int, group: DuplicateGroup) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border: 1px solid #444444; border-radius: 8px; }}'
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        song_lbl = QLabel(f'{group.canonical_artist}  —  {group.canonical_title}')
        song_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 14px; font-weight: 600; background: transparent; border: none;')
        title_row.addWidget(song_lbl, stretch=1)

        savings_lbl = QLabel(f'saves {fmt_bytes(group.space_savings)}')
        savings_lbl.setStyleSheet(f'color: {_TEAL}; font-size: 12px; background: transparent; border: none;')
        title_row.addWidget(savings_lbl)
        layout.addLayout(title_row)

        # Radio button group — one selection per group, no page rebuild
        btn_group = QButtonGroup(card)
        btn_group.setExclusive(True)

        winner = self._winner_overrides.get(idx, group.recommended_winner)
        copy_rows: list[tuple] = []

        for copy in group.copies:
            is_winner = (copy == winner)
            radio, row = self._build_copy_row(copy, is_winner, winner)
            btn_group.addButton(radio)
            if is_winner:
                radio.setChecked(True)
            copy_rows.append((radio, row, copy))
            layout.addWidget(row)

        def _update_selection(_btn: QCheckBox, checked: bool) -> None:
            if not checked:
                return
            for r, row_frame, c in copy_rows:
                is_w = r.isChecked()
                bg     = _ROW  if is_w else _ROW2
                border = f'2px solid {_TEAL}' if is_w else f'1px solid {_SEP}'
                row_frame.setStyleSheet(
                    f'QFrame {{ background: {bg}; border: {border}; border-radius: 6px; }}'
                )
                if is_w:
                    self._winner_overrides[idx] = c

        btn_group.buttonToggled.connect(_update_selection)

        # Metadata note — only shown when copies genuinely disagree on a tag value
        if group.metadata_conflicts:
            fields = ', '.join(c.field for c in group.metadata_conflicts)
            warn = QLabel(
                f'These copies have different {fields} tag{"s" if len(group.metadata_conflicts) > 1 else ""}. '
                f'The checked copy\'s {"values" if len(group.metadata_conflicts) > 1 else "value"} win{"" if len(group.metadata_conflicts) > 1 else "s"}.'
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
            layout.addWidget(warn)

        return card

    def _build_copy_row(self, copy: DuplicateCopy, is_winner: bool, winner: Optional[DuplicateCopy] = None) -> tuple:
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

        # Checkbox selector (exclusive per group via QButtonGroup)
        radio = QCheckBox()
        radio.setStyleSheet(
            f'QCheckBox {{ background: transparent; border: none; spacing: 0; }}'
            f'QCheckBox::indicator {{ width: 16px; height: 16px; }}'
            f'QCheckBox::indicator:unchecked {{ image: url("{_ICON_UNCHECKED}"); }}'
            f'QCheckBox::indicator:checked   {{ image: url("{_ICON_CHECKED}");   }}'
        )
        h.addWidget(radio, alignment=Qt.AlignmentFlag.AlignVCenter)

        # File info
        info_col = QVBoxLayout()
        info_col.setSpacing(3)

        # Filename first — the primary differentiator between copies
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
        fmt_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;')
        info_col.addWidget(fmt_lbl)

        path_lbl = QLabel(copy.folder_context)
        path_lbl.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
        info_col.addWidget(path_lbl)

        # Supporting data — orange on winner (earns attention), muted on non-winner (context only)
        detail_color = _ORANGE if is_winner else _MUTED

        def _detail(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f'color: {detail_color}; font-size: 12px; background: transparent; border: none;')
            return lbl

        if copy.crate_count > 0:
            info_col.addWidget(_detail(
                f'In {copy.crate_count} crate{"s" if copy.crate_count != 1 else ""}'
            ))
        if copy.play_count and copy.play_count > 0:
            info_col.addWidget(_detail(f'{copy.play_count} plays in Serato'))
        if copy.comment:
            info_col.addWidget(_detail(f'Comment: "{copy.comment[:60]}"'))
        if copy.genre_tag:
            info_col.addWidget(_detail(f'Genre: {copy.genre_tag}'))
        if copy.bpm:
            info_col.addWidget(_detail(f'BPM: {int(copy.bpm)}'))

        if is_winner:
            rec_lbl = QLabel('✳  We recommend keeping this one')
            rec_lbl.setStyleSheet(
                f'color: {_TEAL}; font-size: 11px; font-weight: 600; background: transparent; border: none;'
            )
            info_col.addWidget(rec_lbl)

        elif winner is not None:
            # Orange only for data this copy has that the winner doesn't — worth the user's attention
            if copy.comment and not winner.comment:
                warn = QLabel(f'Choosing this preserves Comment: "{copy.comment[:60]}"')
                warn.setWordWrap(True)
                warn.setStyleSheet(f'color: {_ORANGE}; font-size: 11px; background: transparent; border: none;')
                info_col.addWidget(warn)
            if copy.play_count and copy.play_count > (winner.play_count or 0):
                warn = QLabel(f'Choosing this preserves {copy.play_count} plays in Serato')
                warn.setStyleSheet(f'color: {_ORANGE}; font-size: 11px; background: transparent; border: none;')
                info_col.addWidget(warn)
            if copy.crate_count > winner.crate_count:
                warn = QLabel(
                    f'Choosing this preserves {copy.crate_count} crate{"s" if copy.crate_count != 1 else ""}'
                )
                warn.setStyleSheet(f'color: {_ORANGE}; font-size: 11px; background: transparent; border: none;')
                info_col.addWidget(warn)

        h.addLayout(info_col, stretch=1)

        # Clicking anywhere on the row toggles the checkbox
        _r = radio
        row.mousePressEvent = lambda event: _r.toggle()

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

        # Outer: vertical centering via stretches, horizontal centering via HBox
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()

        # Fixed-width inner container — forces text to fill a real width instead of collapsing
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
            f'QPushButton {{ background: {_TEAL}; color: {_CREAM}; border: none; '
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
        approved = []
        for i, group in enumerate(self._groups):
            if i in self._dismissed:
                continue
            winner = self._winner_overrides.get(i, group.recommended_winner)
            if winner:
                approved.append((group, winner))

        if not approved:
            self.done.emit()
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
