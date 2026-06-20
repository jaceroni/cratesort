# CrateSort — Library Empty State, Sidebar Refresh & Dashboard Card Fixes

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt addresses four targeted fixes across two files, plus a critical timing crash fix in the library browser. No architectural changes.

---

## Files in scope

- `src/gui/library_browser.py`
- `src/gui/dashboard.py`
- `src/gui/main_window.py` — timing slot guard

---

## Locked design standards (non-negotiable)

- Orange `#D17D34` = selection/CTA. Teal `#428175` = action. Never swap.
- Red `#C75B5B` = destructive/warning only.
- Cream text: `#f1e3c8`
- Muted text: `#666`
- Action card fixed height: `setMinimumHeight(230)` with a `Fixed` vertical size policy — do not use `setFixedHeight`, to avoid conflicting with the dashboard scroll/grid layout
- Step numbers on action cards are removed — do not reintroduce them

---

## Critical Timing Crash Fix — Library Browser `on_scan_finished`

### `src/gui/library_browser.py` & `src/gui/main_window.py`

When the background scan finishes on startup or library change, `MainWindow._on_scan_finished` invokes `self._library_browser.on_scan_finished(inv, lib)`. Currently, `on_scan_finished` calls `_rebuild_tree()` directly, which throws an `AttributeError` because `self._session_artists` and other session parameters are not yet initialized (they are only created lazily inside `load()`).

### Fix specs

1. In `LibraryBrowserView.__init__` ([library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py)), defensively initialize all session variables to empty states:
   - `self._session_artists: dict[str, str] = {}`
   - `self._session_genre: dict[str, tuple[str, str]] = {}`
   - `self._track_overrides: dict[str, str] = {}`
2. Ensure `QSvgWidget` and `QByteArray` are imported at the top of `library_browser.py` (e.g. `from PyQt6.QtSvgWidgets import QSvgWidget` and `from PyQt6.QtCore import QByteArray`).
3. In `LibraryBrowserView.on_scan_finished(self, inventory, library_path: Path)`, instead of calling `_rebuild_tree()` directly, route it directly to `self.load(inventory, library_path)`. This guarantees that the entire session loading, filter populating, and tree/sidebar rebuilding execute cleanly and in the correct order.

---

## Fix 1 — Library first-launch empty state

### `src/gui/library_browser.py`

When the Library loads and the genre sidebar shows only "All" and "Unclassified" (meaning zero tracks have been classified into any genre), display an inline empty state in the main track pane instead of an empty table.

### Empty state specs

- Displayed in the center of the track pane area, vertically and horizontally centered
- Not a modal, not a blocker — just an inline prompt
- Contents (centered vertically in a QVBoxLayout):
  - Icon: a large music note `♪` or library icon — 48px, `#333`
  - Heading: "Your library hasn't been classified yet." — 14px, `#f1e3c8`, weight 500
  - Subline: "Hit Classify Library to assign genres, clean up filenames, and get your library organized." — 12px, `#666`
  - Visual nudge: A text element or indicator pointing toward the Classify Library button at the top right of the toolbar (e.g. "Classify Library ↗")
- Background: transparent — the track pane background shows through

### When to show vs hide

- **Show** when: library is loaded AND total classified track count across all genres (excluding Unclassified) is zero
- **Hide** when: at least one genre has tracks assigned, OR when classify mode is active
- The standard track table is hidden while the empty state is shown
- The empty state is hidden and the track table is restored the moment Accept Reclassifications is clicked and genres are assigned

### Implementation note

Use a `QStackedWidget` inside the browser's splitter/track area:
- Index 0 is the custom empty state widget (built via `self._build_library_empty_state()`).
- Index 1 is the tree widget `self._tree`.
Replace the tree widget in layout/splitter additions with `self._track_stack`. Update and switch `self._track_stack` index dynamically using a helper `self._update_empty_state()` called at the end of `_rebuild_tree()`, on entering/exiting classify mode, and after manual genre changes or track reassignments.

---

## Fix 2 — Real-time genre sidebar refresh on single edits

### `src/gui/library_browser.py`

Currently the genre sidebar refreshes correctly after Accept Reclassifications but does not refresh after a single genre change made by right-clicking an artist or track and selecting a new genre.

Fix: In `_change_genre_for_selection(self, hint_label, hint_genre)` (around line 1083), after writing the edits to `library_edits.json` and calling `self._sync_genres_to_session()`, call both `self._populate_genre_sidebar()` and `self._update_empty_state()` synchronously. This updates counts in the sidebar immediately and displays/hides the empty state if the track counts change.

Also call `self._populate_genre_sidebar()` and `self._update_empty_state()` at the end of `_reassign_track()` to keep sidebar counts and empty state visibility synced after track reassignments.

---

## Fix 3 — Dashboard action cards fixed height

### `src/gui/dashboard.py`

The three "Go To" action cards (Manage Library, Manage Crates, Organize Media) currently expand vertically to fill available space when the Recent Activity feed is empty. This is incorrect — card height should never change based on what's below them.

### Fix specs

- Inside `_WorkflowCard.__init__`, set the vertical size policy to `Fixed`:
  ```python
  self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
  ```
- Keep `self.setMinimumHeight(230)`. This prevents the grid layout from stretching the cards vertically beyond their natural size when the recent activity list is empty.

---

## Fix 4 — Remove step numbers from action cards, replace with orange label

### `src/gui/dashboard.py`

The "Go To" action cards currently show step numbers (01, 02, 03) as the primary visual element. Remove the step numbers entirely. Replace with the action label text rendered in large orange text as the primary card heading.

### Updated card layout (top to bottom)

- **Primary label**: "Manage Library" / "Manage Crates" / "Organize Media"
  - Font size: 16px
  - Color: `#D17D34` (orange)
  - Font weight: 500
  - Top of card, left-aligned
- **Description text**: existing supporting description copy
  - Font size: 11px
  - Color: `#666`
  - Below the primary label
- **Large SVG icon**: existing icon, right-aligned, 100px, dimmed at rest (`opacity ~0.15` / `_ICON_DIM`), full orange on hover (`_ICON_ACTIVE`)
- **Card hover state**: border turns orange, background warms slightly — unchanged from current behavior

### What to remove

- The step number element (`self._step_label`) — remove completely. Reclaim the vertical spacing for the layout.

---

## Verification checklist

Before marking complete:

1. Loading a fresh unclassified library shows the empty state in the track pane — centered, with heading, subline, and visual nudge toward Classify Library button
2. Empty state disappears and track table appears the moment genres are assigned via Accept Reclassifications
3. Track table shows correctly when any genres exist — empty state never shows on a partially or fully classified library
4. Changing a single artist or track genre via right-click updates the genre sidebar counts immediately — no navigation required
5. Dashboard action cards are the same height with empty Recent Activity as with populated Recent Activity
6. No step numbers (01/02/03) visible anywhere on the dashboard action cards
7. Action card primary label is "Manage Library" / "Manage Crates" / "Organize Media" in large orange text
8. Card hover behavior unchanged — border orange, background warms, icon goes full orange
9. All three cards navigate to correct tabs when clicked
10. Timing slot for scan completion runs safely without throwing `AttributeError` on `_session_artists`
11. Teal = action, Orange = selection/CTA — no role swaps anywhere
