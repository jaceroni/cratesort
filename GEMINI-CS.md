# GEMINI-CS.md

This file provides guidance to Gemini / Antigravity when working with the CrateSort project.

## What this project is

CrateSort is a cross-platform desktop app (macOS-first) that organizes a DJ's digital music library (MP3s and music videos) and manages their Serato DJ Pro crates. It is the digital counterpart to CrateView (a WordPress theme for vinyl collection management). Together they form the Crate suite.

CrateSort is the single writer. Serato is the reader. CrateSort handles all organizational work — genre classification, folder restructuring, metadata cleanup, duplicate detection, crate management — so that Serato only reads the result. The DJ never organizes inside Serato again.

**Tagline**: "Get your shit together."

---

## Tech stack

- **Language**: Python 3.x (Homebrew at `/opt/homebrew/bin/python3`)
- **GUI**: PyQt6 with custom themed UI (not system default)
- **ID3 tags**: `mutagen`
- **Audio fingerprinting**: `chromaprint` / `pyacoustid` (duplicate detection, future)
- **Serato file parsing**: `serato-crate` library for `.crate` read/write
- **Packaging**: PyInstaller → `.app` (macOS), `.exe` (Windows), AppImage (Linux)
- **No external APIs required.** No internet, no API keys, no server.

---

## Development approach

- **Always run prompts with high-effort settings.** Medium effort produces incomplete reads and introduces bugs. High effort is required for this codebase.
- **Read every referenced file completely before writing any code.** Do not skim. Verify every column constant index, every widget reference, every signal connection before using it.
- **Verify imports before using any class or module.** If a class is not already imported in the target file, add it to the imports before using it. Never use a class without first confirming it exists in the import block.
- **Every Gemini prompt must be delivered as a markdown (.md) file.** Never paste code or instructions directly into chat as inline code blocks — always write a proper prompt file.
- **GUI from day one.** No terminal-only phase.
- **Modular architecture.** Every feature is a module that can be independently developed and (in the future) gated behind a subscription tier.
- **Gemini for execution. Planning chat for strategy/design.** The owner (Jace) architects in a separate planning chat, then provides detailed prompts to Gemini.

---

## Core philosophy

- **CrateSort is the single writer. Serato is the reader.** Whatever CrateSort writes, Serato picks up on next launch. CrateSort owns the crate structure completely — crate order, hierarchy, names, membership. Do not defer to Serato's defaults.
- **The folder is the home, the crate is the connection.** Files live in one place on disk. Crates are references — one file, many crates.
- **Inform first, act second.** Preview → approve → execute. Never destructive without user consent.
- **Non-destructive by default.** Rollback. Quarantine. Never permanent delete outside user-approved duplicate consolidation.

---

## Design language — Crate suite visual identity

- **Dark primary background**: `#1a1a1a`
- **Dark panels**: `#2F2F2F`
- **Sub-crate background** (expanded groups): `#222222`
- **Deeper dark** (active parent crate): `#000000`
- **Cream text**: `#f1e3c8`
- **Orange accent / selection**: `#D17D34`
- **Selected crate / warm brown**: `#573d26`
- **Teal action color**: `#428175`
- **Row separator**: `#383838`
- **Grid lines**: `#383838`
- **Branch connector lines**: `#4a4a4a`

### Teal = Action (critical rule)

Teal (`#428175`) is the action color throughout the entire app. Any time something is happening or has just happened, it must be teal:
- Drag indicator lines showing drop targets
- Footer status text after any operation
- Inline edit flashes when a cell edit is committed
- Undo/Redo buttons when active/available

Everything else is informational and uses the standard cream/muted palette. Orange (`#D17D34`) is the selection color. Never swap these roles.

### Track table visual standard

All track listing tables across the entire app must use:
- `setAlternatingRowColors(True)`
- Base color: `#242424`, AlternateBase: `#2a2a2a`
- Full grid lines (both vertical and horizontal): `gridline-color: #383838`
- `setShowGrid(True)`
- Row height: 36px (`setDefaultSectionSize(36)`, `setMinimumSectionSize(36)`, `setMaximumSectionSize(36)`)
- Column header height: 36px (`horizontalHeader().setFixedHeight(36)`)
- For QTreeWidget track tables: include `QTreeWidget::branch { border-bottom: 1px solid #383838; }` and hover/selected branch states to prevent left-edge gaps

---

