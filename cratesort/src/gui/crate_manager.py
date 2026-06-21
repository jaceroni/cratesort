from __future__ import annotations

import json
import shutil
import subprocess
import sys as _sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QEvent, QMimeData, QPoint, QRect, QSettings, QSize, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDrag, QFontMetrics, QIcon, QPen, QPixmap, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog,
    QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QFileDialog, QMenu, QProgressBar, QPushButton, QSplitter,
    QStackedWidget, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from cratesort.src.serato.crate_reader import CrateReader, CrateLibrary, Crate
from cratesort.src.serato.database_reader import read_track_add_dates, clear_cache as _clear_date_cache
from cratesort.src.serato.crate_writer import (
    CrateWriter, read_crate_order as _read_neworder, write_crate_order as _write_neworder,
)
from cratesort.src.utils.undo_manager import (
    UndoManager, AddTracksCommand, RemoveTracksCommand, ReorderTracksCommand,
    CreateCrateCommand, DeleteCrateCommand, RenameCrateCommand,
    ReorderCratesCommand, ReparentCrateCommand, EditTrackMetadataCommand,
)
from cratesort.src.gui.overlays import _CrateSortDialog, _ov_alert, _ov_confirm, _create_dialog_layout

# ---------------------------------------------------------------------------
# Column indices
# ---------------------------------------------------------------------------
TC_POS      = 0
TC_TITLE    = 1
TC_ARTIST   = 2
TC_ALBUM    = 3
TC_DURATION = 4
TC_GENRE    = 5
TC_TAGS     = 6
TC_BPM      = 7
TC_DATE     = 8   # Date Added (Serato crate timestamp — shows — if unavailable)
TC_FORMAT   = 9
TC_YEAR     = 10
TC_BITRATE  = 11
TC_COMMENT  = 12
TC_PATH     = 13

_TRACK_HEADERS = [
    '#', 'Title', 'Artist', 'Album', 'Duration', 'Genre', 'Style Tags',
    'BPM', 'Date Added', 'Format', 'Year', 'Bitrate', 'Comments', 'File Path',
]

_EDITABLE_COLS = {TC_TITLE, TC_ALBUM, TC_TAGS, TC_BPM, TC_YEAR, TC_COMMENT}

_EDITABLE_FIELDS = {
    TC_TITLE:   'title',
    TC_ALBUM:   'album',
    TC_TAGS:    'tags',
    TC_BPM:     'bpm',
    TC_YEAR:    'year',
    TC_COMMENT: 'comment',
}

_TRACKS_MIME = 'application/x-cratesort-tracks'

_MUTED  = '#a89b85'
_CREAM  = '#f1e3c8'
_TEAL   = '#428175'
_ORANGE = '#D17D34'
_PANEL  = '#2F2F2F'
_BORDER = '#444444'

_SETTINGS_KEY   = 'crate_manager_header_state'
_ALL_TRACKS_KEY = '__ALL_TRACKS__'



# ---------------------------------------------------------------------------
# Crate tree item delegate — single source of truth for all cell rendering.
# Replaces CrateRowWidget/setItemWidget approach.
# ---------------------------------------------------------------------------

class CrateItemDelegate(QStyledItemDelegate):

    ROW_HEIGHT = 36
    BAR_WIDTH  = 5

    STATE_A = 'a'  # unselected
    STATE_B = 'b'  # selected, no active sub-crate
    STATE_C = 'c'  # parent of active sub-crate
    STATE_D = 'd'  # selected sub-crate
    STATE_E = 'e'  # track drag-drop hover target

    BG_A      = QColor('#2F2F2F')
    BG_SUB    = QColor('#222222')
    BG_B      = QColor('#573d26')
    BG_C      = QColor('#000000')
    BG_D      = QColor('#573d26')
    BG_E      = QColor('#1a3530')
    BAR_COLOR = QColor('#D17D34')
    BAR_TEAL  = QColor('#428175')
    TEXT_A    = QColor('#f1e3c8')
    TEXT_B    = QColor('#f1e3c8')
    EXPAND_COLOR = QColor('#a89b85')

    def __init__(self, tree: 'QTreeWidget', parent=None):
        super().__init__(parent)
        self._tree   = tree
        self._states: dict[str, str] = {}

    def set_item_state(self, path: str, state: str) -> None:
        self._states[path] = state
        self._tree.viewport().update()

    def get_item_state(self, path: str) -> str:
        return self._states.get(path, self.STATE_A)

    def clear_all_states(self) -> None:
        self._states.clear()
        self._tree.viewport().update()

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width() if option.rect.width() > 0 else 200, self.ROW_HEIGHT)

    def paint(self, painter, option, index) -> None:
        painter.save()

        path  = index.data(Qt.ItemDataRole.UserRole) or ''
        state = self._states.get(path, self.STATE_A)

        # State A background depends on depth: sub-crates are darker
        if state == self.STATE_A:
            bg = self.BG_SUB if index.parent().isValid() else self.BG_A
        else:
            bg = {
                self.STATE_B: self.BG_B,
                self.STATE_C: self.BG_C,
                self.STATE_D: self.BG_D,
                self.STATE_E: self.BG_E,
            }.get(state, self.BG_A)

        # Fill entire cell
        painter.fillRect(option.rect, bg)

        # Left bar: orange for selected states, teal for drop-target
        if state in (self.STATE_B, self.STATE_C, self.STATE_D, self.STATE_E):
            bar_color = self.BAR_TEAL if state == self.STATE_E else self.BAR_COLOR
            bar_rect = QRect(
                option.rect.left(), option.rect.top(),
                self.BAR_WIDTH, option.rect.height()
            )
            painter.fillRect(bar_rect, bar_color)

        # Teal inset border for drop-target state
        if state == self.STATE_E:
            pen = QPen(self.BAR_TEAL, 1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(option.rect.adjusted(1, 0, -1, -1))

        # Crate name text
        text      = index.data(Qt.ItemDataRole.DisplayRole) or ''
        text_rect = option.rect.adjusted(self.BAR_WIDTH + 8, 0, -24, 0)
        painter.setPen(self.TEXT_A)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )

        # Expand/collapse indicator for parent crates
        item = self._tree.itemFromIndex(index)
        if item and item.childCount() > 0:
            indicator      = '▼' if item.isExpanded() else '▶'
            indicator_rect = option.rect.adjusted(option.rect.width() - 45, 0, -25, 0)
            painter.setPen(self.EXPAND_COLOR)
            painter.drawText(
                indicator_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                indicator,
            )

        # Row separator line
        painter.setPen(QColor('#383838'))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())

        painter.restore()


# ---------------------------------------------------------------------------
# Module-level icon cache
# ---------------------------------------------------------------------------

_NOTE_ICON: Optional[QIcon] = None


def _make_note_icon() -> QIcon:
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


def _get_note_icon() -> QIcon:
    global _NOTE_ICON
    if _NOTE_ICON is None:
        _NOTE_ICON = _make_note_icon()
    return _NOTE_ICON


# ---------------------------------------------------------------------------
# Reorderable table widget
# ---------------------------------------------------------------------------

class _NumericItem(QTableWidgetItem):
    """Table item that sorts numerically using its integer UserRole value."""
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return (self.data(Qt.ItemDataRole.UserRole) or 0) < (other.data(Qt.ItemDataRole.UserRole) or 0)
        except TypeError:
            return super().__lt__(other)


class _ReorderableTable(QTableWidget):
    """QTableWidget with manual row drag-to-reorder and cross-widget drag support."""

    rows_reordered = pyqtSignal(list)  # list[str] — new order of original track paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDropIndicatorShown(False)  # We draw our own teal indicator
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Teal drop indicator line (overlay on viewport)
        self._drop_line = QFrame(self.viewport() if self.viewport() else self)
        self._drop_line.setFrameShape(QFrame.Shape.HLine)
        self._drop_line.setFrameShadow(QFrame.Shadow.Plain)
        self._drop_line.setStyleSheet('background: #428175; border: none;')
        self._drop_line.setFixedHeight(2)
        self._drop_line.hide()
        self._drop_insert_row: int = -1

    def _get_insert_row(self, y: int) -> int:
        """Return the row index to insert BEFORE, based on cursor y position."""
        row = self.rowAt(y)
        if row == -1:
            return self.rowCount()
        rect = self.visualRect(self.model().index(row, 0))
        return row + 1 if y > rect.center().y() else row

    def _position_drop_line(self, insert_before: int) -> None:
        vp = self.viewport()
        if insert_before <= 0:
            y = 0
        elif insert_before >= self.rowCount():
            last = self.visualRect(self.model().index(self.rowCount() - 1, 0))
            y = last.bottom()
        else:
            r = self.visualRect(self.model().index(insert_before, 0))
            y = r.top()
        self._drop_line.setGeometry(0, max(0, y - 1), vp.width(), 2)
        self._drop_line.show()
        self._drop_line.raise_()

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.selectedIndexes():
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.unsetCursor()

    def dragEnterEvent(self, event) -> None:
        if event.source() is self:
            self._drop_insert_row = self._get_insert_row(event.position().toPoint().y())
            self._position_drop_line(self._drop_insert_row)
            event.acceptProposedAction()
        elif event.mimeData().hasFormat(_TRACKS_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.source() is self:
            self._drop_insert_row = self._get_insert_row(event.position().toPoint().y())
            self._position_drop_line(self._drop_insert_row)
            event.acceptProposedAction()
        elif event.mimeData().hasFormat(_TRACKS_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._drop_line.hide()
        self.unsetCursor()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._drop_line.hide()
        self.unsetCursor()

        if event.source() is not self:
            event.ignore()
            return

        insert_before = self._get_insert_row(event.position().toPoint().y())
        source_rows   = sorted({idx.row() for idx in self.selectedIndexes()})

        if not source_rows:
            event.ignore()
            return

        # Read current visual order of original crate track paths
        current_order: list[str] = []
        for r in range(self.rowCount()):
            cell = self.item(r, TC_TITLE)  # TC_TITLE = 1
            if cell:
                orig = cell.data(Qt.ItemDataRole.UserRole + 1)
                if orig:
                    current_order.append(orig)

        source_set   = set(source_rows)
        source_paths = [current_order[r] for r in source_rows if r < len(current_order)]
        remaining    = [p for i, p in enumerate(current_order) if i not in source_set]
        n_above      = sum(1 for r in source_rows if r < insert_before)
        real_ins     = max(0, insert_before - n_above)
        new_order    = remaining[:real_ins] + source_paths + remaining[real_ins:]

        if new_order == current_order:
            event.ignore()
            return

        event.acceptProposedAction()
        self.rows_reordered.emit(new_order)

    def startDrag(self, supported_actions) -> None:
        rows  = sorted({idx.row() for idx in self.selectedIndexes()})
        paths: list[str] = []
        for r in rows:
            cell = self.item(r, TC_TITLE)
            if cell:
                orig = cell.data(Qt.ItemDataRole.UserRole + 1)
                if orig:
                    paths.append(orig)
        if not paths:
            super().startDrag(supported_actions)
            return

        mime = QMimeData()
        mime.setData(_TRACKS_MIME, json.dumps(paths).encode('utf-8'))
        drag = QDrag(self)
        drag.setMimeData(mime)

        # Ghost pixmap: teal pill showing track title or "N tracks"
        n = len(paths)
        if n == 1:
            title_cell = self.item(rows[0], TC_TITLE)
            label = title_cell.text() if title_cell else paths[0].rsplit('/', 1)[-1]
        else:
            label = f'{n} tracks'

        font = self.font()
        font.setPointSize(11)
        font.setBold(True)
        fm   = QFontMetrics(font)
        pad_x, pad_y = 14, 7
        pm_w = fm.horizontalAdvance(label) + pad_x * 2
        pm_h = fm.height() + pad_y * 2

        pm = QPixmap(pm_w, pm_h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(0.88)
        p.setBrush(QColor('#428175'))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, pm_w, pm_h, 6, 6)
        p.setOpacity(1.0)
        p.setPen(QColor('#ffffff'))
        p.setFont(font)
        p.drawText(pad_x, pad_y + fm.ascent(), label)
        p.end()

        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm_w // 2, pm_h // 2))
        drag.exec(supported_actions)


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
# Add Tracks dialog
# ---------------------------------------------------------------------------

class _AddTracksDialog(_CrateSortDialog):
    def __init__(self, inventory, current_tracks: set[str], parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 480)

        # Use standard Teal accent layout (safe action/selection)
        layout = _create_dialog_layout(self, '#428175')

        # Since QListWidget and QLineEdit styling is on the dialog or layout, we can set it on parent/self
        self.setStyleSheet(
            'QLabel { color: #f1e3c8; font-size: 13px; background: transparent; }'
            'QLineEdit { background-color: #1a1a1a; color: #f1e3c8; font-size: 13px; '
            'border: 1px solid #444444; border-radius: 4px; padding: 6px 8px; }'
            'QListWidget { background-color: #1a1a1a; color: #f1e3c8; font-size: 13px; }'
        )

        headline = QLabel('Add Tracks to Crate')
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(headline)

        self._search = QLineEdit()
        self._search.setPlaceholderText('Search tracks…')
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self._list, stretch=1)

        for rec in inventory:
            path = str(rec.path)
            label_parts = []
            if rec.title:
                label_parts.append(rec.title)
            if rec.artist:
                label_parts.append(f'— {rec.artist}')
            label = ' '.join(label_parts) if label_parts else rec.filename

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)

            if path in current_tracks:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QBrush(QColor(_MUTED)))
                item.setText(f'{label}  (already in crate)')
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)

            self._list.addItem(item)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self._cancel_btn = QPushButton('Cancel')
        self._cancel_btn.setFixedHeight(36)
        self._cancel_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
            'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
        )
        self._cancel_btn.clicked.connect(self.reject)
        self._add_btn = QPushButton('Add Selected')
        self._add_btn.setFixedHeight(36)
        self._add_btn.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        self._add_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._add_btn)
        layout.addLayout(btn_row)

    def accept(self) -> None:
        """Show immediate loading feedback before the dialog closes."""
        self._add_btn.setText('Adding…')
        self._add_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        QApplication.processEvents()
        super().accept()

    def _filter(self, text: str) -> None:
        q = text.lower().strip()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(q and q not in item.text().lower()))

    def selected_paths(self) -> list[str]:
        result = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if (item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and item.checkState() == Qt.CheckState.Checked):
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result


