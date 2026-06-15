# CrateSort — Library / Classification Merge

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt retires the Classification tab as a standalone destination and merges all classification functionality into the Library tab as an on-demand mode. This is a significant architectural change touching six files. Follow the blast radius and locked rules below precisely.

---

## Files in scope

- `src/gui/main_window.py`
- `src/gui/classifier_view.py`
- `src/gui/library_browser.py`
- `src/gui/dashboard.py`
- `src/gui/organize_view.py`
- `src/core/file_organizer.py`

**No other files are touched.** `src/core/classifier.py` is unchanged — the classification engine is untouched.

---

## Locked decisions (do not deviate)

- Teal `#428175` = action. Orange `#D17D34` = selection/CTA. Never swap.
- Red `#C75B5B` = destructive / warning. Used for Unclassified indicators.
- Row height: 36px. Column header height: 45px. These are app-wide standards.
- `setAlternatingRowColors(True)`. Base `#242424`, AlternateBase `#2a2a2a`.
- Every destructive or significant action requires a modal confirmation.
- Never touch Serato metadata, comments, or cue points.
- Crates are references — moving a track between crates never moves a file on disk.

---

## Change 1 — Retire ClassifierView, remove Classification tab

### `src/gui/main_window.py`

The Classification tab (previously nav index 1) is removed entirely. The new nav is:

| Nav index | ID | Label | Icon | Widget |
|---|---|---|---|---|
| 0 | `dashboard` | Dashboard | dashboard SVG | `DashboardWidget` |
| 1 | `library` | Library | library SVG | `LibraryBrowserView` |
| 2 | `crates` | Crates | crates SVG | `CrateManagerView` |
| 3 | `organize` | Organize | organize SVG | `OrganizeView` |
| 4 | `settings` | Settings | settings SVG | `SettingsView` |

Nav is now 5 items. Content stack index matches nav index exactly. Update `_on_nav()`, `_apply_nav_state()`, `_get_app_state()`, and any hardcoded nav index references throughout the file.

### Nav Gating and Signal Cleanups

1. **Signal Disconnections**:
   - Completely remove the connection of `self._library_browser.track_field_changed` to `self._classifier_view.refresh_track_display` (around line 142) since `_classifier_view` is being removed.
   - In `OrganizeView`, rename the signal `navigate_to_classifier` to `navigate_to_library`. Connect it in `MainWindow` (around line 156) to navigate to the Library tab (index 1).
   - In `DashboardWidget`, when `classify_requested` is emitted, navigate to the Library tab (index 1).
2. **Dead Handler Removal**:
   - Remove the `_on_classify_requested`, `_on_classifier_done`, and `_on_classifier_back` slot methods from `MainWindow` entirely.
3. **App State Navigation Gating**:
   - Retain state 2 as a sub-case of "no library" (so the tooltip "Serato folder not found at this library location" is preserved), keeping it additive:
     - **State 1 (No library path saved/exists)**: Disable Library, Crates, Organize. Tooltip: "Load a library to get started."
     - **State 2 (Library exists but no _Serato_ folder)**: Disable Library, Crates, Organize. Tooltip: "Serato folder not found at this library location."
     - **State 3 (Library and Serato present)**: All nav items are active immediately. There is no classification completion block or gate.
   - **Important `_apply_nav_state()` implementation constraint**: Ensure the three states above are cleanly evaluated and applied to enable/disable navigation buttons and clear/set tooltips dynamically based on the active state.

### `src/gui/classifier_view.py`

This file is retired as a GUI destination. Do not delete it — rename the class to `_ClassifierViewLegacy` and add a module-level comment: `# RETIRED — classification functionality moved to LibraryBrowserView`. Remove all imports of `ClassifierView` from `main_window.py`. The underlying classification logic in `src/core/classifier.py` and the `ClassificationSession` utility are unchanged.

---

## Change 2 — Genre sidebar added to LibraryBrowserView

### `src/gui/library_browser.py`

Add a permanent genre sidebar to the left of the track table. This replaces the "All Genres" dropdown filter in the toolbar — remove the `self._genre_cb` dropdown and its references from the toolbar setup and filter logic.

### Genre sidebar specs

- Width: 180px, fixed
- Background: `#1e1e1e`
- Right border: `1px solid #2a2a2a`
- Header label: "GENRES" in 9px uppercase muted text (`#666`), 12px padding top

### Genre sidebar items

Each item shows:
- Colored dot (6px circle, `#D17D34`)
- Genre name (11px, `#aaa`)
- Artist count · track count (10px, `#555`, right-aligned)

First item is always "All" showing total artist and track counts. Below that, one item per genre that has at least one track, alphabetical. 

