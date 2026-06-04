# CrateSort — Crate Manager Bug Fixes & Polish (Prompt 2)

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates. Read all referenced files before making any changes.

## Terminology

- **Crate tree** = the left panel in the Crates tab showing the crate hierarchy
- **Track panel** = the right panel in the Crates tab showing tracks within a selected crate
- **Resolved track** = a track whose file exists in the scanned library
- **Unresolved track** = a track referenced in a Serato crate whose file was not found in the scanned library

## Files to Read First

Read all of these before writing any code:

- `src/gui/crate_manager.py` — primary file, most changes live here
- `src/gui/main_window.py` — signal wiring, nav handling
- `src/gui/theme.py` — styling constants
- `src/serato/crate_reader.py` — crate data reading
- `src/serato/crate_writer.py` — crate data writing
- `src/gui/library_browser.py` — reference for visual patterns, row height, separators, spacing

---

## Fix 1 — `#` Column: Remove Zero Padding

The `#` column currently displays zero-padded numbers (000001, 000002). Remove all zero padding. Display plain integers only — 1, 2, 3, 100, 1000, 18557. No leading zeros, no zero-fill, no ellipsis truncation on the number itself.

---

## Fix 2 — `#` Column: Auto-Size Width to Content

On load and every time a different crate is selected, calculate the width needed to fully display the longest number in that crate without truncation.

- Example: a crate with 58 tracks needs enough width to show "58". A crate with 18,556 tracks needs enough width to show "18556".
- Set the column width dynamically based on this calculation each time a crate is selected.
- No truncation, no ellipsis — the full integer must always be visible.

---

## Fix 3 — Sort Persistence: Global and Operation-Proof

The active sort column and sort direction must persist globally across the entire Crates tab session.

- When the user sorts by any column in any crate, that sort column and direction become the global active sort.
- Navigating to a different crate must apply the same sort — never revert to `#` order unless the user explicitly clicks the `#` column header.
- After any operation (add track, remove track, delete crate, drag reorder, rename), the track panel must reapply the active sort after refreshing. It must never revert to original order as a side effect of an operation.
- Store the active sort column index and Qt.SortOrder in a single place and reapply it consistently after every track panel rebuild.

---

## Fix 4 — Drag to Reorder Tracks in Track Panel: Fix Broken Drop + UX

Drag reordering within the track panel initiates but the drop never executes. Fix the drop so it actually reorders tracks and writes the new order to the `.crate` file.

Additionally:

- **Hand cursor**: When the user begins dragging a row, the cursor must change to a hand/grab cursor (`Qt.CursorShape.ClosedHandCursor` or equivalent). It must revert to the default cursor on drop or cancel.
- **Drop indicator**: Show a visible horizontal line indicator between rows as the user drags, showing exactly where the dragged track(s) will land. This must update in real time as the cursor moves.
- On successful drop, write the new order permanently to the `.crate` file via `crate_writer.reorder_tracks()`.
- Renumber the `#` column to reflect the new order.
- Reapply the active global sort after renumbering (Fix 3).
- Teal footer text confirms: *"Reordered [X] track(s) in [Crate Name]"*

---

## Fix 5 — Drag to Reorder Crates in Crate Tree: Fix Broken Drop

Dragging crates in the crate tree shows a ghost correctly but the drop never executes. Fix the drop so it actually reorders or reparents the crate and writes the change immediately.

- On drop, compute the new position and parent from the drop target.
- Write the new crate order/hierarchy to the `.crate` files immediately.
- Preserve the expanded/collapsed state of the tree after the drop.
- A crate cannot be dropped onto itself.

---

## Fix 6 — "Not Found in Library": Move from Comments to File Path Column

Currently, unresolved tracks display "Not found in library" in the Comments column. This is incorrect.

- **Remove** "Not found in library" from the Comments column entirely.
- The Comments column must show actual track comment metadata from the file's ID3 tags, or be empty if no comment exists. Never inject status text into Comments.
- **Add** "Not found in library" as the display value in the File Path column for unresolved tracks.
- Resolved tracks display their actual file path in the File Path column.

---

## Fix 7 — File Path Column: Populate for Resolved Tracks

The File Path column is currently empty for all tracks including resolved ones. Fix this so resolved tracks display their full file path in the File Path column.

---

## Fix 8 — Last Column Resize Handle: Add Buffer

The File Path column is the last column in the track panel. Its right-edge resize handle sits flush against the window edge, making it nearly impossible to grab without resizing the application window.

Add a small fixed buffer (minimum 8–12px) of non-interactive space after the last column so the resize handle is always accessible regardless of window width. The track panel should have a minimum width or right margin that ensures the last column's resize handle is always reachable.

---

## Fix 9 — Row Height and Search Field Consistency

The crate tree rows and track panel rows are currently different heights. The "Search crates..." and "Search tracks..." fields are also different heights. Everything must match.

- Set the crate tree row height to exactly match the track panel row height.
- Set both search fields to the same height.
- The visual result should be a clean horizontal alignment across the full width of the screen — crate rows and track rows sitting on the same grid line.
- Reference `library_browser.py` for the row height values already in use.

---

## Fix 10 — Crate Tree Row Separators

The track panel has visible separator lines between each row. The crate tree has no separators — rows float with no visual division.

Add separator lines between crate tree rows that match the style of the track panel row separators. The visual treatment (color, weight, opacity) must be consistent between both panels.

---

## General Requirements

- The `.crate` file order is only ever changed by explicit user drag reorder actions (Fix 4). All other sorting is visual and temporary.
- Serato custom ID3 frames (cue points, beat grids, loops, color tags, markers) are never modified under any circumstances.
- All teal footer status text updates after every operation to describe what happened.
- Tree expanded/collapsed state and crate selection must be preserved after every operation.
- All visual changes must be consistent with `library_browser.py` patterns.