## Launch Screen Architecture

The launch screen is a context-aware single screen — no popup dialog. It lives in `DashboardWidget._build_welcome()` as stack index 0.

### First launch (no saved library path):
- Shows `cs-logo-mascot-stacked.svg` logo, "Get your shit together." tagline, instruction text, single "Select Music Library…" button

### Returning user (saved library path exists):
- Shows same logo and tagline
- Library path displayed as plain muted text (no box or frame)
- "Load Library" primary orange button
- "Choose Different Library" secondary muted button
- "Always load without asking" checkbox — when checked + Load Library clicked, saves `always_load_last = True` to QSettings and skips this screen on next launch

### Key rules:
- `_LaunchDialog` has been deleted — do not recreate it
- No popup modal on launch under any circumstances
- Logo path: `assets/logos/cs-logo-mascot-stacked.svg`
- `always_load_last` preference stored in QSettings key `always_load_last` (bool)

---

## Dashboard Architecture

The dashboard (`src/gui/dashboard.py`) is a session-aware command center. Stack index 2 in `DashboardWidget`. Content is injected by `_populate_dashboard()` after a successful library scan.

### Sections (in order):

1. **Stat Cards** (`_build_stat_cards_section()`) — four cards: Total Tracks, Total Crates, Unique Artists, Hours of Music. Numbers animate from 0 on load with cubic ease-out via `QTimer`. Click any card to replay its animation. Uses `_AnimatedStatCard` widget class.

2. **Action Cards** (`_build_action_cards_section()`) — two groups:
   - **Go To** (4 cards): Change Library, Classify Library, Manage Crates, Organize Media. Large muted step numbers (01–04) turn orange on hover. Uses `_WorkflowCard` widget class.
   - **Create** (2 cards): New Crate, New Smart Crate. Orange accent treatment. Uses `_ClickableCard` widget class.

3. **Recent Activity** (`_build_activity_section()`) — combined feed of crate changes (from checkpoint diff) and recently added tracks (from `read_track_add_dates()`), last 30 days, capped at 10 items. Teal dot = addition/rename, orange dot = removal.

4. **Footer** (`_build_footer_bar()`) — last session timestamp + Serato sync status. Do not modify.

### Dashboard signals on DashboardWidget:
- `library_path_changed` — emitted when library path changes
- `scan_started` — emitted when scan begins
- `scan_finished` — emitted when scan completes
- `classify_requested` — emitted by Classify Library card
- `status_message` — emitted for footer status updates
- `crates_requested` — emitted by Manage Crates card (connect to Crates tab navigation)
- `organize_requested` — emitted by Organize Media card (connect to Organize tab navigation)
- `new_crate_requested` — emitted by New Crate card (connect to new crate dialog)
- `new_smart_crate_requested` — emitted by New Smart Crate card (connect to smart crate dialog)

### Checkpoint system (`src/utils/checkpoint.py`):
- `save_checkpoint(serato_dir, crate_data)` — writes `_CrateSort/checkpoint.json` with crate paths → track counts, timestamp
- `load_checkpoint(serato_dir)` — returns dict or None
- `detect_changes(current, previous)` — normalized path matching (handles mount point/case/separator differences), None guard for failed scans. Returns list of `{type, description}` dicts.
- Change types: `crate_added`, `crate_removed`, `renamed`, `tracks_added`, `tracks_removed`
- **Bug 2 fixed**: path normalization via `_normalize_path()` helper; failed scans stored as `None` (not `0`) to prevent false "tracks removed" reports

### Animation classes (module-level in dashboard.py):
- `_AnimatedStatCard(QFrame)` — stat card with count-up animation. `start_animation(duration_ms)` triggers the effect. `mousePressEvent` replays it.
- `_WorkflowCard(QFrame)` — Go To action card with `enterEvent`/`leaveEvent` for step number hover color change.
- `_ClickableCard(QFrame)` — base clickable card used for Create group.

### Things that must not be modified in the dashboard:
- `_build_dashboard()` — scroll container only, do not touch
- `_build_scanning()` — stack index 1, do not touch
- `_build_welcome()` — stack index 0, do not touch
- `_build_footer_bar()` — correct as-is, do not touch

---

## Crate Manager — Current Architecture

### Crate tree