At the bottom, separated by a 1px `#2a2a2a` border and 8px margin-top:
- **Unclassified** item — dot color `#C75B5B`, text color `#C75B5B`, count color `#C75B5B` at 80% opacity. Only shown when unclassified tracks exist. Hidden when count is zero.

### Genre sidebar interaction

- Click any genre item: filters the track table to that genre. Active item gets `#f1e3c8` text, `#252525` background.
- Click "All": clears genre filter, shows all artists.
- Clicking a genre sidebar item takes priority over any active genre filter state.

---

## Change 3 — Classify mode in LibraryBrowserView

### `src/gui/library_browser.py`

### Classify Library button

Add a teal "Classify Library" button to the right end of the toolbar row (next to Clear Filters). 

- Background: `#428175`
- Text: `#f1e3c8`, 11px, weight 500
- Label: "Classify Library"
- On click: triggers classify mode (see below)

### Classify mode — entry

When Classify Library is clicked:

1. Run the classifier engine (`src/core/classifier.py`) against the current library if results are not already cached in the session.
2. Show the classify mode banner (see below).
3. Reveal the three classify columns: Proposed Genre, Confidence, Status. 
   - **Important column indexing rule**: To avoid shifting the existing column constants (e.g., `LC_TAGS` = 4, `LC_DURATION` = 5, etc.) and causing widespread blast-radius modifications, **append the 3 classify columns at the end of the logical columns list**:
     - `LC_PROPOSED_GENRE = 12`
     - `LC_CONFIDENCE = 13`
     - `LC_STATUS = 14`
   - Set the tree's column count to 15 from the start, but keep columns 12, 13, and 14 hidden by default in normal mode (`self._tree.setColumnHidden(col, True)`).
   - On entering classify mode, first make columns 12, 13, and 14 visible, and then use `self._tree.header().moveSection(logical_index, target_visual_index)` to place them visually adjacent to the Genre column (index 3):
     - `self._tree.header().moveSection(12, 4)`
     - `self._tree.header().moveSection(13, 5)`
     - `self._tree.header().moveSection(14, 6)`
   - **Important layout processing constraint**: To prevent header state corruption or visual layout bugs, do not call `moveSection` inline while executing visibility operations. Defer the `moveSection` visual reorganization using a single-shot timer (e.g. `QTimer.singleShot(0, ...)` or `QTimer.singleShot(50, ...)`) to ensure the table has fully registered the column visibility changes first.
4. Button label changes to "Classifying…" while engine runs, then disappears (banner replaces it as the mode indicator).
5. Remove the old amber warning banner `_no_class_banner` (lines 315–329) entirely, as it is no longer appropriate under the in-Library classification model.

### Classify mode banner

A banner sits below the toolbar row and above the table. Teal-tinted.

- Background: `#1e2e2b`
- Bottom border: `1px solid #2d4a44`
- Padding: 7px 14px
- Left side text (11px, `#7bbdad`): "Classify mode — review proposed genres and correct where needed, then accept."
- Right side buttons:
  - "Cancel" — muted border button (`#2d4a44` border, `#7bbdad` text). Exits classify mode without saving any changes. Columns collapse.
  - "Accept Reclassifications" — teal button (`#428175` bg, `#f1e3c8` text). Saves all proposed genre assignments to `library_edits.json` and collapses classify mode.

### Classify mode columns

**Proposed Genre column:**
- Header teal-tinted background (`#1e2e2b`), teal header text (`#428175`)
- Cell background: `#1c2825`
- Cell text: `#7bbdad` when proposed matches current, `#D17D34` (orange) when proposed differs from current
- For Unclassified proposals: `#C75B5B` text, `#221a1a` background

**Confidence column:**
- Header teal-tinted
- HIGH: `#428175` text
- LOW: `#D17D34` text  
- NONE: `#C75B5B` text
- Cell background: `#1c2825`

**Status column:**
- Header teal-tinted
- "Modified": `#D17D34` text, `#1c2825` background
- Empty otherwise, `#1c2825` background

### Unclassified rows in classify mode

Artist rows with no genre assignment (Unclassified):
- Row background: `#1f1a1a`
- Artist name text: `#C75B5B`
- All classify-mode cells for that row: `#221a1a` background

### Classify mode — exit

**Cancel:** Collapse the three columns, hide the banner, restore "Classify Library" button. Move the columns back to their original logical positions and hide them.
- Defer the layout changes similarly via a single-shot timer to ensure clean GUI cleanup:
  - `self._tree.header().moveSection(12, 12)`
  - `self._tree.header().moveSection(13, 13)`
  - `self._tree.header().moveSection(14, 14)`
  - `self._tree.setColumnHidden(12, True)`
  - `self._tree.setColumnHidden(13, True)`
  - `self._tree.setColumnHidden(14, True)`
