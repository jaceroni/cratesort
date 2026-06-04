# CrateSort — Crate Manager Focused Fix (Prompt 7)

> **Run this at Sonnet high effort. Read every referenced file completely before writing a single line of code. Do not skim. Verify every assumption against the actual code.**

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates.

## Files to Read First

Read ALL of these completely before writing any code:

- `src/gui/crate_manager.py` — primary file, most changes live here
- `src/gui/theme.py` — color constants
- `src/serato/crate_reader.py` — for understanding track path reading per crate
- `src/serato/crate_writer.py` — for crate rename/delete path resolution

---

## Fix 1 — Crate Tree Selection Colors: setItemWidget Approach

Every previous attempt to implement selection colors via stylesheet or delegate has failed due to Qt overriding the colors. This time use `setItemWidget()` to place a custom `QWidget` on each row. This bypasses Qt's selection painting entirely.

### Implementation:

For each crate item in the tree, call `self._crate_tree.setItemWidget(item, 0, widget)` where `widget` is a custom `CrateRowWidget(QWidget)` that:

- Contains a `QLabel` for the crate name text
- Has a fixed-height left bar `QFrame` (5px wide, `#D17D34`) that is shown or hidden depending on state
- Has a background color set via `setStyleSheet("background-color: ...")` on the widget itself

### The four states applied via `CrateRowWidget`:

**State A — unselected:**
- Widget background: `#1a1a1a`
- Label text color: `#f1e3c8`
- Left bar: hidden

**State B — selected (no active sub-crate):**
- Widget background: `#D17D34`
- Label text color: `#1a1a1a`
- Left bar: hidden (full background IS the indicator)

**State C — parent of active sub-crate:**
- Widget background: `#2F2F2F`
- Label text color: `#f1e3c8`
- Left bar: visible, `#D17D34`, 5px wide

**State D — selected sub-crate:**
- Widget background: `#8B5E3C`
- Label text color: `#f1e3c8`
- Left bar: visible, `#D17D34`, 5px wide

### State transition rules:

- Single click any crate → State B. Load its tracks. Never auto-expand.
- Double click a parent crate → expand/collapse. State does not change.
- Single click a sub-crate → sub-crate goes State D. Parent goes State C.
- Click a completely different unrelated crate → all previous states reset to A. New crate goes State B.

### Critical: minimum item resets per interaction

**Do NOT reset the entire tree on every selection change.** This is what is causing the expand/collapse lag. Instead:

- Track `_prev_selected_item` and `_prev_parent_item` as instance variables
- On each selection change, reset ONLY `_prev_selected_item` and `_prev_parent_item` to State A
- Apply new states to the newly selected item and its parent only
- Maximum 4 `CrateRowWidget` updates per selection change, regardless of library size

### Text padding must not shift between states:

- The `QLabel` inside `CrateRowWidget` must have fixed left padding that never changes between states
- The left bar widget sits to the left of the label and is shown/hidden — it must not push the label text when it appears
- Use a `QHBoxLayout` with the bar and label as siblings, with the bar having a fixed width of 5px and the label having consistent left margin

---

## Fix 2 — Expand Indicators: Verify and Force

Parent crates with child crates must show a visible expand/collapse indicator. This has been requested many times and keeps disappearing.

After building the tree:

1. Call `item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)` on EVERY item that has children — do this in `_add_crate_item` and verify it is not being removed anywhere in the rebuild process
2. After the full tree is built, walk every top-level item and every child recursively and assert that any item with `childCount() > 0` has `ShowIndicator` set
3. Add a stylesheet rule for `QTreeWidget::branch` that makes the indicator visible against the dark background — the default macOS indicator may be invisible on dark themes:
```css
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    image: url(none);
    border-image: none;
    background: transparent;
}
```
Use a Unicode arrow character (`▶` collapsed, `▼` expanded) drawn in the `CrateRowWidget` itself if Qt's branch indicator remains invisible — place it to the right of the crate name text, right-aligned in the row.

---

## Fix 3 — Expand/Collapse Performance

Expanding or collapsing a parent crate is noticeably laggy. The root cause is `_reset_all_tree_states()` walking the entire tree on every interaction.

### Fix:

- Remove `_reset_all_tree_states()` entirely — it must not exist
- Replace with targeted resets using `_prev_selected_item` and `_prev_parent_item` (see Fix 1)
- Connect `itemExpanded` and `itemCollapsed` signals — these must not trigger any track loading or state resets. They only expand/collapse the visual tree.
- Expand and collapse must feel instantaneous — no perceptible lag on double-click

---

## Fix 4 — Parent Crate Track Panel: Show Combined Total

When a parent crate is selected, the track panel currently shows only the tracks directly in that crate file. It must show ALL tracks — the parent's own tracks plus every sub-crate's tracks merged into one flat list.

### Implementation:

- When `_load_crate_tracks(crate_path)` is called for a crate that has children in the tree, recursively collect track paths from the crate and all its sub-crates
- Deduplicate track paths (same file may appear in parent and sub-crate)
- Load the combined flat list into the track panel
- The `#` column numbers the combined list sequentially
- The footer status bar shows the combined total: *"Funk · 1629 tracks · ..."*
- The tree count and the track panel count must agree

---

## Fix 5 — Delete After Reparent Causes App Freeze

Deleting a crate that was recently moved/reparented causes the application to freeze. This is a path resolution bug — after `rename_crate()` changes the crate path, the delete operation is likely still using the old path.

### Fix:

- In `_confirm_delete_crate()` and `_delete_crate()`, always resolve the current crate path from the selected tree item at the moment of deletion — never cache the path from before a rename/reparent operation
- After `crate_writer.delete_crate(path)` completes, remove the item from `_crate_order` dict and rebuild the tree
- If `delete_crate()` is blocking the UI thread, move it to a `QThread` or use `QApplication.processEvents()` to keep the UI responsive during deletion
- Add a timeout guard — if the delete operation takes more than 2 seconds, unfreeze the UI and show an error in the teal footer: *"Delete failed — crate file may be locked or missing"*

---

## General Requirements

- **Always run at Sonnet high effort.**
- Do not touch the track panel drag logic, column constants, or Library Browser.
- Serato custom ID3 frames are never modified.
- Teal (`#428175`) = action color. Orange (`#D17D34`) = selection color.
- Tree expanded/collapsed state must be preserved after every operation.
- After any crate drag or delete operation, rebuild only the affected portion of the tree — not the entire tree — to maintain performance.
