from __future__ import annotations

import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from cratesort.src.core.classifier import ClassificationResult, Confidence
from cratesort.src.core.file_organizer import (
    ExecutionResult, FileOrganizer, ReorganizationPlan,
)
from cratesort.src.gui.overlays import _CrateSortDialog, _ov_alert, _ov_confirm, _create_dialog_layout

# ── Color constants (match CLAUDE-CS.md design language) ─────────────────────

_BG       = '#1a1a1a'
_PANEL    = '#2F2F2F'
_CREAM    = '#f1e3c8'
_MUTED    = '#a89b85'
_ORANGE   = '#D17D34'
_TEAL     = '#428175'
_SEP      = '#383838'
_ROW_BASE = '#242424'
_ROW_ALT  = '#2a2a2a'
_DANGER   = '#C75B5B'

# Stack indices
_STATE_GATE     = 0
_STATE_PLANNING = 1
_STATE_PREVIEW  = 2
_STATE_EXEC     = 3
_STATE_DONE     = 4


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

class _PlanWorker(QThread):
    finished = pyqtSignal(object)   # ReorganizationPlan
    errored  = pyqtSignal(str)

    def __init__(
        self,
        library_root: Path,
        serato_dir: Path,
        inventory: list,
        session_path: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._library_root = library_root
        self._serato_dir   = serato_dir
        self._inventory    = inventory
        self._session_path = session_path

    def run(self) -> None:
        try:
            from cratesort.src.gui.classifier_view import ClassificationSession
            from cratesort.src.core.filename_cleaner import FilenameCleaner
            from cratesort.src.utils.the_handler import TheHandler
            from cratesort.src.core.metadata_fixer import MetadataFixer
            from cratesort.src.core.artist_consolidator import ArtistConsolidator
            from cratesort.src.serato.crate_reader import CrateReader

            # 1. Load classification session
            session = ClassificationSession.load(self._session_path)

            # 1a. Apply manual overrides and artist reassignments to the in-memory inventory
            edits_file = self._library_root / '_CrateSort' / 'library_edits.json'
            edits = {}
            if edits_file.exists():
                try:
                    with open(edits_file, encoding='utf-8') as f:
                        edits = json.load(f)
                except Exception:
                    pass

            # Sync session entries to match reassignments and genre overrides
            session.apply_library_edits()

            # Map track paths in classifier session to their entry's artist
            session_artists = {}
            for entry in session.entries:
                for track in entry.tracks:
                    session_artists[Path(track.path)] = entry.artist

            # Per-run shallow copies so the shared inventory is never mutated.
            # _original_* attributes and field overrides are local to this planning run,
            # preventing re-plan from capturing already-overridden values as the baseline.
            inventory = [copy.copy(r) for r in self._inventory]

            # Apply all edits and reassignments to inventory
            for record in inventory:
                record._original_artist  = record.artist
                record._original_title   = record.title
                record._original_album   = record.album
                record._original_bpm     = record.bpm
                record._original_year    = record.year
                record._original_comment = record.comment

                track_edit = edits.get(str(record.path), {})
                if 'reassign_artist' in track_edit:
                    record.artist = track_edit['reassign_artist']
                elif record.path in session_artists:
                    record.artist = session_artists[record.path]

                if 'title' in track_edit:
                    record.title = track_edit['title']
                if 'album' in track_edit:
                    record.album = track_edit['album']
                if 'bpm' in track_edit:
                    try:
                        record.bpm = float(track_edit['bpm'])
                    except ValueError:
                        pass
                if 'year' in track_edit:
                    record.year = track_edit['year']
                if 'comment' in track_edit:
                    record.comment = track_edit['comment']

            # 2. Build classifications dict from ALL entries with a valid genre.
            # 'Unclassified' is now a valid folder destination — tracks without a
            # real genre go to Media/Unclassified/Artist/. Only truly empty genres
            # (blank string, 'Untagged') are skipped here.
            _SKIP_GENRES = {'Untagged', ''}
            classifications: dict = {}
            for entry in session.entries:
                genre = entry.final_genre or entry.proposed_genre
                if not genre or genre in _SKIP_GENRES:
                    continue
                for track in entry.tracks:
                    classifications[Path(track.path)] = ClassificationResult(
                        genre=genre,
                        confidence=Confidence.HIGH,
                        reason=f'Classified ({entry.state}): {genre}',
                    )

            # 3. Reconstruct (TrackRecord, ClassificationResult) pairs
            results = []
            for record in inventory:
                cls = classifications.get(record.path)
                if cls:
                    results.append((record, cls))

            # 4. Generate all proposals
            fn_list = FilenameCleaner().clean_all(inventory)
            filename_proposals = {
                record.path: prop
                for record, prop in zip(inventory, fn_list)
            }

            the_list = TheHandler().analyze_all(
                {r.artist for r in inventory if r.artist}
            )
            the_proposals = {p.original_name: p for p in the_list}

            meta_list = MetadataFixer().analyze_all(results)
            meta_proposals = {p.file_path: p for p in meta_list}

            consolidation_list = ArtistConsolidator().analyze(inventory)
            consolidation: dict = {}
            for cand in consolidation_list:
                for name in [cand.primary_name] + cand.variant_names:
                    consolidation[name] = cand

            crate_lib = CrateReader(self._serato_dir).read()

            # 5. Build the plan
            plan = FileOrganizer(
                self._library_root, self._serato_dir
            ).build_plan(
                inventory=inventory,
                classifications=classifications,
                filename_proposals=filename_proposals,
                the_proposals=the_proposals,
                meta_proposals=meta_proposals,
                consolidation=consolidation,
                crate_library=crate_lib,
            )

            self.finished.emit(plan)

        except Exception as exc:
            import traceback
            self.errored.emit(f'{exc}\n{traceback.format_exc()}')


class _ExecutionWorker(QThread):
    progress = pyqtSignal(int, int, str)   # (current, total, filename)
    finished = pyqtSignal(object)          # ExecutionResult
    errored  = pyqtSignal(str)

    def __init__(self, plan: ReorganizationPlan, parent=None):
        super().__init__(parent)
        self._plan = plan

    def run(self) -> None:
        try:
            def _cb(current: int, total: int, filename: str) -> None:
                self.progress.emit(current, total, filename)

            result = FileOrganizer(
                self._plan.library_root, self._plan.serato_dir
            ).execute(self._plan, progress_callback=_cb)

            self.finished.emit(result)
        except Exception as exc:
            self.errored.emit(str(exc))


class _RollbackWorker(QThread):
    finished = pyqtSignal(object)   # dict
    errored  = pyqtSignal(str)

    def __init__(
        self,
        log_path: Path,
        library_root: Path,
        serato_dir: Optional[Path],
        parent=None,
    ):
        super().__init__(parent)
        self._log_path     = log_path
        self._library_root = library_root
        self._serato_dir   = serato_dir

    def run(self) -> None:
        try:
            result = FileOrganizer(
                self._library_root, self._serato_dir
            ).rollback(self._log_path)
            self.finished.emit(result)
        except Exception as exc:
            self.errored.emit(str(exc))


# ---------------------------------------------------------------------------
# _OrganizeStatCard — Animated stat card for the Organize view
# ---------------------------------------------------------------------------

class _OrganizeStatCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon: str, suffix: str, label: str, is_warning_type: bool = False, parent=None):
        super().__init__(parent)
        self._target   = 0
        self._suffix   = suffix
        self._label_text = label
        self._is_warning_type = is_warning_type
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

    def update_target(self, target: int) -> None:
        self._target = target
        if self._is_warning_type and target > 0:
            val_color = '#D17D34'  # _ORANGE
        else:
            val_color = '#f1e3c8'  # _CREAM
        self._num_label.setStyleSheet(
            f'font-size: 26px; font-weight: 500; color: {val_color}; '
            f'background: transparent; border: none;'
        )

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
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_animation(1400)
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# _WarningsDetailDialog — expandable details for conflicts / path warnings / skipped
# ---------------------------------------------------------------------------

