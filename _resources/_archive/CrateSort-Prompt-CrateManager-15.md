# CrateSort — Track Tables: Full Grid, Consistent Across All Views (Prompt 15)

> **Run this at Sonnet high effort. Read all referenced files completely before making any changes.**

## Files to Read First

- `src/gui/crate_manager.py`
- `src/gui/library_browser.py`
- `src/gui/dashboard.py`
- Any other file containing a track listing table (classification results, organize view)

---

## The Goal

All track listing tables across the entire app must have a consistent visual style:

- **Full grid lines** — both vertical column separators AND horizontal row borders, always
- **Alternating row colors** — `#242424` (odd rows) and `#2a2a2a` (even rows)
- **Grid line color** — `#383838` matching the column header separator style

This applies to every QTableWidget or QTreeWidget that displays track listings anywhere in the app.

---

## The Standard Implementation

Apply this to every track listing table in the app:

Enable alternating row colors:
- `setAlternatingRowColors(True)`

Set alternating colors via palette:
- Base color (odd rows): `#242424`
- AlternateBase color (even rows): `#2a2a2a`

Enable the grid and set its color via stylesheet:
- `setShowGrid(True)`
- Add to the table's stylesheet: `QTableWidget { gridline-color: #383838; }`

---

## Apply To All Track Listing Tables

Find every QTableWidget in these files that displays tracks and apply the standard implementation above:

- `src/gui/crate_manager.py` — the track panel table
- `src/gui/library_browser.py` — the library track table
- `src/gui/dashboard.py` — any track listing tables
- Any classification results view or organize view that contains a track table

---

## General Requirements

- Do NOT touch any row height settings anywhere — setDefaultSectionSize, setMinimumSectionSize, setMaximumSectionSize must remain exactly as they are
- Do NOT touch the crate tree styling or delegate
- Do NOT change column widths, sort behavior, or any other functionality
- The visual result must be identical across all track listing views — same alternating colors, same grid color, same grid style