The crate tree (`self._crate_tree`, `QTreeWidget`) uses a fully custom `CrateItemDelegate(QStyledItemDelegate)` for all item rendering. **Do not use `setItemWidget` or stylesheet-based selection coloring** — macOS overrides both. The delegate's `paint()` method is the single source of truth for all crate tree visual rendering.

#### CrateItemDelegate — four states

| State | Trigger | Background | Left Bar |
|-------|---------|------------|----------|
| A | Unselected top-level | `#2F2F2F` | None |
| A (sub) | Unselected sub-crate | `#222222` | None |
| B | Selected (no active sub-crate) | `#573d26` | `#D17D34`, 5px |
| C | Parent of active sub-crate | `#000000` | `#D17D34`, 5px |
| D | Selected sub-crate | `#573d26` | `#D17D34`, 5px |

State transitions are managed in `_on_tree_selection_changed`. Only `_prev_selected_item` and `_prev_parent_item` are reset on each selection change — never the entire tree. Maximum 4 delegate updates per selection change regardless of library size.

The delegate also draws the expand/collapse arrow (▶/▼) right-aligned in each row for parent crates.

#### Crate tree row height

Controlled by `CrateItemDelegate.sizeHint()` returning `QSize(w, 36)`. Do not use stylesheet `height` rules on `QTreeWidget::item` — they are unreliable on macOS. `setUniformRowHeights(True)` is set on the tree.

#### Crate tree expand/collapse

- **Single click** = select the crate, load its tracks. Never auto-expand.
- **Double click** = toggle expand/collapse. Does not change selection or reload tracks.
- `setChildIndicatorPolicy(ShowIndicator)` is set on every item with children.

#### Sub-crate background grouping

Sub-crates use `#222222` as their State A background (vs `#2F2F2F` for top-level crates). This creates a visual grouping even when the parent isn't the active selection. Detected in `paint()` via `index.parent().isValid()`.

### Track panel

The track panel (`self._track_table`, `_ReorderableTable(QTableWidget)`) has 14 columns:

| Index | Name | Notes |
|-------|------|-------|
| 0 | # | Position in crate, 1-based integer, numeric sort via UserRole |
| 1 | Title | |
| 2 | Artist | |
| 3 | Album | |
| 4 | Duration | |
| 5 | Genre | |
| 6 | Style Tags | |
| 7 | BPM | |
| 8 | Date Added | Pulled from Serato `database V2` via `src/serato/database_reader.py`. Stores Unix timestamp in UserRole for correct chronological sort. Serato stores paths using `\uf022` (U+F022) as a substitute for ` : ` in folder names — normalize on read. Some tracks stored with absolute paths, others relative — handle both. |
| 9 | Format | |
| 10 | Year | |
| 11 | Bitrate | |
| 12 | Comments | Actual ID3 comment metadata only — never inject status text here |
| 13 | File Path | Shows actual path for resolved tracks; "Not found in library" for unresolved |

Column widths persist via QSettings (`_SETTINGS_KEY`). Auto-sizers only run on first launch (no saved state).

#### Track panel sort behavior

- The `#` column sorts numerically (integer UserRole), not as string
- Sorting by any column is visual and temporary — never rewrites the `.crate` file order
- The active sort column and direction persist globally across all crates for the session (`_sort_col`, `_sort_order`)
- After any operation (add, remove, reorder), the active sort is reapplied

#### Track drag reorder

`_ReorderableTable` supports drag-to-reorder within the track panel:
- Shows a teal (`#428175`) horizontal drop indicator line between rows
- On drop: captures new order of track paths, calls `crate_writer.reorder_tracks()`, then **reloads the crate from disk** via `_refresh()` — never manipulates table rows directly
- This reload-after-write approach is mandatory to prevent data corruption

#### Parent crate track panel

When a parent crate is selected, the track panel shows ALL tracks — the parent's own tracks plus every sub-crate's tracks merged into one flat deduplicated list. Uses `_collect_tracks_recursive()`.

### Crate drag and drop

Fully manual drag implementation — Qt's built-in tree drag is disabled (`NoDragDrop`). Mouse events tracked via viewport event filter.

- **Sibling reorder**: teal horizontal line between crate rows; on drop, order saved to `neworder.pref` (UTF-16 BE) in `_Serato_/` folder
- **Reparent**: hover over target crate for 1.5 seconds → auto-expand → drop inside. Target crate highlights with teal border during hover delay.
- **Promote to top level**: dropping a sub-crate beside a top-level item un-nests it
- **Crate cannot be dropped onto itself**

