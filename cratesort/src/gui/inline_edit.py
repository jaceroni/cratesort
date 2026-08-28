"""
One shared inline-edit treatment for every track list.

The Library tree (QTreeWidget.setItemWidget) and the Crates track table
(QTableWidget.setCellWidget) both let you double-click a cell to edit it.
Those two placement APIs position a child widget differently, so the editors
had drifted into looking and sitting differently. `make_inline_editor` gives
both the same QLineEdit: same height, same border/colour, and — via a QSS
`margin` that insets the visible box inside the full 36px row — the same
vertically-centred pill in both.

For the tree to place the editor flush at the row top (like setCellWidget
does), the tree's own `QTreeWidget::item` rule must drop its vertical
padding — `padding: 0px 4px 0px 2px`. Row text stays centred because that
padding was symmetric.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit

from cratesort.src.gui.theme import TRACK_ROW_HEIGHT

# Inset each side by 4px so the visible box is a centred pill in the 36px row.
_ROW_INSET = 4

INLINE_EDIT_QSS = (
    'QLineEdit {'
    ' padding: 1px 8px;'
    ' border: 1px solid #D17D34;'
    ' border-radius: 4px;'
    ' background: #1a1a1a;'
    ' color: #f1e3c8;'
    f' margin: {_ROW_INSET}px 0;'
    ' selection-background-color: #D17D34;'
    ' selection-color: #ffffff;'
    '}'
)


def make_inline_editor(text: str, *, on_commit, on_cancel) -> QLineEdit:
    """A double-click-to-edit field, styled identically for tree and table.

    on_commit / on_cancel are called with no args. Both callers null their
    own editor reference on first call, so a redundant second call (Return
    fires both keyPressEvent and editingFinished) is a harmless no-op.
    """
    editor = QLineEdit(text)
    editor.selectAll()
    editor.setFixedHeight(TRACK_ROW_HEIGHT)
    editor.setStyleSheet(INLINE_EDIT_QSS)

    _orig_key = editor.keyPressEvent

    def _key(event):
        if event.key() == Qt.Key.Key_Escape:
            on_cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            on_commit()
        else:
            _orig_key(event)

    editor.keyPressEvent = _key  # type: ignore[method-assign]
    editor.editingFinished.connect(on_commit)
    return editor
