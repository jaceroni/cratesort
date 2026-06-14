# CLAUDE.md — CrateSort

This file provides guidance to Claude Code when working with the CrateSort project.

## Governance structure

This file is maintained by four specialists who each govern a domain of the project. Read all four sections before beginning any work session.

- **Cody** — Code Steward. Architecture, patterns, locked decisions, file system rules, regression awareness.
- **Brandy** — Brand Guardian. Visual identity, color system, mascot, typography, voice, CrateSuite coherence.
- **Dez** — Design Lead. Component standards, layout, spacing, interaction patterns, motion, app standards.
- **Draper** — Creative Director. The soul of the project. The standard every decision is held against.

---

## What this project is

CrateSort is a cross-platform desktop app (macOS-first) that organizes a DJ's digital music library (MP3s and music videos) and manages their Serato DJ Pro crates. It is the digital counterpart to CrateView (a WordPress theme for vinyl collection management). Together they form the CrateSuite.

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
- **Every Claude Code prompt must be delivered as a markdown (.md) file.** Never paste code or instructions directly into chat as inline code blocks — always write a proper prompt file.
- **GUI from day one.** No terminal-only phase.
- **Modular architecture.** Every feature is a module that can be independently developed and (in the future) gated behind a subscription tier.
- **Claude Code for execution. Planning chat for strategy and design.** The owner (Jace) architects in a separate Claude chat, then provides detailed prompts to Claude Code.
- **For small visual-only changes (height, color, spacing): read the exact lines, change only those lines, do not reason about surrounding layout or touch other files.**

---

## Core philosophy

- **CrateSort is the single writer. Serato is the reader.** Whatever CrateSort writes, Serato picks up on next launch. CrateSort owns the crate structure completely — crate order, hierarchy, names, membership. Do not defer to Serato's defaults.
- **The folder is the home, the crate is the connection.** Files live in one place on disk. Crates are references — one file, many crates.
- **Crates are references, not files.** Moving a track between crates never moves a file on disk. Ever. The only operation that moves files on disk is the Organize view's execute step.
- **Inform first, act second.** Preview → approve → execute. Never destructive without user consent.
- **Non-destructive by default.** Rollback. Quarantine. Never permanent delete outside user-approved duplicate consolidation.

---

## Design language — CrateSuite visual identity

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

**Nav order is locked.** Organize stays at the end — it is a destination, not a routine step. The Dashboard action cards (01/02/03) provide the guided journey nudge without forcing order on the user.

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
| Filename changed + folder same | Rename | `#c9a87a` warm amber |
| Metadata only + folder changed | Move & Tag | `#9fa4c7` lavender |
| Metadata only + folder same | Tag Update | `#9fa4c7` lavender |
| Neither | Move Only | `#e89ebb` pink |

### Rollback from history

`_on_rollback_requested(log_path=None)` — accepts an optional `Path`. If a Path is passed (from history row), sets `_rollback_log_path = log_path`, transitions to State 4 in in-progress mode (labels set, rollback btn hidden, back btn disabled). Guard: `isinstance(log_path, Path)` distinguishes real Path from QPushButton's `checked=False` signal arg.

### reorg_completed signal

`OrganizeView.reorg_completed` pyqtSignal — emitted from `_on_back_to_dashboard()` only (not from cancel). Connected in MainWindow to `_on_reorg_completed()` which calls `_dashboard.start_scan(lib)`. This re-scans the library after a reorg so the Crates tab immediately reflects new file paths without requiring a restart.

---

## File Organizer — Current Architecture

`src/core/file_organizer.py`

### Serato running guard

`src/utils/serato_guard.py` — `is_serato_running() -> bool`. Uses `pgrep`/`tasklist`; never raises (returns False on failure). Called from `OrganizeView._warn_serato_running()` before both execute and rollback. Shows a branded dark modal (`#1a1a1a` bg, `#f1e3c8` text, red dismiss) and blocks the operation if Serato is detected.

### Transaction integrity hardening

- **Incremental rollback log saves**: `execute()` saves the log to disk before any file operations begin, after every successful `_execute_move()`, and in a `try/finally` that covers the crate-rewrite and `_sync_metadata_files()` tail. A crash mid-reorg always has a recoverable log.
- **Log-before-delete (`destination_written` status)**: `_execute_move()` logs the operation with `status='destination_written'` immediately after `tmp_dest.replace(destination)` — before `source_path.unlink()`. If the process is killed between those two, rollback knows the destination file exists and removes it (source never deleted). After the unlink succeeds, the last log entry is updated in-memory to `'completed'`.
- **Duplicate consolidation rollback uses copy**: consolidated duplicates are logged with `'duplicate': True`. Rollback uses `shutil.copy2` (not `shutil.move`) so the surviving destination file stays intact.
- **Atomic JSON writes**: `_write_json_atomic(path, data)` is a module-level helper in `file_organizer.py` that writes to `.tmp` then renames. Used by `_sync_metadata_files()` for both `classification_session.json` and `library_edits.json`.
- **Genre folder sanitization**: `_build_destination()` passes `genre_folder` through `sanitize_path_component()` after the slash-to-colon replacement. Preserves the macOS colon (Finder renders as `/`); strips `?`, `*`, `"`, `<>` etc. that would cause OS exceptions.
- **Windows MAX_PATH warning**: on `win32`, `build_plan()` sets `FileMoveOp.path_too_long = True` for destinations > 240 chars. The operations table appends `⚠ Path` to the action label. `_on_execute()` shows a confirmation dialog before starting the worker if any warnings exist.
- **PathRewriter atomic set**: `rewrite()` snapshots each crate's bytes before modification. On any exception mid-loop, all already-written crates are restored from their snapshots and the loop breaks — Serato never sees a partially-applied rewrite.

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

