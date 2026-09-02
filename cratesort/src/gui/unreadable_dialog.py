"""
"Files CrateSort couldn't read" — an in-app list, opened from the Dashboard
banner the library scan raises when one or more files fail to read.

Read-only: it just shows each skipped file, where it lives, and why it failed,
with a per-row "Show in Finder". The plain-text copy the scanner writes to
_CrateSort/logs/unreadable-files.txt is still there for anyone who wants it.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from cratesort.src.gui.overlays import _CrateSortDialog, _create_dialog_layout

_CREAM = '#f1e3c8'
_MUTED = '#a89b85'
_DIM   = '#7a6a55'


def _collapse_home(p: Path) -> str:
    try:
        return '~/' + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


class _UnreadableFilesDialog(_CrateSortDialog):
    _ROWS_MAX_H = 340  # ~5 rows; scrolls past that

    def __init__(self, entries: list[tuple[Path, str]], parent=None):
        super().__init__(parent)
        self.setMinimumWidth(620)
        self._entries = list(entries)

        layout = _create_dialog_layout(self)

        n = len(self._entries)
        headline = QLabel(
            f'{n:,} File{"s" if n != 1 else ""} CrateSort Couldn’t Read'
        )
        headline.setStyleSheet(
            f'color: {_CREAM}; font-size: 22px; font-weight: 600; '
            f'font-family: "Helvetica Neue", Arial, Helvetica; '
            f'background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        body = QLabel()
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setText(
            '<div style="line-height: 145%;">'
            'These were skipped, not added to your library — usually a damaged '
            'file, or the drive, cable, or macOS filesystem driver stalling on '
            'it. A copy of this list is saved to '
            '<span style="color:#a89b85;">_CrateSort/logs/unreadable-files.txt</span>.'
            '</div>'
        )
        body.setStyleSheet(
            'color: #d5c7ad; font-size: 13px; background: transparent; border: none;'
        )
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
        for path, reason in self._entries:
            rows_v.addWidget(self._build_row(Path(path), reason))
        rows_v.addStretch()
        scroll.setWidget(rows)
        layout.addWidget(scroll)

        self._rows_host = rows
        self._rows_scroll = scroll
        self._fit_rows_scroll()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton('Close')
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(
            'QPushButton { background-color: #aa6326; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 22px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #925521; }'
            'QPushButton:pressed { background-color: #7e491c; }'
        )
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ rows

    def _build_row(self, path: Path, reason: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            'QFrame { background: #2a2a2a; border: none; border-radius: 4px; }'
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 9, 12, 9)
        v.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(10)
        name = QLabel(path.name)
        name.setStyleSheet(
            f'color: {_CREAM}; font-size: 13px; font-weight: 500; '
            f'background: transparent; border: none;'
        )
        name.setWordWrap(False)
        top.addWidget(name, stretch=1)

        reveal = QPushButton('Show in Finder')
        reveal.setFixedHeight(28)
        reveal.setCursor(Qt.CursorShape.PointingHandCursor)
        reveal.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; '
            'border: 1px solid #444444; border-radius: 5px; padding: 0 12px; '
            'font-size: 11px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; '
            'background: rgba(241, 227, 200, 0.05); }'
        )
        reveal.setAutoDefault(False)
        reveal.clicked.connect(lambda _=False, p=path: self._reveal(p))
        top.addWidget(reveal)
        v.addLayout(top)

        folder = QLabel(_collapse_home(path.parent))
        folder.setStyleSheet(
            f'color: {_MUTED}; font-size: 11px; background: transparent; border: none;'
        )
        folder.setWordWrap(False)
        folder.setToolTip(str(path))
        v.addWidget(folder)

        why = QLabel(reason or 'Unknown error')
        why.setStyleSheet(
            f'color: {_DIM}; font-size: 11px; background: transparent; border: none;'
        )
        why.setWordWrap(True)
        v.addWidget(why)

        return frame

    def _reveal(self, path: Path) -> None:
        target = path.parent if path.parent.exists() else path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    # --------------------------------------------------------------- sizing

    def _fit_rows_scroll(self) -> None:
        want = self._rows_host.sizeHint().height()
        if want <= 0:
            want = max(1, len(self._entries)) * 74
        self._rows_scroll.setFixedHeight(min(self._ROWS_MAX_H, want + 2))

    def showEvent(self, event) -> None:
        self._fit_rows_scroll()
        super().showEvent(event)

    def keyPressEvent(self, event) -> None:
        # Dialog keyboard standard: Enter commits the primary action (Close
        # here), Escape cancels — both just dismiss this read-only dialog.
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self.accept()
            return
        super().keyPressEvent(event)
