# CLAUDE.md

This file provides guidance to Claude Code when working with the CrateSort project.

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

- **Always run prompts at Sonnet high effort.** Medium effort produces incomplete reads and introduces bugs. High effort is required for this codebase.
- **Read every referenced file completely before writing any code.** Do not skim. Verify every column constant index, every widget reference, every signal connection before using it.
- **Verify imports before using any class or module.** If a class is not already imported in the target file, add it to the imports before using it. Never use a class without first confirming it exists in the import block.
- **GUI from day one.** No terminal-only phase.
- **Modular architecture.** Every feature is a module that can be independently developed and (in the future) gated behind a subscription tier.
- **For small visual-only changes (height, color, spacing): read the exact lines, change only those lines, do not reason about surrounding layout or touch other files.**

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
- **Red / cancel / destructive**: `#C75B5B`
- **Row separator**: `#383838`
- **Grid lines**: `#383838`
- **Branch connector lines**: `#4a4a4a`

### Color rules (critical)

- **Teal (`#428175`) = action.** Drag indicators, status confirmations, active Undo/Redo buttons, teal flashes on inline edits.
- **Orange (`#D17D34`) = selection / CTA.** Selected crate highlight, step numbers, New Crate button, primary action cards.
- **Red (`#C75B5B`) = cancel / undo / destructive.** Every Cancel, Rollback, Revert, Delete, and Stop button. Hover: `#b24c4c`. Pressed: `#9c3b3b`. No exceptions.
- **Never swap teal and orange roles.**

### Button hover rule

All teal buttons get **darker** on hover, never lighter. `#428175` → hover `#38706a` → pressed `#2d6358`. This applies to every teal button across all views including modals and popups.

### Track table visual standard

All track listing tables across the entire app must use:
- `setAlternatingRowColors(True)`
- Base color: `#242424`, AlternateBase: `#2a2a2a`
- Full grid lines: `gridline-color: #383838`
- `setShowGrid(True)`
- Row height: 36px
- Column header height: 45px (`horizontalHeader().setFixedHeight(45)`)
- For QTreeWidget track tables: include `QTreeWidget::branch { border-bottom: 1px solid #383838; }` and hover/selected branch states to prevent left-edge gaps

---

## Nav structure (locked)

6 items in order. Content stack index matches nav index exactly.

| Nav index | ID | Label | Icon | Content widget |
|---|---|---|---|---|
| 0 | `dashboard` | Dashboard | `⌂` (+ SVG) | `DashboardWidget` |
| 1 | `classification` | Classification | `🔍` (+ SVG) | `ClassifierView` |
| 2 | `library` | Library | `📚` (+ SVG) | `LibraryBrowserView` |
| 3 | `crates` | Crates | `📦` (+ SVG) | `CrateManagerView` |
| 4 | `organize` | Organize | `📁` (+ SVG) | `OrganizeView` |
| 5 | `settings` | Settings | `⚙` (+ SVG) | `SettingsView` |

SVG icons live in `cratesort/assets/icons/` as `icon-{nav_id}.svg`. All are filled orange (`#D17D34`).

Nav buttons load SVGs via `QIcon(str(icon_path))` at `16×16`. The `_on_nav(index)` handler calls `.load()` on the appropriate view. Classification (index 1) guards against "no library loaded" and redirects to Dashboard with a status message.

After reorg or rollback completes, `OrganizeView.reorg_completed` fires → `MainWindow._on_reorg_completed()` → `_dashboard.start_scan(lib)` to rebuild inventory with new file paths.

---

## Launch Screen Architecture

The launch screen is a context-aware single screen — no popup dialog. It lives in `DashboardWidget._build_welcome()` as stack index 0.

### First launch (no saved library path):
- Shows `cs-logo-mascot-stacked.svg` logo, tagline, single "Select Music Library…" button

### Returning user (saved library path exists):
- Same logo and tagline
- Library path as plain muted text
- "Load Library" primary orange button
- "Choose Different Library" secondary muted button
- "Always load without asking" checkbox — saves `always_load_last = True` to QSettings

### Key rules:
- `_LaunchDialog` has been deleted — do not recreate it
- No popup modal on launch under any circumstances
- `always_load_last` preference stored in QSettings key `always_load_last` (bool)

---

## Dashboard Architecture

`src/gui/dashboard.py` — session-aware command center. Stack index 2 in `DashboardWidget`.

### Sections (in order):

