from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QEasingCurve, QPropertyAnimation, QSettings, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFileDialog, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QProgressBar, QPushButton,
)

try:
    from PyQt6.QtSvgWidgets import QSvgWidget
    _SVG_AVAILABLE = True
except ImportError:
    _SVG_AVAILABLE = False

from cratesort.src.gui.overlays import _CrateSortDialog, _create_dialog_layout
from cratesort.src.utils.ffmpeg_tools import (
    friendly_ffmpeg_error, get_ffmpeg_path, parse_duration_from_text,
)
from cratesort.src.utils.metadata_copy import copy_audio_tags, copy_video_tags

logger = logging.getLogger(__name__)

_ORG, _APP = 'JWBC', 'CrateSort'
_LAST_DIR_KEY = 'convert/last_browse_dir'

_ASSETS = Path(__file__).parent.parent.parent / 'assets'
_MASCOT_SVG = _ASSETS / 'logo' / 'cs-logo-mascot-only.svg'

_EYEBROW_STYLE = (
    'color: #5a5a5a; font-size: 10px; letter-spacing: 0.1em; '
    'background: transparent; border: none;'
)

_LIST_STYLE = (
    'QListWidget { background: #383838; border: 1px solid #444444; border-radius: 6px; '
    'color: #f1e3c8; font-size: 12px; padding: 4px; }'
    'QListWidget::item { padding: 4px 6px; }'
    'QListWidget::item:selected { background: #428175; border-radius: 4px; }'
)

_MODES = {
    'wav_mp3': {
        'title':     'Convert Audio to MP3',
        'subtitle':  'Audio · MP3 · 320kbps CBR — maximum quality',
        'exts':      ('.wav', '.aiff', '.aif'),
        'filter':    'Audio Files (*.wav *.aiff *.aif)',
        'out_ext':   '.mp3',
        'noun':      'audio',
    },
    'video_mp4': {
        'title':     'Convert Video to MP4',
        'subtitle':  'Video · MP4 · Original resolution · H.264/AAC (high quality)',
        'exts':      ('.mov', '.mkv', '.avi', '.wmv', '.webm', '.flv', '.m4v', '.mpg', '.mpeg'),
        'filter':    'Video Files (*.mov *.mkv *.avi *.wmv *.webm *.flv *.m4v *.mpg *.mpeg)',
        'out_ext':   '.mp4',
        'noun':      'video',
    },
}


class _Cancelled(Exception):
    pass


def _unique_output_path(src: Path, out_ext: str) -> Path:
    """Same folder as src, same stem, new extension — avoid clobbering an existing file."""
    candidate = src.with_suffix(out_ext)
    if not candidate.exists():
        return candidate
    stem = src.stem
    n = 1
    while candidate.exists():
        candidate = src.parent / f'{stem} ({n}){out_ext}'
        n += 1
    return candidate


