"""
Straggler gather — pre-flight confirm dialog + background worker.

The Dashboard raises a banner when crates reference real files outside the
library folder (see core/straggler_detector.py). Clicking it opens
_GatherStragglersDialog: a per-source-folder confirm. On accept the Dashboard
runs _GatherWorker, which MOVES each selected file (copy -> sha256 verify ->
delete original) into <library>/Media/, re-points every crate reference via
PathRewriter, and writes a rollback log in the same format Organize uses.
"""
from __future__ import annotations

import logging
import shutil
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from cratesort.src.core.file_organizer import RollbackLog, _sha256
from cratesort.src.core.straggler_detector import (
    Straggler, add_dismissed_stragglers, library_drive_root,
)
from cratesort.src.gui.overlays import _CrateSortDialog, _create_dialog_layout
from cratesort.src.serato.path_rewriter import PathChange, PathRewriter

logger = logging.getLogger(__name__)

_ASSETS = Path(__file__).parent.parent.parent / 'assets'
_ICON_CHECKED   = str(_ASSETS / 'icons' / 'checkbox-checked.svg')
_ICON_UNCHECKED = str(_ASSETS / 'icons' / 'checkbox-unchecked.svg')

_CREAM  = '#f1e3c8'
_MUTED  = '#a89b85'
_ORANGE = '#D17D34'
_ORANGE_DK = '#aa6326'
_TEAL   = '#428175'
_SEP    = '#383838'


def _style_checkbox(cb: QCheckBox, color: str = _CREAM, font_px: int = 12) -> None:
    """Standard CrateSort checkbox — SVG check/uncheck icons, never the bare
    theme-default orange indicator fill (see settings_view / dashboard)."""
    cb.setStyleSheet(
        f'QCheckBox {{ color: {color}; font-size: {font_px}px; background: transparent; spacing: 8px; }}'
        f'QCheckBox::indicator {{ width: 16px; height: 16px; }}'
        f'QCheckBox::indicator:unchecked {{ image: url("{_ICON_UNCHECKED}"); }}'
        f'QCheckBox::indicator:checked   {{ image: url("{_ICON_CHECKED}");   }}'
    )


def _fmt_bytes(n: int) -> str:
    step = 1024.0
    val = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if val < step:
            return f'{val:.0f} {unit}' if unit in ('B', 'KB') else f'{val:.1f} {unit}'
        val /= step
    return f'{val:.1f} PB'