1. **Stat Cards** (`_build_stat_cards_section()`) — four cards: Total Tracks, Total Crates, Unique Artists, Hours of Music. Count-up animation on load. No icon labels — numbers and labels only. `_AnimatedStatCard(target, suffix, label)` — note: no icon parameter.

2. **Action Cards** (`_build_action_cards_section()`) — two groups:
   - **Go To** (3 cards, not 4): `01 Classify Library`, `02 Manage Crates`, `03 Organize Media`. "Change Library" card was removed — that lives in Settings now.
     - Step numbers always orange (visible at rest, not just on hover).
     - On hover: border turns orange, background warms slightly.
     - Large SVG icon (100px, `AlignTop`) on the right side of each card: icon-classification.svg, icon-crates.svg, icon-organize.svg. Dimmed (`#2a2a2a`) at rest, full orange on hover.
     - Card height: `setMinimumHeight(230)`.
   - **Create** (2 cards): `＋ New Crate` (orange), `✦ New Smart Crate` (orange). Both use the same orange warm-tinted base/hover style (`#2a2218` base, orange border on hover).

3. **Recent Activity** (`_build_activity_section()`) — combined feed: crate changes, recently added tracks, and reorganization events (teal dot = reorg/addition, orange dot = rollback/removal). Last 30 days, capped at 10 items.

4. **Footer** (`_build_footer_bar()`) — last session timestamp + Serato sync status. Do not modify.

### Serato sync warning:

When changes are detected on launch, an amber banner appears with a "Review && Sync…" button (min-width 170px, `&&` required for literal ampersand in PyQt6). The `_ChangeReviewDialog` shows each change with timestamp and a **Revert** button. Revert marks the change as pending (row grays out, button becomes Undo). On "Sync && Proceed": reverts execute, checkpoint saves, re-scan triggers. On Cancel: nothing written.

### Checkpoint system (`src/utils/checkpoint.py`):

- Schema: `{crate_path: [track_path, ...]}` — stores full track lists, not just counts.
- Backward compatible: old checkpoints with integer values are handled by `_count(val)` / `_track_list(val)` helpers.
- `detect_changes()` returns dicts with `prev_tracks` (list for revert) and `old_crate_path` (for rename revert).
- `_ChangeReviewDialog` uses `prev_tracks` to restore crate files on revert.

### Dashboard layout rule:

`_dashboard_layout` uses `addStretch()` at the end — do NOT add `setAlignment(AlignTop)` to it. The stretch absorbs extra space. Adding AlignTop conflicts with addStretch and causes gaps at large window sizes. Section widgets must use `setMinimumHeight`, not `setFixedHeight`, so they don't over-constrain the layout.

---

## Crate Manager — Current Architecture

### New crate buttons

Two buttons at the top of the crate panel (below the search bar), inside a `QWidget` container with `setFixedHeight(45)` and `setContentsMargins(8, 5, 8, 5)`:
- **＋ New Crate** — orange (`#D17D34`), calls `_on_new_crate()`
- **✦ Smart Crate** — teal (`#428175`), calls `_on_new_smart_crate()` (Pro stub)

The container is fixed at 45px. The track table header is also `setFixedHeight(45)` so they align side-by-side in the splitter.

### Default crate selection

On first visit to Crates tab: defaults to "All Tracks" (`_ALL_TRACKS_KEY`).
On return visits: restores `_last_selected_path` or `_current_crate_path`.
Resets to All Tracks on app restart (in-memory only, not persisted).
Implemented via: `restore_sel = self._last_selected_path or self._current_crate_path or _ALL_TRACKS_KEY` in `load()`, followed by the same post-rebuild track-load block as `_refresh()`.

### Track-to-crate drag and drop

Tracks can be dragged from the track panel and dropped onto a crate in the crate tree. Key details:
- `setDragDropMode(NoDragDrop)` must be called BEFORE `setAcceptDrops(True)` — NoDragDrop internally calls `setAcceptDrops(false)` and propagates to viewport, overriding any prior True call.
- Correct order: `setDragEnabled(False)` → `setDragDropMode(NoDragDrop)` → `setDropIndicatorShown(False)` → `setAcceptDrops(True)` → `viewport().setAcceptDrops(True)`
- The eventFilter handles `DragEnter`, `DragMove`, `DragLeave`, `Drop` events on the crate tree viewport.
- On hover during drag: target crate lights up with `STATE_E` (teal-tinted bg `#1a3530`, teal left bar). Prior state saved and restored on leave/drop.
- Ghost drag pixmap: teal pill showing track title (single) or "N tracks" (multi), built in `startDrag()` using `QFontMetrics` + `QPainter`.
- Multi-track drag: `startDrag()` collects all selected rows by `{idx.row() for idx in self.selectedIndexes()}`.