### Crate CRUD — confirmation dialogs

Every destructive action requires a modal confirmation dialog centered on screen, blocking all interaction:
- **Delete empty crate**: "Delete '[Name]'? This cannot be undone." → Delete / Cancel
- **Delete populated crate**: "Delete '[Name]'? It contains [X] tracks. This cannot be undone." → Delete / Cancel
- **Remove track(s) from crate**: "Remove '[Title]' from [Crate]?" or "Remove [X] tracks from [Crate]?" → Remove / Cancel

### Export Crate to Folder (paid tier)

Right-click any crate → **"Export Crate to Folder..."**

- Exports only the crate that was right-clicked — never the parent, never sub-crates
- Opens a native OS folder picker with no default location — user picks freely (local drive, external drive, USB, anywhere)
- CrateSort creates a new folder at the chosen destination named exactly after the crate
- All files from that crate are copied flat into the folder — no Genre/Artist subfolders
- Originals are never moved or modified
- Filename collision handling: if two tracks share the same filename, the second copy is renamed with a number suffix (e.g. `Inner City Blues (2).mp3`). Artist name is never appended — filename = song title only, always.
- Teal footer confirms on completion: "Exported 23 tracks to 'Gangsta Rap'"
- **Paid tier feature** — consistent with all other file operation features

### Tree state preservation

Expanded/collapsed state and selected crate are preserved after every operation. On tab switch away and return, `showEvent` re-triggers `_on_tree_selection_changed` to reapply delegate colors.

---

## Undo/Redo System

- `src/utils/undo_manager.py` — Command pattern, 10-state stack, global across tabs
- 8 command classes: `AddTracksCommand`, `RemoveTracksCommand`, `ReorderTracksCommand`, `CreateCrateCommand`, `DeleteCrateCommand`, `RenameCrateCommand`, `ReorderCratesCommand`, `ReparentCrateCommand`
- Undo/Redo buttons in sidebar below album art — teal when active, gray when inactive
- Cmd+Z / Cmd+Shift+Z keyboard shortcuts
- Auto-tab switch when undoing a cross-tab action
- Teal footer text describes what was undone/redone

---

## Serato File Format (research confirmed)

- **`.crate` files**: only contain `ptrk` (track path). No timestamps, no metadata.
- **`database V2`**: TLV binary format, UTF-16 BE. Contains `uadd` (add timestamp), `pfil` (file path), and full track metadata per `otrk` record.
- **`neworder.pref`**: UTF-16 BE text. One `[crate]CrateName%%SubcrateName` entry per line between `[begin record]` and `[end record]`. Canonical crate display order that Serato reads on launch.
- **`collapsed.pref`**: tracks which parent crates are expanded/collapsed in Serato UI.
- Serato uses `\uf022` (U+F022 private-use) as a substitute for ` : ` in folder names within database V2 paths.

---

## Genre taxonomy (12 parent genres)

These are the only folder-level categories. Style distinctions live in metadata and Serato crates.

| Genre | Key styles |
|-------|-----------|
| Blues | Chicago Blues, Delta Blues, Electric Blues, Jump Blues, Texas Blues |
| Country | Classic Country, Country Western, Honky-Tonk, Outlaw Country |
| Electronic | Ambient, Breakbeat, Downtempo, Drum & Bass, Electro, Trip-Hop |
| Funk/Soul | Afro Funk, Brazilian Funk, Breakdance / Park Jams, Chicano Soul, Classic Funk, Classic Soul, Disco, Go-Go, Instrumental Funk, Modern Funk, Neo Soul, P-Funk, Psychedelic Soul, Rare Groove |
| Hip-Hop/Rap | Boom Bap, Conscious, G-Funk, Gangsta, Golden Era, Hardcore, Instrumental Hip-Hop, Jazzy Hip-Hop, Old School, Southern, Underground, West Coast |
| House | Acid House, Chicago House, Deep House, Garage, Soulful House, Tech House |
| Jazz | Avant-Garde, Bebop, Bossa Nova, Cool Jazz, Fusion, Hard Bop, Jazz-Funk, Latin Jazz, Library, Lo-Fi, Modal, Smooth Jazz, Soul-Jazz, Swing |
| R&B | Classic R&B, Contemporary R&B, Freestyle, New Jack Swing, Quiet Storm, Slow Jams, '50s R&B / Doo-Wop |
| Reggae | Dancehall, Dub, Roots Reggae, Ska |
| Rock | Alternative, Art Rock, Blues Rock, Boogie Rock, Country Rock, Early Rock & Roll, Folk Rock, Garage Rock, Hard Rock, Heartland Rock, New Wave, Oldies, Pop Rock, Progressive Rock, Psychedelic Rock, Soft Rock, Southern Rock, Surf Rock, Synth-Pop |
| Seasonal | Holiday, Christmas, Halloween |
| Specialty | DJ Drops, Scratch Records, Sound Effects, TV Themes, Break Records |