class _MediaConvertWorker(QThread):
    progress     = pyqtSignal(int, int, str)   # (current_index, total, filename)
    file_progress = pyqtSignal(int)            # 0-100 for the file currently converting
    file_done    = pyqtSignal(str, bool, str, str)  # (filename, success, message, output_path)
    all_done     = pyqtSignal()

    def __init__(self, files: list[Path], mode: str, parent=None):
        super().__init__(parent)
        self._files      = files
        self._mode       = mode
        self._cancelled  = False
        self._proc: Optional[subprocess.Popen] = None

    def cancel(self) -> None:
        self._cancelled = True
        proc = self._proc
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def run(self) -> None:
        total = len(self._files)
        for i, src in enumerate(self._files, start=1):
            if self._cancelled:
                break
            self.progress.emit(i, total, src.name)
            try:
                output_path = self._convert_one(src)
                self.file_done.emit(src.name, True, '', str(output_path))
            except _Cancelled:
                break
            except Exception as exc:
                self.file_done.emit(src.name, False, str(exc), '')
        self.all_done.emit()

    def _convert_one(self, src: Path) -> Path:
        out_ext = _MODES[self._mode]['out_ext']
        output_path = _unique_output_path(src, out_ext)

        if self._mode == 'wav_mp3':
            args = ['-map_metadata', '0', '-vn', '-c:a', 'libmp3lame', '-b:a', '320k']
        else:
            vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            args = [
                '-map_metadata', '0', '-vf', vf, '-c:v', 'libx264', '-preset', 'fast',
                '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
            ]

        # Duration comes from this same process's own startup banner (merged stderr),
        # not a separate probe call — one less subprocess, one less place to fail,
        # and the very first real progress tick lands as soon as ffmpeg opens the file.
        self._proc = subprocess.Popen(
            [get_ffmpeg_path(), '-y', '-nostdin', '-i', str(src), *args,
             '-progress', 'pipe:1', '-stats_period', '0.1', '-nostats', str(output_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        assert self._proc.stdout is not None
        duration = 0.0
        recent_lines: list[str] = []
        try:
            for raw_line in self._proc.stdout:
                if self._cancelled:
                    self._proc.terminate()
                    break
                # ffmpeg's own log lines can carry non-UTF-8 metadata (camera model
                # strings, encoder tags, etc. in other encodings) — decode leniently
                # so a stray byte never crashes the read loop mid-conversion.
                stripped = raw_line.decode('utf-8', errors='replace').strip()
                if not stripped:
                    continue
                is_progress_kv = ' ' not in stripped and stripped.count('=') == 1
                if not is_progress_kv:
                    recent_lines.append(stripped)
                    if len(recent_lines) > 6:
                        recent_lines.pop(0)
                if duration <= 0 and stripped.startswith('Duration:'):
                    duration = parse_duration_from_text(stripped)
                elif stripped.startswith('out_time_us=') and duration > 0:
                    try:
                        us = int(stripped.split('=')[1])
                        pct = int(min(us / (duration * 1_000_000), 1.0) * 100)
                        self.file_progress.emit(pct)
                    except (ValueError, IndexError):
                        pass
            self._proc.wait()
            returncode = self._proc.returncode
        finally:
            self._proc = None

        if self._cancelled:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise _Cancelled()
        if returncode != 0:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raw_detail = ' — '.join(recent_lines[-2:])
            raise RuntimeError(friendly_ffmpeg_error(raw_detail) if raw_detail else 'Conversion failed.')

        self.file_progress.emit(100)

        try:
            if self._mode == 'wav_mp3':
                copy_audio_tags(src, output_path)
            else:
                copy_video_tags(src, output_path)
        except Exception:
            logger.warning('Metadata copy failed for %s', src, exc_info=True)

        return output_path


class _ConvertDialog(_CrateSortDialog):
    """
    Convert local WAV/AIFF files to MP3, or local video files (MOV, MKV, AVI, WMV,
    WEBM, FLV, M4V, MPG/MPEG) to MP4.

    Batch-capable: queue multiple files, each converted file is saved next to its
    original (same folder, new extension). Originals are never modified or deleted.
    """

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self._mode   = mode
        self._config = _MODES[mode]
        self._queued_files: list[Path] = []
        self._worker: Optional[_MediaConvertWorker] = None
        self._results: list[tuple[str, bool, str, str]] = []

        self.setMinimumWidth(480)
        layout = _create_dialog_layout(self)

        title_lbl = QLabel(self._config['title'])
        title_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 22px; font-weight: 600; '
            'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
        )
        layout.addWidget(title_lbl)

        subtitle_lbl = QLabel(self._config['subtitle'])
        subtitle_lbl.setStyleSheet(
            'color: #a89b85; font-size: 12px; background: transparent; border: none;'
        )
        layout.addWidget(subtitle_lbl)
        layout.addSpacing(10)

        layout.addWidget(self._eyebrow('FILES TO CONVERT'))

        self._file_list = QListWidget()
        self._file_list.setStyleSheet(_LIST_STYLE)
        self._file_list.setFixedHeight(120)
        self._file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._file_list)

        list_btn_row = QHBoxLayout()
        list_btn_row.setSpacing(8)

        browse_btn = QPushButton('Browse…')
        browse_btn.setFixedHeight(32)
        browse_btn.setStyleSheet(self._secondary_btn_style())
        browse_btn.clicked.connect(self._on_browse)
        list_btn_row.addWidget(browse_btn)

        remove_btn = QPushButton('Remove Selected')
        remove_btn.setFixedHeight(32)
        remove_btn.setStyleSheet(self._secondary_btn_style())
        remove_btn.clicked.connect(self._on_remove_selected)
        list_btn_row.addWidget(remove_btn)
        list_btn_row.addStretch()
        layout.addLayout(list_btn_row)
        layout.addSpacing(8)

        hint = QLabel(
            f"Each converted file is saved next to its original — "
            f"song{self._config['exts'][0]} → song{self._config['out_ext']}."
        )
        hint.setStyleSheet('color: #5a5248; font-size: 11px; background: transparent; border: none;')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addSpacing(14)

        self._stage_lbl = QLabel('')
        self._stage_lbl.setStyleSheet(_EYEBROW_STYLE)
        self._stage_lbl.hide()
        layout.addWidget(self._stage_lbl)

        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)

        self._mascot: Optional[QLabel] = None
        self._mascot_anim: Optional[QPropertyAnimation] = None
        if _SVG_AVAILABLE and _MASCOT_SVG.exists():
            mascot_svg = QSvgWidget(str(_MASCOT_SVG))
            mascot_svg.setFixedSize(66, 66)
            mascot_svg.setStyleSheet('background: transparent;')
            mascot_svg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            opacity_effect = QGraphicsOpacityEffect(mascot_svg)
            mascot_svg.setGraphicsEffect(opacity_effect)
            anim = QPropertyAnimation(opacity_effect, b'opacity', self)
            anim.setDuration(1100)
            anim.setKeyValueAt(0.0, 0.3)
            anim.setKeyValueAt(0.5, 1.0)
            anim.setKeyValueAt(1.0, 0.3)
            anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            anim.setLoopCount(-1)
            self._mascot = mascot_svg
            self._mascot_anim = anim
            self._mascot.hide()
            prog_row.addWidget(self._mascot)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            'QProgressBar { background: #2a2a2a; border: none; border-radius: 3px; }'
            'QProgressBar::chunk { background: #428175; border-radius: 3px; }'
        )
        self._progress_bar.hide()
        self._pct_lbl = QLabel('0%')
        self._pct_lbl.setFixedWidth(36)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._pct_lbl.setStyleSheet(
            'color: #a89b85; font-size: 12px; background: transparent; border: none;'
        )
        self._pct_lbl.hide()
        prog_row.addWidget(self._progress_bar, stretch=1)
        prog_row.addWidget(self._pct_lbl)
        layout.addLayout(prog_row)

        self._result_lbl = QLabel()
        self._result_lbl.setWordWrap(True)
        self._result_lbl.setStyleSheet('background: transparent; border: none;')
        self._result_lbl.hide()
        layout.addWidget(self._result_lbl)

        self._folder_link_lbl = QLabel()
        self._folder_link_lbl.setWordWrap(True)
        self._folder_link_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._folder_link_lbl.setOpenExternalLinks(False)
        self._folder_link_lbl.setStyleSheet(
            'background: transparent; border: none; font-size: 12px;'
        )
        self._folder_link_lbl.linkActivated.connect(self._on_open_folder_link)
        self._folder_link_lbl.hide()
        layout.addWidget(self._folder_link_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._cancel_btn = QPushButton('Cancel')
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; '
            'background: rgba(241, 227, 200, 0.05); }'
        )
        self._cancel_btn.clicked.connect(self._on_cancel)

        self._convert_btn = QPushButton('Convert')
        self._convert_btn.setFixedHeight(36)
        self._convert_btn.setStyleSheet(self._primary_btn_style())
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._on_convert)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._convert_btn)
        layout.addLayout(btn_row)

    # ── Styling helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _eyebrow(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(_EYEBROW_STYLE)
        return lbl

    @staticmethod
    def _secondary_btn_style() -> str:
        return (
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 0 14px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #a89b85; }'
        )

    @staticmethod
    def _primary_btn_style() -> str:
        return (
            'QPushButton { background-color: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 24px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
            'QPushButton:disabled { background-color: #2a2a2a; color: #5a5248; }'
        )

    # ── File queue ───────────────────────────────────────────────────────────

    def _on_browse(self) -> None:
        settings = QSettings(_ORG, _APP)
        start_dir = str(settings.value(_LAST_DIR_KEY, str(Path.home())))
        paths, _ = QFileDialog.getOpenFileNames(
            self, 'Select Files to Convert', start_dir, self._config['filter'],
        )
        if not paths:
            return
        settings.setValue(_LAST_DIR_KEY, str(Path(paths[0]).parent))
        existing = {str(p) for p in self._queued_files}
        for p in paths:
            if p not in existing:
                self._queued_files.append(Path(p))
                item = QListWidgetItem(Path(p).name)
                item.setData(Qt.ItemDataRole.UserRole, p)
                self._file_list.addItem(item)
        self._convert_btn.setEnabled(bool(self._queued_files))

    def _on_remove_selected(self) -> None:
        for item in self._file_list.selectedItems():
            path_str = item.data(Qt.ItemDataRole.UserRole)
            self._queued_files = [p for p in self._queued_files if str(p) != path_str]
            self._file_list.takeItem(self._file_list.row(item))
        self._convert_btn.setEnabled(bool(self._queued_files))

    # ── Convert ──────────────────────────────────────────────────────────────

    def _on_convert(self) -> None:
        if not self._queued_files:
            return
        self._convert_btn.setEnabled(False)
        self._result_lbl.hide()
        self._folder_link_lbl.hide()
        self._results = []

        self._stage_lbl.show()
        self._progress_bar.show()
        self._pct_lbl.show()
        if self._mascot is not None:
            self._mascot.show()
            self._mascot_anim.start()

        self._worker = _MediaConvertWorker(list(self._queued_files), self._mode, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._current = 0
        self._total = len(self._queued_files)
        self._worker.start()

    def _on_progress(self, current: int, total: int, filename: str) -> None:
        self._current = current
        self._total = total
        self._stage_lbl.setText(f'CONVERTING ({current} OF {total}): {filename.upper()}')
        overall = int(100 * (current - 1) / total) if total else 0
        self._progress_bar.setValue(overall)
        self._pct_lbl.setText(f'{overall}%')

    def _on_file_progress(self, pct: int) -> None:
        if not self._total:
            return
        overall = int(100 * ((self._current - 1) + pct / 100) / self._total)
        self._progress_bar.setValue(overall)
        self._pct_lbl.setText(f'{overall}%')

    def _on_file_done(self, filename: str, success: bool, message: str, output_path: str) -> None:
        self._results.append((filename, success, message, output_path))

    def _on_all_done(self) -> None:
        self._progress_bar.setValue(100)
        self._pct_lbl.setText('100%')
        self._stage_lbl.hide()
        if self._mascot is not None:
            self._mascot_anim.stop()
            self._mascot.hide()

        saved_paths = [out for _, ok, _, out in self._results if ok]
        failed = [(f, m) for f, ok, m, _ in self._results if not ok]
        succeeded = len(saved_paths)
        total = len(self._results)

        if succeeded == 1 and not failed:
            self._set_result(f'Saved: {saved_paths[0]}', error=False)
        elif saved_paths:
            parents = {str(Path(p).parent) for p in saved_paths}
            if len(parents) == 1:
                where = f'Saved to {next(iter(parents))}'
            else:
                where = 'Saved:\n' + '\n'.join(saved_paths)
            summary = f'{succeeded} of {total} file{"s" if total != 1 else ""} converted. {where}'
            self._set_result(summary, error=bool(failed))
        else:
            summary = f'0 of {total} files converted.'
            self._set_result(summary, error=True)

        if failed:
            detail = '; '.join(f'{f} ({m})' for f, m in failed)
            current = self._result_lbl.text()
            self._result_lbl.setText(f'{current}\n{len(failed)} failed: {detail}')

        if saved_paths:
            folders = sorted({str(Path(p).parent) for p in saved_paths})
            link_style = 'color: #428175; text-decoration: none;'
            links = [
                f'<a href="{QUrl.fromLocalFile(folder).toString()}" style="{link_style}">'
                f'Show {Path(folder).name} in Finder</a>'
                if len(folders) > 1 else
                f'<a href="{QUrl.fromLocalFile(folder).toString()}" style="{link_style}">Show in Finder</a>'
                for folder in folders
            ]
            self._folder_link_lbl.setText('<br>'.join(links))
            self._folder_link_lbl.show()

        self._convert_btn.setText('Close')
        self._convert_btn.setEnabled(True)
        self._convert_btn.setStyleSheet(
            'QPushButton { background-color: #6B9E78; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 24px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #5a8e67; }'
        )
        self._convert_btn.clicked.disconnect()
        self._convert_btn.clicked.connect(self.accept)
        self._cancel_btn.hide()

    # ── Cancel ───────────────────────────────────────────────────────────────

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        if self._mascot is not None:
            self._mascot_anim.stop()
        self.reject()

    def _on_open_folder_link(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _set_result(self, text: str, *, error: bool) -> None:
        color = '#C75B5B' if error else '#6B9E78'
        self._result_lbl.setStyleSheet(
            f'color: {color}; font-size: 12px; background: transparent; border: none;'
        )
        self._result_lbl.setText(text)
        self._result_lbl.show()