### CrateItemDelegate — five states

| State | Trigger | Background | Left Bar |
|-------|---------|------------|----------|
| A | Unselected top-level | `#2F2F2F` | None |
| A (sub) | Unselected sub-crate | `#222222` | None |
| B | Selected (no active sub-crate) | `#573d26` | `#D17D34`, 5px |
| C | Parent of active sub-crate | `#000000` | `#D17D34`, 5px |
| D | Selected sub-crate | `#573d26` | `#D17D34`, 5px |
| E | Track drag hover target | `#1a3530` | `#428175`, 5px + teal inset border |

### Track panel

14 columns. Header height: 45px. Column widths persist via QSettings (`_SETTINGS_KEY`).

| Index | Name |
|---|---|
| 0 | # (position, numeric sort) |
| 1 | Title |
| 2 | Artist |
| 3 | Album |
| 4 | Duration |
| 5 | Genre |
| 6 | Style Tags |
| 7 | BPM |
| 8 | Date Added |
| 9 | Format |
| 10 | Year |
| 11 | Bitrate |
| 12 | Comments |
| 13 | File Path |

---

## Organize View — Current Architecture

`src/gui/organize_view.py` — `QStackedWidget` across 5 states:

- **State 0: Gate / Landing Screen** — always shown on tab visit. Shows classification status (toggles `_gate_needs_class_widget` / `_gate_ready_widget`) and a history list of up to 3 recent reorganizations (`_history_layout`). Each history row shows date, file count, and either "Rolled back on [date]" or a red **Rollback** button. `_refresh_gate_screen()` is called on every `load()` and every `_on_back_to_dashboard()`. `load()` never auto-transitions to planning — user clicks "Plan Reorganization…".
- **State 1: Planning Screen** — `_PlanWorker` thread builds the plan.
- **State 2: Preview Screen** — animated stat cards + operations table.
- **State 3: Executing Screen** — copy-verify-delete progress.
- **State 4: Done Screen** — success or rollback-in-progress state. Has `self._done_back_btn` (re-enabled after rollback finishes) and `self._rollback_btn`. The detail line now shows crate path update status: "N crate(s) updated" on success, or "Crate paths not updated — use Repair Crate Paths in Settings" if `paths_rewritten == 0`.

### Operations table action labels:

| Condition | Label | Color |
|---|---|---|
| Filename changed + folder changed | Move & Rename | `#d98c52` peach |
| Filename changed + folder same | **Rename** | `#c9a87a` warm amber |
| Metadata only + folder changed | Move & Tag | `#9fa4c7` lavender |
| Metadata only + folder same | **Tag Update** | `#9fa4c7` lavender |
| Neither | Move Only | `#e89ebb` pink |

### Rollback from history

`_on_rollback_requested(log_path=None)` — accepts an optional `Path`. If a Path is passed (from history row), sets `_rollback_log_path = log_path`, transitions to State 4 in in-progress mode (labels set, rollback btn hidden, back btn disabled). Guard: `isinstance(log_path, Path)` distinguishes real Path from QPushButton's `checked=False` signal arg.

### reorg_completed signal

`OrganizeView.reorg_completed` pyqtSignal — emitted from `_on_back_to_dashboard()` only (not from cancel). Connected in MainWindow to `_on_reorg_completed()` which calls `_dashboard.start_scan(lib)`. This re-scans the library after a reorg so the Crates tab immediately reflects new file paths without requiring a restart.

---

## File Organizer — Current Architecture

`src/core/file_organizer.py`

### Crate path update after reorg

`_update_crate_paths()` in `FileOrganizer.execute()` supplies both relative-to-library-root and absolute path variants for every moved file. If `paths_rewritten == 0` after a non-zero move count, the crate files were not updated — the Done screen now surfaces this with a prompt to use Repair Crate Paths in Settings.

**Two serato_crate API paths (important):**
- `CrateReader` uses `SeratoCrate.load()` → returns `Path` objects, calls `.as_posix()` → normalized POSIX strings
- `PathRewriter` uses `read_crate_file()` → returns raw UTF-16 decoded strings directly