def _collapse_home(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return '~' + s[len(home):] if s.startswith(home) else s


# ---------------------------------------------------------------------------
# Confirm dialog
# ---------------------------------------------------------------------------

class _GatherStragglersDialog(_CrateSortDialog):
    """Per-source-folder confirm. After exec() returns Accepted, read
    `selected_stragglers`. Dismiss-list writes happen inside this dialog."""

    def __init__(self, stragglers: list[Straggler], library_root: Path, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(560)
        self._all = list(stragglers)
        self._library_root = library_root
        self.selected_stragglers: list[Straggler] = list(stragglers)

        # Group by source folder, preserving the detector's sort order.
        self._by_folder: "OrderedDict[Path, list[Straggler]]" = OrderedDict()
        for s in self._all:
            self._by_folder.setdefault(s.source_path.parent, []).append(s)

        self._folder_checks: dict[Path, QCheckBox] = {}

        layout = _create_dialog_layout(self)

        headline = QLabel('Move Tracks Into Library')
        headline.setStyleSheet(
            f'color: {_CREAM}; font-size: 22px; font-weight: 600; '
            f'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        body = QLabel()
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setText(
            '<div style="line-height: 145%;">'
            'Select the tracks that you’d like to move into your library. Note that '
            'these files will be moved (not copied) into a folder named Media — inside '
            'the directory you selected on startup. If you do not want these files moved, '
            'CrateSort will not be able to manage them.'
            '</div>'
        )
        body.setStyleSheet(f'color: #d5c7ad; font-size: 13px; background: transparent; border: none;')
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { background: transparent; border: none; }')

        rows = QWidget()
        rows.setStyleSheet('background: transparent;')
        rows_v = QVBoxLayout(rows)
        rows_v.setContentsMargins(0, 0, 0, 0)
        rows_v.setSpacing(4)

        for folder, items in self._by_folder.items():
            rows_v.addWidget(self._build_folder_row(folder, items))
        scroll.setWidget(rows)
        layout.addWidget(scroll)
        # A QScrollArea defaults to an Expanding vertical policy — left alone it
        # stretches to eat the dialog's surplus height, leaving a big gap below
        # one or two rows. Pin it to its own content height, hard-capped so a
        # long list scrolls instead of growing the dialog without bound.
        self._rows_host   = rows
        self._rows_scroll = scroll
        self._fit_rows_scroll()

        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;'
        )
        self._summary_lbl.setWordWrap(True)
        layout.addWidget(self._summary_lbl)
        layout.addSpacing(4)

        # "Don't ask" toggle on its own line...
        self._dismiss_cb = QCheckBox("Don't ask me to move these files again")
        _style_checkbox(self._dismiss_cb, color=_MUTED, font_px=12)
        dismiss_row = QHBoxLayout()
        dismiss_row.addWidget(self._dismiss_cb)
        dismiss_row.addStretch()
        layout.addLayout(dismiss_row)
        layout.addSpacing(4)

        # ...buttons on the line below it.
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self._not_now_btn = QPushButton('Not Now')
        self._not_now_btn.setFixedHeight(36)
        self._not_now_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
        )
        self._not_now_btn.clicked.connect(self._on_not_now)
        self._not_now_btn.setAutoDefault(False)
        btn_row.addWidget(self._not_now_btn)

        self._go_btn = QPushButton()
        self._go_btn.setFixedHeight(36)
        self._go_btn.setStyleSheet(
            f'QPushButton {{ background-color: {_ORANGE_DK}; color: #ffffff; border: none; '
            f'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }}'
            f'QPushButton:hover {{ background-color: #925521; }}'
            f'QPushButton:pressed {{ background-color: #7e491c; }}'
            f'QPushButton:disabled {{ background-color: #4a3a2a; color: #8a7a68; }}'
        )
        self._go_btn.clicked.connect(self._on_go)
        self._go_btn.setDefault(True)
        btn_row.addWidget(self._go_btn)

        layout.addLayout(btn_row)

        self._recompute()

    # ── list sizing ──────────────────────────────────────────────────────

    _ROWS_MAX_H = 300  # ~7 folder rows; scrolls past that

    def _fit_rows_scroll(self) -> None:
        want = self._rows_host.sizeHint().height()
        if want <= 0:  # sizeHint not resolved yet — fall back to a row-count estimate
            want = max(1, self._rows_host.layout().count()) * 38
        self._rows_scroll.setFixedHeight(min(self._ROWS_MAX_H, want + 2))

    def showEvent(self, event) -> None:
        # Recompute *before* the base class runs adjustSize()/centres/bounces,
        # in case the construction-time sizeHint was stale — otherwise the
        # dialog would be sized to the old list height. Single-line rows make
        # the first calc reliable; this is the guard for a future multi-line row.
        self._fit_rows_scroll()
        super().showEvent(event)

    # ── selection ─────────────────────────────────────────────────────────

    def _build_folder_row(self, folder: Path, items: list[Straggler]) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet('QFrame { background: #2a2a2a; border: none; border-radius: 4px; }')
        h = QHBoxLayout(frame)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(10)

        cb = QCheckBox()
        cb.setChecked(True)
        cb.toggled.connect(self._recompute)
        _style_checkbox(cb)
        self._folder_checks[folder] = cb
        h.addWidget(cb)

        path_lbl = QLabel(_collapse_home(folder))
        path_lbl.setStyleSheet(f'color: {_CREAM}; font-size: 13px; background: transparent; border: none;')
        path_lbl.setWordWrap(False)
        h.addWidget(path_lbl, stretch=1)

        total = sum(s.size for s in items)
        meta = QLabel(f'{len(items):,} file{"s" if len(items) != 1 else ""}  ·  {_fmt_bytes(total)}')
        meta.setStyleSheet(f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;')
        meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(meta)
        return frame

    def _recompute(self, *_) -> None:
        selected: list[Straggler] = []
        selected_folders: list[Path] = []
        for folder, items in self._by_folder.items():
            if self._folder_checks[folder].isChecked():
                selected.extend(items)
                selected_folders.append(folder)
        self.selected_stragglers = selected

        count = len(selected)
        if count:
            size = _fmt_bytes(sum(s.size for s in selected))
            src  = ', '.join(_collapse_home(f) for f in selected_folders)
            self._summary_lbl.setText(
                f'{count:,} file{"s" if count != 1 else ""} • {size} will be moved from: {src}'
            )
        else:
            self._summary_lbl.setText('Select tracks to move them into your library.')

        self._go_btn.setText(
            f'Move {count:,} File{"s" if count != 1 else ""} In' if count else 'Move Files In'
        )
        self._go_btn.setEnabled(count > 0)

    # ── button handlers ──────────────────────────────────────────────────

    def _dismiss(self, paths: set[str]) -> None:
        if not paths:
            return
        try:
            add_dismissed_stragglers(self._library_root, paths)
        except Exception as exc:
            logger.warning('[Straggler] Failed to write dismiss list: %s', exc)

    def _on_go(self) -> None:
        if self._dismiss_cb.isChecked():
            selected_keys = {str(s.source_path) for s in self.selected_stragglers}
            self._dismiss({str(s.source_path) for s in self._all
                           if str(s.source_path) not in selected_keys})
        self.accept()

    def _on_not_now(self) -> None:
        if self._dismiss_cb.isChecked():
            self._dismiss({str(s.source_path) for s in self._all})
        self.reject()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_not_now()
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Progress dialog
# ---------------------------------------------------------------------------

class _GatherProgressDialog(_CrateSortDialog):
    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(480)
        layout = _create_dialog_layout(self)

        self._title = QLabel('Moving Tracks In…')
        self._title.setStyleSheet(
            f'color: {_CREAM}; font-size: 22px; font-weight: 600; '
            f'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)
        layout.addSpacing(8)

        self._bar = QProgressBar()
        self._bar.setRange(0, max(1, total))
        self._bar.setValue(0)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            'QProgressBar { background: #383838; border: none; border-radius: 4px; }'
            f'QProgressBar::chunk {{ background: {_TEAL}; border-radius: 4px; }}'
        )
        layout.addWidget(self._bar)

        self._detail = QLabel(f'0 of {total:,}')
        self._detail.setStyleSheet(f'color: {_MUTED}; font-size: 12px; background: transparent; border: none;')
        self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        self._close_btn = QPushButton('Close')
        self._close_btn.setFixedHeight(36)
        self._close_btn.setEnabled(False)
        self._close_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; }'
            'QPushButton:disabled { color: #5a5a5a; border-color: #333333; }'
        )
        self._close_btn.clicked.connect(self.accept)
        layout.addWidget(self._close_btn)

    def update_progress(self, done: int, total: int, name: str) -> None:
        self._bar.setValue(done)
        self._detail.setText(f'{done:,} of {total:,}  ·  {name}')

    def show_result(self, moved: int, crates_modified: int, failures: list[str]) -> None:
        self._bar.setValue(self._bar.maximum())
        self._title.setText('Done.' if not failures else 'Done — with issues')
        lines = [
            f'{moved:,} track{"s" if moved != 1 else ""} moved in · '
            f'{crates_modified:,} crate{"s" if crates_modified != 1 else ""} updated'
        ]
        if failures:
            lines.append('')
            lines.append('Could not move:')
            lines.extend(f'• {f}' for f in failures[:8])
            if len(failures) > 8:
                lines.append(f'…and {len(failures) - 8} more')
        self._detail.setText('\n'.join(lines))
        self._close_btn.setEnabled(True)
        self._close_btn.setDefault(True)

    def keyPressEvent(self, event) -> None:
        # Don't let Escape/Return dismiss while the move is still running.
        if not self._close_btn.isEnabled() and event.key() in (
            Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter,
        ):
            return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class _GatherWorker(QThread):
    progress = pyqtSignal(int, int, str)     # done, total, current filename
    finished = pyqtSignal(object)            # {'moved', 'failed', 'crates_modified', 'log_path'}
    errored  = pyqtSignal(str)

    def __init__(
        self,
        stragglers: list[Straggler],
        library_root: Path,
        serato_dir: Path,
        current_crates: dict,
        parent=None,
    ):
        super().__init__(parent)
        self._stragglers = list(stragglers)
        self._library_root = library_root
        self._serato_dir = serato_dir
        self._drive_root = library_drive_root(current_crates, library_root)

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            import traceback
            self.errored.emit(f'{exc}\n{traceback.format_exc()}')

    def _run(self) -> None:
        media = self._library_root / 'Media'
        media.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = self._serato_dir.parent / '_CrateSort' / f'reorganization_log_{ts}.json'
        rlog = RollbackLog(log_path)
        rlog.set_context(self._library_root, self._serato_dir)
        rlog._data['kind'] = 'straggler_gather'
        rlog.save()

        drive_root = Path(self._drive_root)
        total = len(self._stragglers)
        moved = 0
        failures: list[str] = []
        path_changes: list[PathChange] = []
        used: set[Path] = set()

        for i, s in enumerate(self._stragglers):
            self.progress.emit(i, total, s.source_path.name)
            try:
                dest = self._unique_dest(media, s.source_path.name, used)
                shutil.copy2(s.source_path, dest)
                if _sha256(dest) != _sha256(s.source_path):
                    dest.unlink(missing_ok=True)
                    raise RuntimeError('copy verification failed (hash mismatch)')
                s.source_path.unlink()
                used.add(dest)
                moved += 1

                rlog._data['moves'].append({
                    'source': str(s.source_path),
                    'destination': str(dest),
                    'sha256': '',
                    'executed_at': datetime.now().isoformat(),
                    'status': 'completed',
                })
                rlog.save()

                try:
                    new_ref = dest.relative_to(drive_root).as_posix()
                except ValueError:
                    new_ref = str(dest).lstrip('/')
                for ref in s.crate_refs:
                    path_changes.append(PathChange(old_path=ref, new_path=new_ref))
            except Exception as exc:
                logger.warning('[Straggler] Failed to move %s: %s', s.source_path, exc)
                failures.append(f'{s.source_path.name} — {exc}')

        self.progress.emit(total, total, '')

        crates_modified = 0
        if path_changes:
            try:
                result = PathRewriter(self._serato_dir).rewrite(path_changes, dry_run=False)
                crates_modified = result.crates_modified
                for b in result.backup_paths:
                    rlog.log_crate_backup(b)
            except Exception as exc:
                logger.error('[Straggler] Crate rewrite failed: %s', exc)
                failures.append(f'crate references not updated — {exc}')
        rlog.save()

        self.finished.emit({
            'moved': moved,
            'failed': failures,
            'crates_modified': crates_modified,
            'log_path': log_path,
        })

    @staticmethod
    def _unique_dest(folder: Path, name: str, used: set[Path]) -> Path:
        cand = folder / name
        if cand not in used and not cand.exists():
            return cand
        stem, ext = Path(name).stem, Path(name).suffix
        n = 2
        while True:
            cand = folder / f'{stem} ({n}){ext}'
            if cand not in used and not cand.exists():
                return cand
            n += 1
