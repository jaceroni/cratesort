# CrateSort — Crate Tree State C Path Mismatch Fix (Prompt 12)

> **Run this at Sonnet high effort. Read `src/gui/crate_manager.py` completely before making any changes.**

## Files to Read First

- `src/gui/crate_manager.py` — only file to change

---

## The Problem

State C IS being set on the parent item (confirmed by terminal output showing "[State C] applying to parent: 'Funk'"). However the parent crate is not turning black. This means the path key used to SET the state in `_states` dict does not match the path key used to LOOK UP the state in `paint()`.

In `_on_tree_selection_changed`, the parent path comes from `parent_item.data(0, Qt.ItemDataRole.UserRole)`.

In `CrateItemDelegate.paint()`, the path lookup comes from `index.data(Qt.ItemDataRole.UserRole)`.

These two values must be identical strings for the lookup to work. They are currently not matching.

---

## Fix 1 — Debug the Path Mismatch

Add these two print statements and run the app, click a sub-crate, paste the output:

In `_on_tree_selection_changed`, immediately before the `set_item_state` call for State C:
- Print the exact string value of `parent_path`

In `CrateItemDelegate.paint()`, at the very top of the method:
- Print `path` and `state` for every item being painted

This will show the exact strings being used on both sides and reveal the mismatch.

---

## Fix 2 — Orange Left Bar on State B

When a top-level crate is directly selected (State B), it must show the bright orange left bar in addition to the burnt orange background. Currently State B has no bar.

In `CrateItemDelegate.paint()`, change the bar drawing condition from:

State C and D only show the bar

To:

State B, C, and D all show the bar. State A is the only state with no bar.

---

## Fix 3 — Caret/Arrow Padding from Right Edge

The expand/collapse arrow (▶/▼) is too close to the right edge of the crate tree panel. Move it 25px away from the right edge.

In `CrateItemDelegate.paint()`, find where the indicator rect is calculated. Change the right-side adjustment so the arrow renders 25px from the right edge of the row instead of flush against it.

---

## Fix 4 — Vertical Connector Line for Sub-Crate Groups

When a parent crate is expanded, a vertical line must connect the parent to its sub-crates visually. This line must be drawn in the branch gutter area to the left of the sub-crate text.

Add these rules to the crate tree stylesheet:

QTreeWidget::branch:has-siblings:!adjoins-item — border-left: 1px solid #4a4a4a, background: #2F2F2F

QTreeWidget::branch:has-siblings:adjoins-item — border-left: 1px solid #4a4a4a, background: #2F2F2F

QTreeWidget::branch:!has-siblings:adjoins-item — border-left: 1px solid #4a4a4a, background: #2F2F2F

These draw a subtle vertical line in the branch gutter connecting sub-crates to their parent without interfering with the delegate's item rendering.

---

## What NOT to Change

Do not touch drag logic, expand behavior, track panel, library browser, or any other view. Only make the four changes described above. After running, paste the terminal output when clicking a sub-crate.
