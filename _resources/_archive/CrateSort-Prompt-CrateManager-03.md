# CrateSort — Crate Manager Bug Fixes & Polish (Prompt 3)

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates. Read all referenced files before making any changes.

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
- Undo/Redo buttons when active

Everything else is informational and uses the standard cream/muted palette. This rule applies to every view in the app.

## Files to Read First

Read all of these before writing any code:

- `src/gui/crate_manager.py` — primary file, most changes live here
- `src/gui/main_window.py` — signal wiring, nav handling
- `src/gui/theme.py` — styling constants
- `src/serato/crate_reader.py` — crate data reading
- `src/serato/crate_writer.py` — crate data writing
- `src/gui/library_browser.py` — reference for visual patterns, row height, teal flash behavior

---

## Fix 1 — `#` Column: Numeric Sort

The `#` column is sorting as a string (lexicographic), producing order like 1, 10, 100, 101, 11, 12, 2... instead of 1, 2, 3, 4, 5, 10, 11, 100.

Fix: store the integer value in `Qt.ItemDataRole.UserRole` on every `#` column cell and sort by that role instead of the display text. The display text remains a plain integer string (no padding). The sort must be numeric in both ascending and descending directions.

---

## Fix 2 — `#` Column: Sort Toggle Not Working

Clicking the `#` column header does not toggle between ascending and descending sort order. Every other column toggles correctly.

The likely cause is that the `#` header click is being intercepted by the "restore crate file order" logic and never reaching the sort toggle. Fix this so:

- First click on `#` header = sort ascending by position (1, 2, 3...)
- Second click on `#` header = sort descending by position (...3, 2, 1)
- The ascending/descending arrow indicator in the header must reflect the current direction
- The "restore crate file order" behavior is effectively the same as sorting ascending by `#` — implement it as such rather than as a separate intercept

---

## Fix 3 — Sub-Crate Expand Indicators: Still Missing

Parent crates with child crates still do not show expand/collapse arrows despite being targeted in previous prompts. This must be fixed.

- Every crate item that has at least one child crate must show an expand/collapse arrow/caret
- The indicator must be visible even when the crate is collapsed
- Use `setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)` on every parent item
- Verify this works for all nesting levels (parent → child → grandchild)

---

## Fix 4 — Parent Crate Track Count: Include Sub-Crate Totals

Parent crates currently show only the count of tracks directly in that crate, ignoring sub-crate contents. Example: Blues shows (0) even though its sub-crate Jump Blues has 14 tracks.

Fix: the count displayed next to each parent crate name must be the **combined total** of all tracks across the parent crate and all of its sub-crates at any depth.

- Blues (0 direct + 14 in Jump Blues) → displays as **Blues (14)**
- Funk (799 direct + 49 + 102 + 59 + 446 + 174 in sub-crates) → displays as **Funk (1629)**
- Leaf crates (no children) display their own count unchanged
- Recalculate on every crate tree load and after any add/remove operation

---

## Fix 5 — Drag to Reorder Tracks in Track Panel: Full Rewrite

The current drag-reorder implementation corrupts the track panel — dropping on an existing row replaces it instead of inserting before/after it, creating empty ghost rows and destroying track data. The drop never writes to the `.crate` file. This needs a full rewrite.

### Requirements:

**Drop behavior:**
- Dragging must insert the dragged row(s) between existing rows — never overwrite an existing row
- Drop targets are only valid **between** rows, never **on** a row
- If the user drops on a row rather than between rows, snap to the nearest between-row position

**Drop indicator:**
- Show a teal (`#428175`) horizontal line between rows indicating exactly where the dragged track(s) will land
- The line must update in real time as the cursor moves up and down the list
- The line must be clearly visible — at least 2px thick, full width of the track panel

**Cursor:**
- Change to `Qt.CursorShape.ClosedHandCursor` when a drag begins
- Revert to default cursor on drop or cancel

**On successful drop:**
- Write the new track order permanently to the `.crate` file immediately via `crate_writer.reorder_tracks()`
- Renumber the `#` column to reflect the new order
- Reapply the active global sort after renumbering
- Show teal footer text: *"Reordered [X] track(s) in [Crate Name]"*

**Multi-select:**
- Shift-selecting multiple tracks and dragging them must move all selected tracks as a group to the drop position

