# CrateSort — Crate Manager Bug Fixes & Polish (Prompt 4)

> **Run this at Sonnet high effort. Read every referenced file completely before writing a single line of code. Do not skim. Do not make assumptions about column constants — verify every index before using it.**

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates.

## Core Philosophy

CrateSort is the single writer. Serato is the reader. Whatever CrateSort writes, Serato picks up on next launch. CrateSort owns the crate structure completely — crate order, crate hierarchy, crate names. Do not defer to Serato's defaults or alphabetical ordering. If reordering crates means Serato picks up the new order, that is intentional and correct.

## Terminology

- **Crate tree** = the left panel in the Crates tab showing the crate hierarchy
- **Track panel** = the right panel in the Crates tab showing tracks within a selected crate
- **Resolved track** = a track whose file exists in the scanned library
- **Unresolved track** = a track referenced in a Serato crate whose file was not found in the scanned library

## Design Rule — Teal = Action

Teal (`#428175`) is the action color throughout the entire app. Any time something is happening or has just happened, it must be teal:
- Drag indicator lines showing drop targets
- Footer status text after any operation
- Inline edit flashes when a cell edit is committed

Everything else is informational and uses the standard cream/muted palette.

## Files to Read First

Read ALL of these completely before writing any code:

- `src/gui/crate_manager.py` — primary file, most changes live here
- `src/gui/main_window.py` — signal wiring, nav handling
- `src/gui/theme.py` — styling constants
- `src/serato/crate_reader.py` — crate data reading
- `src/serato/crate_writer.py` — crate data writing
- `src/gui/library_browser.py` — reference for visual patterns, row height, teal flash behavior
- `src/core/scanner.py` — TrackRecord structure reference

---

## Fix 1 — Crate Tree: Full Visual Overhaul

The crate tree selection indicators, hierarchy connectors, and expand behavior all need a complete visual overhaul. The current implementation has broken indentation, text shifting on selection, partial orange slivers instead of solid indicators, and connector lines that don't close properly.

### Selection indicator — orange bar

- A solid orange (`#D17D34`) bar, **25-30px wide**, on the left edge of any selected row
- This bar fills the left gutter between the tree edge and the text start
- It is NOT a background color behind the text — it is a left-side accent bar of fixed width
- Implement via `::branch` and `::item` stylesheet rules or a custom delegate — whichever produces a clean, non-shifting result

### Parent crate states

- **Unselected, no sub-crate active**: standard dark background (`#1a1a1a`), no orange bar
- **Selected directly (no sub-crates expanded or active)**: orange bar on left, standard background
- **When a sub-crate within it is selected**: background shifts to dark charcoal (`#2F2F2F`) — signals "I am the active parent". Orange bar present on the parent row.
- **Selected sub-crate**: orange bar on left, burnt orange background (`#D17D34`) behind text area

### Text indentation — must not shift

- Sub-crate text is indented from parent text — that indentation is fixed and correct
- Text must NEVER shift or bump further right due to selection state or expand/collapse state
- The orange bar occupies the left gutter — it must not push text

### Expand/collapse

- No visible arrow or caret that displaces text position
- Single click expands/collapses a parent crate
- The expand indicator, if any, must live entirely within the left gutter and not affect text position

### Vertical connector lines

- A vertical line runs down the left side of all sub-crate rows in an expanded group
- The line fills the full width of the indent area — not a hairline, a solid muted block
- Color: `#4a4a4a` — visible but not distracting
- Lines must work at all nesting levels

### Bottom cap — critical

- A horizontal line at the bottom of the **last sub-crate** in each expanded group connects to the vertical connector line
- This closes the bracket, making it unambiguous where one parent's sub-crates end and the next parent begins
- Without this cap, adjacent parent crates appear to belong to the group above them

---

## Fix 2 — Track Drag Reorder: Full Rewrite Using Reload-After-Write

The current `takeItem`/`removeRow`/`insertRow` approach corrupts rows and never writes to disk. Abandon it completely.

### New approach — capture, write, reload:

1. On drag start: record the original order of all track paths in the crate
2. Show teal (`#428175`) horizontal drop indicator line between rows in real time as cursor moves — at least 2px thick, full width of track panel
3. Change cursor to `Qt.CursorShape.ClosedHandCursor` on drag start, revert on drop or cancel
4. On drop: compute the new order of track paths based on where the rows were dragged to
5. Call `crate_writer.reorder_tracks(crate_path, new_order)` to write the new order to the `.crate` file
6. **Immediately reload the crate from the `.crate` file** by calling the same populate method used when a crate is selected — this guarantees the track panel always reflects what's on disk with no orphaned rows, no ghost rows, no data corruption
7. Renumber the `#` column after reload
8. Reapply the active global sort after renumbering
9. Preserve the selected crate in the tree after reload
10. Show teal footer text: *"Reordered [X] track(s) in [Crate Name]"*

### Multi-select drag:
- Shift-selecting multiple tracks and dragging moves all selected tracks as a group to the drop position

### Drop target:
- Drop targets are only valid **between** rows, never **on** a row
- If cursor is over a row rather than between rows, snap to the nearest between-row gap

---

## Fix 3 — Crate Drag Reorder and Reparent: Full Rewrite

Crate dragging shows a ghost but never executes. The current implementation does not work at all. This needs to be built from scratch with a fully manual drag implementation — do not rely on Qt's built-in tree drag behavior.

### Sibling reorder (drag between crates at the same level):

- Show a teal (`#428175`) horizontal line between crate rows indicating where the dragged crate will land
- The line updates in real time as the cursor moves
- On drop between siblings, reorder the crates
- Write the new order to `.crate` files immediately
- Note: CrateSort owns crate order completely. If reordering requires renaming crate files so Serato picks up the new order, do it. Serato reads whatever CrateSort writes.

### Reparent (drag onto a parent to make sub-crate):

- If the cursor hovers over a target crate (not between crates) for **1.5 seconds**, that crate expands automatically and accepts the drop as a new sub-crate
- The target crate highlights with a subtle teal border during the hover-to-expand delay
- On drop inside an expanded parent, the dragged crate becomes a sub-crate of that parent
- Write the new hierarchy to `.crate` files immediately

### General rules:
- A crate cannot be dropped onto itself
- Expanded/collapsed state of the tree must be preserved after the drop
- Teal footer text confirms: *"Moved '[Crate Name]' to [new position/parent]"*

---

## Fix 4 — Row Height: Same Explicit Pixel Value on Both Panels

The crate tree rows and track panel rows are still different heights and drift apart when scrolling. This must be fixed with identical explicit pixel values — no dynamic calculation, no "close enough."

### Implementation:

- Choose one explicit integer pixel value for all rows: **34px**
- Crate tree:
  - `setUniformRowHeights(True)`
  - stylesheet: `QTreeWidget::item { height: 34px; min-height: 34px; max-height: 34px; }`
- Track panel (QTableWidget — does NOT have setUniformRowHeights):
  - `verticalHeader().setDefaultSectionSize(34)`
  - `verticalHeader().setMinimumSectionSize(34)`
  - `verticalHeader().setMaximumSectionSize(34)`
- Both search fields ("Search crates..." and "Search tracks..."): set to the same fixed height explicitly — `setFixedHeight(34)`
- No row height should ever be calculated dynamically after this — all hardcoded to 34px

---

## Fix 5 — File Path Column: Width and Accessibility

The File Path column is being clipped and the resize handle is inaccessible even with horizontal scrolling.

### Implementation:

- Set File Path column minimum width to **300px** — wide enough to show "Not found in library" without truncation
- Set `horizontalScrollMode` to `QAbstractItemView.ScrollMode.ScrollPerPixel` on the track table for smooth scrolling
- Do NOT use `setContentsMargins` for the right buffer — it is not working
- Instead, set a right margin on the track panel's scroll area or add a fixed-width empty spacer column as the last column (invisible, non-interactive, ~20px) so the File Path resize handle is always accessible
- The user must be able to grab and resize the File Path column via horizontal scroll without resizing the application window

---

## General Requirements

- **Always run at Sonnet high effort.** Read every file completely. Verify every column constant index before using it — do not assume they are the same as in previous sessions.
- The `.crate` file order is only ever changed by explicit user drag reorder actions. All other sorting is visual and temporary.
- Serato custom ID3 frames (cue points, beat grids, loops, color tags, markers) are never modified under any circumstances.
- Teal (`#428175`) is the action color — drag indicators, footer status text, edit flashes. Never use teal for static informational display.
- Tree expanded/collapsed state and crate selection must be preserved after every operation.
- All visual changes must be consistent with `library_browser.py` patterns.
- After any operation that modifies crate contents, reload the track panel from the `.crate` file rather than manipulating table rows directly. This is the only reliable way to guarantee data integrity.