class _WarningsDetailDialog(_CrateSortDialog):
    def __init__(self, plan: ReorganizationPlan, parent=None):
        super().__init__(parent)
        self._elastic = False
        self.setMinimumWidth(620)
        self.setMinimumHeight(480)

        # Use standard Red accent layout (warnings/conflicts)
        layout = _create_dialog_layout(self, '#C75B5B')

        title_lbl = QLabel('Plan Warnings & Conflicts')
        title_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(title_lbl)

        lines: list[str] = []

        if plan.conflicts:
            lines.append(f'CONFLICTS  ({len(plan.conflicts)})')
            lines.append('─' * 60)
            for c in plan.conflicts:
                lines.append(f'  Destination: {c.destination_path.name}')
                for s in c.sources:
                    lines.append(f'    From: {s}')
            lines.append('')

        path_warns = [op for op in plan.operations if getattr(op, 'path_too_long', False)]
        if path_warns:
            lines.append(f'PATH LENGTH WARNINGS  ({len(path_warns)})')
            lines.append('─' * 60)
            for op in path_warns:
                lines.append(f'  {op.destination_path}')
            lines.append('')

        if plan.protected_skipped:
            lines.append(f'PROTECTED / SKIPPED  ({len(plan.protected_skipped)})')
            lines.append('─' * 60)
            for file_path, reason in plan.protected_skipped:
                lines.append(f'  {reason}: {file_path.name}')
            lines.append('')

        if not lines:
            lines.append('No warnings or conflicts.')

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText('\n'.join(lines))
        text_edit.setStyleSheet(
            f'QTextEdit {{ background-color: {_BG}; color: {_CREAM}; '
            f'border: 1px solid #444; border-radius: 4px; '
            f'font-size: 12px; font-family: monospace; padding: 8px; }}'
        )
        layout.addWidget(text_edit, stretch=1)

        close_btn = QPushButton('Close')
        close_btn.setFixedWidth(100)
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(
            f'QPushButton {{ background-color: {_TEAL}; color: #ffffff; '
            f'border: none; border-radius: 6px; '
            f'font-size: 13px; font-weight: 600; }}'
            f'QPushButton:hover {{ background-color: #38706a; }}'
            f'QPushButton:pressed {{ background-color: #2d6358; }}'
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


class _UnclassifiedWarningDialog(_CrateSortDialog):
    def __init__(self, count: int, parent=None):
        super().__init__(parent)
        self._elastic = False
        self.setMinimumWidth(480)

        # Satsuma Orange accent for warning selection/confirm
        layout = _create_dialog_layout(self, '#D17D34')

        title_lbl = QLabel('Unclassified Tracks Detected')
        title_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(title_lbl)
        layout.addSpacing(6)

        body = QLabel()
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setText(
            f'<div style="line-height: 145%;">{count:,} track{"s" if count != 1 else ""} have no genre assignment '
            f'and will be moved to an Unclassified folder in your Media directory. '
            f'You can reclassify them later.</div>'
        )
        body.setWordWrap(True)
        body.setStyleSheet('color: #d5c7ad; font-size: 14px; background: transparent; border: none;')
        layout.addWidget(body)
        layout.addSpacing(12)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        go_back_btn = QPushButton('Go Back to Library')
        go_back_btn.setFixedHeight(36)
        go_back_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
            'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
        )
        go_back_btn.clicked.connect(self.reject)

        proceed_btn = QPushButton('Proceed')
        proceed_btn.setFixedHeight(36)
        proceed_btn.setStyleSheet(
            'QPushButton { background-color: #D17D34; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #be6e2c; }'
            'QPushButton:pressed { background-color: #aa5d21; }'
        )
        proceed_btn.clicked.connect(self.accept)

        btn_row.addWidget(go_back_btn)
        btn_row.addStretch()
        btn_row.addWidget(proceed_btn)
        layout.addLayout(btn_row)