For typical POSIX paths these are equivalent. Mismatch can occur if the raw string has non-standard Unicode representation (e.g., a superscript character stored with different NFC/NFD encoding than Python's Path derives from the filesystem). If crate paths are not updating, use Repair Crate Paths in Settings to replay all reorg logs through the PathRewriter.

### Path rewriter fix (critical)

`.crate` files store paths in two formats:
1. **Relative** to library root: `MP3/Blues/track.mp3`
2. **Absolute**: `/Users/.../MP3/Blues/track.mp3`

`_update_crate_paths()` must supply both variants for each moved file. Serato also inconsistently encodes `:` as `` (U+F022) in some crate files. `PathRewriter._process_crate()` normalizes stored paths via `inner_val.replace('', ':')` before lookup so both encoding variants match.

### Stems handling

- `_execute_move()` moves paired `.serato-stems` files alongside their audio file.
- `.serato-stems` packages can be **files OR directories** — all code must handle both.
- `_will_be_empty()` ignores stems (file or dir) when checking if a source directory is empty.
- `_clean_empty_dir_recursive()` quarantines orphaned stems to `_CrateSort/orphaned_stems/` (preserving relative path structure) before removing empty dirs. Uses `_quarantine_stems_in()` which checks `child.name.lower().endswith('.serato-stems')` — NOT `child.is_dir()`.

### Title tag sync

When `build_plan()` generates an operation, it also adds a `MetadataChange(field='title')` to sync the ID3 title tag with the clean destination filename stem. This prevents `FilenameCleaner` from re-proposing the same rename on every subsequent run.

### _sync_metadata_files

Called after every execute and rollback. Updates `classification_session.json` and `library_edits.json` with new file paths so subsequent scans find correct records.
- Forward (after execute): old path → new path
- Reverse (after rollback): new path → original path
- Normalises keys to `Path` objects internally before lookup.

### Rollback log

`RollbackLog` stores `rolled_back_at` ISO timestamp and saves when rollback completes. The Organize gate screen reads this to determine whether to show the Rollback button or a "Rolled back on [date]" label.

### Protected prefixes

`DEFAULT_PROTECTED_PREFIXES = ()` — no folders are protected. The docstring claiming `_`-prefixed folders are skipped is outdated and wrong.

---

## Settings View

`src/gui/settings_view.py` — `SettingsView(QWidget)`

### Signals
- `library_changed(Path)` — user picked a new library. MainWindow handles: saves to QSettings, calls `_dashboard.start_scan(path)`, navigates to Dashboard.
- `repair_requested` — triggers `_on_repair_crate_paths()` in MainWindow, which replays all reorg logs through PathRewriter to fix stale crate references.

### Sections

**Your Library**
- Current library path display
- Change Library button (orange) — opens folder picker
- Auto-load on startup checkbox — persists `always_load_last` to QSettings. Uses SVG indicator images from `assets/icons/checkbox-checked.svg` (orange fill + black checkmark) and `assets/icons/checkbox-unchecked.svg`.

**Maintenance**
- Repair Crate Paths (teal) — replays reorg logs through PathRewriter
- Reset Track Table Columns (muted) — removes `_SETTINGS_KEY` from QSettings

**About**
- App name, version, tagline
- 5-step workflow walkthrough

### load(library_path) must be called in `_on_nav` for index 5.

---

## Serato File Format (research confirmed)

- **`.crate` files**: only contain `ptrk` (track path). No timestamps, no metadata. Paths can be relative OR absolute depending on how the crate was created.
- **`database V2`**: TLV binary format, UTF-16 BE. Contains `uadd` (add timestamp), `pfil` (file path), and full track metadata per `otrk` record.
- **`neworder.pref`**: UTF-16 BE text. Canonical crate display order.
- **`collapsed.pref`**: tracks crate expansion states.
- Serato uses `` (U+F022 private-use) as a substitute for `:` in folder names — inconsistently applied. Always normalize on read by replacing `` → `:` before path comparisons.

---

## Genre taxonomy (12 parent genres)

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

## File organization rules

- CrateSort works in place — reorganizes within the user's designated directory
- Genre/Artist/track hierarchy. No style subfolders on disk.
- **Filename = song title only.** Artist prefix is stripped from both the filename AND the ID3 title tag.
- "The" moved to end with comma: `The Doors` → `Doors, The/`
- macOS: `/` in artist names replaced with `:` in filesystem (Finder renders `:` as `/`). Implemented in `sanitize_filename()` via `sys.platform == 'darwin'` check.
- No empty genre folders
- No file deletion outside user-approved duplicate consolidation
- No independent file moves outside user-triggered reorganization

---

## Things that must never be broken

- **Serato custom ID3 frames** — cue points, beat grids, loops, color tags — never overwritten
- **The `.crate` file order** — only changed by explicit user drag reorder, never by sorting
- **CrateItemDelegate** — the single source of truth for crate tree rendering; never revert to setItemWidget or stylesheet selection coloring
- **Reload-after-write pattern** — after any crate content modification, reload from `.crate` file rather than manipulating table rows directly
- **Track panel column constants** — verify every index before use
- **Column width persistence** — QSettings save/restore; auto-sizers only run on first launch
- **Confirmation dialogs** — every destructive action requires modal confirmation before executing
- **Teal = action, Orange = selection/CTA, Red = cancel/destructive** — never swap these roles
- **45px header/button-row height** — track table header and crate panel new-crate button container both fixed at 45px
- **`_LaunchDialog` is deleted** — do not recreate it or any other launch popup
- **`addStretch()` in `_dashboard_layout`** — do not add `setAlignment(AlignTop)` to this layout; it conflicts with addStretch at large window sizes
- **`setDragDropMode(NoDragDrop)` before `setAcceptDrops(True)`** — NoDragDrop overrides acceptDrops; order is mandatory

---

## Undo/Redo System

- `src/utils/undo_manager.py` — Command pattern, 10-state stack, global across tabs
- 9 command classes: `AddTracksCommand`, `RemoveTracksCommand`, `ReorderTracksCommand`, `CreateCrateCommand`, `DeleteCrateCommand`, `RenameCrateCommand`, `ReorderCratesCommand`, `ReparentCrateCommand`, `EditTrackMetadataCommand`
- Undo/Redo buttons in sidebar below album art — teal when active, gray when inactive
- Cmd+Z / Cmd+Shift+Z keyboard shortcuts

### EditTrackMetadataCommand

Covers inline track metadata edits (title, album, tags, BPM, year, comment) made via the double-click editor in the Crate Manager track table.

- Stores: `file_path` (str), `field` (str), `field_col` (int = `TC_*` constant), `old_val`, `new_val`
- `execute()` / `undo()` both call `_apply(val)` which updates `_edits` dict, calls `_save_edits()`, finds the row by `TC_PATH` lookup (sort-order safe), updates the cell text, and flashes the row
- Wired into `_commit_editor()` in `crate_manager.py` — if `_undo_manager` is present the command is pushed instead of applying inline; if no undo manager (e.g., standalone use) it falls back to direct application
- **Artist reassignment and genre overrides are not yet covered** — those go through separate context-menu paths and still write directly to `library_edits.json` without undo

---

## Serato integration rules

- **Serato's edits always win** on startup sync. CrateSort absorbs changes, never overwrites.
- **Serato custom ID3 frames** (cue points, beat grids, loops, color tags, markers) are NEVER modified under any circumstances.
- **Crate file order** is only ever changed by explicit user drag reorder actions.
- **CrateSort owns crate structure.** Crate order, hierarchy, names — all controlled by CrateSort.
- **The `_Serato_` folder must live on the same drive as the media files.**
- **CrateSort never auto-creates the `_Serato_/` folder structure.**

### Startup sync (built)

On every launch after scan, CrateSort:
1. Reads current `.crate` files and compares to `checkpoint.json`
2. If changes detected: shows amber banner and `_ChangeReviewDialog` with per-change Revert buttons
3. User can revert individual changes before syncing
4. On "Sync && Proceed": reverts execute, checkpoint saves with track lists, re-scan triggers

---

## Monetization model (future, not built in v1)

- **Free tier**: Serato crate management (view, create, rename, duplicate, delete, drag tracks)
- **Paid tier** (~$5-10/month or ~$100/year): Drive reorganization, Export Crate to Folder, duplicate detection, style suggestions, smart crate builder, CrateView bridge
- Smart Crate button exists (✦) in the Crates tab and Dashboard but shows a "Pro feature" stub — not yet built.

---

## Related project

**CrateView** (https://www.mycrateview.com) — WordPress child theme for vinyl collection management. CrateSort can optionally connect to CrateView's JSON cache for vinyl/digital alignment. Read-only optional plugin, not a core dependency.