---

## Fix 6 — Drag to Reorder Crates in Crate Tree: Full Rewrite

Dragging crates shows a ghost but the drop never executes — crates do not reorder. This needs a full rewrite.

### Requirements:

**Drop between crates (reorder siblings):**
- Show a teal (`#428175`) horizontal line between crate rows indicating where the dragged crate will land
- The line must update in real time as the cursor moves
- On drop between crates at the same level, reorder the crates among their siblings
- Write the new order to `.crate` files immediately on drop

**Drop onto a crate (make sub-crate):**
- If the user hovers over a target crate (not between crates) for 1.5 seconds, that crate expands automatically and accepts the drop as a new sub-crate
- Alternatively, if the user has manually expanded a parent crate and drops inside it, it becomes a sub-crate of that parent
- The target crate must highlight (subtle teal border or background tint) during the hover-to-expand delay

**General:**
- A crate cannot be dropped onto itself
- Expanded/collapsed state of the tree must be preserved after the drop
- Teal footer text confirms the operation: *"Moved '[Crate Name]' to [new position/parent]"*

---

## Fix 7 — Row Height Drift: Use Uniform Row Heights

The crate tree and track panel rows start roughly aligned but drift apart further down the list due to fractional pixel differences in how each panel calculates row height.

Fix:
- Call `setUniformRowHeights(True)` on both the crate tree and the track panel — this forces Qt to use a single consistent row height across all rows rather than calculating per-row
- Set an explicit identical integer pixel row height on both panels (e.g. `setDefaultSectionSize(34)` or equivalent) — not "close enough" but the exact same value set the same way in both
- Verify both search fields ("Search crates..." and "Search tracks...") are also the same fixed height
- After this fix, rows should remain visually aligned across the full width of the screen regardless of how far the user scrolls

---

## Fix 8 — File Path Column: Default Width and Resize Buffer

- Set the File Path column default width wide enough to fully display "Not found in library" without truncation — calculate the pixel width of that string using font metrics and set it as the default
- Increase the right-side buffer from 10px to 30px so the File Path column resize handle is always grabbable without accidentally resizing the application window

---

## Fix 9 — Date Added Column

Add a Date Added column to the track panel showing when each track was added to the crate.

- Pull the date from the `.crate` file — Serato stores an add-timestamp per track entry; read it from `crate_reader.py`
- If the timestamp exists: display as a numerical date (e.g. `2024-03-15` or `03/15/2024` — match whatever format Serato uses)
- If the timestamp does not exist for a track: display `—` (em dash, consistent with other empty fields)
- Column is sortable — ascending shows oldest additions first, descending shows most recently added first
- Column is resizable and draggable like all other columns
- Column width persists via the existing QSettings column state save/restore
- Place the Date Added column after BPM and before Format in the default column order

---

## Fix 10 — Crate Tree Parent/Child Connector Lines

When a parent crate is expanded, there is no visual indicator connecting the parent to its sub-crates. When scrolled deep into a long list of sub-crates, the user loses track of which parent they belong to.

Add vertical connector lines to the crate tree:

- A vertical line runs down the left side of all sub-crate rows, from the parent crate to the last child in that group
- The line is styled in a subtle muted color (use `#4a4a4a` or similar — visible but not distracting)
- When a sub-crate is selected, the connector line for its parent group remains visible so the user always knows which parent they are under
- Lines must work at all nesting levels (parent → child → grandchild)
- If Qt's built-in tree lines are sufficient (`setRootIsDecorated(True)` + stylesheet `::branch` styling), use those and style them to match the CrateSort theme. If custom painting is needed, implement a clean custom delegate.

---

## General Requirements

- The `.crate` file order is only ever changed by explicit user drag reorder actions (Fix 5). All other sorting is visual and temporary.
- Serato custom ID3 frames (cue points, beat grids, loops, color tags, markers) are never modified under any circumstances.
- Teal (`#428175`) is the action color — used for drag indicators, footer status text, and edit flashes. Never use teal for static informational display.
- All teal footer status text updates after every operation to describe what happened.
- Tree expanded/collapsed state and crate selection must be preserved after every operation.
- All visual changes must be consistent with `library_browser.py` patterns.
