"""
Tests that the Library track tree and the Crates track table share one
row height, and that the double-click-to-edit inline editor is rendered at
that full height in both — so descenders (g/p/y) never clip while typing.

See _resources/rinse-testing-findings-2026-08-27.md #3. Two separate causes:
  1. The tree had no row-height setting (~26px) vs the table's 36px.
  2. QTableWidget.setCellWidget stretches its editor to the row; QTreeWidget
     .setItemWidget does NOT — so the editor must size itself, in both.

Requires a QApplication; skipped automatically if PyQt6 can't start
(e.g. no display and no offscreen platform).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from cratesort.src.gui.theme import STYLESHEET, TRACK_ROW_HEIGHT

# A QLineEdit needs enough interior height, after the theme's padding+border,
# to show a 14px font's descenders. This is the floor the fix must clear.
_MIN_LEGIBLE_EDITOR_HEIGHT = 32


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    yield app


def test_editor_height_clears_descenders():
    assert TRACK_ROW_HEIGHT >= _MIN_LEGIBLE_EDITOR_HEIGHT


def test_delegate_size_hint_is_track_row_height(qapp):
    from cratesort.src.gui.library_browser import _TrackRowHeightDelegate

    tree = QTreeWidget()
    tree.setColumnCount(1)
    tree.setItemDelegate(_TrackRowHeightDelegate(tree))
    QTreeWidgetItem(tree).setText(0, "ggjjppyy descenders")

    idx = tree.model().index(0, 0)
    hint = tree.itemDelegate().sizeHint(QStyleOptionViewItem(), idx)
    assert hint.height() == TRACK_ROW_HEIGHT


def test_library_tree_renders_uniform_rows(qapp):
    from cratesort.src.gui.library_browser import _TrackRowHeightDelegate

    tree = QTreeWidget()
    tree.setColumnCount(2)
    tree.setHeaderLabels(["title", "album"])
    tree.setItemDelegate(_TrackRowHeightDelegate(tree))
    for text in ("Pimpology (Bootleg)", "ggjjppyy", "plain"):
        row = QTreeWidgetItem(tree)
        row.setText(0, text)
        row.setText(1, "x")
    tree.resize(400, 300)
    tree.show()
    qapp.processEvents()

    heights = [
        tree.visualItemRect(tree.topLevelItem(n)).height() for n in range(3)
    ]
    assert heights == [TRACK_ROW_HEIGHT] * 3


def test_tree_inline_editor_is_full_row_height(qapp):
    """setItemWidget does not stretch the editor — it must size itself."""
    from cratesort.src.gui.library_browser import _TrackRowHeightDelegate

    tree = QTreeWidget()
    tree.setColumnCount(2)
    tree.setItemDelegate(_TrackRowHeightDelegate(tree))
    item = QTreeWidgetItem(tree)
    item.setText(0, "Pimpology gjpy")
    item.setText(1, "x")
    tree.resize(400, 200)
    tree.show()
    qapp.processEvents()

    editor = QLineEdit("Pimpology gjpy")
    editor.setFixedHeight(TRACK_ROW_HEIGHT)  # mirrors _on_item_double_clicked
    tree.setItemWidget(item, 0, editor)
    qapp.processEvents()

    assert editor.height() == TRACK_ROW_HEIGHT


def test_table_inline_editor_is_full_row_height(qapp):
    table = QTableWidget(1, 2)
    vh = table.verticalHeader()
    vh.setDefaultSectionSize(TRACK_ROW_HEIGHT)
    vh.setMinimumSectionSize(TRACK_ROW_HEIGHT)
    vh.setMaximumSectionSize(TRACK_ROW_HEIGHT)
    table.setItem(0, 0, QTableWidgetItem("Pimpology gjpy"))
    table.resize(400, 200)
    table.show()
    qapp.processEvents()

    editor = QLineEdit("Pimpology gjpy")
    editor.setFixedHeight(TRACK_ROW_HEIGHT)  # mirrors _on_track_double_clicked
    table.setCellWidget(0, 0, editor)
    qapp.processEvents()

    assert editor.height() >= _MIN_LEGIBLE_EDITOR_HEIGHT


def test_crates_track_table_uses_the_same_constant(qapp):
    from cratesort.src.gui.crate_manager import CrateManagerView

    view = CrateManagerView(undo_manager=None)
    vh = view._track_table.verticalHeader()
    assert vh.defaultSectionSize() == TRACK_ROW_HEIGHT
    assert vh.minimumSectionSize() == TRACK_ROW_HEIGHT
    assert vh.maximumSectionSize() == TRACK_ROW_HEIGHT


def test_both_screens_use_the_shared_inline_editor(qapp):
    """Library tree and Crates table build the exact same editor widget."""
    from cratesort.src.gui.inline_edit import INLINE_EDIT_QSS, make_inline_editor

    calls = []
    editor = make_inline_editor(
        "Highway to Hell",
        on_commit=lambda: calls.append("commit"),
        on_cancel=lambda: calls.append("cancel"),
    )
    assert editor.height() == TRACK_ROW_HEIGHT
    assert editor.styleSheet() == INLINE_EDIT_QSS
    assert "margin" in INLINE_EDIT_QSS  # the centred-inset-pill treatment
