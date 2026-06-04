# CrateSort — Track Panel: Remove Borders, Add Alternating Row Colors (Prompt 14)

> **Run this at Sonnet high effort. Read `src/gui/crate_manager.py` and `src/gui/library_browser.py` completely before making any changes.**

## Files to Read First

- `src/gui/crate_manager.py` — primary file
- `src/gui/library_browser.py` — reference for how alternating row colors are implemented in the Library view

---

## The Goal

The crates track panel currently has visible borders on every row and column, making it visually inconsistent with the Dashboard, Classification, and Library views which use borderless rows with alternating row colors. This prompt removes the borders and adds alternating row colors to match the rest of the app.

---

## Change 1 — Remove Row and Column Borders from Track Panel

In the track panel's (`_track_table`) stylesheet, remove any rules that add borders to rows or columns. Specifically remove:

- Any `border` or `border-bottom` rules on `QTableWidget::item`
- Any `gridline-color` settings
- Any `QTableWidget` border rules that create visible grid lines between cells

Also call `self._track_table.setShowGrid(False)` to disable Qt's built-in grid lines.

---

## Change 2 — Add Alternating Row Colors

Enable alternating row colors on the track panel to replace the visual separation that borders were providing.

Call `self._track_table.setAlternatingRowColors(True)`.

Set the alternating colors via the widget's palette:

- Base color (odd rows): `#242424`
- Alternate base color (even rows): `#2a2a2a`

Apply via:
```
palette = self._track_table.palette()
palette.setColor(QPalette.ColorRole.Base, QColor('#242424'))
palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#2a2a2a'))
self._track_table.setPalette(palette)
```

---

## What NOT to Change

- Do NOT touch any row height settings — `setDefaultSectionSize`, `setMinimumSectionSize`, `setMaximumSectionSize` must remain exactly as they are
- Do NOT touch the crate tree styling, separator lines, or delegate
- Do NOT touch the Library Browser, Dashboard, or any other view
- Do NOT change column widths, sort behavior, or any other track panel functionality
- Only remove borders and add alternating row colors to the track panel
