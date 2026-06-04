# CrateSort — Crate Tree Final Fix (Prompt 9)

> **Run this at Sonnet high effort. Read `src/gui/crate_manager.py` completely before writing a single line of code. This prompt fixes the crate tree selection colors, parent state logic, sub-crate indentation, and row height alignment. Do not change anything outside the crate tree.**

## Files to Read First

- `src/gui/crate_manager.py` — primary file
- `src/gui/theme.py` — color constants

---

## The Visual Target

Here is exactly what the crate tree must look like. Memorize this before writing any code:

- **Panel background:** `#2F2F2F` — the entire crate tree panel
- **Unselected crate:** `#2F2F2F` background, cream `#f1e3c8` text — blends with panel, invisible
- **Selected crate (any crate clicked directly, no sub-crate involved):** warm brown `#8B5E3C` background, cream `#f1e3c8` text, NO left bar
- **Active parent (parent whose sub-crate is selected):** `#2F2F2F` background (same as panel — it just shows the orange left bar), orange `#D17D34` left bar 5px wide, cream text
- **Selected sub-crate:** warm brown `#8B5E3C` background, cream `#f1e3c8` text, orange `#D17D34` left bar 5px wide

---

## Fix 1 — CrateRowWidget: Correct Colors for All Four States

Find `CrateRowWidget` and its `set_state()` method (or equivalent). Replace the color values for all four states with exactly these — no other values:

**State A — unselected:**
```python
self.setStyleSheet("background-color: #2F2F2F;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.hide()
```

**State B — selected (directly clicked, no active sub-crate):**
```python
self.setStyleSheet("background-color: #8B5E3C;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.hide()
```

**State C — active parent (sub-crate within this parent is selected):**
```python
self.setStyleSheet("background-color: #2F2F2F;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.show()  # orange #D17D34, 5px wide
```

**State D — selected sub-crate:**
```python
self.setStyleSheet("background-color: #8B5E3C;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.show()  # orange #D17D34, 5px wide
```

Verify the orange bar `_bar` QFrame has:
```python
self._bar.setFixedWidth(5)
self._bar.setStyleSheet("background-color: #D17D34; border: none;")
```

---

## Fix 2 — Parent State Logic: Force State C on Parent

In `_on_tree_selection_changed`, after the new item is selected:

1. Reset `_prev_selected_item` to State A
2. Reset `_prev_parent_item` to State A  
3. Get the new item's parent: `parent_item = current.parent()`
4. If `parent_item` is not None AND `parent_item` is not the invisible root:
   - Apply State D to the new item
   - Get the parent's widget: `parent_widget = self._crate_tree.itemWidget(parent_item, 0)`
   - If `parent_widget` is not None: `parent_widget.set_state("C")`
   - Store `parent_item` as `_prev_parent_item`
5. If `parent_item` is None (top-level crate selected):
   - Apply State B to the new item
   - `_prev_parent_item = None`
6. Store the new item as `_prev_selected_item`

This logic must execute every single time a crate is clicked. Add a debug print to confirm:
```python
print(f"[Selection] item={crate_name}, parent={parent_name}, state={'D' if parent_item else 'B'}")
```

---

## Fix 3 — Sub-Crate Indentation: Remove Extra Left Notch

Sub-crate rows currently have an extra left indent that creates a visible notch before the text. This must be removed.

The indentation of sub-crate text relative to parent text should come only from Qt's natural tree indentation — do not add any extra left margin or padding on sub-crate items.

In `CrateRowWidget.__init__()`, verify the layout has zero extra left margin:
```python
layout = QHBoxLayout(self)
layout.setContentsMargins(0, 0, 0, 0)
layout.setSpacing(0)
layout.addWidget(self._bar)   # 5px, hidden by default
layout.addWidget(self._label) # fills remaining width
```

The `_label` must have a fixed left padding of 8px for text breathing room:
```python
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent; padding-left: 8px;")
```

This padding must be the same in ALL states — never changes.

---

## Fix 4 — Row Height: Match Track Panel Exactly

The crate tree rows are still taller than the track panel rows. 

- `CrateRowWidget.setFixedHeight(32)` — widget body is 32px
- `QTreeWidget::item { height: 34px; min-height: 34px; max-height: 34px; border-bottom: 1px solid #383838; padding: 0px; }` — Qt item is 34px total with 1px separator

Verify BOTH of these are set. If the rows are still drifting or mismatched, add:
```python
self._crate_tree.setUniformRowHeights(True)
```
immediately after `self._crate_tree` is instantiated.

Also verify `horizontalHeader().setFixedHeight(34)` is set on the track table so the column header row matches too.

---

## Fix 5 — Vertical Connector Line for Sub-Crate Groups

When a parent crate is expanded, a vertical line must appear on the left side of the sub-crate rows connecting them visually to their parent.

Add this to the `QTreeWidget` stylesheet:
```css
QTreeWidget::branch:has-siblings:!adjoins-item {
    border-image: none;
    border-left: 1px solid #4a4a4a;
}
QTreeWidget::branch:has-siblings:adjoins-item {
    border-image: none;
    border-left: 1px solid #4a4a4a;
}
QTreeWidget::branch:!has-siblings:adjoins-item {
    border-image: none;
    border-left: 1px solid #4a4a4a;
}
```

This draws a subtle `#4a4a4a` vertical line in the branch gutter connecting sub-crates to their parent. It must not interfere with the expand arrow indicator.

---

---

## Fix 6 — All Tracks Row: Remove Bold, Match Other Crates

The "All Tracks" row at the top of the crate tree is currently bold in all states and shows dark text when selected. It must follow the exact same styling as every other crate row.

- Remove any bold font weight applied to the All Tracks item or its `CrateRowWidget`
- The All Tracks `CrateRowWidget` must use identical state colors as all other rows — State B (`#8B5E3C` warm brown, cream text) when selected
- Search the file for any special-case styling applied to the All Tracks item (look for `_ALL_TRACKS_KEY` or similar) and remove any font weight or color overrides
- All Tracks must be visually indistinguishable from any other crate row except for its name and position

---

## Fix 7 — Drag Reparent: Works When Dropped Between Sub-Crates

Dragging a crate into a parent works when dropped directly on the parent row, but not when dropped between sub-crate rows within that parent. The crate stays where it was.

Fix: when the drop position is between two sub-crate rows that share the same parent, treat the drop as a reparent into that shared parent.

- Detect the target row at the drop position
- If the target row is a sub-crate (its path contains `/`), resolve its parent: `parent_path = "/".join(target_path.split("/")[:-1])`
- Reparent the dragged crate under that resolved parent
- The dragged crate is inserted at the position between the two sub-crates where it was dropped
- Write the change to `.crate` files immediately
- Teal footer text confirms: *"Moved '[Crate Name]' into [Parent Name]"*

---

## What NOT to Change

- Do not touch the track panel, track drag logic, column constants, or any other view
- Do not change expand/collapse behavior (single click = select, double click = expand/collapse)
- Do not remove the expand indicators (`setChildIndicatorPolicy(ShowIndicator)`)
- Only change what is explicitly described in this prompt