# ---------------------------------------------------------------------------
# Styled text-input dialog (replaces QInputDialog.getText)
# ---------------------------------------------------------------------------

class _NameInputDialog(_CrateSortDialog):
    """Styled text-input dialog replacing QInputDialog.getText()."""

    def __init__(self, parent, title: str, prompt: str, prefill: str = ''):
        super().__init__(parent)
        self.setMinimumWidth(480)

        # Use standard Teal accent layout (safe action/input)
        layout = _create_dialog_layout(self, '#428175')

        headline = QLabel(title)
        headline.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        layout.addWidget(headline)
        layout.addSpacing(6)

        prompt_lbl = QLabel()
        prompt_lbl.setTextFormat(Qt.TextFormat.RichText)
        prompt_lbl.setText(f'<div style="line-height: 145%;">{prompt}</div>')
        prompt_lbl.setStyleSheet(
            'color: #d5c7ad; font-size: 14px; background: transparent; border: none;'
        )
        layout.addWidget(prompt_lbl)
        layout.addSpacing(4)

        self._edit = QLineEdit(prefill)
        self._edit.selectAll()
        self._edit.setStyleSheet(
            'QLineEdit { background-color: #1a1a1a; color: #f1e3c8; font-size: 13px; '
            'border: 1px solid #444444; border-radius: 4px; padding: 6px 8px; }'
        )
        layout.addWidget(self._edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        cancel = QPushButton('Cancel')
        cancel.setFixedHeight(36)
        cancel.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
            'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
        )
        cancel.clicked.connect(self.reject)
        ok = QPushButton('OK')
        ok.setDefault(True)
        ok.setFixedHeight(36)
        ok.setStyleSheet(
            'QPushButton { background-color: #428175; color: #ffffff; border: none; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }'
            'QPushButton:hover { background-color: #38706a; }'
            'QPushButton:pressed { background-color: #2d6358; }'
        )
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def get_name(self) -> Optional[str]:
        if self.exec() == QDialog.DialogCode.Accepted:
            return self._edit.text().strip() or None
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_crate_name(name: str) -> Optional[str]:
    """Return an error message if name is invalid, else None."""
    if not name or not name.strip():
        return 'Crate name cannot be empty.'
    if '/' in name or '\\' in name:
        return 'Crate name cannot contain slashes.'
    if '%' in name:
        return "Crate name cannot contain '%' — it conflicts with Serato's internal path encoding."
    return None


# ---------------------------------------------------------------------------
# Worker: async track table loading
# ---------------------------------------------------------------------------

class _CrateLoadWorker(QThread):
    progress = pyqtSignal(int, int, str)   # (done, total, label)
    finished = pyqtSignal(object)          # payload dict
    errored  = pyqtSignal(str)

    def __init__(
        self,
        track_paths: list,
        inventory_by_path: dict,
        inventory_by_name: dict,
        edits: dict,
        session_genre: dict,
        track_genre_overrides: dict,
        add_dates: dict,
        library_path,
        label: str,
        parent=None,
    ):
        super().__init__(parent)
        self._track_paths           = track_paths
        self._inventory_by_path     = inventory_by_path
        self._inventory_by_name     = inventory_by_name
        self._edits                 = edits
        self._session_genre         = session_genre
        self._track_genre_overrides = track_genre_overrides
        self._add_dates             = add_dates
        self._library_path          = library_path
        self._label                 = label
        self._cancelled             = False

    def cancel(self) -> None:
        self._cancelled = True

    def _resolve(self, track_path: str):
        if track_path in self._inventory_by_path:
            return self._inventory_by_path[track_path]
        if self._library_path:
            key = str(self._library_path / track_path)
            if key in self._inventory_by_path:
                return self._inventory_by_path[key]
        rec = self._inventory_by_name.get(Path(track_path).name)
        if rec:
            return rec
        stem = Path(track_path).stem.lower()
        if len(stem) >= 5:
            for candidate in self._inventory_by_name.values():
                cs = Path(candidate.filename).stem.lower()
                if cs == stem or stem in cs or cs in stem:
                    return candidate
        return None

    def run(self) -> None:
        try:
            total          = len(self._track_paths)
            rows: list     = []
            resolved_count = 0
            total_dur_secs = 0.0

            for i, tp in enumerate(self._track_paths):
                if self._cancelled:
                    return
                rec = self._resolve(tp)
                if rec is not None:
                    row = self._build_resolved(tp, rec)
                    resolved_count += 1
                    total_dur_secs += row['duration_secs']
                else:
                    row = {'resolved': False, 'track_path': tp,
                           'filename': Path(tp).name}
                rows.append(row)
                self.progress.emit(i + 1, total, self._label)

            if self._cancelled:
                return

            self.finished.emit({
                'rows':           rows,
                'track_paths':    self._track_paths,
                'label':          self._label,
                'total':          total,
                'resolved_count': resolved_count,
                'total_dur_secs': total_dur_secs,
            })
        except Exception as exc:
            import traceback
            self.errored.emit(f'{exc}\n{traceback.format_exc()}')

    def _build_resolved(self, tp: str, rec) -> dict:
        edits      = self._edits.get(str(rec.path), {})
        path_str   = str(rec.path)
        artist_key = f'__artist__{rec.artist}' if rec.artist else ''

        genre = (
            edits.get('genre')
            or (self._edits.get(artist_key, {}).get('genre') if artist_key else None)
            or self._track_genre_overrides.get(path_str)
            or self._session_genre.get(rec.artist or '')
            or rec.genre
            or '—'
        )

        date_str = '—'
        date_ts  = 0
        if self._add_dates and self._library_path:
            try:
                rel_key = Path(path_str).relative_to(self._library_path).as_posix()
                add_dt  = self._add_dates.get(rel_key)
                if add_dt is None:
                    add_dt = self._add_dates.get(rel_key.replace(' : ', ''))
                if add_dt:
                    date_str = add_dt.strftime('%Y-%m-%d')
                    date_ts  = int(add_dt.timestamp())
            except ValueError:
                pass

        return {
            'resolved':      True,
            'track_path':    tp,
            'path_str':      path_str,
            'title':         edits.get('title',            rec.title   or ''),
            'artist':        edits.get('reassign_artist',  rec.artist  or ''),
            'album':         edits.get('album',            rec.album   or ''),
            'genre':         genre,
            'tags':          edits.get('tags',             ''),
            'bpm':           edits.get('bpm', str(round(rec.bpm)) if rec.bpm else '—'),
            'year':          edits.get('year',             rec.year    or '—'),
            'comment':       edits.get('comment',          rec.comment or ''),
            'dur':           _fmt_dur(rec.duration),
            'fmt':           rec.extension.lstrip('.').upper() if rec.extension else '—',
            'bitrate':       f'{rec.bitrate} kbps' if rec.bitrate else '—',
            'path':          path_str,
            'date_str':      date_str,
            'date_ts':       date_ts,
            'duration_secs': rec.duration or 0.0,
        }


# ---------------------------------------------------------------------------
# Export Crate to Folder — worker + progress dialog
# ---------------------------------------------------------------------------

class _ExportCrateWorker(QThread):
    progress = pyqtSignal(int, int, str)   # (done, total, filename)
    finished = pyqtSignal(object)          # {'copied': int, 'failed': int, 'dest': Path}
    errored  = pyqtSignal(str)

    def __init__(
        self,
        crate_library,
        root_crate_path: str,
        inventory_by_path: dict,
        inventory_by_name: dict,
        edits: dict,
        library_path,
        total: int,
        dest_folder: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._crate_library     = crate_library
        self._root_crate_path   = root_crate_path
        self._inventory_by_path = inventory_by_path
        self._inventory_by_name = inventory_by_name
        self._edits             = edits
        self._library_path      = library_path
        self._total             = total
        self._dest              = dest_folder
        self._cancelled         = False
        self._done              = 0

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            crate_name  = self._root_crate_path.split('/')[-1]
            export_root = self._dest / crate_name
            export_root.mkdir(parents=True, exist_ok=True)
            copied, failed = self._export_crate(self._root_crate_path, export_root)
            if not self._cancelled:
                self.finished.emit({'copied': copied, 'failed': failed, 'dest': export_root})
        except Exception as exc:
            import traceback
            self.errored.emit(f'{exc}\n{traceback.format_exc()}')

    def _export_crate(self, crate_path: str, dest_folder: Path) -> tuple:
        if self._cancelled or crate_path not in self._crate_library.crates:
            return 0, 0
        crate  = self._crate_library.crates[crate_path]
        copied = 0
        failed = 0

        # Direct tracks → dest_folder / Artist /
        for tp in crate.tracks:
            if self._cancelled:
                break
            rec = self._resolve(tp)
            if rec is None:
                failed += 1
                self._done += 1
                self.progress.emit(self._done, self._total, '')
                continue
            track_edits = self._edits.get(str(rec.path), {})
            artist      = track_edits.get('reassign_artist', rec.artist or 'Unknown Artist')
            artist_dir  = dest_folder / artist
            artist_dir.mkdir(exist_ok=True)
            src  = Path(str(rec.path))
            dest = self._unique_dest(artist_dir / src.name)
            try:
                shutil.copy2(src, dest)
                copied += 1
            except Exception:
                failed += 1
            self._done += 1
            self.progress.emit(self._done, self._total, src.name)

        # Subcrates → dest_folder / _SubcrateName / (underscore prefix sorts to top)
        for child_path in crate.children:
            if self._cancelled:
                break
            child_name = '_' + child_path.split('/')[-1]
            child_dest = dest_folder / child_name
            child_dest.mkdir(exist_ok=True)
            c, f = self._export_crate(child_path, child_dest)
            copied += c
            failed += f

        return copied, failed

    def _resolve(self, track_path: str):
        if track_path in self._inventory_by_path:
            return self._inventory_by_path[track_path]
        if self._library_path:
            key = str(self._library_path / track_path)
            if key in self._inventory_by_path:
                return self._inventory_by_path[key]
        rec = self._inventory_by_name.get(Path(track_path).name)
        if rec:
            return rec
        stem = Path(track_path).stem.lower()
        if len(stem) >= 5:
            for candidate in self._inventory_by_name.values():
                cs = Path(candidate.filename).stem.lower()
                if cs == stem or stem in cs or cs in stem:
                    return candidate
        return None

    @staticmethod
    def _unique_dest(path: Path) -> Path:
        if not path.exists():
            return path
        stem, suffix, parent = path.stem, path.suffix, path.parent
        n = 2
        while True:
            candidate = parent / f'{stem}_{n}{suffix}'
            if not candidate.exists():
                return candidate
            n += 1


class _ExportProgressDialog(_CrateSortDialog):
    cancelled = pyqtSignal()

    def __init__(self, crate_name: str, total: int, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(480)

        # Use standard Teal accent layout (safe action/progress)
        layout = _create_dialog_layout(self, '#428175')

        title = QLabel('Exporting Crate')
        title.setStyleSheet(
            'color: #f1e3c8; font-size: 17px; font-weight: 600; '
            'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(6)

        name_lbl = QLabel()
        name_lbl.setTextFormat(Qt.TextFormat.RichText)
        name_lbl.setText(f'<div style="line-height: 145%; text-align: center;">{crate_name}</div>')
        name_lbl.setStyleSheet('color: #d5c7ad; font-size: 14px; background: transparent; border: none;')
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_lbl)
        layout.addSpacing(8)

        self._bar = QProgressBar()
        self._bar.setRange(0, total)
        self._bar.setValue(0)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            'QProgressBar { background: #383838; border: none; border-radius: 4px; }'
            f'QProgressBar::chunk {{ background: {_TEAL}; border-radius: 4px; }}'
        )
        layout.addWidget(self._bar)

        self._count_lbl = QLabel(f'0 of {total:,}')
        self._count_lbl.setStyleSheet('color: #a89b85; font-size: 12px; background: transparent; border: none;')
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._count_lbl)

        cancel_btn = QPushButton('Cancel')
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(
            'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
            'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
            'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
            'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
        )
        cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(cancel_btn)

    def update_progress(self, done: int, total: int) -> None:
        self._bar.setValue(done)
        self._count_lbl.setText(f'{done:,} of {total:,}')

    def _on_cancel(self) -> None:
        self.cancelled.emit()
        self.close()


# ---------------------------------------------------------------------------
# Crate Manager view
# ---------------------------------------------------------------------------