No changes written.

**Accept Reclassifications:**
1. Write all proposed genre assignments to `library_edits.json` for any artist/track where proposed genre differs from current.
2. Update the Genre column in the table to reflect accepted values.
3. Collapse the three classify-mode columns (restoring visual positions and calling `setColumnHidden(col, True)` using the same deferred layout processing strategy).
4. Hide the banner, restore "Classify Library" button.
5. Refresh the genre sidebar counts to reflect any genre changes.

---

## Change 4 — Organize warning dialog & Unclassified file moves

### `src/gui/organize_view.py`

Remove the hard gate that previously blocked Organize when unclassified tracks existed.

Replace with a warning dialog. When the user initiates a reorganization and unclassified tracks are detected:

Show a modal dialog styled to CrateSort standards (dark `#1a1a1a` background, `#f1e3c8` text):

- Title: "Unclassified Tracks Detected"
- Body: "X tracks have no genre assignment and will be moved to an Unclassified folder in your Media directory. You can reclassify them later."
- Two buttons: "Go Back to Library" (red, `#C75B5B`) on the left, "Proceed" (teal, `#428175`) on the right.

If user clicks Proceed: reorganization continues. Unclassified tracks go to `Media/Unclassified/Artist/track` following the same Genre/Artist/Track hierarchy.

If user clicks Go Back to Library: dialog closes, nav switches to Library tab (index 1) via the `navigate_to_library` signal.

#### Plan Worker Modification
In `_PlanWorker.run()`, do not filter out/skip session entries where genre is in `_UC_GENRES`. Instead:
- If a session entry's genre is not set, or is in `_UC_GENRES` (`'Unclassified'`, `'Untagged'`, `''`), default it to `'Unclassified'` and build the `ClassificationResult` for its tracks with `genre='Unclassified'`.

### `src/core/file_organizer.py`

In `build_plan()`, allow `'Unclassified'` to be processed as a valid destination genre:
- Modify the guard that skips entries:
  ```python
  cls = classifications.get(record.path)
  if not cls or not cls.genre or cls.genre in ('Unclassified', 'Untagged'):
  ```
  Change it to only skip files when `cls.genre` is `'Untagged'` or empty/None (after defaulting them to `'Unclassified'` when classifications are built). Specifically, treat `'Unclassified'` as a valid target genre directory name.
- When `_build_destination()` runs, it will naturally resolve the genre folder as `Unclassified` and place the file in `Media/Unclassified/Artist/track`.

---

## Change 5 — Dashboard action cards updated

### `src/gui/dashboard.py`

Update the three "Go To" workflow action cards. Labels, icons, and nav targets:

| Card | Old label | New label | Nav target |
|---|---|---|---|
| 01 | Classify Library | Manage Library | Library (index 1) |
| 02 | Manage Crates | Manage Crates | Crates (index 2) — unchanged |
| 03 | Organize Media | Organize Media | Organize (index 3) — unchanged |

Update nav index references to match the new 5-item nav. Card 01 navigates to index 1 (Library), card 02 to index 2 (Crates), card 03 to index 3 (Organize).

Update the SVG icon for card 01 from `icon-classification.svg` to `icon-library.svg`.

---

## Verification checklist

Before marking complete, verify:

1. App launches cleanly. No Classification tab visible in nav.
2. Nav has exactly 5 items: Dashboard, Library, Crates, Organize, Settings.
3. With no library loaded: Library, Crates, Organize are visibly disabled with tooltips. State 2 tooltip is shown correctly when Serato is missing.
4. With library loaded: all five nav items are active.
5. Genre sidebar appears in Library with correct counts. Clicking a genre filters the table.
6. Unclassified bucket appears in red at bottom of sidebar only when unclassified tracks exist.
7. "Classify Library" button appears in Library toolbar.
8. Clicking it shows the banner and inserts the three teal-tinted columns visually adjacent to Genre (logical columns 12, 13, 14 are moved to visual indices 4, 5, 6).
9. Cancel exits classify mode with no changes written. Columns are hidden and restored to original logical positions.
10. Accept Reclassifications saves genres, collapses columns, refreshes sidebar counts.
11. Organize shows warning dialog when unclassified tracks exist — does not hard block.
12. Proceed from warning dialog continues reorganization, Go Back navigates to Library.
13. Dashboard cards show Manage Library / Manage Crates / Organize Media with correct nav targets.
14. No references to ClassifierView remain in main_window.py imports or nav setup.
15. Undo/Redo buttons still functional.
16. Teal = action, Orange = selection, Red = destructive — no role swaps anywhere.
