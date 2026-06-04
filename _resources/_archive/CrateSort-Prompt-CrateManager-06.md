# CrateSort — Crate Tree Focused Fix (Prompt 6)

> **Run this at Sonnet high effort. Read `src/gui/crate_manager.py` completely before writing a single line of code. Do not change anything outside of the crate tree. Do not touch the track panel, the track drag logic, the footer, or any other view. This prompt is exclusively about the crate tree.**

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates.

## Files to Read First

Read ALL of these completely before writing any code:

- `src/gui/crate_manager.py` — primary file
- `src/gui/theme.py` — color constants
- `src/serato/crate_writer.py` — for understanding how crate rename/move is written to disk

---

## The Six Problems to Fix

### Problem 1 — Selection Colors: Use Pure Python, No Stylesheets

Qt stylesheets are being overridden by Qt's internal selection system and producing wrong colors. Remove ALL stylesheet-based selection coloring from the crate tree. Do not use `QTreeWidget::item:selected`, `QTreeWidget::item:hover`, or any stylesheet selector that controls selection state colors.

Instead, implement all four states purely in Python using `QTreeWidgetItem.setBackground()` and `QTreeWidgetItem.setForeground()` called explicitly whenever selection changes.

- See the CrateSort-Prompt-CrateManager-06.jpg file in the _resources directory for a visual mockup of how the parent crate and sub-crate style should be.

Also disable Qt's default highlight completely before anything else:

```python
palette = self._crate_tree.palette()
palette.setColor(QPalette.ColorRole.Highlight, QColor("#1a1a1a"))
palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#f1e3c8"))
self._crate_tree.setPalette(palette)
```

---

### Problem 2 — Selection State Logic: Four States, Applied Correctly

Implement these four states in `_on_tree_selection_changed`. Every time selection changes:
1. Reset ALL items in the tree to State A first
2. Apply the correct state to the newly selected item
3. If the newly selected item has a parent, apply State C to that parent

**State A — unselected:**
```python
item.setBackground(0, QBrush(QColor("#1a1a1a")))
item.setForeground(0, QBrush(QColor("#f1e3c8")))
```

**State B — selected crate (no active sub-crate, or parent selected but not yet expanded into):**
```python
item.setBackground(0, QBrush(QColor("#D17D34")))
item.setForeground(0, QBrush(QColor("#1a1a1a")))
```

**State C — parent of the currently selected sub-crate:**
```python
item.setBackground(0, QBrush(QColor("#2F2F2F")))
item.setForeground(0, QBrush(QColor("#f1e3c8")))
```
Paint the orange left bar (4-5px, `#D17D34`) for State C using a custom `QStyledItemDelegate` `paint()` method. Draw the bar as a filled rectangle on the left edge of the item rect. Do not use gradients or stylesheets for this bar.

**State D — selected sub-crate:**
```python
item.setBackground(0, QBrush(QColor("#8B5E3C")))
item.setForeground(0, QBrush(QColor("#f1e3c8")))
```
Same orange left bar as State C via the same delegate `paint()` method.

**State transition rules:**
- Single click any crate → State B. Load tracks. Never auto-expand.
- Double click a parent crate → expand/collapse. State does not change (parent stays State B if it was selected, or stays whatever state it was).
- Single click a sub-crate → sub-crate goes State D. Its parent goes State C.
- Click a completely different unrelated crate → all previous states reset to A. New crate goes State B.

---

### Problem 3 — Expand Indicators: Restore and Keep

Every crate that has child crates must show a visible expand/collapse indicator (arrow or caret). This must work at all nesting levels.

```python
item.setChildIndicatorPolicy(
    QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
)
```

Call this on every item that has children, every time the tree is built or rebuilt. Verify it is not being removed or overridden anywhere in the rebuild process.

The indicator must live in the left gutter and must NOT shift the text position.

---

### Problem 4 — Row Height: Fix Without Stylesheet

The crate tree rows are taller than the track panel rows. The stylesheet `height: 34px` on `QTreeWidget::item` is not working reliably.

Find what is actually controlling the crate tree row height — it may be padding in the stylesheet, the item delegate's `sizeHint()`, or a style option. Fix it at the source:

- If the delegate controls height: override `sizeHint()` to return `QSize(width, 34)`
- If stylesheet padding is inflating height: remove the padding entirely and set height only via the delegate
- Do not add padding to stylesheet items — it inflates row height unpredictably on macOS

Target: crate tree rows must visually match the track panel rows (34px) when the app is running. Verify by scrolling both panels and confirming rows stay aligned.

---

### Problem 5 — Crate Drag: Sub-Crate Cannot Be Dragged to Top Level

Once a crate is nested as a sub-crate, it cannot be dragged back out to the top level. It can be moved between parent crates, but it is permanently stuck as a sub-crate once nested.

Fix: the top level of the crate tree must be a valid drop target.

- When the user drags a crate and the teal drop indicator line appears **between top-level crates** (not inside any parent), the drop zone is the top level
- On drop at the top level, un-nest the crate: move it out of its current parent and make it a top-level peer
- Write the change to `.crate` files immediately via `crate_writer`
- Teal footer text confirms: *"Moved '[Crate Name]' to top level"*

---

### Problem 6 — Crate Drag: Sibling Reorder Not Working Inside Nested Parents

Dragging to reorder crates within a nested parent (sub-crates among their siblings) does not work. The drag executes but the order does not change.

Fix: sibling reorder must work at every nesting level, not just the top level.

- When dragging a sub-crate among its siblings within the same parent, the teal drop indicator line must appear between sibling rows
- On drop, reorder the siblings and write the new order immediately
- The parent crate must not change — only the order of its children

---

## What NOT to Change

- Do not touch the track panel, track drag logic, track table, or track panel columns
- Do not touch the footer status bar logic beyond confirming teal text fires after crate drag operations
- Do not touch the Library Browser, Dashboard, Organize, or Settings views
- Do not change any column constants in the track panel
- Do not add any new visual elements not specified in this prompt — no connector lines, no shadows, no extra borders

---

## General Requirements

- Serato custom ID3 frames are never modified under any circumstances
- Teal (`#428175`) = action color for drag indicators and footer text
- Orange (`#D17D34`) = selection color
- Tree expanded/collapsed state must be preserved after every operation
- After any crate drag operation, reload the crate tree and reapply selection states