# ---------------------------------------------------------------------------
# OrganizeView — 5-state stacked widget
# ---------------------------------------------------------------------------

class OrganizeView(QWidget):
    """
    Organize tab (content index 3).

    States
    ------
    0  Gate        — classifier not yet run; shows instructional message
    1  Planning    — _PlanWorker running in background
    2  Preview     — plan ready; user reviews stat cards + operations table
    3  Executing   — _ExecutionWorker running
    4  Done        — success; offers rollback
    """

    navigate_to_library    = pyqtSignal()
    navigate_to_dashboard  = pyqtSignal()
    reorg_completed        = pyqtSignal()   # emitted after a reorg or rollback finishes
    status_message         = pyqtSignal(str, str)   # (message, state)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._inventory:          list                       = []
        self._library_path:       Optional[Path]             = None
        self._serato_dir:         Optional[Path]             = None
        self._plan:               Optional[ReorganizationPlan] = None
        self._exec_result:        Optional[ExecutionResult]  = None
        self._rollback_log_path:  Optional[Path]             = None

        self._plan_worker: Optional[_PlanWorker]      = None
        self._exec_worker: Optional[_ExecutionWorker] = None
        self._rb_worker:   Optional[_RollbackWorker]  = None

        # Session plan cache — survives tab switches; cleared on execute/rollback or when
        # library_edits.json is modified after the plan was built.
        self._cached_plan:       Optional[ReorganizationPlan] = None
        self._cached_plan_mtime: Optional[float]              = None

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_gate())       # 0
        self._stack.addWidget(self._build_planning())   # 1
        self._stack.addWidget(self._build_preview())    # 2
        self._stack.addWidget(self._build_exec())       # 3
        self._stack.addWidget(self._build_done())       # 4
        self._stack.setCurrentIndex(_STATE_GATE)

    # ── Public API ────────────────────────────────────────────────────

    def load(self, inventory: list, library_path: Path, serato_dir: Path) -> None:
        """
        Called from MainWindow._on_nav() when the Organize tab is selected.
        Restores the Preview screen if a plan was built this session and the
        library hasn't changed; otherwise shows the gate screen with history.
        """
        # Invalidate the cache if a different library is loaded or edits have changed since plan was built
        if self._cached_plan is not None:
            if self._cached_plan.library_root != library_path:
                self._cached_plan = None
                self._cached_plan_mtime = None
            else:
                edits_file = library_path / '_CrateSort' / 'library_edits.json'
                current_mtime = edits_file.stat().st_mtime if edits_file.exists() else None
                if current_mtime != self._cached_plan_mtime:
                    self._cached_plan = None
                    self._cached_plan_mtime = None

        self._inventory    = inventory
        self._library_path = library_path
        self._serato_dir   = serato_dir

        if self._cached_plan is not None:
            # Plan already built this session — restore Preview directly, no re-plan
            self._plan = self._cached_plan
            self._populate_preview(self._cached_plan)
            self._stack.setCurrentIndex(_STATE_PREVIEW)
            self.status_message.emit(
                'Reorganization plan ready. Review before executing.', 'green'
            )
            return

        self._refresh_gate_screen()
        self._stack.setCurrentIndex(_STATE_GATE)

    # ── State 0: Gate ─────────────────────────────────────────────────

    def _build_gate(self) -> QWidget:
        outer = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(0)
        layout.setContentsMargins(80, 60, 80, 60)

        # ── Ready-to-plan panel (always shown when library is loaded) ─
        ready_msg = QLabel(
            'Click below to analyze your library and prepare a reorganization plan. '
            'You can review every proposed change before anything moves on disk.'
        )
        ready_msg.setWordWrap(True)
        ready_msg.setStyleSheet(f'color: {_CREAM}; font-size: 14px;')
        layout.addWidget(ready_msg)
        layout.addSpacing(16)

        plan_btn = QPushButton('Plan Reorganization…')
        plan_btn.setMinimumHeight(40)
        plan_btn.setFixedWidth(220)
        plan_btn.setStyleSheet(
            f'QPushButton {{ background-color: {_TEAL}; color: #ffffff; '
            f'border: none; border-radius: 5px; padding: 7px 16px; '
            f'font-size: 13px; font-weight: 600; }}'
            f'QPushButton:hover {{ background-color: #38706a; }}'
            f'QPushButton:pressed {{ background-color: #2d6358; }}'
        )
        plan_btn.clicked.connect(self._on_plan_clicked)
        layout.addWidget(plan_btn)

        # ── Separator ─────────────────────────────────────────────────
        layout.addSpacing(20)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f'background-color: {_SEP}; border: none;')
        layout.addWidget(sep)
        layout.addSpacing(20)

        # ── History section ───────────────────────────────────────────
        self._history_header = QLabel('RECENT REORGANIZATIONS')
        self._history_header.setStyleSheet(
            'font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em;'
        )
        layout.addWidget(self._history_header)
        layout.addSpacing(10)

        self._history_container = QWidget()
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(8)
        layout.addWidget(self._history_container)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        return outer

    def _refresh_gate_screen(self) -> None:
        if not self._library_path:
            return

        # Clear previous history rows
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        crate_sort_dir = self._library_path / '_CrateSort'
        log_files = sorted(
            crate_sort_dir.glob('reorganization_log_*.json'),
            reverse=True,
        )[:3]

        if not log_files:
            empty = QLabel('No reorganization history found.')
            empty.setStyleSheet(f'color: {_MUTED}; font-size: 12px;')
            self._history_layout.addWidget(empty)
            return

        for log_path in log_files:
            try:
                with open(log_path, encoding='utf-8') as f:
                    log_data = json.load(f)
            except Exception:
                continue

            executed_at    = log_data.get('executed_at', '')
            moves          = log_data.get('moves', [])
            moved_count    = sum(1 for m in moves if m.get('status') == 'completed')
            rolled_back_at = log_data.get('rolled_back_at')

            try:
                dt  = datetime.fromisoformat(executed_at)
                date_str = dt.strftime(f'%B {dt.day}, %Y at %I:%M %p')
            except Exception:
                date_str = executed_at

            row = QFrame()
            row.setStyleSheet(
                f'QFrame {{ background-color: {_PANEL}; border: 0.5px solid {_SEP}; '
                f'border-radius: 6px; }}'
            )
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(14, 10, 14, 10)
            row_h.setSpacing(12)

            info = QVBoxLayout()
            info.setSpacing(3)

            date_lbl = QLabel(date_str)
            date_lbl.setStyleSheet(
                f'color: {_CREAM}; font-size: 13px; font-weight: 500; '
                f'border: none; background: transparent;'
            )
            info.addWidget(date_lbl)

            count_lbl = QLabel(
                f'{moved_count:,} file{"s" if moved_count != 1 else ""} moved'
            )
            count_lbl.setStyleSheet(
                f'color: {_MUTED}; font-size: 12px; border: none; background: transparent;'
            )
            info.addWidget(count_lbl)
            row_h.addLayout(info, stretch=1)

            if rolled_back_at:
                try:
                    rb_dt   = datetime.fromisoformat(rolled_back_at)
                    rb_date = rb_dt.strftime(f'%B {rb_dt.day}, %Y')
                except Exception:
                    rb_date = rolled_back_at
                rb_lbl = QLabel(f'Rolled back on {rb_date}')
                rb_lbl.setStyleSheet(
                    f'color: {_MUTED}; font-size: 12px; border: none; background: transparent;'
                )
                rb_lbl.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                row_h.addWidget(rb_lbl)
            else:
                rb_btn = QPushButton('Rollback')
                rb_btn.setMinimumHeight(30)
                rb_btn.setStyleSheet(
                    f'QPushButton {{ background-color: {_DANGER}; color: #ffffff; '
                    f'border: none; border-radius: 4px; padding: 4px 12px; '
                    f'font-size: 12px; font-weight: 600; }}'
                    f'QPushButton:hover {{ background-color: #b24c4c; }}'
                    f'QPushButton:pressed {{ background-color: #9c3b3b; }}'
                )
                rb_btn.clicked.connect(
                    lambda _, p=log_path: self._on_rollback_requested(p)
                )
                row_h.addWidget(rb_btn)

            self._history_layout.addWidget(row)

    def _count_unclassified_tracks(self) -> int:
        """Return how many tracks have no valid genre assignment in the session."""
        if not self._library_path:
            return 0
        session_path = self._library_path / '_CrateSort' / 'classification_session.json'
        if not session_path.exists():
            return len(self._inventory)
        try:
            from cratesort.src.gui.classifier_view import ClassificationSession
            session = ClassificationSession.load(session_path)
            session.apply_library_edits()
            count = 0
            _UC = {'Unclassified', 'Untagged', ''}
            for entry in session.entries:
                genre = entry.final_genre or entry.proposed_genre
                if not genre or genre in _UC:
                    count += len(entry.tracks)
            return count
        except Exception:
            return 0

    def _warn_unclassified(self, count: int) -> bool:
        """Show warning dialog for unclassified tracks. Returns True to proceed."""
        dlg = _UnclassifiedWarningDialog(count, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.navigate_to_library.emit()
            return False
        return True

    def _on_plan_clicked(self) -> None:
        if not self._library_path:
            return
        # Warn if unclassified tracks exist — user may proceed or go back to Library
        unclassified = self._count_unclassified_tracks()
        if unclassified > 0:
            if not self._warn_unclassified(unclassified):
                return
        session_path = self._library_path / '_CrateSort' / 'classification_session.json'
        self._stack.setCurrentIndex(_STATE_PLANNING)
        self.status_message.emit('Building reorganization plan…', 'amber')
        self._start_plan_worker(session_path)

    # ── State 1: Building plan ─────────────────────────────────────────

    def _build_planning(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(80, 80, 80, 80)

        lbl = QLabel('Building reorganization plan…')
        lbl.setStyleSheet(f'color: {_CREAM}; font-size: 14px; font-weight: 500;')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bar = QProgressBar()
        bar.setRange(0, 0)  # indeterminate
        bar.setFixedWidth(360)
        bar.setFixedHeight(8)

        sub = QLabel('Analyzing library structure, filenames, and crate assignments…')
        sub.setStyleSheet(f'color: {_MUTED}; font-size: 12px;')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(lbl)
        layout.addWidget(bar, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
        return w

    # ── State 2: Plan Preview ─────────────────────────────────────────

    def _build_preview(self) -> QWidget:
        w = QWidget()
        main_layout = QVBoxLayout(w)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Upper container for content, keeping the 28px left/right margins and 24px top margin
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(28, 24, 28, 16)
        content_layout.setSpacing(16)

        # Stat cards strip — populated later by _populate_stats()
        self._stats_frame = QWidget()
        self._stats_layout = QHBoxLayout(self._stats_frame)
        self._stats_layout.setContentsMargins(0, 0, 0, 0)
        self._stats_layout.setSpacing(10)
        
        # Pre-create standard cards
        self._card_move = _OrganizeStatCard('➔', '', 'Files to Move', parent=self)
        self._card_stay = _OrganizeStatCard('✓', '', 'Files Staying Put', parent=self)
        self._card_folders = _OrganizeStatCard('⧉', '', 'New Folders to Create', parent=self)
        self._card_crates = _OrganizeStatCard('⊞', '', 'Crates to Update', parent=self)
        self._card_warnings = _OrganizeStatCard('▲', '', 'Warnings / Conflicts', is_warning_type=True, parent=self)

        self._stats_layout.addWidget(self._card_move)
        self._stats_layout.addWidget(self._card_stay)
        self._stats_layout.addWidget(self._card_folders)
        self._stats_layout.addWidget(self._card_crates)
        self._stats_layout.addWidget(self._card_warnings)
        
        content_layout.addWidget(self._stats_frame)

        # Operations table
        self._ops_table = QTableWidget(0, 6)
        self._ops_table.setHorizontalHeaderLabels(
            ['Action', 'Proposed Filename', 'Current Filename', 'Proposed Folder', 'Current Folder', 'Crates Affected']
        )

        hdr = self._ops_table.horizontalHeader()
        hdr.setFixedHeight(36)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        vh = self._ops_table.verticalHeader()
        vh.setDefaultSectionSize(36)
        vh.setMinimumSectionSize(36)
        vh.setMaximumSectionSize(36)
        vh.hide()

        self._ops_table.setAlternatingRowColors(True)
        self._ops_table.setShowGrid(True)
        self._ops_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ops_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._ops_table.setSortingEnabled(True)
        self._ops_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {_PANEL};
                alternate-background-color: {_ROW_ALT};
                color: {_CREAM};
                gridline-color: {_SEP};
                border: 1px solid {_SEP};
                border-radius: 4px;
                font-size: 13px;
            }}
            QTableWidget::item {{
                background-color: {_ROW_BASE};
                padding: 0 8px;
            }}
            QTableWidget::item:alternate {{
                background-color: {_ROW_ALT};
            }}
            QTableWidget::item:selected {{
                background-color: {_ORANGE};
                color: #2F2F2F;
            }}
            QHeaderView::section {{
                background-color: {_BG};
                color: {_MUTED};
                border: none;
                border-bottom: 1px solid {_SEP};
                border-right: 1px solid {_SEP};
                padding: 0 8px;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-weight: 600;
            }}
            QHeaderView::section:last {{
                border-right: none;
            }}
        """)
        content_layout.addWidget(self._ops_table, stretch=1)
        main_layout.addWidget(content_container, stretch=1)

        # Footer Frame (exactly like classifier_view.pyresults footer)
        footer_frame = QFrame()
        footer_frame.setStyleSheet(
            f'QFrame {{ background-color: {_PANEL}; border-top: 1px solid {_SEP}; '
            'border-radius: 0; }'
        )
        btn_layout = QHBoxLayout(footer_frame)
        btn_layout.setContentsMargins(20, 10, 20, 10)
        btn_layout.setSpacing(10)

        self._execute_btn = QPushButton('Execute Reorganization')
        self._execute_btn.setProperty('secondary', 'true')
        self._execute_btn.clicked.connect(self._on_execute)

        cancel_btn = QPushButton('Cancel && Go Back to Dashboard')
        cancel_btn.setProperty('flat', 'true')
        cancel_btn.setStyleSheet(f'QPushButton {{ color: {_DANGER}; }} QPushButton:hover {{ color: #b24c4c; }}')
        cancel_btn.clicked.connect(self._on_cancel_preview)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self._execute_btn)

        main_layout.addWidget(footer_frame)

        return w

    def _populate_stats(self, summary) -> None:
        self._card_move.update_target(summary.files_to_move)
        self._card_stay.update_target(summary.files_staying)
        self._card_folders.update_target(summary.new_folders)
        self._card_crates.update_target(summary.crates_to_update)
        total_warnings = summary.conflict_count + summary.path_warnings + summary.protected_skipped
        self._card_warnings.update_target(total_warnings)

        # Trigger animations with visual cascade offsets
        QTimer.singleShot(100, lambda: self._card_move.start_animation(1600))
        QTimer.singleShot(220, lambda: self._card_stay.start_animation(1400))
        QTimer.singleShot(340, lambda: self._card_folders.start_animation(1500))
        QTimer.singleShot(460, lambda: self._card_crates.start_animation(1300))
        QTimer.singleShot(580, lambda: self._card_warnings.start_animation(1400))

    def _populate_ops_table(self, plan: ReorganizationPlan) -> None:
        self._ops_table.setSortingEnabled(False)
        self._ops_table.setRowCount(0)
        self._ops_table.setRowCount(len(plan.operations))
        for row, op in enumerate(plan.operations):
            folder_changed = op.source_path.parent != op.destination_path.parent
            if op.filename_change and folder_changed:
                action_text = 'Move & Rename'
                action_color = '#d98c52'
            elif op.filename_change and not folder_changed:
                action_text = 'Rename'
                action_color = '#c9a87a'
            elif op.metadata_changes and folder_changed:
                action_text = 'Move & Tag'
                action_color = '#9fa4c7'
            elif op.metadata_changes and not folder_changed:
                action_text = 'Tag Update'
                action_color = '#9fa4c7'
            else:
                action_text = 'Move Only'
                action_color = '#e89ebb'
            if getattr(op, 'path_too_long', False):
                action_text += ' ⚠ Path'
                action_color = _ORANGE

            proposed_filename = op.destination_path.name
            try:
                rel_parent = op.destination_path.parent.relative_to(plan.library_root)
                proposed_folder = str(rel_parent) if str(rel_parent) != '.' else ''
            except ValueError:
                proposed_folder = str(op.destination_path.parent)

            try:
                rel_src_parent = op.source_path.parent.relative_to(plan.library_root)
                current_folder = str(rel_src_parent) if str(rel_src_parent) != '.' else ''
            except ValueError:
                current_folder = str(op.source_path.parent)

            crates = (
                ', '.join(Path(c).stem for c in op.crates_affected)
                if op.crates_affected else '—'
            )

            # Column 0: Action
            item_act = QTableWidgetItem(action_text)
            item_act.setForeground(QBrush(QColor(action_color)))
            item_act.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._ops_table.setItem(row, 0, item_act)

            # Column 1: Proposed Filename
            item_prop_fn = QTableWidgetItem(proposed_filename)
            item_prop_fn.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._ops_table.setItem(row, 1, item_prop_fn)

            # Column 2: Current Filename
            item_curr = QTableWidgetItem(op.source_path.name)
            item_curr.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._ops_table.setItem(row, 2, item_curr)

            # Column 3: Proposed Folder
            item_prop_fld = QTableWidgetItem(proposed_folder.replace(':', '/'))
            item_prop_fld.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._ops_table.setItem(row, 3, item_prop_fld)

            # Column 4: Current Folder
            item_curr_fld = QTableWidgetItem(current_folder.replace(':', '/'))
            item_curr_fld.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._ops_table.setItem(row, 4, item_curr_fld)

            # Column 5: Crates Affected
            item_crates = QTableWidgetItem(crates)
            item_crates.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._ops_table.setItem(row, 5, item_crates)
        self._ops_table.setSortingEnabled(True)

    # ── State 3: Execution progress ───────────────────────────────────

    def _build_exec(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(80, 80, 80, 80)

        self._exec_label = QLabel('Executing reorganization…')
        self._exec_label.setStyleSheet(
            f'color: {_CREAM}; font-size: 14px; font-weight: 500;'
        )
        self._exec_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._exec_bar = QProgressBar()
        self._exec_bar.setFixedWidth(480)
        self._exec_bar.setFixedHeight(8)
        self._exec_bar.setValue(0)
        self._exec_bar.setRange(0, 100)

        self._exec_step = QLabel('')
        self._exec_step.setStyleSheet(f'color: {_MUTED}; font-size: 12px;')
        self._exec_step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._exec_step.setWordWrap(True)

        self._cancel_exec_btn = QPushButton('Cancel')
        self._cancel_exec_btn.setProperty('flat', 'true')
        self._cancel_exec_btn.setFixedWidth(100)
        self._cancel_exec_btn.setStyleSheet(f'QPushButton {{ color: {_DANGER}; }} QPushButton:hover {{ color: #b24c4c; }}')
        self._cancel_exec_btn.setEnabled(False)  # disabled during crate writes

        layout.addWidget(self._exec_label)
        layout.addWidget(self._exec_bar, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._exec_step)
        layout.addSpacing(8)
        layout.addWidget(self._cancel_exec_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    # ── State 4: Completion & Rollback ────────────────────────────────

    def _build_done(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(80, 80, 80, 80)

        self._done_label = QLabel('Reorganization complete!')
        self._done_label.setStyleSheet(
            f'color: {_TEAL}; font-size: 20px; font-weight: 600;'
        )
        self._done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._done_detail = QLabel('')
        self._done_detail.setStyleSheet(f'color: {_MUTED}; font-size: 13px;')
        self._done_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_detail.setWordWrap(True)

        layout.addWidget(self._done_label)
        layout.addWidget(self._done_detail)
        layout.addSpacing(20)

        self._done_back_btn = QPushButton('Back to Dashboard')
        self._done_back_btn.setProperty('secondary', 'true')
        self._done_back_btn.setMinimumHeight(40)
        self._done_back_btn.setFixedWidth(220)
        self._done_back_btn.clicked.connect(self._on_back_to_dashboard)
        layout.addWidget(self._done_back_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        self._rollback_btn = QPushButton('Rollback Reorganization')
        self._rollback_btn.setMinimumHeight(40)
        self._rollback_btn.setFixedWidth(220)
        self._rollback_btn.setStyleSheet(
            f'QPushButton {{ background-color: {_DANGER}; color: #ffffff; '
            f'border: none; border-radius: 5px; padding: 7px 16px; '
            f'font-size: 13px; font-weight: 600; min-height: 28px; }}'
            f'QPushButton:hover {{ background-color: #b24c4c; }}'
            f'QPushButton:pressed {{ background-color: #9c3b3b; }}'
            f'QPushButton:disabled {{ background-color: #3a3a3a; color: #a89b85; }}'
        )
        self._rollback_btn.clicked.connect(self._on_rollback_requested)
        layout.addWidget(self._rollback_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return w

    # ── Worker management ─────────────────────────────────────────────

    def _start_plan_worker(self, session_path: Path) -> None:
        if self._plan_worker is not None:
            try:
                self._plan_worker.finished.disconnect()
                self._plan_worker.errored.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._plan_worker = _PlanWorker(
            self._library_path,
            self._serato_dir,
            self._inventory,
            session_path,
        )
        self._plan_worker.finished.connect(self._on_plan_ready)
        self._plan_worker.errored.connect(self._on_plan_error)
        self._plan_worker.start()

    def _on_plan_ready(self, plan: ReorganizationPlan) -> None:
        self._plan        = plan
        self._cached_plan = plan
        edits_file = (self._library_path / '_CrateSort' / 'library_edits.json') if self._library_path else None
        self._cached_plan_mtime = edits_file.stat().st_mtime if edits_file and edits_file.exists() else None
        self._populate_preview(plan)
        self._stack.setCurrentIndex(_STATE_PREVIEW)
        self.status_message.emit(
            'Reorganization plan ready. Review before executing.', 'green'
        )

    def _populate_preview(self, plan: ReorganizationPlan) -> None:
        """Populate Preview screen widgets from a plan. Called by _on_plan_ready and load()."""
        self._populate_stats(plan.summary)
        self._populate_ops_table(plan)
        try:
            self._card_warnings.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._card_warnings.clicked.connect(self._show_warnings_dialog)

    def _show_warnings_dialog(self) -> None:
        if not self._plan:
            return
        dlg = _WarningsDetailDialog(self._plan, self)
        dlg.exec()

    def _on_plan_error(self, message: str) -> None:
        self.status_message.emit('Plan build failed.', 'error')
        _ov_alert(self, 'Plan Error', f'Could not build reorganization plan:\n\n{message[:400]}')
        self._stack.setCurrentIndex(_STATE_GATE)

    # ── Slots ─────────────────────────────────────────────────────────

    def _warn_serato_running(self) -> bool:
        """Show a branded blocking modal if Serato is open. Returns True if user should abort."""
        try:
            from cratesort.src.utils.serato_guard import is_serato_running
            if not is_serato_running():
                return False
        except Exception:
            return False
        _ov_alert(
            self,
            'Serato DJ Pro is Running',
            'Serato DJ Pro is currently open.\n\n'
            'Close Serato before reorganizing your library. '
            'If Serato is open during reorganization, it will overwrite '
            "CrateSort's changes when it closes.",
        )
        return True

    def _on_execute(self) -> None:
        if not self._plan:
            return
        if self._warn_serato_running():
            return
        if sys.platform == 'win32' and self._plan.summary.path_warnings > 0:
            n = self._plan.summary.path_warnings
            if not _ov_confirm(
                self,
                'Path Length Warning',
                f'{n:,} operation(s) have destination paths that may exceed '
                f"Windows' 260-character path limit and could fail.\n\nProceed anyway?",
                confirm_text='Proceed',
            ):
                return
        self._stack.setCurrentIndex(_STATE_EXEC)
        self._exec_bar.setValue(0)
        self._exec_step.setText('')
        self._exec_label.setText('Executing reorganization…')
        self.status_message.emit('Reorganizing library…', 'amber')

        self._exec_worker = _ExecutionWorker(self._plan)
        self._exec_worker.progress.connect(self._on_exec_progress)
        self._exec_worker.finished.connect(self._on_exec_finished)
        self._exec_worker.errored.connect(self._on_exec_error)
        self._exec_worker.start()

    def _on_exec_progress(self, current: int, total: int, filename: str) -> None:
        if total > 0:
            self._exec_bar.setValue(int(100 * current / total))
        self._exec_step.setText(
            f'Copying and verifying ({current} of {total}): {filename}…'
        )

    def _on_exec_finished(self, result: ExecutionResult) -> None:
        self._cached_plan = None; self._cached_plan_mtime = None   # plan consumed — force re-plan on next visit
        self._exec_result = result
        self._rollback_log_path = result.rollback_log_path
        moved   = len(result.completed)
        failed  = len(result.failed)
        skipped = len(result.skipped)

        self._done_label.setText('Reorganization complete!')
        detail = f'{moved:,} file{"s" if moved != 1 else ""} moved successfully.'
        if failed:
            detail += f'  {failed:,} file{"s" if failed != 1 else ""} failed.'
        if skipped:
            detail += (
                f'  {skipped:,} file{"s" if skipped != 1 else ""} could not be moved'
                f' — destination already existed. Check the log for details.'
            )
        if moved > 0:
            summary = result.crate_rewrite_summary
            if summary and summary.get('paths_rewritten', 0) > 0:
                detail += f'  {summary["crates_modified"]:,} crate(s) updated.'
            else:
                detail += '  Crate paths not updated — use Repair Crate Paths in Settings.'
        self._done_detail.setText(detail)
        self._rollback_btn.setVisible(True)
        self._rollback_btn.setEnabled(bool(self._rollback_log_path))
        self._done_back_btn.setEnabled(True)
        self._stack.setCurrentIndex(_STATE_DONE)
        self.status_message.emit(
            f'Reorganization complete. {moved:,} files moved.', 'green'
        )

    def _on_exec_error(self, message: str) -> None:
        self._cached_plan = None; self._cached_plan_mtime = None   # execution failed — state is uncertain, require re-plan
        self.status_message.emit('Execution failed.', 'error')
        _ov_alert(self, 'Execution Error', f'Reorganization failed:\n\n{message[:400]}')
        self._stack.setCurrentIndex(_STATE_PREVIEW)

    def _on_cancel_preview(self) -> None:
        self._plan = None
        self._refresh_gate_screen()
        self._stack.setCurrentIndex(_STATE_GATE)
        self.status_message.emit('', '')
        self.navigate_to_dashboard.emit()

    def _on_back_to_dashboard(self) -> None:
        self._plan        = None
        self._exec_result = None
        self._refresh_gate_screen()
        self._stack.setCurrentIndex(_STATE_GATE)
        self.status_message.emit('', '')
        self.reorg_completed.emit()
        self.navigate_to_dashboard.emit()

    def _on_rollback_requested(self, log_path: Optional[Path] = None) -> None:
        active_log = log_path if isinstance(log_path, Path) else self._rollback_log_path
        if not active_log:
            return
        if self._rb_worker is not None and self._rb_worker.isRunning():
            return
        if self._warn_serato_running():
            return

        if not _ov_confirm(
            self,
            'Confirm Rollback',
            'This will undo the reorganization and restore all files to their '
            'original locations.\n\nAre you sure you want to continue?',
            confirm_text='Rollback',
            confirm_danger=True,
        ):
            return

        self._rollback_log_path = active_log
        self._done_label.setText('Rolling back reorganization…')
        self._done_detail.setText('Restoring files and updating Serato crates…')
        self._rollback_btn.setVisible(False)
        self._done_back_btn.setEnabled(False)
        self._stack.setCurrentIndex(_STATE_DONE)
        self.status_message.emit('Rolling back reorganization…', 'amber')

        self._rb_worker = _RollbackWorker(
            self._rollback_log_path,
            self._library_path,
            self._serato_dir,
        )
        self._rb_worker.finished.connect(self._on_rollback_finished)
        self._rb_worker.errored.connect(self._on_rollback_error)
        self._rb_worker.start()

    def _on_rollback_finished(self, result: dict) -> None:
        self._cached_plan = None; self._cached_plan_mtime = None   # library state changed — plan no longer valid
        restored = result.get('restored', 0)
        failed   = result.get('failed', 0)
        self._done_label.setText('Rollback complete.')
        detail = f'{restored:,} file{"s" if restored != 1 else ""} restored.'
        if failed:
            detail += f'  {failed:,} failed.'
        self._done_detail.setText(detail)
        self._rollback_btn.setEnabled(False)
        self._done_back_btn.setEnabled(True)
        self.status_message.emit(
            f'Rollback complete. {restored:,} files restored.', 'green'
        )

    def _on_rollback_error(self, message: str) -> None:
        self._rollback_btn.setEnabled(True)
        self._done_back_btn.setEnabled(True)
        _ov_alert(self, 'Rollback Error', f'Rollback failed:\n\n{message[:400]}')
        self.status_message.emit('Rollback failed.', 'error')