`_update_crate_paths()` must supply both variants for each moved file. Serato also inconsistently encodes `:` as `\uf022` (U+F022) in some crate files. `PathRewriter._process_crate()` normalizes stored paths via `inner_val.replace('\uf022', ':')` before lookup so both encoding variants match.

### Stems handling

- `_execute_move()` moves paired `.serato-stems` files alongside their audio file.
- `.serato-stems` packages can be **files OR directories** — all code must handle both.
- `_will_be_empty()` ignores stems (file or dir) when checking if a source directory is empty.
- `_clean_empty_dir_recursive()` quarantines orphaned stems to `_CrateSort/orphaned_stems/` (preserving relative path structure) before removing empty dirs. Uses `_quarantine_stems_in()` which checks `child.name.lower().endswith('.serato-stems')` — NOT `child.is_dir()`.

#### Known gap — subdirectory stems (Phase A fix)

Current stems pairing logic only looks for `.serato-stems` files sitting **directly alongside** the audio file in the same directory. If stems are nested in a subdirectory relative to the audio file, they are not found during `_execute_move()` and end up quarantined to `_CrateSort/orphaned_stems/` rather than traveling with their parent.

**Fix requirements (Phase A):**
- Stems search must recurse into subdirectories of the audio file's parent directory, not just check the same level
- When stems are found in a subdirectory, the full relative path relationship between audio file and stems must be preserved at the destination — stems move to the same relative position alongside the audio file at its new location
- Rollback must move stems back to their original location alongside their parent file — not leave them at the destination
- Path length must be checked for stems destination paths on Windows (same MAX_PATH guard as audio files)
- The rollback log must explicitly record stems moves alongside their parent audio file move so recovery is complete

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
- Serato uses `\uf022` (U+F022 private-use) as a substitute for `:` in folder names — inconsistently applied. Always normalize on read by replacing `\uf022` → `:` before path comparisons.

---

## Genre taxonomy (13 parent genres)

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
| Traditional | Pre-rock vocal pop, standards, classic crooners (Sinatra, Dean Martin, Brenda Lee) |

**Critical classification rules:**
- "Pop" is NEVER a valid genre.
- Synth-Pop and New Wave → Rock, not Electronic.
- Breakdance / Park Jams → Funk/Soul, not Hip-Hop/Rap.
- Soul → Funk/Soul, not R&B.
- All genre and style terms: Title Case.
- Artist genre changes never cascade to tracks. Style tags are fully independent between artists and tracks.

---

## File organization rules

- CrateSort works in place — reorganizes within the user's designated directory
- Genre/Artist/track hierarchy. No style subfolders on disk.
- **Filename = song title only.** Artist prefix is stripped from both the filename AND the ID3 title tag.
- "The" moved to end with comma: `The Doors` → `Doors, The/`
- macOS: `/` in artist names replaced with `:` in filesystem (Finder renders `:` as `/`). Implemented in `sanitize_filename()` via `sys.platform == 'darwin'` check.
- No empty genre folders
- No file deletion outside user-approved duplicate consolidation (quarantine, not permanent delete)
- No independent file moves outside user-triggered reorganization

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

## Things that must never be broken

- **Serato custom ID3 frames** — cue points, beat grids, loops, color tags — never overwritten
- **The `.crate` file order** — only changed by explicit user drag reorder, never by sorting
- **Crates are references** — moving a track between crates never moves a file on disk. Ever.
- **CrateItemDelegate** — the single source of truth for crate tree rendering; never revert to setItemWidget or stylesheet selection coloring
- **Reload-after-write pattern** — after any crate content modification, reload from `.crate` file rather than manipulating table rows directly
- **Track panel column constants** — verify every index before use
- **Column width persistence** — QSettings save/restore; auto-sizers only run on first launch
- **Confirmation dialogs** — every destructive action requires modal confirmation before executing
- **Teal = action, Orange = selection/CTA, Red = cancel/destructive** — never swap these roles
- **45px header/button-row height** — track table header and crate panel new-crate button container both fixed at 45px
- **36px track row height** — app-wide standard; never change without updating all views simultaneously
- **`_LaunchDialog` is deleted** — do not recreate it or any other launch popup
- **`addStretch()` in `_dashboard_layout`** — do not add `setAlignment(AlignTop)` to this layout; it conflicts with addStretch at large window sizes
- **`setDragDropMode(NoDragDrop)` before `setAcceptDrops(True)`** — NoDragDrop overrides acceptDrops; order is mandatory
- **Every Claude Code prompt delivered as a .md file** — never inline code blocks, no exceptions

---

## Monetization model (future, not built in v1)

- **Free tier**: Dashboard, Classification, Library metadata editing (reassign artists, fix years, add style tags, clean filenames). Genuinely useful on its own — not a crippled demo.
- **Paid tier** (~$5–10/month or ~$100/year): Crate creation and management, Organize (physical file reorganization), Export Crate to Folder, duplicate detection, smart crate builder, CrateView bridge.
- The free tier must feel complete. Paid features are additive power, not the removal of basic dignity.
- Architecture supports feature gating without rewrites.

---

## Related project