**Critical classification rules:**
- "Pop" is NEVER a valid genre.
- Synth-Pop and New Wave → Rock, not Electronic.
- Breakdance / Park Jams → Funk/Soul, not Hip-Hop/Rap.
- Soul → Funk/Soul, not R&B.
- All genre and style terms: Title Case.

---

## Serato integration rules

- **Serato's edits always win** on startup sync. CrateSort absorbs changes, never overwrites.
- **Serato custom ID3 frames** (cue points, beat grids, loops, color tags, markers) are NEVER modified under any circumstances.
- **Crate file order** is only ever changed by explicit user drag reorder actions. All other sorting is visual and temporary.
- **CrateSort owns crate structure.** Crate order, hierarchy, names — all controlled by CrateSort. Serato reads whatever CrateSort writes.
- **Crate order is written to `neworder.pref`** (UTF-16 BE) in the `_Serato_/` folder. `neworder.pref` is the canonical display order that Serato reads on launch.

### Library and Serato directory architecture (locked)

**The `_Serato_` folder must live on the same drive as the media files.** This is the only architecture that works correctly for DJs who hot-swap drives between computers.

- CrateSort points at a single root directory (the media drive root)
- CrateSort expects `_Serato_/` to exist at that same root alongside the media folders
- Everything travels together — media files and Serato data on the same drive
- When the DJ plugs into any computer, they Option-launch Serato and point it at the drive's `_Serato_/` folder

**CrateSort never auto-creates the `_Serato_/` folder structure.** If `_Serato_/` is not found at the media root, CrateSort displays a guided message directing the user to copy or initialize `_Serato_/` at the drive root.

### Startup sync sequence (not yet built)

On every launch, CrateSort will:
1. Read the `_Serato_/` folder on the drive
2. Compare against its last known checkpoint
3. Surface any changes for the user to review
4. User confirms before CrateSort unlocks (Amber → Change Review → Green)

---

## File organization rules

- CrateSort works in place — reorganizes within the user's designated directory
- Genre/Artist/track hierarchy. No style subfolders on disk.
- Filename = song title only.
- "The" moved to end with comma: `The Doors` → `Doors, The/`
- No empty genre folders
- No file deletion outside user-approved duplicate consolidation (quarantine, not permanent delete)
- No independent file moves outside user-triggered reorganization

---

## Things that must never be broken

- **Serato custom ID3 frames** — cue points, beat grids, loops, color tags — never overwritten
- **The `.crate` file order** — only changed by explicit user drag reorder, never by sorting
- **CrateItemDelegate** — the single source of truth for crate tree rendering; never revert to setItemWidget or stylesheet selection coloring
- **Reload-after-write pattern** — after any crate content modification, reload from `.crate` file rather than manipulating table rows directly
- **Track panel column constants** — verify every index before use; they shift when columns are added
- **Column width persistence** — QSettings save/restore; auto-sizers only run on first launch
- **Confirmation dialogs** — every destructive action requires modal confirmation before executing
- **Teal = action, Orange = selection** — never swap these color roles
- **36px row height** — app-wide standard; never change without updating all views simultaneously
- **`_LaunchDialog` is deleted** — do not recreate it or any other launch popup

---

## Monetization model (future, not built in v1)

- **Free tier**: Serato crate management (view, create, rename, duplicate, delete, drag tracks)
- **Paid tier** (~$5-10/month or ~$100/year): Drive reorganization, Export Crate to Folder, duplicate detection, style suggestions, smart crate builder, CrateView bridge
- Architecture supports feature gating without rewrites.

---

## Related project

**CrateView** (https://www.mycrateview.com) — WordPress child theme for vinyl collection management. CrateSort can optionally connect to CrateView's JSON cache for vinyl/digital alignment. Read-only optional plugin, not a core dependency.
