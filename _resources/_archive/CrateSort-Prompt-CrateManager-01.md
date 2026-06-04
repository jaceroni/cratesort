# CrateSort — Crate Manager Polish & New Features (Prompt 1)

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates. Read all referenced files before making any changes.

## Terminology

- **Crate tree** = the left panel in the Crates tab showing the crate hierarchy
- **Track panel** = the right panel in the Crates tab showing tracks within a selected crate
- **Library** = the Library tab only — do not confuse with the track panel

## Files to Read First

Read all of these before writing any code:

- `src/gui/crate_manager.py` — primary file, most changes live here
- `src/gui/main_window.py` — signal wiring, nav handling, album art connections
- `src/gui/theme.py` — styling constants
- `src/serato/crate_reader.py` — crate data reading
- `src/serato/crate_writer.py` — crate data writing
- `src/gui/library_browser.py` — reference for inline editing patterns, icon spacing, context menus, teal flash, and cross-view data sync. Match these patterns exactly.
- `src/core/scanner.py` — reference for TrackRecord structure

---

## Fix 1 — Sub-Crate Expand Indicators

Crates with child crates do not currently show expand/collapse arrows in the crate tree. Apply `setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)` to every crate item that has children. Verify the arrows appear and function correctly on all parent crates.

---

## Fix 2 — Remove from Crate: Loading Feedback and No Freeze

When removing a track from a crate, the UI briefly freezes with no feedback. Fix this so the operation is non-blocking. Show a brief status message in the teal footer text immediately when the operation begins, and update it when complete.

---

## Fix 3 — Tree State Preservation

After any operation (add track, remove track, delete crate, rename crate, duplicate crate, drag reorder), the crate tree must restore its previous expanded/collapsed state and re-select the previously selected crate. The tree must never collapse back to its root state after an operation.

---

## Fix 4 — Music Note Icon Spacing

The music note ♪ icon on track rows in the track panel must match the spacing used in the Library Browser exactly. Reference `library_browser.py` for the correct implementation and apply the same approach here.

---

## New Feature 1 — `#` Position Column

Add a `#` column as the leftmost column in the track panel.

- Fixed width: 40px
- Displays the 1-based position of each track as it appears in the `.crate` file
- This is always the default sort when a crate is opened or re-selected
- Clicking the `#` column header restores crate file order if the user has sorted by another column
- Sorting by any other column is visual and temporary — it never rewrites the `.crate` file order
- When a track is added to a crate it appends to the end and receives the next `#` number
- When tracks are reordered via drag (see New Feature 3), the `#` column renumbers to reflect the new order

---

## New Feature 2 — Visual-Only Column Sorting

Sorting by any column other than `#` is temporary and visual only. It must never rewrite the `.crate` file. The `.crate` file order is only ever changed by explicit drag reorder actions (New Feature 3). Clicking the `#` column header always restores the `.crate` file order.

---

## New Feature 3 — Drag to Reorder Tracks Within the Track Panel

The user must be able to drag one or more tracks within the track panel to reorder them.

- Single selection and Shift multi-select drag are both supported
- On drop, the new order is written permanently to the `.crate` file
- The `#` column renumbers immediately to reflect the new order
- Tree state is preserved (Fix 3 applies)
- Teal footer text confirms: *"Reordered [X] track(s) in [Crate Name]"*

---

## New Feature 4 — Drag Track(s) from Track Panel to a Crate in the Tree

The user must be able to drag one or more selected tracks from the track panel and drop them onto a crate in the crate tree to add them to that crate.

- Single selection and Shift multi-select drag are both supported
- On drop, check for duplicates. Tracks already in the target crate are skipped silently.
- If some tracks were skipped due to duplicates, show in the teal footer: *"Added [X] of [Y] tracks to [Crate Name] ([Z] already in crate)"*
- If all tracks were added successfully, show: *"Added [X] track(s) to [Crate Name]"*
- The target crate in the tree must highlight visually when a valid drag is hovering over it
- Tree state is preserved after the drop (Fix 3 applies)

---

## New Feature 5 — Drag to Reorder Crates in the Crate Tree

The user must be able to drag crates within the crate tree to reorder them among siblings or move them under a different parent crate.

- Dragging a crate reorders it among its siblings or reparents it under a new parent
- The new order and hierarchy is written to the `.crate` files immediately on drop
- A crate cannot be dropped onto itself
- Expanded/collapsed state is preserved after the drag (Fix 3 applies)

---

## New Feature 6 — Delete Key for Tracks

When one or more tracks are selected in the track panel and the user presses the Delete key, show a modal confirmation dialog centered on screen before taking any action.

**Single track:**
> Remove '[Track Title]' from [Crate Name]?

Buttons: **Remove** / **Cancel**

**Multiple tracks:**
> Remove [X] tracks from [Crate Name]?

Buttons: **Remove** / **Cancel**

The dialog must block all interaction until dismissed. Nothing is removed until the user clicks Remove. On confirmation, remove the track(s) and update the teal footer: *"Removed [X] track(s) from [Crate Name]"*

---

## New Feature 7 — Delete Key for Crates

When a crate is selected in the crate tree and the user presses the Delete key, show a modal confirmation dialog centered on screen before taking any action.

**Empty crate:**
> Delete '[Crate Name]'? This cannot be undone.

Buttons: **Delete** / **Cancel**

**Populated crate:**
> Delete '[Crate Name]'? It contains [X] tracks. This cannot be undone.

Buttons: **Delete** / **Cancel**

The dialog must block all interaction until dismissed. Nothing is deleted until the user clicks Delete.

---

## New Feature 8 — Modal Confirmation for Right-Click "Remove from Crate"

The existing right-click → Remove from Crate currently removes tracks silently. Replace this with the same modal confirmation flow described in New Feature 6. The behavior must be identical whether the user uses the Delete key or the right-click menu.

---

## New Feature 9 — Crate Tree Row Height and Search Padding

Two visual fixes for the crate tree:

1. **Row height** — the crate tree row height is currently shorter than the track panel row height, making the layout feel inconsistent and cramped. Match the crate tree row height to the track panel row height.

2. **Search field padding** — there is insufficient space between the "Search crates..." field and the first crate row. Add enough padding so the first crate row does not feel like it is bumping the bottom of the search field.

---

## General Requirements

- All changes must be visually and behaviorally consistent with `library_browser.py` — teal flash, icon sizing, context menus, inline editing behavior. Reference it directly.
- Serato custom ID3 frames (cue points, beat grids, loops, color tags, markers) are never modified under any circumstances.
- The `.crate` file order is sacred and is only ever changed by explicit user drag reorder actions (New Feature 3).
- All modal confirmation dialogs are centered on screen and block all interaction until dismissed.
- Teal footer status text updates after every operation to describe what happened.
- Tree expanded/collapsed state and crate selection must be preserved after every operation.