**CrateView** (https://www.mycrateview.com) — WordPress child theme for vinyl collection management. Part of CrateSuite alongside CrateSort. CrateSort can optionally connect to CrateView's JSON cache for vinyl/digital alignment. Read-only optional plugin, not a core dependency.

---


# CODY — Code Steward Protocol

This section governs how Claude Code approaches every task in the CrateSort codebase. These are not suggestions — they are mandatory checks that must complete before any code is written.

---

## Pre-flight checklist

Before writing a single line of code, answer every question below. If any answer is "yes" or "maybe," follow the corresponding protocol before proceeding.

1. **Does this change touch the file system?** (rename, move, copy, delete, create directories)
   → Follow the File System Rules below.

2. **Does this change touch any existing UI component?** (layouts, stylesheets, widget sizing, row heights, column widths)
   → Follow the Blast Radius Protocol below.

3. **Does this change touch crate reading or writing?**
   → Verify reload-after-write pattern is preserved. Never manipulate table rows directly after a crate write — always reload from the `.crate` file.
   → Verify the crates-are-references rule is preserved. See below.

4. **Does this change touch track panel columns?**
   → Verify every column index constant before use. Columns shift when new ones are added. Read the full column table in CLAUDE-CS.md before touching any index.

5. **Does this change touch any existing signal or slot?**
   → Trace every connection before and after. Confirm nothing is double-connected and nothing is orphaned.

6. **Does this change touch any layout or size constraint?**
   → Check for `addStretch()` vs `setAlignment()` conflicts. Verify `setFixedHeight()` vs `setMinimumHeight()` is appropriate. Never use `setFixedHeight` on a section widget inside `_dashboard_layout`.

7. **Does this change add a new button or interactive element?**
   → Verify color role: teal = action, orange = selection/CTA, red = cancel/destructive. Verify hover state follows the button hover rule. Never swap these roles.

---

## The crates-are-references rule

**This is both a hard engineering rule and a core design principle.**

Crates are references to files. They are never files themselves. Moving a track from one crate to another — in any direction, through any interaction — must never move, copy, rename, or touch the file on disk.

- Dragging a track to a new crate = adds a reference in the new crate's `.crate` file. The file on disk does not move.
- Removing a track from a crate = removes the reference from the `.crate` file. The file on disk is not deleted or moved.
- Deleting a crate = removes the `.crate` file. No files on disk are affected.
- Reordering tracks in a crate = reorders references. No files on disk are affected.

**The only operation that moves files on disk is the Organize view's execute step** — and only when explicitly triggered by the user after previewing and approving the full plan.

Any code that touches crate operations must be verified against this rule before it ships. If a crate operation could possibly touch a file on disk, it is wrong.

---

## File system rules

Any operation that touches files on disk is the highest-risk category in this codebase. Follow these rules without exception.

### Rename and move operations — atomic rule

**A file rename or move and its corresponding crate reference update must happen in the same atomic operation.** They must never be separated into two steps with any possible failure point between them.

- If the file is renamed → the crate path is updated in the same transaction.
- If the file is moved → the crate path is updated in the same transaction.
- If either operation fails → both roll back. No partial states.
- After any rename or move, verify the new path exists on disk AND the crate reference resolves to that path before reporting success.

This is the root cause of the rename desync failure mode: CrateSort writes the new filename to disk correctly, but the crate reference is updated as a separate step that can fail silently or not persist. On reload, CrateSort finds the crate reference pointing to the old filename and reports "file not found." The file is fine. The reference is stale. Atomic updates prevent this entirely.

### Special character handling

Before any file operation, sanitize paths for:
- Apostrophes and single quotes (`'`)
- Double quotes (`"`)
- Inch/measurement marks (`"`, `'`)
- Colons (`:`) — on macOS, stored as U+F022 in Serato crate files. Normalize on read via `replace('\uf022', ':')` before any path comparison.
- Slashes in artist names — on macOS, replace `/` with `:` in filesystem (Finder renders `:` as `/`). Implemented in `sanitize_filename()` via `sys.platform == 'darwin'` check.
- Unicode edge cases (NFC vs NFD encoding). Use `unicodedata.normalize('NFC', path)` before comparisons.

Failure to handle any of these can cause a file to be silently skipped during reorganization, leaving it behind in its original location.

### Directory cleanup — post-move verification

After any file move operation:
1. Verify the file exists at the new location before removing anything from the old location.
2. Check whether the source directory is now empty using `_will_be_empty()` — which correctly ignores `.serato-stems` files and directories.
3. If the source directory is empty (ignoring stems), clean it up. Do not leave empty genre or artist folders.
4. Orphaned `.serato-stems` files or packages (file or directory) must be quarantined to `_CrateSort/orphaned_stems/` via `_quarantine_stems_in()` — never deleted.

### Reorganization completeness

A reorganization is not complete until every file in the plan has been verified at its destination. Do not report success until:
- All files have been moved and verified at new paths.
- All empty source directories have been cleaned up.
- All crate references have been updated to new paths.
- `_sync_metadata_files()` has been called to update `classification_session.json` and `library_edits.json`.

If any file in the plan cannot be moved, surface the failure explicitly. Never silently skip a file and report the reorganization as successful.

---

## Blast radius protocol

Before modifying any existing feature, map every component it could affect. This is mandatory — do not skip it because the change seems small.

### Step 1 — Identify the blast radius

For the component you are about to change, list:
- Every other widget that shares a layout container with it.
- Every stylesheet rule that applies to it (global QSS, per-widget QSS, inline style).
- Every signal it emits and every slot connected to those signals.
- Every QSettings key it reads or writes.
- Every constant or index it depends on (column indices, nav indices, stack indices).

### Step 2 — Identify regression risks

For each item in the blast radius, ask:
- Could changing the target component change the layout, size, or position of this item?
- Could changing the target component affect this signal chain?
- Could changing the target component change the value of a shared constant or index?

### Step 3 — Scope the change

Write only what is necessary to accomplish the stated goal. Do not refactor adjacent code. Do not improve unrelated things. Do not touch files not in scope. If a change in one file requires a corresponding change in another, name both files explicitly before writing any code.

### Known regression patterns

- **Layout contamination**: Adding padding, margins, or size constraints to one widget shifts its siblings. Always check the parent layout type and what else it contains before changing any size constraint.
- **Stylesheet bleed**: A QSS rule targeting a widget class applies to all instances unless scoped with an object name. Always verify the scope of any stylesheet change.
- **Column index shift**: Adding a column to the track panel shifts every index above the insertion point. Use `TC_*` constants — never raw integers.
- **Row height inconsistency**: App-wide standard is 45px for headers and button rows, 36px for track rows. Any row height change must be applied everywhere simultaneously.

---

## Known failure vectors

### FV-1 — Rename desync (highest frequency)

**What happens**: User renames a file. File saves correctly on disk. On reload, CrateSort reports "file not found."

**Root cause**: File rename and crate reference update are two separate operations. The crate reference update can fail silently or not persist.

**Fix principle**: Atomic updates. Rename + crate reference update in one transaction. Both roll back on any failure. Verify new path and updated crate reference before reporting success.

**Check when touching**: `FileOrganizer`, `PathRewriter`, any rename or inline metadata edit flow, `EditTrackMetadataCommand`.

---

### FV-2 — Reorganization incompleteness

**What happens**: During reorganization, some files are not moved. Old directories are not removed. Library ends up partially reorganized.

**Root cause**: Special characters in filenames break path handling. File move verification not performed. `_will_be_empty()` not called before directory cleanup.

**Fix principle**: Sanitize all paths before any file operation. Verify every file at its destination before removing source. Surface every failure explicitly — never silently skip.

**Check when touching**: `FileOrganizer.execute()`, `_execute_move()`, `_clean_empty_dir_recursive()`, `sanitize_filename()`, `_update_crate_paths()`.

---

### FV-3 — Visual regression from feature additions

**What happens**: A new feature is added. An unrelated UI element changes — buttons get taller, spacing shifts, a layout breaks.

**Root cause**: Blast radius not mapped before the change.

**Fix principle**: Follow the Blast Radius Protocol before every change. Scope changes to only what is necessary.

**Check when touching**: Any layout container, any QSS block, any `setFixedHeight` or `setMinimumHeight` call, any widget sharing a layout with other widgets.

---

### FV-4 — Windows MAX_PATH path length limit

**What happens**: On Windows, total file paths are limited to 260 characters by default (MAX_PATH). The Genre/Artist/Track folder hierarchy CrateSort creates can approach or exceed this limit with long artist names or long track titles, causing file operations to fail silently or throw cryptic errors.

**Root cause**: Deep folder nesting combined with long names. A path like `D:\Music\Hip-Hop-Rap\Some Very Long Artist Name\Some Very Long Album Name\Some Very Long Track Title That Goes On.mp3` can easily exceed 260 characters.

**Fix principle**: When building or validating any file path during reorganization, check total path length before attempting the operation. On Windows, warn the user if a proposed path exceeds 240 characters (leaving a 20-char safety buffer). Crate names are OS filenames — subject to the standard 255-character filename limit on all platforms.

**Check when touching**: `FileOrganizer.build_plan()`, `sanitize_filename()`, any path construction logic, any Windows-specific path handling.

---

## Summary — the three questions

Before every task, answer these three questions:

1. **Does this touch the file system?** → Atomic rule. Sanitize. Verify. Clean up.
2. **What else does this touch?** → Map the blast radius before writing anything.
3. **Does this match a known failure vector?** → Verify the fix principle is preserved.

If you cannot answer all three questions confidently, read the relevant files before proceeding.

---

# BRANDY — Brand Guardian Protocol

This section governs brand identity across all CrateSort work. CrateSort is one product inside a larger brand family — CrateSuite. Every visual, copy, and interactive decision must be coherent with that family, not just with CrateSort in isolation.

---

## CrateSuite — the parent brand

**CrateSuite** (CamelCase, no space) is the parent brand housing all products: CrateView, CrateSort, and future apps (CrateEdit, etc.). This is not just a naming convention — it is a brand architecture decision. A user who knows CrateView must immediately recognize CrateSort as family. Shared identity is intentional and load-bearing.

All CrateSuite products share:
- The same color palette (exact hex values, no approximations)
- The same mascot character (expression and gesture vary per product)
- The same logotype style (script font, same weight and feel)
- The same motion and interaction system (easing, hover states, modals, transitions)
- The same typographic hierarchy

The only things that change between products are the product name, the mascot gesture, and the tagline.

---

## The mascot

The mascot is drawn in the **rubber hose** style — the defining animation aesthetic of 1920s and 1930s cartoons. Characterized by flexible, jointless limbs that bend like tubes, bold shapes, large expressive faces, and exaggerated bouncy movement. Iconic references: Felix the Cat, Betty Boop, Cuphead. This style is a hard constraint — not a loose inspiration.

The character is a monkey with headphones, sitting in or emerging from an orange milk crate. The character design is consistent across all CrateSuite products. The expression and hand gesture communicate each product's personality.

**CrateView mascot**: Rock horns gesture, eyes up, expressive. Personality: discovery, browsing, "dig deeper." The DJ finding something great.

**CrateSort mascot**: Head down, digging through records inside the crate. Personality: focused, purposeful, working. The DJ getting organized.

**Current app state**: The CrateSort logotype (script wordmark) is live in the app. The mascot has not yet been integrated into the app UI — it is a planned addition, not a missing asset. When it is placed, all rubber hose animation and motion rules apply.

**Rules for mascot usage:**
- Never alter the character's core design — proportions, rubber hose style, headphones, crate.
- Never use rigid, angular, or mechanical motion on the mascot. Rubber hose moves fluidly, elastically, and with exaggeration. Stiff motion breaks the character.
- Never use the wrong gesture for the wrong product.
- Never create a new gesture without explicit approval.
- The mascot is always paired with the logotype in lockup — never used as a standalone icon without the wordmark in formal contexts.
- When animating the mascot, honor the rubber hose principles: bouncy easing, squash and stretch, fluid limb movement. No linear or mechanical transitions.

---

## The logotype

Script font, same style and weight across all CrateSuite products. Only the product name changes.

**Three approved lockup backgrounds:**
- Orange pill (`#D17D34` background, cream text)
- Teal pill (`#428175` background, cream text)
- Black pill (`#1a1a1a` background, cream text)

All lockups work on the cream/parchment background (`#f1e3c8`). The logotype is never placed on an arbitrary background color outside these approved combinations.

**CamelCase is mandatory.** CrateSort, CrateView, CrateSuite — always. Never "Crate Sort," "cratesort," "CRATESORT," or any other variation.

---

## Color palette — exact values, no approximations

These are the only approved colors for CrateSort UI. Do not substitute, approximate, or introduce new colors without explicit approval.

| Role | Hex | Usage |
|------|-----|-------|
| Dark background | `#1a1a1a` | Primary app background |
| Dark panels | `#2F2F2F` | Panel and card surfaces |
| Sub-crate background | `#222222` | Expanded sub-crate groups |
| Active parent crate | `#000000` | Deeper dark for active parent state |
| Cream text | `#f1e3c8` | All primary text |
| Orange — selection/CTA | `#D17D34` | Selected states, CTAs, New Crate button, step numbers |
| Warm brown — selected bg | `#573d26` | Selected crate background |
| Teal — action | `#428175` | Drag indicators, status confirmations, active Undo/Redo, inline edit flashes |
| Red — destructive | `#C75B5B` | Cancel, Rollback, Revert, Delete, Stop buttons |
| Row separator | `#383838` | Table row separators and grid lines |
| Branch connectors | `#4a4a4a` | Crate tree branch lines |

**Color role rules — never break these:**
- Teal is action. Orange is selection. Red is destructive. These roles are permanent and non-negotiable.
- Never swap teal and orange.
- Never use red for anything other than cancel, undo, rollback, revert, delete, or stop.
- Never introduce a new accent color. If a new UI state requires a color, map it to an existing role first.

---

## Typography

- **Primary UI font**: Clean sans-serif. Not system default — CrateSort has its own themed UI.
- **Logotype/branding font**: Script style matching the CrateView logotype. Used only for the wordmark — never for UI copy.
- **Title Case**: All genre names, style terms, UI section headers, and card labels use Title Case.
- **Tagline**: "Get your shit together." — exact punctuation, lowercase throughout, period at end. Never paraphrase, soften, or punctuate differently.

---

## Tone and voice

CrateSort's personality is distinct from CrateView's while still being family.

**CrateView** is the record store you browse on a Saturday afternoon. Warm, exploratory, unhurried. "Dig faster. Dig deeper."

**CrateSort** is the tool you pick up when the library is a mess and it needs fixing. Direct, purposeful, no-nonsense. "Get your shit together." It respects the DJ's time. It doesn't over-explain. It tells you what it found, what it's going to do, and what it needs from you — then it gets out of the way.

**Voice rules:**
- Direct over decorative. Say what the app is doing in plain language.
- Confident but not aggressive. "25 tracks need classification" not "WARNING: 25 unclassified tracks detected."
- Respect the user's expertise. This is a tool for working DJs, not a beginner tutorial.
- Error messages are clear and actionable. Never vague ("Something went wrong"), never alarming ("CRITICAL ERROR"), never condescending ("Oops!").
- Status messages are brief. "Library synced." "3 crates updated." "Reorganization complete." Full stop.

---

## Motion and interaction — CrateSuite system

All CrateSuite products share the same motion and interaction language. These are not CrateSort-specific — they are suite-level standards that must remain consistent across products.

- **Easing**: Cubic ease-out for all transitions and animations. Count-up animations on stat cards use QTimer with cubic ease-out curve.
- **Hover states**: All interactive elements respond to hover. Teal buttons get darker on hover — never lighter. Orange elements warm slightly on hover. Never use a hover state that conflicts with the color role rules.
- **Modals and confirmations**: Every destructive action requires a modal confirmation before executing. Modal style is consistent — dark background, cream text, teal confirm, red cancel. No exceptions.
- **Status feedback**: Every significant operation produces a status message. Teal text for success/completion. Amber for in-progress or warnings. Red for failures. Status clears on next operation.
- **Transitions**: Smooth, not instant. Fast enough to feel responsive, slow enough to feel intentional. Nothing should flash or snap without a transition.
- **Mascot animation** (when integrated): Must honor rubber hose principles — bouncy easing, squash and stretch, fluid elastic movement. Never linear, never mechanical, never stiff.

---

## What Brandy watches for

These are the brand drift patterns to flag before any work ships:

- A new color introduced that isn't in the approved palette.
- Teal and orange swapped in any context.
- The tagline paraphrased, softened, or punctuated differently.
- "CrateSort," "CrateView," or "CrateSuite" written as two words, all lowercase, or all caps.
- A modal, button, or status message that doesn't follow the voice rules.
- A motion or transition that doesn't match the CrateSuite easing standard.
- The mascot animated with mechanical or stiff motion — rubber hose rules apply.
- The mascot used with the wrong gesture for the wrong product.
- Any UI element that would look out of place in CrateView — or out of place in CrateSort but not CrateView. Both are wrong. They're family.

---

# DEZ — Design Lead Protocol

This section governs design standards, component craft, interaction patterns, and the overall feel of CrateSort. Dez is not just a style guide — Dez is the standard that separates CrateSort from every other DJ library tool that came before it.

---

## The design mandate

DJs have been managing their libraries inside performance tools that were never designed for library management. The result is spreadsheet-level UI, no undo, no rollback, and interactions that treat the DJ's time as worthless.

CrateSort's design mandate is simple: **never make the DJ feel like they're using Serato's library tab.** Every component, every interaction, every moment of feedback must answer "premium tool built for a working DJ" — not "utility."

The aesthetic target is **Apple's minimalism combined with the dopest record shop in town.** Apple: everything in its right place, nothing unnecessary, quiet confidence, the interface gets out of the way. The record shop: dark walls, warm light, perfectly organized bins, swagger that's earned not performed. You walk in and feel like you're in the right place.

**What this means in practice:**
- No Excel spreadsheet aesthetics. Tables are data containers, not the personality of the app.
- No vanilla system alerts. Every modal, every dialog, every status message must feel like CrateSort.
- No visual clutter. Every element on screen earns its place.
- Warmth comes from color, not decoration. The dark background, cream text, and orange/teal accents do the work.

---

## The emotional payoffs — protect these above all else

These are the moments where CrateSort earns the user's trust. The design must honor each one.

**Undo/Redo** — this is trust. The user can try things without fear of breaking something permanently. The Undo/Redo buttons must always be visible, always reflect their state (teal when active, muted when unavailable), and always work instantly. Never bury them. Never make the user hunt for them.

**Rollback after reorganization** — this is emotional reassurance. Even after closing the app, the user can roll back a full library reorganization and every file goes back exactly where it was. This is magic. The UI around rollback must communicate that confidence — clear history, clear timestamps, a red Rollback button that means business but doesn't feel dangerous.

**Export Crate to Folder** — this is liberation. Right-click a crate, pick a destination, and every file from everywhere lands in one flat folder ready for a USB drive. The interaction must be fast, clear, and satisfying. The confirmation must tell the user exactly what happened — how many files, where they went.

**Drag and drop** — this is the signature interaction. Dragging crates to reorder them, dragging tracks between crates, dragging multiple tracks at once. It must feel fluid, responsive, and physically satisfying. The ghost drag pixmap, the hover state on the target crate, the drop confirmation — all of these are part of the choreography. Never let a refactor break the feel of this interaction.

**Non-destructive by default** — nothing is permanent without explicit approval. Crate changes never move files. File changes are previewable. Reorganization is reversible. The app earns trust by never doing anything the DJ didn't ask for. Every UI element that reinforces this principle — the preview screen before organize, the rollback button in history, the quarantine instead of delete — must be treated as a feature, not a formality.

---

## Component standards

### Tables and track lists

Tables are the primary data surface in CrateSort. They must not look like system tables.

- `setAlternatingRowColors(True)` — base `#242424`, alternate `#2a2a2a`. The difference is subtle and intentional.
- Full grid lines: `gridline-color: #383838`. Both horizontal and vertical.
- Row height: 36px for track rows. Non-negotiable app-wide standard.
- Column header height: 45px. Fixed. Aligns with the crate panel button row.
- Column headers have visual weight — they are the navigation layer of the table. They must be visually distinct from data rows.
- Right-click on any row opens a context menu. Double-click on any editable cell opens the inline editor. Both must work. Neither replaces the other.

### Modals and confirmation dialogs

When you interrupt a user, you owe them a good experience. A sterile system dialog says "I don't care that I interrupted you." A well-designed modal says "I know I stopped you — here's exactly what you need."

**Modal anatomy:**
- Dark background (`#1a1a1a` or `#2F2F2F` panel)
- Cream text (`#f1e3c8`)
- Clear, direct headline — one sentence, what is happening
- Supporting text if needed — brief, no jargon
- Action buttons: teal confirm (right), red cancel (left) — always this order
- No system chrome. No OS-default button styles.

**Modal entry animation:**
- Subtle bounce on entry. One small overshoot, settles immediately.
- Rubber hose energy — not a performance, just a feeling. The modal arrives with confidence, not with a thud.
- Duration: fast. ~200ms total. The bounce should be felt, not watched.
- Never animate on exit — just dismiss. The user made a decision; respect it immediately.

**Destructive confirmation modals** get one additional treatment: the red cancel button is slightly more prominent than usual. The user should feel the weight of the decision without feeling trapped.

### Status and alert system

The alert color system uses pastel, slightly opaque variations of the standard semantic colors. Soft enough to complement the cream, orange, and teal palette without demanding attention. This is working — protect it.

- **Teal (action/success)**: operation completed, sync confirmed, library loaded
- **Amber (in-progress/warning)**: scanning, changes detected, startup sync in progress
- **Red (failure/destructive)**: operation failed, file not found, destructive action pending
- **Muted/gray**: informational, passive, no action required

Status messages are brief. Subject + verb + count if relevant. "Library synced." "3 crates updated." "25 tracks need classification." No exclamation points. No alarming language. No vague messages.

### Drag and drop — interaction choreography

This is the signature interaction. Every part of it must feel good.

**During drag:**
- Ghost pixmap: teal pill, track title (single) or "N tracks" (multi). Clean, legible, follows the cursor naturally.
- Target crate lights up with STATE_E (teal-tinted background, teal left bar). Clear visual confirmation of where the drop will land.
- Non-target crates dim slightly. Focus narrows to the destination.

**On drop:**
- Immediate visual confirmation — the target crate updates, the tracks appear.
- Brief teal flash on the receiving crate. Not a long animation — just a moment of acknowledgment.
- If the drop fails for any reason, the ghost pixmap returns to its origin smoothly. Never just disappear.

**Drag reordering of crates:**
- Drag indicator line (teal, 2px) shows exactly where the crate will land.
- Snappy and responsive. No lag between cursor position and indicator position.

### Inline editing

Right-click OR double-click to edit. Both must work. This is not redundant — different users have different muscle memory and both patterns must be respected.

- Double-click activates the inline editor immediately, no delay.
- Right-click opens a context menu with Edit as the primary option.
- Inline editor matches the cell's visual style — dark background, cream text, no jarring white input box.
- On commit (Enter or blur): teal flash on the cell confirms the save. Brief, immediate, satisfying.
- On cancel (Escape): cell returns to original value instantly.

---

## Motion system — CrateSort specific

The motion system is shared across CrateSuite products, but CrateSort has specific motion needs based on its interactions.

**Core easing**: Cubic ease-out for all transitions. Things arrive with energy and settle smoothly. Nothing bounces endlessly. Nothing snaps.

**Rubber hose principle for UI**: The rubber hose drawing style (flexible, bouncy, organic) informs how CrateSort's UI moves — not how it looks. A modal that bounces in slightly feels alive. A crate that gives a little when you drag it feels physical. A stat card that counts up feels like it's working. These are small moments that add up to a premium feel.

Apply rubber hose energy to:
- Modal entry (small overshoot, ~200ms)
- Drag initiation (slight scale-up on the ghost pixmap as it lifts)
- Drop confirmation (brief scale pulse on the receiving element)
- Stat card count-up animations (cubic ease-out, not linear)

Never apply rubber hose energy to:
- Destructive confirmations — these should feel deliberate, not playful
- Error states — these should feel immediate and clear
- Any operation the user is waiting on — don't animate loading states with bounce

**Duration guidelines:**
- Micro-interactions (flash, highlight, hover): 100–150ms
- Entry animations (modal, panel): 180–220ms
- Data transitions (count-up, progress): 300–600ms
- Nothing exceeds 600ms unless it's a deliberate progress indicator

---

## Layout architecture — future-aware rules

**The media player is coming.** A persistent media player will eventually occupy the lower third of the app — audio playback and music video support. Every view must be designed with this in mind.

**Rules:**
- Never use `setFixedHeight` on the main window or any top-level container in a way that would prevent the player bar from being added.
- Leave a minimum of 80–100px of architectural headroom at the bottom of every view for the future player bar.
- No critical UI elements in the bottom 80px of any current view — that space belongs to the player.
- When the player is eventually built, it must not feel bolted on. It should feel like it was always there.

---

## What Dez watches for

These are the design drift patterns to flag before any work ships:

- A table or list that looks like a system default — no alternating rows, no grid lines, wrong row height.
- A modal that uses OS-default styling — white background, system buttons, no animation.
- A modal entry with no animation, or an animation that is too long or too bouncy.
- A drag interaction that lost its ghost pixmap, hover state, or drop confirmation.
- A status message that is vague, alarming, or uses an exclamation point.
- A new color used for status that doesn't follow the pastel alert system.
- Motion that is either too mechanical (no ease, no life) or too performative (too much bounce, too long).
- Any layout that would break when the media player bar is added to the bottom.
- Any component that answers "utility" instead of "premium tool built for a working DJ."

---

# DRAPER — Creative Director Context

This section is different from Cody, Brandy, and Dez. Those sections govern rules. This section carries the soul.

Draper is not a checklist. Draper is the answer to the question every specialist must be able to ask themselves before anything ships: **does this belong in CrateSort?**

Not "does it follow the rules." Not "is it technically correct." Does it belong here. Does it feel right. Does it serve the DJ who needs this tool.

---

## The wound this app was built to heal

CrateSort didn't start as a product idea. It started as frustration.

A hard drive disconnects from Serato without being safely ejected. On the next launch, crates are scrambled. Files that share the same song title — same name, different artist — get silently swapped into the wrong crates. No alert. No warning. No indication that anything went wrong. You only find out when you're at the gig.

You accidentally hover over a crate instead of a track and hit delete. The crate is gone. No undo. No recovery except restoring a backup — if you have one, if it's recent enough, if the crate was in it.

Serato says a file can't be found. You can see it in Finder. You go to "Relocate Lost Files," manually hunt it down, reassign it. Then it happens again with another file. Then another.

Files tagged with rerelease years instead of original release years. A 1990s track showing up as 2018 because that's when the remaster dropped. Wrong genres from whoever tagged them at the source. No style tags. No batch tools. A library that technically works but constantly lies to you.

Third-party solutions exist but charge too much for tools that still don't respect the DJ's time or intelligence.

**This is what CrateSort was built to fix.** Not as a feature list. As a response to genuine pain. Every design decision, every engineering decision, every product decision flows from this origin. When something in CrateSort doesn't feel right — when it feels cold, clunky, or disrespectful of the user's time — it's because it forgot where it came from.

---

## What CrateSort actually is

A library management tool for working DJs. Not a performance tool. Not a streaming app. Not a file browser. A librarian — the one thing Serato, Traktor, and Rekordbox never bothered to build properly.

**The five screens are five independent jobs:**

**Dashboard** — the session command center. What changed since last time. What needs attention. Where to go next. Oriented, not overwhelming.

**Classification** — the first pass. The app studies the library and proposes how everything should be organized: one genre per artist, style tags at the track level, correct years, clean filenames. The DJ validates and approves. Nothing moves yet.

**Library** — the editing surface. Every file is visible. Every metadata field is editable. Right-click, double-click, adjust anything. Fix wrong years, add style tags, reassign misattributed tracks, confirm classification looks right. Still nothing moves on disk.

**Crates** — the Serato mirror. What the DJ's Serato library looks like, but better. Bigger canvas. Undo/redo. Drag tracks between crates without removing them from the original. Build smart crates with real rules. Manage the performance environment without ever touching Serato directly. **Crates are references, not files. This is a hard rule and a design principle — the crate environment is safe by definition. Moving a track between crates never moves a file on disk. Ever.**

**Organize** — the big move. Only when the DJ is ready. Takes all the classification and metadata work and physically restructures the drive: Genre/Artist/Track hierarchy, clean filenames, Serato crate paths updated automatically. Full rollback available even after the app is closed. This is the most consequential action in the app and it should feel like it — weighty, deliberate, and completely reversible.

**Nav order is locked:** Dashboard → Classification → Library → Crates → Organize → Settings. Organize stays at the end. It is a destination, not a routine step. The Dashboard action cards (01/02/03) provide the guided journey nudge without forcing the order on anyone.

---

## The features that earn trust

These are not selling points. They are the moments where CrateSort proves it understands what a DJ actually needs.

**Undo/redo** — you can try things without fear. This alone separates CrateSort from every DJ library tool that existed before it.

**Rollback after reorganization** — even after closing the app, you can put everything back exactly where it was. The UI around rollback must communicate confidence without making the user feel like they're defusing a bomb.

**Export Crate to Folder** — right-click a crate, pick a destination, every file from everywhere lands in one flat folder ready for a USB drive. No matter how many different locations those files live in, they come together in one place. A DJ who discovers this feature will not go back.

**Non-destructive by default** — nothing is permanent without explicit user approval. Crate changes don't move files. Reorganization is reversible. Duplicates go to quarantine, not the trash. The app earns trust by never doing anything the DJ didn't ask for.

**Smart crates with real rules** — automatically populate a crate with all Rock files from the 1980s with the Progressive style tag and "house party" in the comment field. No other DJ tool offers this with this level of control and this little friction.

---

## The monetization split — and why it matters for design

**Free tier**: Dashboard, Classification, Library metadata editing (reassign artists, fix years, add style tags, clean filenames). This is the on-ramp. It's genuinely useful on its own and demonstrates the value of having a proper librarian tool.

**Paid tier**: Crate creation and management, Organize (physical file reorganization), Export Crate to Folder, duplicate detection, smart crates, CrateView bridge.

**Why this split matters for design**: The free tier must feel complete, not crippled. A DJ using the free tier should feel like they have a real tool — not a demo. The paid features are additive power, not the removal of basic dignity. This distinction must be honored in every gating decision and every piece of copy around tier boundaries.

---

## The user

A working DJ. Not a hobbyist — someone who plays gigs, manages a real library, lives with the consequences of a messy hard drive. They've been burned by Serato scrambling their crates. They know what it feels like to lose a carefully built playlist before a show.

They are not asking for a beautiful app. They are asking for a tool that works, that they can trust, and that doesn't make them feel stupid. If CrateSort also happens to be beautiful — and it should be — that's what makes them recommend it to every other DJ they know.

**Design for the DJ who has been burned before.** Every decision that builds trust is a good decision. Every decision that introduces uncertainty — even if technically correct — is a bad one.

---

## The Draper test

Before anything ships, ask these questions:

1. **Does this serve the DJ who has been burned by Serato?** Not a hypothetical user. The specific person who lost a crate, who had files swapped, who spent an hour relocating lost files the night before a gig.

2. **Does this build trust or introduce uncertainty?** If a user sees this and wonders "wait, what did that just do to my files?" — it failed.

3. **Does this feel like it belongs in CrateSort?** Not just technically correct. Not just brand-compliant. Does it feel like part of the same tool that someone cared about building.

4. **Is this the dopest record shop in town, or is it a spreadsheet?** Premium. Warm. Confident. Purposeful. Never sterile, never utilitarian, never condescending.

5. **Would Jace look at this and know immediately if something was off?** The creative director doesn't need to articulate why something is wrong. The smell test is the test. If it smells off, it's off.

---

## What Draper watches for

These are the drift patterns that don't belong to any single specialist — the ones only a creative director catches:

- A feature that technically works but feels like it doesn't trust the user.
- A design that solved the wrong problem — technically correct but emotionally wrong.
- A status message, error, or confirmation that forgets the DJ is a professional.
- A workflow that adds steps where there should be fewer.
- Anything that makes CrateSort feel more like Serato's library tab than the premium alternative to it.
- A decision made for technical convenience that costs the user a moment of joy or confidence.
- Copy that talks down to the user. Language that's vague when it should be specific. Tone that's alarming when it should be calm.
- Any moment where the app interrupts the user and doesn't make that interruption worth it.
- The free tier feeling crippled instead of genuinely useful.
- The absence of delight where delight was possible and wouldn't cost anything.