class CrateManagerView(QWidget):
    track_selected      = pyqtSignal(str)
    album_art_requested = pyqtSignal(str)
    navigate_to_settings = pyqtSignal()   # emitted by "Load Library" on empty-state screen

    def __init__(self, undo_manager: Optional['UndoManager'] = None, parent=None):
        super().__init__(parent)
        self._undo_manager = undo_manager
        self._library_path: Optional[Path]              = None
        self._inventory                                  = []
        self._inventory_by_path: dict[str, object]      = {}
        self._inventory_by_name: dict[str, object]      = {}
        self._crate_library: Optional[CrateLibrary]     = None
        self._current_crate_path: Optional[str]         = None
        self._edits: dict[str, dict[str, str]]           = {}
        self._session_genre: dict[str, str]              = {}  # artist → classified genre
        self._track_genre_overrides: dict[str, str]      = {}  # file_path → genre from session
        self._add_dates: dict[str, 'datetime']           = {}  # file_path → datetime from uadd
        self._original_track_paths: list[str]            = []
        self._settings = QSettings('JWBC', 'CrateSort')

        self._edit_widget:   Optional[QLineEdit] = None
        self._edit_row:      int                 = -1
        self._edit_col:      int                 = -1
        self._edit_original: str                 = ''

        self._context_rows: list[int] = []
        self._prev_selected_item: Optional[QTreeWidgetItem] = None
        self._prev_parent_item:   Optional[QTreeWidgetItem] = None
        self._crate_delegate: Optional['CrateItemDelegate'] = None
        self._sort_col:   int              = TC_POS
        self._sort_order: Qt.SortOrder     = Qt.SortOrder.AscendingOrder

        # Crate order persistence (Fix 3)
        self._crate_order: dict[str, list[str]] = {}  # "" = top-level; path = children of that crate

        # Expanded state preserved across tab switches
        self._expanded_paths: set[str] = set()
        self._last_selected_path: Optional[str] = None
        self._last_scroll_pos: int = 0

        # Drop target highlight for track-onto-crate drag
        self._track_drop_target_key:   Optional[str] = None
        self._track_drop_prior_state:  str            = CrateItemDelegate.STATE_A

        # Manual crate drag state (Fix 3)
        self._crate_drag_item:   Optional[QTreeWidgetItem] = None
        self._crate_drag_active: bool                      = False
        self._crate_drag_start:  Optional[QPoint]          = None
        self._crate_hover_item:  Optional[QTreeWidgetItem] = None
        self._crate_hover_timer: QTimer                    = QTimer()
        self._crate_hover_timer.setSingleShot(True)
        self._crate_hover_timer.timeout.connect(self._on_crate_hover_expand)
        self._crate_drop_line: Optional[QFrame] = None  # created in _build_crate_panel

        # Pre-initialize so eventFilter never raises AttributeError
        # if events fire during _build_crate_panel() before _build_track_panel() runs
        self._track_table: Optional[_ReorderableTable] = None  # type: ignore[assignment]
        self._load_worker:   Optional[_CrateLoadWorker]       = None
        self._export_worker: Optional[_ExportCrateWorker]     = None
        self._export_dialog: Optional[_ExportProgressDialog]  = None

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_empty())   # 0
        self._stack.addWidget(self._build_main())    # 1
        self._stack.setCurrentIndex(0)

        # Connect reorder signal after widgets are built
        self._track_table.rows_reordered.connect(self._on_tracks_reordered)

    # ── Public API ────────────────────────────────────────────────────

    def load(self, inventory, library_path: Path) -> None:
        self._library_path = library_path
        self._inventory    = list(inventory)
        self._inventory_by_path = {}
        self._inventory_by_name = {}
        for rec in self._inventory:
            self._inventory_by_path[str(rec.path)] = rec
            self._inventory_by_name[rec.filename]  = rec

        self._edits = {}
        self._load_edits()
        self._load_crate_order()
        _clear_date_cache()  # ensure fresh parse when library changes
        self._session_genre = {}
        self._track_genre_overrides = {}
        self._load_session_genres()

        serato_dir = library_path / '_Serato_'

        # Load Serato add-dates from database V2 (cached after first load)
        if serato_dir.exists():
            self._add_dates = read_track_add_dates(serato_dir)
        else:
            self._add_dates = {}
        if not serato_dir.exists():
            self._stack.setCurrentIndex(0)
            return

        self._stack.setCurrentIndex(1)
        self._set_status('Loading crates…')
        QApplication.processEvents()

        # Save expanded state, selection, and scroll before rebuild (tab-switch preservation)
        expanded, selected = self._save_tree_state()
        if expanded:
            self._expanded_paths = expanded
        if selected:
            self._last_selected_path = selected
        self._last_scroll_pos = self._crate_tree.verticalScrollBar().value()

        inv_paths = {rec.path for rec in self._inventory}
        self._crate_library = CrateReader(serato_dir).read(inv_paths)

        # First visit: default to All Tracks. Return visit: restore prior selection.
        # Both reset to All Tracks on app restart (in-memory only, not persisted).
        restore_sel = self._last_selected_path or self._current_crate_path or _ALL_TRACKS_KEY
        self._rebuild_crate_tree(
            restore_expanded=self._expanded_paths if self._expanded_paths else None,
            restore_selected=restore_sel,
        )

        # Load tracks for the selected/default crate
        if restore_sel == _ALL_TRACKS_KEY:
            self._load_all_tracks()
        elif self._crate_library and restore_sel in self._crate_library.crates:
            self._current_crate_path = restore_sel
            self._load_crate_tracks(restore_sel)

        # Restore scroll position after tree is rebuilt
        QTimer.singleShot(0, lambda: self._crate_tree.verticalScrollBar().setValue(self._last_scroll_pos))
        self._set_status('')

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Reapply selection state after returning to the Crates tab
        if self._prev_selected_item and self._crate_delegate:
            self._on_tree_selection_changed(self._prev_selected_item, None)

    def _on_new_crate(self) -> None:
        self._crate_new(parent_path=None)

    def _on_new_smart_crate(self) -> None:
        _ov_alert(
            self, 'Smart Crates',
            'Smart Crates is a Pro feature.\n\n'
            'Create rule-based dynamic crates that automatically update '
            'based on metadata filters (e.g. genre, BPM, year).',
        )

    # ── Empty state ───────────────────────────────────────────────────

    def _build_empty(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(0)
        h = QLabel('Crate Manager')
        h.setProperty('role', 'heading')
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s = QLabel(
            'No Serato library found. Go to Settings to load a library '
            'that contains a _Serato_ folder.'
        )
        s.setProperty('role', 'muted')
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setWordWrap(True)
        layout.addWidget(h)
        layout.addSpacing(8)
        layout.addWidget(s)
        layout.addSpacing(16)
        load_btn = QPushButton('Load Library')
        load_btn.setFixedWidth(160)
        load_btn.setMinimumHeight(38)
        load_btn.setStyleSheet(
            f'QPushButton {{ background-color: {_TEAL}; color: #ffffff; '
            f'border: none; border-radius: 5px; padding: 6px 16px; '
            f'font-size: 13px; font-weight: 600; }}'
            f'QPushButton:hover {{ background-color: #38706a; }}'
            f'QPushButton:pressed {{ background-color: #2d6358; }}'
        )
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.clicked.connect(self.navigate_to_settings.emit)
        layout.addWidget(load_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── Main layout ───────────────────────────────────────────────────

    def _build_main(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(1)
        self._splitter.addWidget(self._build_crate_panel())
        self._splitter.addWidget(self._build_track_panel())
        self._splitter.setSizes([280, 900])

        layout.addWidget(self._splitter, stretch=1)
        layout.addWidget(self._build_status_bar())
        return w

    # ── Crate panel (left) ─────────────────────────────────────────────

    def _build_crate_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Search ────────────────────────────────────────────────────────
        self._crate_search = QLineEdit()
        self._crate_search.setPlaceholderText('Search crates…')
        self._crate_search.setClearButtonEnabled(True)
        self._crate_search.setFixedHeight(36)
        self._crate_search.setStyleSheet(
            f'QLineEdit {{ background: #252525; border: none; '
            f'border-bottom: 1px solid {_BORDER}; '
            f'color: {_CREAM}; padding: 0px 12px; }}'
        )
        self._crate_search.textChanged.connect(self._filter_crates)
        layout.addWidget(self._crate_search)

        # ── New crate buttons — fixed height matches track table header ──────
        btn_container = QWidget()
        btn_container.setFixedHeight(45)
        btn_row = QHBoxLayout(btn_container)
        btn_row.setContentsMargins(8, 5, 8, 5)
        btn_row.setSpacing(6)

        new_crate_btn = QPushButton('＋ New Crate')
        new_crate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_crate_btn.setStyleSheet(
            f'QPushButton {{ background: {_ORANGE}; color: #ffffff; font-size: 12px; '
            f'font-weight: 600; border: none; border-radius: 5px; padding: 0 10px; }}'
            f'QPushButton:hover {{ background: #b8682a; }}'
            f'QPushButton:pressed {{ background: #9c5520; }}'
        )
        new_crate_btn.clicked.connect(self._on_new_crate)
        btn_row.addWidget(new_crate_btn)

        smart_crate_btn = QPushButton('✦ Smart Crate')
        smart_crate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        smart_crate_btn.setStyleSheet(
            f'QPushButton {{ background: {_TEAL}; color: #ffffff; font-size: 12px; '
            f'font-weight: 600; border: none; border-radius: 5px; padding: 0 10px; }}'
            f'QPushButton:hover {{ background: #38706a; }}'
            f'QPushButton:pressed {{ background: #2d6358; }}'
        )
        smart_crate_btn.clicked.connect(self._on_new_smart_crate)
        btn_row.addWidget(smart_crate_btn)

        layout.addWidget(btn_container)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f'background: {_BORDER}; border: none;')
        layout.addWidget(sep)

        self._crate_tree = QTreeWidget()
        self._crate_delegate = CrateItemDelegate(self._crate_tree)
        self._crate_tree.setItemDelegate(self._crate_delegate)
        self._crate_tree.setColumnCount(1)
        self._crate_tree.setHeaderHidden(True)
        self._crate_tree.setRootIsDecorated(True)
        self._crate_tree.setIndentation(16)

        # Double-click expands/collapses; single click only selects
        self._crate_tree.setExpandsOnDoubleClick(True)

        # setDragDropMode(NoDragDrop) internally calls setAcceptDrops(false) and
        # propagates it to the viewport — so setAcceptDrops(True) must come after.
        self._crate_tree.setDragEnabled(False)
        self._crate_tree.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self._crate_tree.setDropIndicatorShown(False)
        self._crate_tree.setAcceptDrops(True)
        self._crate_tree.viewport().setAcceptDrops(True)

        from PyQt6.QtGui import QPalette
        pal = self._crate_tree.palette()
        pal.setColor(QPalette.ColorRole.Highlight,       QColor('#2F2F2F'))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor('#f1e3c8'))
        self._crate_tree.setPalette(pal)

        self._crate_tree.setStyleSheet("""
    QTreeWidget {
        background-color: #2F2F2F;
        border: none;
        border-right: 1px solid #444444;
        outline: none;
    }
    QTreeWidget::item {
        padding: 0px;
        border: none;
    }
    QTreeWidget::branch {
        background-color: #2F2F2F;
    }
    QTreeWidget::branch:has-children:!has-siblings:closed,
    QTreeWidget::branch:closed:has-children:has-siblings {
        image: url(none);
    }
    QTreeWidget::branch:open:has-children:!has-siblings,
    QTreeWidget::branch:open:has-children:has-siblings {
        image: url(none);
    }
    QTreeWidget::branch:has-siblings:!adjoins-item {
        border-left: 1px solid #444444;
        background: #2F2F2F;
    }
    QTreeWidget::branch:has-siblings:adjoins-item {
        border-left: 1px solid #444444;
        background: #2F2F2F;
    }
    QTreeWidget::branch:!has-siblings:adjoins-item {
        border-left: 1px solid #444444;
        background: #2F2F2F;
    }
""")
        self._crate_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._crate_tree.customContextMenuRequested.connect(self._on_crate_context_menu)
        self._crate_tree.itemClicked.connect(self._on_crate_clicked)
        self._crate_tree.currentItemChanged.connect(self._on_tree_selection_changed)
        self._crate_tree.itemExpanded.connect(lambda _: self._crate_tree.viewport().update())
        self._crate_tree.itemCollapsed.connect(lambda _: self._crate_tree.viewport().update())
        self._crate_tree.installEventFilter(self)
        self._crate_tree.viewport().installEventFilter(self)

        # Fix 3: teal drop indicator line for crate drag (created lazily on viewport)
        self._crate_drop_line = QFrame(self._crate_tree.viewport())
        self._crate_drop_line.setFrameShape(QFrame.Shape.HLine)
        self._crate_drop_line.setStyleSheet('background: #428175; border: none;')
        self._crate_drop_line.setFixedHeight(2)
        self._crate_drop_line.hide()

        layout.addWidget(self._crate_tree, stretch=1)
        return panel

    # ── Track panel (right) ────────────────────────────────────────────

    def _build_track_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._track_search = QLineEdit()
        self._track_search.setPlaceholderText('Search tracks by title, artist, or album…')
        self._track_search.setClearButtonEnabled(True)
        self._track_search.setFixedHeight(36)
        self._track_search.setStyleSheet(
            f'QLineEdit {{ background: #252525; border: none; '
            f'border-bottom: 1px solid {_BORDER}; '
            f'color: {_CREAM}; padding: 0px 12px; }}'
        )
        self._track_search.textChanged.connect(self._filter_tracks)
        layout.addWidget(self._track_search)

        self._track_table = _ReorderableTable()
        self._track_table.setColumnCount(len(_TRACK_HEADERS))
        self._track_table.setHorizontalHeaderLabels(_TRACK_HEADERS)

        hdr = self._track_table.horizontalHeader()
        hdr.setSectionsMovable(True)
        hdr.setSectionsClickable(True)
        hdr.setSortIndicatorShown(True)
        hdr.setStretchLastSection(False)
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hdr.sectionClicked.connect(self._on_header_clicked)

        self._track_table.verticalHeader().setVisible(False)
        self._track_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._track_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self._track_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._track_table.setAlternatingRowColors(True)
        self._track_table.setShowGrid(True)
        self._track_table.setStyleSheet('QTableWidget { gridline-color: #383838; }')

        from PyQt6.QtGui import QPalette
        _pal = self._track_table.palette()
        _pal.setColor(QPalette.ColorRole.Base,          QColor('#242424'))
        _pal.setColor(QPalette.ColorRole.AlternateBase, QColor('#2a2a2a'))
        self._track_table.setPalette(_pal)

        self._track_table.verticalHeader().setDefaultSectionSize(36)
        self._track_table.verticalHeader().setMinimumSectionSize(36)
        self._track_table.verticalHeader().setMaximumSectionSize(36)
        self._track_table.horizontalHeader().setFixedHeight(45)

        self._track_table.setSortingEnabled(True)
        self._track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._track_table.customContextMenuRequested.connect(self._on_track_context_menu)
        self._track_table.itemClicked.connect(self._on_track_clicked)
        self._track_table.itemDoubleClicked.connect(self._on_track_double_clicked)
        self._track_table.installEventFilter(self)
        self._track_table.viewport().installEventFilter(self)

        # Fix 5: smooth horizontal scrolling
        self._track_table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        saved_state = self._settings.value(_SETTINGS_KEY)
        if saved_state:
            self._track_table.horizontalHeader().restoreState(saved_state)

        # Persist column widths immediately whenever the user drags a resize handle
        self._track_table.horizontalHeader().sectionResized.connect(
            lambda _idx, _old, _new: self._settings.setValue(
                _SETTINGS_KEY,
                self._track_table.horizontalHeader().saveState(),
            )
        )

        # Loading overlay (shown while _CrateLoadWorker runs)
        load_overlay = QWidget()
        load_overlay.setStyleSheet('background: #242424;')
        ol = QVBoxLayout(load_overlay)
        ol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ol.setSpacing(12)

        self._load_label = QLabel('Loading…')
        self._load_label.setStyleSheet(
            f'color: {_CREAM}; font-size: 14px; background: transparent;'
        )
        self._load_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ol.addWidget(self._load_label)

        self._load_progress = QProgressBar()
        self._load_progress.setRange(0, 100)
        self._load_progress.setValue(0)
        self._load_progress.setFixedWidth(360)
        self._load_progress.setFixedHeight(8)
        self._load_progress.setTextVisible(False)
        self._load_progress.setStyleSheet(
            'QProgressBar { background: #383838; border: none; border-radius: 4px; }'
            f'QProgressBar::chunk {{ background: {_TEAL}; border-radius: 4px; }}'
        )
        ol.addWidget(self._load_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self._load_count = QLabel()
        self._load_count.setStyleSheet(
            f'color: {_MUTED}; font-size: 12px; background: transparent;'
        )
        self._load_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ol.addWidget(self._load_count)

        # Stack: 0 = table, 1 = loading overlay
        self._track_content_stack = QStackedWidget()
        self._track_content_stack.addWidget(self._track_table)
        self._track_content_stack.addWidget(load_overlay)
        self._track_content_stack.setCurrentIndex(0)

        layout.addWidget(self._track_content_stack, stretch=1)

        # Fix 5: set minimum width on TC_PATH column and minimum section size
        self._track_table.setColumnWidth(TC_PATH, 300)
        self._track_table.horizontalHeader().setMinimumSectionSize(30)

        return panel

    # ── Status bar ─────────────────────────────────────────────────────

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f'QFrame {{ background: {_PANEL}; border-top: 1px solid {_BORDER}; }}'
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 6, 16, 6)
        self._status_label = QLabel()
        self._status_label.setStyleSheet(f'color: {_MUTED}; font-size: 12px;')
        row.addWidget(self._status_label)
        row.addStretch()
        return bar

    # ── Status helper ──────────────────────────────────────────────────

    def _set_status(self, text: str, teal: bool = False) -> None:
        color = _TEAL if teal else _MUTED
        self._status_label.setStyleSheet(f'color: {color}; font-size: 12px;')
        self._status_label.setText(text)

    # ── Tree state save/restore ────────────────────────────────────────

    def _save_tree_state(self) -> tuple[set[str], Optional[str]]:
        expanded: set[str] = set()
        selected: Optional[str] = None

        def _walk(item: QTreeWidgetItem) -> None:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key and key != _ALL_TRACKS_KEY and item.isExpanded():
                expanded.add(key)
            for i in range(item.childCount()):
                _walk(item.child(i))

        root = self._crate_tree.invisibleRootItem()
        for i in range(root.childCount()):
            _walk(root.child(i))

        sel = self._crate_tree.selectedItems()
        if sel:
            selected = sel[0].data(0, Qt.ItemDataRole.UserRole)
        return expanded, selected

    def _restore_tree_state(self, expanded: set[str], selected: Optional[str]) -> None:
        def _walk(item: QTreeWidgetItem) -> None:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            if key and key in expanded:
                item.setExpanded(True)
            if key and key == selected:
                self._crate_tree.setCurrentItem(item)
            for i in range(item.childCount()):
                _walk(item.child(i))

        root = self._crate_tree.invisibleRootItem()
        for i in range(root.childCount()):
            _walk(root.child(i))

    # ── Refresh helper ─────────────────────────────────────────────────

    def _refresh(self, select: Optional[str] = None) -> None:
        """Reload crate library from disk, preserving tree expand state."""
        expanded, currently_selected = self._save_tree_state()
        target = select if select is not None else currently_selected

        if self._library_path:
            serato_dir = self._library_path / '_Serato_'
            inv_paths  = {rec.path for rec in self._inventory}
            self._crate_library = CrateReader(serato_dir).read(inv_paths)

        self._rebuild_crate_tree(restore_expanded=expanded, restore_selected=target)

        if target:
            if target == _ALL_TRACKS_KEY:
                self._load_all_tracks()
            elif self._crate_library and target in self._crate_library.crates:
                self._current_crate_path = target
                self._load_crate_tracks(target)

    # ── Crate tree population ──────────────────────────────────────────

    def _rebuild_crate_tree(
        self,
        restore_expanded: Optional[set[str]] = None,
        restore_selected: Optional[str] = None,
    ) -> None:
        # Clear stale selection state before rebuilding so no crate appears multi-selected
        self._prev_selected_item = None
        self._prev_parent_item   = None
        if self._crate_delegate:
            self._crate_delegate.clear_all_states()

        self._crate_tree.blockSignals(True)
        self._crate_tree.clear()

        if not self._crate_library:
            self._crate_tree.blockSignals(False)
            return

        # Debug: print first few crate names to verify Serato name parsing
        print(f'[CrateManager] {len(self._crate_library.crates)} crates loaded')
        for fp in list(self._crate_library.top_level)[:8]:
            c = self._crate_library.crates[fp]
            print(f'  {fp!r} → name={c.name!r}, tracks={c.track_count}')

        unique_paths: set[str] = set()
        for crate in self._crate_library.crates.values():
            unique_paths.update(crate.tracks)

        all_item = QTreeWidgetItem(self._crate_tree)
        all_label = f'All Tracks  ({len(unique_paths):,})'
        all_item.setText(0, all_label)
        all_item.setData(0, Qt.ItemDataRole.UserRole, _ALL_TRACKS_KEY)

        # Sort top-level by saved order (key "" in _crate_order dict)
        top_level = list(self._crate_library.top_level)
        if "" in self._crate_order:
            saved = self._crate_order[""]
            order_index = {p: i for i, p in enumerate(saved)}
            top_level.sort(key=lambda fp: order_index.get(fp, len(saved)))

        for full_path in top_level:
            self._add_crate_item(self._crate_tree.invisibleRootItem(), full_path)

        if restore_expanded is not None:
            self._restore_tree_state(restore_expanded, restore_selected)
        else:
            self._crate_tree.collapseAll()

        self._crate_tree.blockSignals(False)
        self._filter_crates(self._crate_search.text())

        # Reapply selection state after rebuild (old item refs are now invalid)
        self._prev_selected_item = None
        self._prev_parent_item   = None
        current = self._crate_tree.currentItem()
        if current:
            self._on_tree_selection_changed(current, None)

    def _total_crate_tracks(self, full_path: str) -> int:
        """Recursively sum track counts for a crate and all its sub-crates."""
        if not self._crate_library or full_path not in self._crate_library.crates:
            return 0
        crate = self._crate_library.crates[full_path]
        return crate.track_count + sum(
            self._total_crate_tracks(child) for child in crate.children
        )

    def _add_crate_item(self, parent_item: QTreeWidgetItem, full_path: str) -> None:
        if not self._crate_library or full_path not in self._crate_library.crates:
            return
        crate = self._crate_library.crates[full_path]
        total = self._total_crate_tracks(full_path)
        item  = QTreeWidgetItem(parent_item)
        label = f'{crate.name}  ({total:,})'
        item.setText(0, label)   # kept for text-based filtering
        item.setData(0, Qt.ItemDataRole.UserRole, full_path)
        # Use saved child order if available; otherwise fall back to CrateReader order
        children = list(crate.children)
        if full_path in self._crate_order:
            saved_ch = self._crate_order[full_path]
            ch_index = {p: i for i, p in enumerate(saved_ch)}
            children.sort(key=lambda p: ch_index.get(p, len(saved_ch)))
        for child_path in children:
            self._add_crate_item(item, child_path)
        has_ch = item.childCount() > 0
        if has_ch:
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )

    def _filter_crates(self, text: str) -> None:
        q = text.lower().strip()
        root = self._crate_tree.invisibleRootItem()
        self._apply_crate_filter(root, q)

    def _apply_crate_filter(self, parent: QTreeWidgetItem, q: str) -> bool:
        any_visible = False
        for i in range(parent.childCount()):
            item = parent.child(i)
            key  = item.data(0, Qt.ItemDataRole.UserRole)
            if key == _ALL_TRACKS_KEY:
                item.setHidden(bool(q))
                if not q:
                    any_visible = True
                continue
            full_path     = key or ''
            name          = full_path.split('/')[-1].lower()
            child_visible = self._apply_crate_filter(item, q)
            own_match     = not q or q in name
            visible       = own_match or child_visible
            item.setHidden(not visible)
            if visible:
                any_visible = True
        return any_visible

    def _filter_tracks(self, text: str) -> None:
        q = text.lower().strip()
        for row in range(self._track_table.rowCount()):
            if not q:
                self._track_table.setRowHidden(row, False)
                continue
            title_cell  = self._track_table.item(row, TC_TITLE)
            artist_cell = self._track_table.item(row, TC_ARTIST)
            album_cell  = self._track_table.item(row, TC_ALBUM)
            match = any(
                q in (cell.text().lower() if cell else '')
                for cell in (title_cell, artist_cell, album_cell)
            )
            self._track_table.setRowHidden(row, not match)

    # ── Crate tree selection states ────────────────────────────────────

    def _on_tree_selection_changed(self, current: QTreeWidgetItem, _previous) -> None:
        if not current or not self._crate_delegate:
            return

        # Reset previous states
        if self._prev_selected_item:
            prev_path = self._prev_selected_item.data(0, Qt.ItemDataRole.UserRole) or ''
            self._crate_delegate.set_item_state(prev_path, CrateItemDelegate.STATE_A)
        if self._prev_parent_item:
            prev_parent_path = self._prev_parent_item.data(0, Qt.ItemDataRole.UserRole) or ''
            self._crate_delegate.set_item_state(prev_parent_path, CrateItemDelegate.STATE_A)
        self._prev_selected_item = None
        self._prev_parent_item   = None

        current_path = current.data(0, Qt.ItemDataRole.UserRole) or ''
        parent_item  = current.parent()

        # Debug
        crate_name  = current_path.split('/')[-1]
        parent_name = (parent_item.data(0, Qt.ItemDataRole.UserRole) or '').split('/')[-1] if parent_item else 'None'

        if parent_item and parent_item.data(0, Qt.ItemDataRole.UserRole):
            self._crate_delegate.set_item_state(current_path, CrateItemDelegate.STATE_D)
            parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole) or ''
            self._crate_delegate.set_item_state(parent_path, CrateItemDelegate.STATE_C)
            self._prev_parent_item = parent_item
        else:
            self._crate_delegate.set_item_state(current_path, CrateItemDelegate.STATE_B)

        self._prev_selected_item = current

    # ── Crate click → load tracks ──────────────────────────────────────

    def _on_crate_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            return
        self._current_crate_path = key
        if key == _ALL_TRACKS_KEY:
            self._track_search.setPlaceholderText('Search all tracks by title, artist, or album…')
            self._load_all_tracks()
        else:
            name = (
                self._crate_library.crates[key].name
                if self._crate_library and key in self._crate_library.crates
                else key.split('/')[-1]
            )
            self._track_search.setPlaceholderText(
                f'Searching "{name}" — select All Tracks to search your full library…'
            )
            self._load_crate_tracks(key)

    def _load_all_tracks(self) -> None:
        if not self._crate_library:
            return
        seen: set[str]       = set()
        track_paths: list[str] = []
        for crate in self._crate_library.crates.values():
            for tp in crate.tracks:
                if tp not in seen:
                    seen.add(tp)
                    track_paths.append(tp)
        self._start_load_worker(track_paths, 'All Tracks')

    def _collect_tracks_recursive(self, crate_path: str) -> list[str]:
        """Return deduplicated track paths from crate + all sub-crates at any depth."""
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return []
        crate  = self._crate_library.crates[crate_path]
        seen:   set[str]  = set()
        result: list[str] = []
        for tp in crate.tracks:
            if tp not in seen:
                seen.add(tp)
                result.append(tp)
        for child_path in crate.children:
            for tp in self._collect_tracks_recursive(child_path):
                if tp not in seen:
                    seen.add(tp)
                    result.append(tp)
        return result

    def _load_crate_tracks(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate  = self._crate_library.crates[crate_path]
        # Show combined tracks for parent crates (own tracks + all descendants)
        tracks = self._collect_tracks_recursive(crate_path) if crate.children else list(crate.tracks)
        self._start_load_worker(tracks, crate.name)

    def _total_duration(self, track_paths: list[str]) -> str:
        total_secs = 0.0
        for tp in track_paths:
            rec = self._resolve_track(tp)
            if rec and rec.duration:
                total_secs += rec.duration
        if total_secs == 0:
            return '—'
        hours   = int(total_secs // 3600)
        minutes = int((total_secs % 3600) // 60)
        seconds = int(total_secs % 60)
        if hours:
            return f'{hours}h {minutes}m {seconds}s'
        return f'{minutes}m {seconds}s'

    # ── Worker: launch / progress / finish ────────────────────────────

    def _start_load_worker(self, track_paths: list, label: str) -> None:
        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.progress.disconnect()
            self._load_worker.finished.disconnect()
            self._load_worker.errored.disconnect()
            self._load_worker.cancel()
            self._load_worker = None

        if not track_paths:
            self._populate_track_table([])
            self._status_label.setText('')
            return

        self._load_label.setText(label)
        self._load_progress.setValue(0)
        self._load_count.setText(f'0 of {len(track_paths):,}')
        self._track_content_stack.setCurrentIndex(1)
        self._track_search.setEnabled(False)

        self._load_worker = _CrateLoadWorker(
            track_paths=list(track_paths),
            inventory_by_path=dict(self._inventory_by_path),
            inventory_by_name=dict(self._inventory_by_name),
            edits=dict(self._edits),
            session_genre=dict(self._session_genre),
            track_genre_overrides=dict(self._track_genre_overrides),
            add_dates=self._add_dates,
            library_path=self._library_path,
            label=label,
            parent=self,
        )
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.errored.connect(self._on_load_errored)
        self._load_worker.start()

    def _on_load_progress(self, done: int, total: int, _label: str) -> None:
        pct = int(done / total * 100) if total else 0
        self._load_progress.setValue(pct)
        self._load_count.setText(f'{done:,} of {total:,}')

    def _on_load_finished(self, payload: dict) -> None:
        rows           = payload['rows']
        track_paths    = payload['track_paths']
        label          = payload['label']
        total          = payload['total']
        resolved_count = payload['resolved_count']
        dur_secs       = payload['total_dur_secs']

        self._populate_track_table_from_rows(rows, track_paths)

        total_dur = _fmt_dur(dur_secs) if dur_secs else '—'
        if label == 'All Tracks':
            unresolved = total - resolved_count
            self._status_label.setText(
                f'All Tracks  ·  {total:,} tracks  ·  {total_dur}'
                f'  ·  {resolved_count:,} resolved, {unresolved:,} unresolved'
            )
        else:
            self._status_label.setText(
                f'{label}  ·  {total:,} tracks  ·  {total_dur}'
            )

        self._track_content_stack.setCurrentIndex(0)
        self._track_search.setEnabled(True)
        self._load_worker = None

    def _on_load_errored(self, msg: str) -> None:
        self._track_content_stack.setCurrentIndex(0)
        self._track_search.setEnabled(True)
        self._load_worker = None
        _ov_alert(self, 'Load Error', f'Failed to load tracks:\n{msg}')

    # ── Track table population ─────────────────────────────────────────

    def _populate_track_table_from_rows(
        self, rows: list, track_paths: list
    ) -> None:
        self._track_search.blockSignals(True)
        self._track_search.clear()
        self._track_search.blockSignals(False)
        self._track_table.setSortingEnabled(False)
        self._track_table.setRowCount(0)
        self._track_table.setRowCount(len(rows))
        self._original_track_paths = list(track_paths)

        for row_idx, row in enumerate(rows):
            if row['resolved']:
                self._populate_resolved_row_from_data(row_idx, row)
            else:
                self._populate_unresolved_row(row_idx, row['track_path'])

        self._track_table.setSortingEnabled(True)
        self._track_table.sortByColumn(self._sort_col, self._sort_order)
        if not self._settings.value(_SETTINGS_KEY):
            self._size_pos_column(len(rows))
            QTimer.singleShot(100, self._enforce_min_col_widths)

    def _populate_resolved_row_from_data(self, row: int, d: dict) -> None:
        tp       = d['track_path']
        path_str = d['path_str']

        pos_cell = _NumericItem(str(row + 1))
        pos_cell.setData(Qt.ItemDataRole.UserRole,     row + 1)
        pos_cell.setData(Qt.ItemDataRole.UserRole + 1, tp)
        self._track_table.setItem(row, TC_POS, pos_cell)

        values = [
            d['title'], d['artist'], d['album'], d['dur'], d['genre'],
            d['tags'], d['bpm'], d['date_str'], d['fmt'], d['year'],
            d['bitrate'], d['comment'], d['path'],
        ]
        for i, val in enumerate(values):
            col  = i + 1
            cell = QTableWidgetItem(val)
            cell.setData(Qt.ItemDataRole.UserRole,     path_str)
            cell.setData(Qt.ItemDataRole.UserRole + 1, tp)
            if col == TC_TITLE:
                cell.setIcon(_get_note_icon())
            if col == TC_DATE and d['date_ts']:
                cell = _NumericItem(val)
                cell.setData(Qt.ItemDataRole.UserRole,     d['date_ts'])
                cell.setData(Qt.ItemDataRole.UserRole + 1, tp)
                self._track_table.setItem(row, col, cell)
                continue
            self._track_table.setItem(row, col, cell)

        if d['comment']:
            self._track_table.item(row, TC_COMMENT).setToolTip(d['comment'])

    def _populate_track_table(self, track_paths: list[str]) -> None:
        self._track_search.blockSignals(True)
        self._track_search.clear()
        self._track_search.blockSignals(False)
        self._track_table.setSortingEnabled(False)
        self._track_table.setRowCount(0)
        self._track_table.setRowCount(len(track_paths))
        self._original_track_paths = list(track_paths)  # preserve for removal

        for row, tp in enumerate(track_paths):
            rec = self._resolve_track(tp)
            if rec is not None:
                self._populate_resolved_row(row, tp, rec)
            else:
                self._populate_unresolved_row(row, tp)

        self._track_table.setSortingEnabled(True)
        self._track_table.sortByColumn(self._sort_col, self._sort_order)
        # Only auto-size columns on first-ever use; once the user has set their
        # preferred widths those are saved and we leave them alone.
        if not self._settings.value(_SETTINGS_KEY):
            self._size_pos_column(len(track_paths))
            QTimer.singleShot(100, self._enforce_min_col_widths)

    def _populate_resolved_row(self, row: int, track_path: str, rec) -> None:
        edits = self._edits.get(str(rec.path), {})

        path_str = str(rec.path)
        artist_key = f'__artist__{rec.artist}' if rec.artist else ''
        title  = edits.get('title',   rec.title  or '')
        artist = edits.get('reassign_artist', rec.artist or '')
        album  = edits.get('album',   rec.album  or '')
        genre  = (
            edits.get('genre')
            or (self._edits.get(artist_key, {}).get('genre') if artist_key else None)
            or self._track_genre_overrides.get(path_str)
            or self._session_genre.get(rec.artist or '')
            or rec.genre
            or '—'
        )
        tags    = edits.get('tags',    '')
        bpm     = edits.get('bpm',     str(round(rec.bpm)) if rec.bpm else '—')
        year    = edits.get('year',    rec.year    or '—')
        comment = edits.get('comment', rec.comment or '')
        dur     = _fmt_dur(rec.duration)
        fmt     = rec.extension.lstrip('.').upper() if rec.extension else '—'
        bitrate = f'{rec.bitrate} kbps' if rec.bitrate else '—'
        path    = str(rec.path)

        pos_cell = _NumericItem(str(row + 1))
        pos_cell.setData(Qt.ItemDataRole.UserRole, row + 1)    # integer for numeric sort
        pos_cell.setData(Qt.ItemDataRole.UserRole + 1, track_path)
        self._track_table.setItem(row, TC_POS, pos_cell)

        # Resolve Date Added from Serato database V2.
        # database V2 stores relative paths; rec.path is absolute — strip library root.
        # The reader normalises U+F022 → ' : ', so rel_key uses real filesystem chars.
        add_dt  = None
        rel_key = None
        if self._add_dates and self._library_path:
            try:
                rel_key = Path(path).relative_to(self._library_path).as_posix()
                add_dt  = self._add_dates.get(rel_key)
                # Fallback: try with Serato's private-use char in place of ' : '
                if add_dt is None:
                    add_dt = self._add_dates.get(rel_key.replace(' : ', ''))
            except ValueError:
                pass  # path not under library_path — leave add_dt as None

        date_str = add_dt.strftime('%Y-%m-%d') if add_dt else '—'
        date_ts  = int(add_dt.timestamp()) if add_dt else 0

        values = [title, artist, album, dur, genre, tags, bpm, date_str, fmt, year, bitrate, comment, path]
        for i, val in enumerate(values):
            col  = i + 1  # shift by 1 due to TC_POS
            cell = QTableWidgetItem(val)
            cell.setData(Qt.ItemDataRole.UserRole, path)
            cell.setData(Qt.ItemDataRole.UserRole + 1, track_path)  # original crate path
            if col == TC_TITLE:
                cell.setIcon(_get_note_icon())
            if col == TC_DATE and date_ts:
                # Swap for a _NumericItem so Qt sorts by the integer timestamp
                cell = _NumericItem(val)
                cell.setData(Qt.ItemDataRole.UserRole,     date_ts)    # numeric sort key
                cell.setData(Qt.ItemDataRole.UserRole + 1, track_path)
                # (UserRole is overwritten below by the general path assignment — re-set here)
                self._track_table.setItem(row, col, cell)
                continue
            self._track_table.setItem(row, col, cell)

        if comment:
            self._track_table.item(row, TC_COMMENT).setToolTip(comment)

    def _populate_unresolved_row(self, row: int, track_path: str) -> None:
        filename = Path(track_path).name
        muted    = QBrush(QColor(_MUTED))

        # TC_POS cell (col 0)
        pos_cell = _NumericItem(str(row + 1))
        pos_cell.setData(Qt.ItemDataRole.UserRole, row + 1)    # integer for numeric sort
        pos_cell.setData(Qt.ItemDataRole.UserRole + 1, track_path)
        pos_cell.setForeground(muted)
        f = pos_cell.font()
        f.setItalic(True)
        pos_cell.setFont(f)
        self._track_table.setItem(row, TC_POS, pos_cell)

        values = [
            filename, '', '', '—', '—', '', '—', '—', '—', '—', '—',
            '', 'Not found in library',
        ]
        for i, val in enumerate(values):
            col  = i + 1  # shift by 1 due to TC_POS
            cell = QTableWidgetItem(val)
            cell.setData(Qt.ItemDataRole.UserRole, track_path)
            cell.setData(Qt.ItemDataRole.UserRole + 1, track_path)
            cell.setForeground(muted)
            f = cell.font()
            f.setItalic(True)
            cell.setFont(f)
            if col == TC_TITLE:
                cell.setIcon(_get_note_icon())
            self._track_table.setItem(row, col, cell)

    # ── Track click / selection ────────────────────────────────────────

    def _on_track_clicked(self, item: QTableWidgetItem) -> None:
        row       = item.row()
        path_item = self._track_table.item(row, TC_PATH)
        if not path_item:
            return
        raw_path      = path_item.text()
        rec           = self._resolve_track(raw_path)
        resolved_path = str(rec.path) if rec else raw_path
        self.track_selected.emit(resolved_path)
        self.album_art_requested.emit(resolved_path)

    # ── Inline editing ─────────────────────────────────────────────────

    def _on_track_double_clicked(self, item: QTableWidgetItem) -> None:
        col = item.column()
        if col not in _EDITABLE_COLS:
            return
        row       = item.row()
        path_item = self._track_table.item(row, TC_PATH)
        if not path_item:
            return
        rec = self._resolve_track(path_item.text())
        if rec is None:
            return

        self._commit_editor()

        current = item.text()
        editor  = QLineEdit(current)
        editor.selectAll()
        editor.setMinimumHeight(26)

        self._edit_widget   = editor
        self._edit_row      = row
        self._edit_col      = col
        self._edit_original = current

        _orig_kp = editor.keyPressEvent
        def _handle_key(event):
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_editor()
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._commit_editor()
            else:
                _orig_kp(event)
        editor.keyPressEvent = _handle_key  # type: ignore[method-assign]

        editor.editingFinished.connect(self._commit_editor)

        self._track_table.setCellWidget(row, col, editor)
        editor.setFocus()

    def _commit_editor(self) -> None:
        if self._edit_widget is None:
            return
        row, col, widget, original = (
            self._edit_row, self._edit_col,
            self._edit_widget, self._edit_original,
        )
        new_val = widget.text()

        self._edit_widget   = None
        self._edit_row      = -1
        self._edit_col      = -1
        self._edit_original = ''

        try:
            self._track_table.removeCellWidget(row, col)
        except Exception:
            pass

        if new_val == original:
            return

        path_item = self._track_table.item(row, TC_PATH)
        if not path_item:
            return
        rec = self._resolve_track(path_item.text())
        if rec is None:
            return

        field_name = _EDITABLE_FIELDS.get(col)
        if not field_name:
            return

        if self._undo_manager:
            cmd = EditTrackMetadataCommand(
                self, str(rec.path), field_name, col, original, new_val,
            )
            self._undo_manager.push(cmd)  # execute() updates cell + saves
        else:
            cell = self._track_table.item(row, col)
            if cell:
                cell.setText(new_val)
            self._edits.setdefault(str(rec.path), {})[field_name] = new_val
            self._save_edits()
            self._flash_row(row)

    def _cancel_editor(self) -> None:
        if self._edit_widget is None:
            return
        row, col = self._edit_row, self._edit_col
        self._edit_widget   = None
        self._edit_row      = -1
        self._edit_col      = -1
        self._edit_original = ''
        try:
            self._track_table.removeCellWidget(row, col)
        except Exception:
            pass

    def _flash_row(self, row: int) -> None:
        teal  = QBrush(QColor(_TEAL))
        cream = QBrush(QColor(_CREAM))
        for col in range(self._track_table.columnCount()):
            cell = self._track_table.item(row, col)
            if cell:
                cell.setForeground(teal)
        def _restore(r=row):
            for c in range(self._track_table.columnCount()):
                it = self._track_table.item(r, c)
                if it:
                    it.setForeground(cream)
        QTimer.singleShot(1500, _restore)

    def eventFilter(self, obj, event) -> bool:
        # Guard: _track_table is pre-initialized to None and assigned in _build_track_panel.
        # If events fire during _build_crate_panel() before that happens, bail out safely.
        if self._track_table is None:
            return super().eventFilter(obj, event)

        # 1. Click-away editor close (existing — track_table viewport)
        if (event.type() == QEvent.Type.MouseButtonPress
                and self._edit_widget is not None
                and obj is self._track_table.viewport()):
            click_pos = event.position().toPoint()
            if not self._edit_widget.geometry().contains(click_pos):
                self._commit_editor()
                return False

        # 2. Key events on track table (Delete key)
        elif obj is self._track_table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                selected_rows = sorted({idx.row() for idx in self._track_table.selectedIndexes()})
                if selected_rows:
                    self._confirm_remove_tracks(selected_rows)
                return True

        # 3. Key events on crate tree (Delete key)
        elif obj is self._crate_tree and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                sel = self._crate_tree.selectedItems()
                if sel:
                    key = sel[0].data(0, Qt.ItemDataRole.UserRole)
                    if key and key != _ALL_TRACKS_KEY:
                        self._confirm_delete_crate(key)
                return True

        # 5. Crate tree viewport: track-table drag onto crate OR manual crate drag
        elif obj is self._crate_tree.viewport():
            # --- Tracks-from-table drop (Qt DragDrop events from track table) ---
            if event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasFormat(_TRACKS_MIME):
                    event.acceptProposedAction()
                    return True
                event.ignore()
                return True

            elif event.type() == QEvent.Type.DragMove:
                if event.mimeData().hasFormat(_TRACKS_MIME):
                    pt     = event.position().toPoint()
                    target = self._crate_tree.itemAt(pt)
                    if target:
                        key = target.data(0, Qt.ItemDataRole.UserRole)
                        if key and key != _ALL_TRACKS_KEY:
                            if key != self._track_drop_target_key:
                                if self._track_drop_target_key:
                                    self._crate_delegate.set_item_state(
                                        self._track_drop_target_key,
                                        self._track_drop_prior_state)
                                self._track_drop_prior_state = \
                                    self._crate_delegate.get_item_state(key)
                                self._track_drop_target_key = key
                                self._crate_delegate.set_item_state(key, CrateItemDelegate.STATE_E)
                            event.acceptProposedAction()
                            return True
                # Not over a valid crate — clear any active highlight
                if self._track_drop_target_key:
                    self._crate_delegate.set_item_state(
                        self._track_drop_target_key, self._track_drop_prior_state)
                    self._track_drop_target_key  = None
                    self._track_drop_prior_state = CrateItemDelegate.STATE_A
                event.ignore()
                return True

            elif event.type() == QEvent.Type.DragLeave:
                if self._track_drop_target_key:
                    self._crate_delegate.set_item_state(
                        self._track_drop_target_key, self._track_drop_prior_state)
                    self._track_drop_target_key  = None
                    self._track_drop_prior_state = CrateItemDelegate.STATE_A
                return False

            elif event.type() == QEvent.Type.Drop:
                pt     = event.position().toPoint()
                target = self._crate_tree.itemAt(pt)
                if self._track_drop_target_key:
                    self._crate_delegate.set_item_state(
                        self._track_drop_target_key, self._track_drop_prior_state)
                    self._track_drop_target_key  = None
                    self._track_drop_prior_state = CrateItemDelegate.STATE_A
                if event.mimeData().hasFormat(_TRACKS_MIME):
                    if target:
                        key = target.data(0, Qt.ItemDataRole.UserRole)
                        if key and key != _ALL_TRACKS_KEY:
                            raw   = bytes(event.mimeData().data(_TRACKS_MIME)).decode('utf-8')
                            paths = json.loads(raw)
                            self._add_tracks_to_crate(key, paths)
                            event.acceptProposedAction()
                            return True
                    event.ignore()
                    return True
                event.ignore()
                return True

            # --- Manual crate drag (Fix 3) ---
            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    item = self._crate_tree.itemAt(event.position().toPoint())
                    if item:
                        key = item.data(0, Qt.ItemDataRole.UserRole)
                        if key and key != _ALL_TRACKS_KEY:
                            self._crate_drag_item   = item
                            self._crate_drag_start  = event.position().toPoint()
                            self._crate_drag_active = False
                return False  # allow normal selection processing

            elif event.type() == QEvent.Type.MouseMove:
                if (self._crate_drag_item and self._crate_drag_start
                        and not self._crate_drag_active):
                    dist = (event.position().toPoint() - self._crate_drag_start).manhattanLength()
                    if dist > 8:
                        self._crate_drag_active = True
                        self._crate_tree.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                if self._crate_drag_active and self._crate_drag_item:
                    self._update_crate_drop_indicator(event.position().toPoint())
                    return True
                return False

            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self._crate_drag_active and self._crate_drag_item:
                    if self._crate_drop_line:
                        self._crate_drop_line.hide()
                    self._crate_hover_timer.stop()
                    self._crate_tree.viewport().unsetCursor()
                    self._execute_crate_drop(event.position().toPoint())
                self._crate_drag_item   = None
                self._crate_drag_active = False
                self._crate_drag_start  = None
                self._crate_hover_item  = None
                return False

        return super().eventFilter(obj, event)

    # ── Manual crate drag helpers (Fix 3) ─────────────────────────────

    def _update_crate_drop_indicator(self, pos: QPoint) -> None:
        """Position the teal drop indicator line for crate drag."""
        if not self._crate_drop_line:
            return

        target = self._crate_tree.itemAt(pos)
        vp     = self._crate_tree.viewport()

        if target is None:
            # Below all items — append to end
            count = self._crate_tree.topLevelItemCount()
            if count > 0:
                last_item = self._crate_tree.topLevelItem(count - 1)
                rect      = self._crate_tree.visualItemRect(last_item)
                y         = rect.bottom()
            else:
                y = 0
            self._crate_drop_line.setGeometry(0, max(0, y - 1), vp.width(), 2)
            self._crate_drop_line.show()
            self._crate_drop_line.raise_()
            # Stop hover timer — not hovering over an item
            self._crate_hover_timer.stop()
            self._crate_hover_item = None
            return

        target_key = target.data(0, Qt.ItemDataRole.UserRole)
        drag_key   = self._crate_drag_item.data(0, Qt.ItemDataRole.UserRole) if self._crate_drag_item else None

        # Don't drop onto self or into own subtree
        if target_key == drag_key or (drag_key and target_key and target_key.startswith(drag_key + '/')):
            self._crate_drop_line.hide()
            self._crate_hover_timer.stop()
            self._crate_hover_item = None
            return

        rect     = self._crate_tree.visualItemRect(target)
        top_zone = rect.top() + rect.height() // 3
        bot_zone = rect.bottom() - rect.height() // 3

        if pos.y() < top_zone:
            # Top third → insert BEFORE (sibling reorder)
            y = rect.top()
            self._crate_drop_line.setGeometry(0, max(0, y - 1), vp.width(), 2)
            self._crate_drop_line.show()
            self._crate_drop_line.raise_()
            self._crate_hover_timer.stop()
            self._crate_hover_item = None
        elif pos.y() > bot_zone:
            # Bottom third → insert AFTER (sibling reorder)
            y = rect.bottom()
            self._crate_drop_line.setGeometry(0, max(0, y - 1), vp.width(), 2)
            self._crate_drop_line.show()
            self._crate_drop_line.raise_()
            self._crate_hover_timer.stop()
            self._crate_hover_item = None
        else:
            # Middle third → reparent zone: show teal border on target, start timer
            self._crate_drop_line.hide()
            if target is not self._crate_hover_item:
                self._crate_hover_timer.stop()
                self._crate_hover_item = target
                self._crate_hover_timer.start(1500)

    def _execute_crate_drop(self, pos: QPoint) -> None:
        """Execute the crate drop: reorder siblings."""
        if not self._crate_drag_item:
            return

        drag_key = self._crate_drag_item.data(0, Qt.ItemDataRole.UserRole)
        if not drag_key or drag_key == _ALL_TRACKS_KEY:
            return

        target = self._crate_tree.itemAt(pos)

        is_sub = '/' in drag_key   # True when dragged item is a sub-crate

        if target is None:
            # Dropped below all items — move to end of top-level
            self._crate_reorder_sibling(drag_key, None, promote_to_top=is_sub)
            return

        target_key = target.data(0, Qt.ItemDataRole.UserRole)
        if not target_key or target_key == drag_key:
            return

        # Don't allow dropping into own subtree
        if target_key.startswith(drag_key + '/'):
            return

        rect     = self._crate_tree.visualItemRect(target)
        top_zone = rect.top() + rect.height() // 3
        bot_zone = rect.bottom() - rect.height() // 3

        # Middle third = reparent into target crate (or its parent if target is a sub-crate)
        if top_zone <= pos.y() <= bot_zone:
            if target_key and target_key != _ALL_TRACKS_KEY:
                if '/' in target_key:
                    # Target is itself a sub-crate — reparent under its parent
                    parent_path = '/'.join(target_key.split('/')[:-1])
                    self._crate_reparent(drag_key, parent_path)
                else:
                    self._crate_reparent(drag_key, target_key)
            return

        # Determine whether target is a sub-crate and get its parent path
        target_is_sub      = '/' in target_key
        target_parent_path = '/'.join(target_key.split('/')[:-1]) if target_is_sub else None
        drag_parent_path   = '/'.join(drag_key.split('/')[:-1]) if is_sub else None
        same_parent        = target_is_sub and (drag_parent_path == target_parent_path)

        # Promotion: top-level drag dropped beside another top-level item
        target_is_toplevel = target.parent() is None
        promote            = is_sub and target_is_toplevel

        if pos.y() < top_zone:
            # Insert BEFORE target
            if target_is_sub and not same_parent:
                # Dropping before a sub-crate that isn't our sibling →
                # reparent drag under that sub-crate's parent
                self._crate_reparent(drag_key, target_parent_path)
            else:
                self._crate_reorder_sibling(drag_key, target_key, promote_to_top=promote)
        else:
            # Insert AFTER target — find the item after target at same level
            parent_item = target.parent()
            if parent_item:
                idx = parent_item.indexOfChild(target)
                next_idx = idx + 1
                if next_idx < parent_item.childCount():
                    next_item = parent_item.child(next_idx)
                    next_key  = next_item.data(0, Qt.ItemDataRole.UserRole)
                    next_is_sub = '/' in next_key if next_key else False
                    next_same   = next_is_sub and (drag_parent_path == '/'.join(next_key.split('/')[:-1]))
                    if next_is_sub and not next_same:
                        self._crate_reparent(drag_key, '/'.join(next_key.split('/')[:-1]))
                    else:
                        self._crate_reorder_sibling(drag_key, next_key, promote_to_top=promote)
                else:
                    # After last child — reparent into the same parent if needed
                    if target_is_sub and not same_parent:
                        self._crate_reparent(drag_key, target_parent_path)
                    else:
                        self._crate_reorder_sibling(drag_key, None, promote_to_top=promote)
            else:
                # Top-level target
                root = self._crate_tree.invisibleRootItem()
                idx  = root.indexOfChild(target)
                next_idx = idx + 1
                if next_idx < root.childCount():
                    next_item = root.child(next_idx)
                    next_key  = next_item.data(0, Qt.ItemDataRole.UserRole)
                    if next_key == _ALL_TRACKS_KEY:
                        self._crate_reorder_sibling(drag_key, None, promote_to_top=promote)
                    else:
                        self._crate_reorder_sibling(drag_key, next_key, promote_to_top=promote)
                else:
                    self._crate_reorder_sibling(drag_key, None, promote_to_top=promote)

    def _crate_reorder_sibling(
        self,
        drag_path: str,
        insert_before_path: Optional[str],
        promote_to_top: bool = False,
    ) -> None:
        """Reorder drag_path among its siblings; optionally promote a sub-crate to top level."""
        if not self._crate_library:
            return

        crate_name = drag_path.split('/')[-1]

        # Promote: sub-crate dragged to top level — rename file first
        if promote_to_top and '/' in drag_path:
            writer = self._writer()
            if not writer:
                return
            result = writer.rename_crate(drag_path, crate_name)
            if not result.success:
                _ov_alert(self, 'Promote Crate', f'Failed: {result.error}')
                return
            # Update _crate_order to remove from old parent
            old_parent = '/'.join(drag_path.split('/')[:-1])
            if old_parent in self._crate_order:
                self._crate_order[old_parent] = [
                    p for p in self._crate_order[old_parent] if p != drag_path
                ]
            drag_path = crate_name

        # Determine the order key (parent path or "" for top-level)
        if '/' in drag_path:
            order_key = '/'.join(drag_path.split('/')[:-1])
            if order_key in self._crate_library.crates:
                siblings = list(self._crate_library.crates[order_key].children)
            else:
                siblings = []
        else:
            order_key = ""
            siblings  = list(self._crate_library.top_level)

        current = self._crate_order.get(order_key, siblings)
        captured_current = list(current)
        order   = [p for p in current if p != drag_path]

        # Ensure all siblings are present
        existing = set(order)
        for p in siblings:
            if p not in existing and p != drag_path:
                order.append(p)

        if insert_before_path is None:
            order.append(drag_path)
        else:
            try:
                order.insert(order.index(insert_before_path), drag_path)
            except ValueError:
                order.append(drag_path)

        if self._undo_manager:
            cmd = ReorderCratesCommand(self, order_key, captured_current, list(order))
            self._undo_manager.push(cmd)
            if promote_to_top:
                self._set_status(f'Moved "{crate_name}" to top level', teal=True)
            else:
                self._set_status(f'Moved "{crate_name}"', teal=True)
            return
        # fallback: existing direct code
        self._crate_order[order_key] = order
        self._save_crate_order()
        self._refresh(select=drag_path)
        if promote_to_top:
            self._set_status(f'Moved "{crate_name}" to top level', teal=True)
        else:
            self._set_status(f'Moved "{crate_name}"', teal=True)

    def _crate_reparent(self, drag_path: str, new_parent_path: str) -> None:
        """Move crate under a new parent via CrateWriter.rename_crate."""
        if not self._crate_library or drag_path not in self._crate_library.crates:
            return
        crate_name = drag_path.split('/')[-1]
        new_path   = f'{new_parent_path}/{crate_name}'
        if new_path == drag_path:
            return
        writer = self._writer()
        if not writer:
            return
        if self._undo_manager:
            cmd = ReparentCrateCommand(self, drag_path, new_parent_path)
            self._undo_manager.push(cmd)
            target_display = new_parent_path.split('/')[-1]
            self._set_status(f'Moved "{crate_name}" into "{target_display}"', teal=True)
            return
        # fallback: existing direct code
        result = writer.rename_crate(drag_path, new_path)
        if result.success:
            self._refresh(select=new_path)
            target_display = new_parent_path.split('/')[-1]
            self._set_status(f'Moved "{crate_name}" into "{target_display}"', teal=True)
        else:
            _ov_alert(self, 'Move Crate', f'Failed: {result.error}')

    def _on_crate_hover_expand(self) -> None:
        """Called when hover timer fires — expand the hovered crate."""
        if self._crate_hover_item:
            self._crate_hover_item.setExpanded(True)

    # ── Track path resolution ──────────────────────────────────────────

    def _resolve_track(self, track_path: str):
        if track_path in self._inventory_by_path:
            return self._inventory_by_path[track_path]

        if self._library_path:
            candidate = self._library_path / track_path
            key = str(candidate)
            if key in self._inventory_by_path:
                return self._inventory_by_path[key]

        rec = self._inventory_by_name.get(Path(track_path).name)
        if rec:
            return rec

        stem = Path(track_path).stem.lower()
        if len(stem) >= 5:
            for candidate in self._inventory_by_name.values():
                cs = Path(candidate.filename).stem.lower()
                if cs == stem or stem in cs or cs in stem:
                    return candidate

        return None

    # ── Crate context menu ─────────────────────────────────────────────

    def _on_crate_context_menu(self, pos) -> None:
        item = self._crate_tree.itemAt(pos)
        if item is None:
            menu    = QMenu(self)
            new_act = menu.addAction('New Crate…')
            action  = menu.exec(self._crate_tree.viewport().mapToGlobal(pos))
            if action == new_act:
                self._crate_new(parent_path=None)
            return

        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key == _ALL_TRACKS_KEY:
            return

        menu       = QMenu(self)
        new_act    = menu.addAction('New Crate…')
        sub_act    = menu.addAction('New Subcrate…')
        menu.addSeparator()
        rename_act = menu.addAction('Rename…')
        dup_act    = menu.addAction('Duplicate')
        menu.addSeparator()
        del_act    = menu.addAction('Delete')
        menu.addSeparator()
        add_t_act  = menu.addAction('Add Tracks…')
        menu.addSeparator()
        export_act = menu.addAction('Export Crate to Folder…')

        action = menu.exec(self._crate_tree.viewport().mapToGlobal(pos))
        if action == new_act:
            self._crate_new(parent_path=None)
        elif action == sub_act:
            self._crate_new_sub(key)
        elif action == rename_act:
            self._crate_rename(key)
        elif action == dup_act:
            self._crate_duplicate(key)
        elif action == del_act:
            self._crate_delete(key)
        elif action == add_t_act:
            self._crate_add_tracks(key)
        elif action == export_act:
            self._export_crate_to_folder(key)

    # ── Crate CRUD operations ──────────────────────────────────────────

    def _writer(self) -> Optional[CrateWriter]:
        if not self._library_path:
            return None
        return CrateWriter(self._library_path / '_Serato_')

    def _crate_new(self, parent_path: Optional[str]) -> None:
        name = _NameInputDialog(self, 'New Crate', 'Crate name:').get_name()
        if not name:
            return
        if err := _validate_crate_name(name):
            _ov_alert(self, 'Invalid Crate Name', err)
            return
        writer     = self._writer()
        if not writer:
            return
        crate_path = f'{parent_path}/{name}' if parent_path else name
        self._set_status('Creating crate…')
        if self._undo_manager:
            cmd = CreateCrateCommand(self, crate_path, name)
            self._undo_manager.push(cmd)
            self._set_status(f'Created: {name}', teal=True)
        else:
            result = writer.create_crate(crate_path)
            if not result.success:
                _ov_alert(self, 'Create Crate', f'Failed: {result.error}')
                self._set_status('')
                return
            self._refresh(select=crate_path)
            self._set_status(f'Created: {name}', teal=True)

    def _crate_new_sub(self, parent_path: str) -> None:
        name = _NameInputDialog(self, 'New Subcrate', 'Subcrate name:').get_name()
        if not name:
            return
        if err := _validate_crate_name(name):
            _ov_alert(self, 'Invalid Crate Name', err)
            return
        writer = self._writer()
        if not writer:
            return
        child_path = f'{parent_path}/{name}'
        self._set_status('Creating subcrate…')
        if self._undo_manager:
            cmd = CreateCrateCommand(self, child_path, name)
            self._undo_manager.push(cmd)
            self._set_status(f'Created: {name}', teal=True)
        else:
            result = writer.create_subcrate(parent_path, name)
            if not result.success:
                _ov_alert(self, 'New Subcrate', f'Failed: {result.error}')
                self._set_status('')
                return
            self._refresh(select=child_path)
            self._set_status(f'Created: {name}', teal=True)

    def _crate_rename(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate    = self._crate_library.crates[crate_path]
        old_name = crate.name
        new_name = _NameInputDialog(self, 'Rename Crate', 'New name:', prefill=old_name).get_name()
        if not new_name or new_name == old_name:
            return
        if err := _validate_crate_name(new_name):
            _ov_alert(self, 'Invalid Crate Name', err)
            return
        parent   = crate.parent
        new_path = f'{parent}/{new_name}' if parent else new_name
        writer   = self._writer()
        if not writer:
            return
        self._set_status('Renaming crate…')
        if self._undo_manager:
            cmd = RenameCrateCommand(self, crate_path, new_path, old_name, new_name)
            self._undo_manager.push(cmd)
            self._set_status(f'Renamed to: {new_name}', teal=True)
        else:
            result = writer.rename_crate(crate_path, new_path)
            if not result.success:
                _ov_alert(self, 'Rename Crate', f'Failed: {result.error}')
                self._set_status('')
                return
            # Update _crate_order: replace old path with new across all keys
            self._crate_order = {
                k: [new_path if p == crate_path else p for p in v]
                for k, v in self._crate_order.items()
            }
            self._save_crate_order()
            self._refresh(select=new_path)
            self._set_status(f'Renamed to: {new_name}', teal=True)

    def _crate_duplicate(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate    = self._crate_library.crates[crate_path]
        parent   = crate.parent
        base_dst = f'{parent}/{crate.name} (Copy)' if parent else f'{crate.name} (Copy)'
        writer   = self._writer()
        if not writer:
            return
        dst_path = base_dst
        suffix   = 1
        while dst_path in self._crate_library.crates:
            suffix  += 1
            dst_path = f'{base_dst} {suffix}'
        self._set_status('Duplicating crate…')
        result = writer.duplicate_crate(crate_path, dst_path)
        if not result.success:
            _ov_alert(self, 'Duplicate Crate', f'Failed: {result.error}')
            self._set_status('')
            return
        self._refresh(select=dst_path)
        self._set_status(f'Duplicated: {crate.name}', teal=True)

    def _crate_delete(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate = self._crate_library.crates[crate_path]
        if crate.track_count > 0:
            msg = f'Delete "{crate.name}"? It contains {crate.track_count} tracks. This cannot be undone.'
        else:
            msg = f'Delete "{crate.name}"? This cannot be undone.'
        if not _ov_confirm(self, 'Delete Crate', msg, confirm_text='Delete', confirm_danger=True):
            return
        writer = self._writer()
        if not writer:
            return
        self._set_status('Deleting crate…')
        QApplication.processEvents()  # keep UI responsive during file I/O
        if self._undo_manager:
            cmd = DeleteCrateCommand(self, crate_path, crate.name, list(crate.tracks))
            self._undo_manager.push(cmd)
            self._set_status(f'Deleted: {crate.name}', teal=True)
        else:
            try:
                result = writer.delete_crate(crate_path)
            except Exception as exc:
                self._set_status('Delete failed — crate file may be locked or missing', teal=True)
                return
            if not result.success:
                _ov_alert(self, 'Delete Crate', f'Failed: {result.error}')
                self._set_status('')
                return
            # Remove from all order keys
            self._crate_order = {
                k: [p for p in v if p != crate_path]
                for k, v in self._crate_order.items()
            }
            self._save_crate_order()
            self._current_crate_path = _ALL_TRACKS_KEY
            self._refresh(select=_ALL_TRACKS_KEY)
            self._set_status(f'Deleted: {crate.name}', teal=True)

    def _crate_add_tracks(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate = self._crate_library.crates[crate_path]

        # Build current set with both original crate paths AND resolved local paths
        # so the dialog can correctly gray out tracks regardless of path format
        current_set = set(crate.tracks)
        for tp in crate.tracks:
            rec = self._resolve_track(tp)
            if rec:
                current_set.add(str(rec.path))

        dlg = _AddTracksDialog(self._inventory, current_set, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        paths = dlg.selected_paths()
        if not paths:
            return
        writer = self._writer()
        if not writer:
            return
        self._set_status(f'Adding {len(paths)} track(s)…')
        if self._undo_manager:
            cmd = AddTracksCommand(self, crate_path, paths, crate.name)
            self._undo_manager.push(cmd)
            self._set_status(f'Added {len(paths)} track(s)', teal=True)
        else:
            result = writer.add_tracks(crate_path, paths)
            if not result.success:
                _ov_alert(self, 'Add Tracks', f'Failed: {result.error}')
                self._set_status('')
                return
            self._reload_current_crate()
            self._set_status(f'Added {result.tracks_affected} track(s)', teal=True)

        # Scroll to and select the first newly added track
        first_path = paths[0] if paths else None
        if first_path:
            for row in range(self._track_table.rowCount()):
                cell = self._track_table.item(row, TC_TITLE)
                if cell and cell.data(Qt.ItemDataRole.UserRole) == first_path:
                    self._track_table.selectRow(row)
                    self._track_table.scrollToItem(
                        cell,
                        QAbstractItemView.ScrollHint.PositionAtCenter,
                    )
                    break

    def _reload_current_crate(self) -> None:
        self._refresh(select=self._current_crate_path)

    # ── Export Crate to Folder ─────────────────────────────────────────

    def _count_export_tracks(self, crate_path: str) -> int:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return 0
        crate = self._crate_library.crates[crate_path]
        return len(crate.tracks) + sum(
            self._count_export_tracks(child) for child in crate.children
        )

    def _export_crate_to_folder(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            _ov_alert(self, 'Export Crate', 'Crate data unavailable.')
            return

        total = self._count_export_tracks(crate_path)
        if total == 0:
            _ov_alert(self, 'Export Crate', 'This crate has no tracks that could be found on disk.')
            return

        dest_str = QFileDialog.getExistingDirectory(
            self, 'Choose Export Destination', str(Path.home())
        )
        if not dest_str:
            return

        crate_name = crate_path.split('/')[-1]
        crate      = self._crate_library.crates[crate_path]

        # Inform the user when subcrates are present — they export as _Name folders
        if crate.children:
            subcrate_names = sorted(child.split('/')[-1] for child in crate.children)
            prefixed       = ', '.join(f'_{n}' for n in subcrate_names)
            msg = (
                f'{prefixed}\n\n'
                f'Subcrate folders — sorted above your artists. Continue?'
            )
            if not _ov_confirm(self, 'Export Crate to Folder', msg):
                return

        self._export_dialog = _ExportProgressDialog(crate_name, total, self)
        self._export_worker = _ExportCrateWorker(
            crate_library=self._crate_library,
            root_crate_path=crate_path,
            inventory_by_path=dict(self._inventory_by_path),
            inventory_by_name=dict(self._inventory_by_name),
            edits=dict(self._edits),
            library_path=self._library_path,
            total=total,
            dest_folder=Path(dest_str),
            parent=self,
        )

        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.errored.connect(self._on_export_errored)
        self._export_dialog.cancelled.connect(self._on_export_cancelled)

        self._export_worker.start()
        self._export_dialog.exec()

    def _on_export_progress(self, done: int, total: int, _filename: str) -> None:
        if self._export_dialog:
            self._export_dialog.update_progress(done, total)

    def _on_export_finished(self, result: dict) -> None:
        if self._export_dialog:
            self._export_dialog.close()
        self._export_dialog = None
        self._export_worker = None
        copied = result['copied']
        failed = result['failed']
        dest   = result['dest']
        msg = f'Exported {copied:,} track{"s" if copied != 1 else ""} to:\n{dest}'
        if failed:
            msg += f'\n\n⚠ {failed} file{"s" if failed != 1 else ""} could not be copied.'
        _ov_alert(self, 'Export Complete', msg)

    def _on_export_errored(self, msg: str) -> None:
        if self._export_dialog:
            self._export_dialog.close()
        self._export_dialog = None
        self._export_worker = None
        _ov_alert(self, 'Export Failed', f'Export failed:\n{msg[:500]}')

    def _on_export_cancelled(self) -> None:
        if self._export_worker:
            self._export_worker.cancel()
        self._export_dialog = None
        self._export_worker = None

    # ── Track context menu ─────────────────────────────────────────────

    def _on_track_context_menu(self, pos) -> None:
        item = self._track_table.itemAt(pos)
        if item is None:
            return

        clicked_row   = item.row()
        selected_rows = sorted({idx.row() for idx in self._track_table.selectedIndexes()})
        if clicked_row not in selected_rows:
            self._track_table.clearSelection()
            self._track_table.selectRow(clicked_row)
            selected_rows = [clicked_row]
        self._context_rows = selected_rows

        menu          = QMenu(self)
        reassign_act  = menu.addAction('Reassign Artist…')
        chg_genre_act = menu.addAction('Change Genre…')
        edit_tags_act = menu.addAction('Edit Style Tags…')
        menu.addSeparator()
        finder_act    = menu.addAction('Show in Finder')
        menu.addSeparator()
        cp_artist_act = menu.addAction('Copy Artist')
        cp_title_act  = menu.addAction('Copy Title')
        cp_path_act   = menu.addAction('Copy File Path')
        menu.addSeparator()
        remove_act    = menu.addAction('Remove from Crate')

        action = menu.exec(self._track_table.viewport().mapToGlobal(pos))

        if action == chg_genre_act:
            self._change_genre_for_rows(self._context_rows)
        elif action == edit_tags_act:
            self._edit_tags_for_rows(self._context_rows)
        elif action == reassign_act:
            self._reassign_artist_for_row(clicked_row)
        elif action == finder_act:
            path_item = self._track_table.item(clicked_row, TC_PATH)
            if path_item:
                rec = self._resolve_track(path_item.text())
                _show_in_finder(str(rec.path) if rec else path_item.text())
        elif action == cp_artist_act:
            cell = self._track_table.item(clicked_row, TC_ARTIST)
            QApplication.clipboard().setText(cell.text() if cell else '')
        elif action == cp_title_act:
            cell = self._track_table.item(clicked_row, TC_TITLE)
            QApplication.clipboard().setText(cell.text() if cell else '')
        elif action == cp_path_act:
            path_item = self._track_table.item(clicked_row, TC_PATH)
            QApplication.clipboard().setText(path_item.text() if path_item else '')
        elif action == remove_act:
            self._confirm_remove_tracks(self._context_rows)

    def _change_genre_for_rows(self, rows: list[int]) -> None:
        from cratesort.src.gui.classifier_view import _ChangeGenreDialog
        if not rows:
            return
        hint_genre = ''
        genre_cell = self._track_table.item(rows[0], TC_GENRE)
        if genre_cell:
            hint_genre = genre_cell.text()
        if len(rows) == 1:
            title_cell = self._track_table.item(rows[0], TC_TITLE)
            label      = title_cell.text() if title_cell else '1 track'
        else:
            label = f'{len(rows)} tracks'

        dlg = _ChangeGenreDialog(label, hint_genre, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_genre = dlg.selected_genre
        track_changes: dict[str, str] = {}
        for row in rows:
            path_item = self._track_table.item(row, TC_PATH)
            if not path_item:
                continue
            rec = self._resolve_track(path_item.text())
            if rec is None:
                continue
            cell = self._track_table.item(row, TC_GENRE)
            if cell:
                cell.setText(new_genre)
            self._edits.setdefault(str(rec.path), {})['genre'] = new_genre
            track_changes[str(rec.path)] = new_genre
        self._save_edits()
        self._sync_genres_to_session({}, track_changes)

    def _edit_tags_for_rows(self, rows: list[int]) -> None:
        from cratesort.src.gui.classifier_view import _EditTagsDialog
        if not rows:
            return
        row       = rows[0]
        path_item = self._track_table.item(row, TC_PATH)
        if not path_item:
            return
        rec = self._resolve_track(path_item.text())
        if rec is None:
            return
        current_tags_str = self._edits.get(str(rec.path), {}).get('tags', '')
        current_tags     = [t.strip() for t in current_tags_str.split(',') if t.strip()]
        proxy = type('T', (), {
            'filename':  rec.filename,
            'title':     rec.title,
            'genre_tag': rec.genre,
            'tags':      current_tags,
            'comment':   rec.comment,
        })()
        dlg = _EditTagsDialog(proxy, self)
        dlg.setWindowTitle(f'Edit Style Tags — {rec.filename}')
        if dlg.exec() == QDialog.DialogCode.Accepted:
            tags_str = ', '.join(proxy.tags)
            self._edits.setdefault(str(rec.path), {})['tags'] = tags_str
            self._save_edits()
            tags_cell = self._track_table.item(row, TC_TAGS)
            if tags_cell:
                tags_cell.setText(tags_str)

    def _reassign_artist_for_row(self, row: int) -> None:
        from cratesort.src.gui.classifier_view import _ReassignArtistDialog
        path_item = self._track_table.item(row, TC_PATH)
        if not path_item:
            return
        rec = self._resolve_track(path_item.text())
        if rec is None:
            return
        existing_artists = sorted({rec.artist for rec in self._inventory if rec.artist})
        dlg = _ReassignArtistDialog(existing_artists, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_artist = dlg.artist_name.strip()
        if not new_artist:
            return
        self._edits.setdefault(str(rec.path), {})['reassign_artist'] = new_artist
        self._save_edits()
        artist_cell = self._track_table.item(row, TC_ARTIST)
        if artist_cell:
            artist_cell.setText(new_artist)

    def _remove_from_crate(self, rows: list[int]) -> None:
        if not self._current_crate_path or self._current_crate_path == _ALL_TRACKS_KEY:
            return
        writer = self._writer()
        if not writer:
            return
        paths_to_remove: list[str] = []
        for row in rows:
            path_item = self._track_table.item(row, TC_TITLE)  # any cell has the data
            if path_item:
                original = path_item.data(Qt.ItemDataRole.UserRole + 1)
                if original:
                    paths_to_remove.append(original)
        if not paths_to_remove:
            return
        n = len(paths_to_remove)
        crate_name = ''
        if self._crate_library and self._current_crate_path in self._crate_library.crates:
            crate_name = self._crate_library.crates[self._current_crate_path].name
        self._set_status(f'Removing {n} track(s)…')
        if self._undo_manager:
            cmd = RemoveTracksCommand(self, self._current_crate_path, paths_to_remove, crate_name)
            self._undo_manager.push(cmd)
            self._set_status(f'Removed {n} track(s)', teal=True)
        else:
            result = writer.remove_tracks(self._current_crate_path, paths_to_remove)
            if not result.success:
                _ov_alert(self, 'Remove Tracks', f'Failed: {result.error}')
                self._set_status('')
                return
            self._refresh(select=self._current_crate_path)
            self._set_status(f'Removed {result.tracks_affected} track(s)', teal=True)

    def _confirm_remove_tracks(self, rows: list[int]) -> None:
        if not rows:
            return
        if len(rows) == 1:
            title_cell = self._track_table.item(rows[0], TC_TITLE)
            label      = f'"{title_cell.text()}"' if title_cell else '1 track'
            msg        = f'Remove {label} from {self._current_crate_path!r}?'
        else:
            msg = f'Remove {len(rows)} tracks from {self._current_crate_path!r}?'

        if _ov_confirm(self, 'Remove Tracks', msg, confirm_text='Remove', confirm_danger=True):
            self._remove_from_crate(rows)

    def _confirm_delete_crate(self, crate_path: str) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate  = self._crate_library.crates[crate_path]
        name   = crate.name
        if crate.track_count > 0:
            msg = (f'Delete "{name}"? It contains {crate.track_count} tracks. '
                   f'This cannot be undone.')
        else:
            msg = f'Delete "{name}"? This cannot be undone.'

        if _ov_confirm(self, 'Delete Crate', msg, confirm_text='Delete', confirm_danger=True):
            writer = self._writer()
            if not writer:
                return
            self._set_status('Deleting crate…')
            QApplication.processEvents()
            if self._undo_manager:
                cmd = DeleteCrateCommand(self, crate_path, name, list(crate.tracks))
                self._undo_manager.push(cmd)
                self._set_status(f'Deleted: {name}', teal=True)
                return
            # fallback: existing direct code
            try:
                result = writer.delete_crate(crate_path)
            except Exception:
                self._set_status('Delete failed — crate file may be locked or missing', teal=True)
                return
            if not result.success:
                _ov_alert(self, 'Delete Crate', f'Failed: {result.error}')
                self._set_status('')
                return
            self._crate_order = {
                k: [p for p in v if p != crate_path]
                for k, v in self._crate_order.items()
            }
            self._save_crate_order()
            self._current_crate_path = _ALL_TRACKS_KEY
            self._refresh(select=_ALL_TRACKS_KEY)
            self._set_status(f'Deleted: {name}', teal=True)

    def _on_tracks_reordered(self, new_order: list[str]) -> None:
        """Fix 2: reload from disk after writing the new order — single source of truth."""
        if not self._current_crate_path or self._current_crate_path == _ALL_TRACKS_KEY:
            return
        old_order = list(self._original_track_paths)
        crate_name = self._current_crate_path.split('/')[-1]
        if self._crate_library and self._current_crate_path in self._crate_library.crates:
            crate_name = self._crate_library.crates[self._current_crate_path].name
        if self._undo_manager:
            cmd = ReorderTracksCommand(self, self._current_crate_path, old_order, new_order, crate_name)
            self._undo_manager.push(cmd)
            self._set_status(f'Reordered {len(new_order)} track(s) in {crate_name}', teal=True)
            return
        # fallback: existing direct code
        writer = self._writer()
        if not writer:
            return
        result = writer.reorder_tracks(self._current_crate_path, new_order)
        if not result.success:
            _ov_alert(self, 'Reorder Tracks', f'Failed: {result.error}')
            return
        # Reload from disk — this is the single source of truth
        self._refresh(select=self._current_crate_path)
        self._set_status(
            f'Reordered {len(new_order)} track(s) in {crate_name or self._current_crate_path}',
            teal=True,
        )

    def _add_tracks_to_crate(self, crate_path: str, paths: list[str]) -> None:
        if not self._crate_library or crate_path not in self._crate_library.crates:
            return
        crate = self._crate_library.crates[crate_path]
        current_set = set(crate.tracks)
        for tp in crate.tracks:
            rec = self._resolve_track(tp)
            if rec:
                current_set.add(str(rec.path))
        new_paths  = [p for p in paths if p not in current_set]
        skip_count = len(paths) - len(new_paths)
        if not new_paths:
            self._set_status(f'All {len(paths)} track(s) already in "{crate.name}"', teal=True)
            return
        writer = self._writer()
        if not writer:
            return
        result = writer.add_tracks(crate_path, new_paths)
        if not result.success:
            _ov_alert(self, 'Add Tracks', f'Failed: {result.error}')
            return
        self._refresh(select=self._current_crate_path)
        if skip_count:
            self._set_status(
                f'Added {result.tracks_affected} track(s) to "{crate.name}" '
                f'({skip_count} already present, skipped)', teal=True
            )
        else:
            self._set_status(f'Added {result.tracks_affected} track(s) to "{crate.name}"', teal=True)

    def _on_header_clicked(self, _col: int) -> None:
        # Qt has already updated the sort indicator and re-sorted the table.
        # Read the new state and persist it so it survives crate navigation.
        QTimer.singleShot(0, self._persist_current_sort)

    def _persist_current_sort(self) -> None:
        hdr = self._track_table.horizontalHeader()
        self._sort_col   = hdr.sortIndicatorSection()
        self._sort_order = hdr.sortIndicatorOrder()

    # ── Genre sync ─────────────────────────────────────────────────────

    def _sync_genres_to_session(
        self,
        artist_changes: dict[str, str],
        track_changes: dict[str, str],
    ) -> None:
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
            print(f'[CrateManager] Failed to sync to session: {exc}')

    # ── Persistence ────────────────────────────────────────────────────

    def _load_session_genres(self) -> None:
        if not self._library_path:
            return
        session_file = self._library_path / '_CrateSort' / 'classification_session.json'
        if not session_file.exists():
            return
        try:
            with open(session_file, encoding='utf-8') as f:
                data = json.load(f)
            for entry in data.get('entries', []):
                artist = entry.get('artist', '')
                genre  = entry.get('final_genre') or entry.get('proposed_genre', '')
                if artist and genre:
                    self._session_genre[artist] = genre
                for track in entry.get('tracks', []):
                    tp = track.get('path', '')
                    tg = track.get('genre_tag', '')
                    if tp and tg:
                        self._track_genre_overrides[tp] = tg
        except Exception as exc:
            print(f'[CrateManager] Session genre load error: {exc}')

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

    def _crate_order_file(self) -> Optional[Path]:
        if not self._library_path:
            return None
        return self._library_path / '_CrateSort' / 'crate_order.json'

    def _collect_all_crates_in_order(self) -> list[str]:
        """Depth-first walk of the crate tree in current display order."""
        if not self._crate_library:
            return []
        result: list[str] = []
        top_level = list(self._crate_library.top_level)
        if "" in self._crate_order:
            saved = self._crate_order[""]
            idx   = {p: i for i, p in enumerate(saved)}
            top_level.sort(key=lambda p: idx.get(p, len(saved)))

        def _walk(crate_path: str) -> None:
            result.append(crate_path)
            if crate_path not in self._crate_library.crates:
                return
            children = list(self._crate_library.crates[crate_path].children)
            if crate_path in self._crate_order:
                saved_ch = self._crate_order[crate_path]
                ch_idx   = {p: i for i, p in enumerate(saved_ch)}
                children.sort(key=lambda p: ch_idx.get(p, len(saved_ch)))
            for child in children:
                _walk(child)

        for path in top_level:
            _walk(path)
        return result

    def _load_crate_order(self) -> None:
        """Load crate order: neworder.pref is the source of truth, crate_order.json is fallback."""
        serato_dir = (self._library_path / '_Serato_') if self._library_path else None

        # Try neworder.pref first
        if serato_dir and serato_dir.exists():
            flat = _read_neworder(serato_dir)
            if flat:
                # Convert flat list → nested dict structure
                order_dict: dict[str, list[str]] = {}
                for cs_path in flat:
                    parent = '/'.join(cs_path.split('/')[:-1]) if '/' in cs_path else ''
                    order_dict.setdefault(parent, []).append(cs_path)
                self._crate_order = order_dict
                return

        # Fall back to crate_order.json
        p = self._crate_order_file()
        if p and p.exists():
            try:
                with open(p, encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and 'order' in data:
                    self._crate_order = {"": data['order']}
                elif isinstance(data, dict):
                    self._crate_order = data
                else:
                    self._crate_order = {}
            except Exception:
                self._crate_order = {}
        else:
            self._crate_order = {}

    def _save_crate_order(self) -> None:
        """Save crate order to both neworder.pref (Serato) and crate_order.json (fallback)."""
        # Write to Serato's neworder.pref
        if self._library_path:
            serato_dir = self._library_path / '_Serato_'
            if serato_dir.exists():
                flat = self._collect_all_crates_in_order()
                if flat:
                    ok = _write_neworder(serato_dir, flat)
                    if ok:
                        self._set_status(
                            'Crate order saved — Serato will reflect this order on next launch.',
                            teal=True,
                        )

        # Also persist to crate_order.json as fallback
        p = self._crate_order_file()
        if not p:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(self._crate_order, f, indent=2)

    # ── Column widths ──────────────────────────────────────────────────

    def _size_pos_column(self, track_count: int) -> None:
        fm  = self._track_table.horizontalHeader().fontMetrics()
        pad = 20
        w   = max(fm.horizontalAdvance(str(track_count)) + pad,
                  fm.horizontalAdvance('#') + pad,
                  30)
        self._track_table.setColumnWidth(TC_POS, w)

    def _enforce_min_col_widths(self) -> None:
        hdr = self._track_table.horizontalHeader()
        fm  = hdr.fontMetrics()
        for col in range(self._track_table.columnCount()):
            text  = _TRACK_HEADERS[col]
            min_w = fm.horizontalAdvance(text) + 40
            if self._track_table.columnWidth(col) < min_w:
                self._track_table.setColumnWidth(col, min_w)

    def save_state(self) -> None:
        self._settings.setValue(
            _SETTINGS_KEY,
            self._track_table.horizontalHeader().saveState(),
        )
