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
- **Packaging**: PyInstaller → `.app` (macOS) — **shipped, beta, unsigned**. `.exe` (Windows) and AppImage (Linux) not yet built. See Cody's "Packaging & Distribution" section for the full macOS pipeline.
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

**Nav is now 5 items. Classification tab has been eliminated.**

| Nav index | ID | Label | Icon | Content widget |
|---|---|---|---|---|
| 0 | `dashboard` | Dashboard | dashboard SVG | `DashboardWidget` |
| 1 | `library` | Library | library SVG | `LibraryBrowserView` |
| 2 | `crates` | Crates | crates SVG | `CrateManagerView` |
| 3 | `organize` | Organize | organize SVG | `OrganizeView` |
| 4 | `settings` | Settings | settings SVG | `SettingsView` |

`classifier_view.py` has been renamed to `_ClassifierViewLegacy` and is retired as a GUI destination. The backend `_ClassifyWorker` and `ClassificationSession` models inside it remain active and are used by `library_browser.py`.

Nav order is locked. Content stack index matches nav index exactly.

SVG icons live in `cratesort/assets/icons/` as `icon-{nav_id}.svg`. All are filled orange (`#D17D34`).

Nav buttons load SVGs via `QIcon(str(icon_path))` at `16×16`. The `_on_nav(index)` handler calls `.load()` on the appropriate view. `_on_nav()` guards against disabled nav items in "No library loaded" state — clicks on Library, Crates, and Organize are silent no-ops. When no-library is detected mid-session, redirects to Settings (index 4) as the recovery path.

After reorg or rollback completes, `OrganizeView.reorg_completed` fires → `MainWindow._on_reorg_completed()` → `_dashboard.start_scan(lib)` to rebuild inventory with new file paths.

**Nav order is locked.** Organize stays at the end — it is a destination, not a routine step.

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

### Nav state rules

**Two states only:**

**No library loaded:**
- Dashboard: Active
- Library: Disabled (visible, reduced opacity, tooltip: "Load a library to get started.")
- Crates: Disabled (same tooltip)
- Organize: Disabled (same tooltip)
- Settings: Active

**Library loaded:**
- All nav items: Active
- No classification gate on any nav item
- Organize shows warning dialog if unclassified tracks exist — does NOT hard block

Stale library path (saved in QSettings but no longer exists on disk): path and `always_load_last` both cleared from QSettings immediately; welcome screen shown in first-launch state (commit 739c97e).

---

## Classification Architecture

**Classification is a mode inside the Library tab, not a separate screen.**

The Library tab is the single unified environment for all track and artist editing. Classification is triggered by a "Classify Library" button in the Library toolbar.

### Classify mode behavior

- "Classify Library" button (teal, `#428175`) lives in the Library toolbar
- Clicking it runs `_ClassifyWorker` in the background and enters classify mode
- Classify mode inserts three columns into the track table: Proposed Genre (LC_CLS_PROPOSED, logical index 12), Confidence (LC_CLS_CONFIDENCE, logical index 13), Status (LC_CLS_STATUS, logical index 14)
- These columns are visually repositioned adjacent to the Genre column via `moveSection` after insertion
- A classify mode banner appears below the toolbar: teal background `#1a3530`, left border `3px solid #428175`, padding 12px, ⚡ icon, 12px text
- "Accept Reclassifications" button (teal) saves all proposals to `library_edits.json` and exits classify mode
- "Cancel" button exits classify mode without saving

### Auto-classify on first load

When `load()` runs and `_is_classification_complete()` returns `False` **and `self.isVisible()` is `True`**, `_on_classify_clicked(auto_classify=True)` is called automatically. The `isVisible()` guard prevents the modal from firing during background scans while the user is on the Dashboard — it only triggers when the user has explicitly navigated to Library.

`_on_classify_clicked` takes `checked: bool = False, auto_classify: bool = False`. The manual toolbar button passes `checked` (Qt signal arg); `auto_classify` is always passed as a keyword.

**Auto-classify path (two sub-cases):**

1. **Session already exists** (`classification_session.json` found): loads it, calls `apply_library_edits()`, enters classify mode directly — no modal shown.

2. **No session** (first-run): shows the `_AnalyzeLibraryModal` takeover and runs `_ClassifyWorker` in the background.

**Manual toolbar path** (`auto_classify=False`): same existing behavior — if session exists, enter classify mode directly; otherwise disable the button, run the worker, reconnect to `_on_classify_finished` / `_on_classify_error`.

### Classify mode navigate-away guard dialog

When the user tries to navigate away from Library while in classify mode, `_UnsavedClassifyDialog` appears with:
- **Headline**: "Classifications not saved"
- **Body**: "You haven't accepted your classifications yet — your genre corrections won't be written to your files until you do."
- **Primary button (teal)**: "Stay and Finish" — closes dialog, keeps user in classify mode
- **Secondary button (red)**: "Leave Anyway" — exits classify mode, allows navigation

This dialog is the only navigate-away guard for classify mode. Do not add additional dialogs or change these labels without explicit approval.

### Classify mode banner copy (locked)

The classify mode banner reads:
> "This is your library how we see it — review the artists and their nested files. Right-click/double-click an artist or their tracks to correct anything that looks off. Not sure about something? Change its genre to 'Unclassified' and move on. Your files are not touched until you reorganize."

Do not change this copy without explicit approval.

### _AnalyzeLibraryModal (first-run classify UI)

Three classes live in `library_browser.py`, inserted before `LibraryBrowserView`:

**`_AnimatedStatCardWidget(QFrame)`** — stat card with a 16ms QTimer that eases a numeric counter toward `_target_value` using `step = max(1, int(diff * 0.15))` (positive diff) / `min(-1, int(diff * 0.15))` (negative diff). Cards: `#1a1a1a` background, `1px solid #444444` border, 8px radius.

**`_ModalOverlay`** — now lives in `src/gui/overlays.py`. See **Dialog & Overlay Architecture** section below.

**`_AnalyzeLibraryModal(_CrateSortDialog)`** — inherits `_CrateSortDialog` from `overlays.py` (overlay scrim + bounce animation handled by base class). Fixed `520×280`. Inner `QFrame#modal_container` (`#2F2F2F`, 1px `#444444` border, 12px radius) provides the visual surface. Contains:
- Headline + subtitle labels
- Row of 3 `_AnimatedStatCardWidget` cards: Tracks Analyzed, Artists Classified, Corrections Made (last one stays at 0 — `# TODO: real-time comparison signal not yet available`)
- `QStackedWidget` (fixed 45px height, no layout jump):
  - Page 0: 4px `QProgressBar` (`#383838` bg, `#428175` chunk), determinate from first progress tick
  - Page 1: "Review Results" button (180×36px, teal)
- `review_requested = pyqtSignal()` — emitted by the button

**API:** `update_stats(tracks_count, artists_count)`, `update_percent(percent)`, `on_classification_complete()` (switches stack to page 1).

**Pre-compile step** (before starting worker): iterates `self._inventory` using the same DJ-tools/video grouping logic as `_ClassifyWorker.run()` to build `_auto_artist_tracks_map: dict[str, int]` and `_auto_dj_tools_count: int`. Progress slot uses these to increment `_processed_tracks_count` as each artist name arrives.

**Cleanup:** `_cleanup_auto_classify_ui()` — calls `modal.close()` which emits `finished` → `_CrateSortDialog._cleanup_overlay` tears down the scrim automatically. Resets all `_auto_*` state fields. Called by `_on_review_results_clicked` (then enters classify mode with `_auto_classify_session`) and `_on_auto_classify_error`.

### Modal subtitle copy (locked)

> "Analyzing your DJ library and media files – validating artists and genres..."

### Overlay rendering requirement

`_ModalOverlay` must have `self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)` set in `__init__` to render its stylesheet background color. Without it the scrim is invisible. This is a known PyQt6 behavior for custom `QWidget` subclasses.

### Classify Library button auto-disable

`_refresh_classify_btn()` is called at the end of every `load()`. It disables the Classify Library button when `_count_unclassified_artists()` returns 0. `_count_unclassified_artists()` only counts artists whose genre is in the Unclassified set AND who have no explicit `genre` entry in `self._edits` (i.e., `library_edits.json`). Artists explicitly set to Unclassified via right-click or via `_exit_classify_mode_accept` are counted as handled. If new tracks are added and rescanned, their artists have no edits entry → count > 0 → button re-enables automatically.

`_exit_classify_mode_accept` writes `genre: 'Unclassified'` to the edits dict for any remaining Unclassified artist with no existing entry before saving — this acknowledges them so the button can disable.

### Classification complete definition

Classification is complete when `_CrateSort/classification_accepted.flag` exists on disk. This flag is written ONLY when the user clicks Accept Reclassifications. Individual right-click genre edits do NOT set this flag.

`_is_classification_complete()` checks for this flag file. It does NOT check `library_edits.json` entry counts or `classification_session.json` existence.

### Five-state confidence system

| State | Meaning | Color |
|---|---|---|
| MATCHED | Existing ID3 tag matches taxonomy exactly — no change needed | `#f1e3c8` (cream) |
| HIGH | Classifier confident in proposal | `#428175` (teal) |
| MEDIUM | Classifier moderate confidence | `#9fa4c7` (lavender) |
| LOW | Limited signal, user should review | `#D17D34` (orange) |
| NONE | No usable data, user must decide | `#C75B5B` (red) |

MATCHED entries are not written to `library_edits.json` on Accept — their existing tag is their classification.

### Artist genre fallback chain (in _rebuild_tree)

1. Artist override in `library_edits.json` — key format `f'__artist__{artist}'`
2. Classification session `final_genre` or `proposed_genre` from `_classify_lookup(artist)`
3. Taxonomy-validated ID3 majority vote — only accepts exact matches against the 13 valid parent genres (case-insensitive). Invalid tags ("Pop", "Alternative Rock", "Hip Hop") are rejected.
4. Default to `''` — Unclassified

Raw ID3 tags are only trusted at Step 3 if they match one of the 13 valid parent genres exactly. No other fallback.

### Genre sidebar in Library

The Library tab has a permanent 180px genre sidebar (resizable via QSplitter, persists via QSettings `library/sidebar_width`). It shows:
- "All Artists" at top — total library counts
- One item per populated genre, alphabetical, with artist and track count subline
- Unclassified bucket at bottom in red — only visible when count > 0

Sidebar bucketing is driven by artist genre only. Track genre tags are metadata — they never determine which sidebar bucket an artist appears in.

After any genre change, `_populate_genre_sidebar()` and `_apply_filter()` are called immediately — no nav round-trip required.

### Navigate-away guard in classify mode

When the user clicks a nav item while classify mode is active, `_UnsavedClassifyDialog` appears:
- "Leave Anyway" (red) — exits classify mode without saving, allows navigation
- "Stay and Finish" (teal) — dismisses dialog, keeps user in Library

### Unclassified genre

Unclassified is a valid, selectable genre in the right-click Change Genre menu. It is a deliberate "flag for later" choice. During Organize, unclassified tracks go to `Media/Unclassified/Artist/Track` — same hierarchy as other genres. Organize shows a warning dialog (not a block) when unclassified tracks exist.

---

## Dialog & Overlay Architecture

All custom dialogs in CrateSort are built on the canonical classes in `src/gui/overlays.py`. **Never recreate these patterns inline.**

### `_ModalOverlay(QWidget)` — `overlays.py`
Full-window child of the main window. Style: `rgba(26, 26, 26, 217)` + `WA_StyledBackground`. Installs an event filter on the parent window; on `Resize`, updates geometry and re-centers the dialog. `mousePressEvent` accepts to block click-through. `removeFromParent()` removes the event filter before deletion. `set_modal(widget)` registers the dialog for centering.

### `_CrateSortDialog(QDialog)` — `overlays.py`
Base class for every CrateSort dialog. In `__init__`:
- Sets `FramelessWindowHint | Dialog` and `WA_TranslucentBackground`
- Creates `_ModalOverlay` over `parent.window()`, calls `set_modal(self)`, shows overlay
- Connects `self.finished` → `_cleanup_overlay` (removes event filter, hides, `deleteLater`)

In `showEvent`: calls `overlay.center_modal()` then `run_bounce_animation()` (200ms cubic ease-out, shrinks from 90% to full geometry via `QPropertyAnimation`).

**Usage:** subclass `_CrateSortDialog`, add a `QFrame` container with dark-panel styling, lay out content inside it. The overlay and animation are handled automatically.

### `_ov_alert(parent, title, body)` — `overlays.py`
One-button alert built on `_CrateSortDialog`. Always teal OK button, right-aligned.

### `_ov_confirm(parent, title, body, confirm_text, cancel_text, confirm_danger)` — `overlays.py`
Two-button confirmation. Cancel (muted outline, left) + Confirm (teal or red if `confirm_danger=True`, right). Returns `bool`.

### Dialog container styling standard
Every dialog built on `_CrateSortDialog` wraps all content in a `QFrame` with:
```
background-color: #2F2F2F; border: 1px solid #444444; border-radius: 12px;
```
The dialog itself is transparent (`WA_TranslucentBackground`) — the frame provides all visual weight. Always use an `objectName` for the QSS selector to avoid cascading.

### Files that import from overlays.py
`library_browser.py`, `organize_view.py`, `classifier_view.py`, `crate_manager.py`, `settings_view.py`, `dashboard.py`, `main_window.py`. `theme.py` still contains `QMessageBox` style rules for any future system dialogs — leave those alone.

---

## Free Tier Metadata Write-Through

Under the monetization model, free tier edits write directly to audio files on disk at the point of edit. This is implemented in `library_browser.py` and backed by a public wrapper in `file_organizer.py`.

### `write_file_metadata(file_path, field, value) → bool` — `file_organizer.py`
Thin public wrapper around the internal mutagen tag helpers. Loads the file with `mutagen.File(path, easy=False)`, calls `_write_metadata_tag(audio, ext, field, value)`, saves. Returns `True` on success, `False` on any failure. **Never raises** — catches all exceptions and logs.

**Supported fields:** `genre`, `artist`, `title`, `album`, `bpm`, `year`, `comment`.
**Supported formats:** MP3/WAV/AIFF, MP4/M4A, FLAC.
**Not supported:** `tags` (style tags — virtual-only, deferred).

### Write-through call sites in `library_browser.py`

| Method | Field written | Failure behavior |
|---|---|---|
| `_commit_active_editor` | `title/album/bpm/year/comment` | Reverts cell display; 5s warning in `_count_label`; staging in `library_edits.json` always preserved |
| `_reassign_track` | `artist` | Single warning after all tracks; partial success accepted |
| `_change_artist_genre` | `genre` (all tracks for artist) | Same |
| `_exit_classify_mode_accept` | `genre` (all accepted tracks) | Same; flag file still written |

**In-memory sync rule:** after every successful `write_file_metadata()`, update the corresponding `TrackRecord` field directly (`rec.title = new_val`, `rec.genre = new_val`, etc.). Never trigger a full re-scan.

**`library_edits.json` is not replaced.** Both the disk write and the JSON staging write happen. They are not mutually exclusive. The JSON staging acts as the Organize fallback for any disk-write failures.

---

## Dashboard Architecture

`src/gui/dashboard.py` — session-aware command center. Stack index 2 in `DashboardWidget`.

### Sections (in order):

1. **Stat Cards** (`_build_stat_cards_section()`) — four cards: Total Tracks, Total Crates, Unique Artists, Hours of Music. Count-up animation on load. No icon labels — numbers and labels only. `_AnimatedStatCard(target, suffix, label)` — note: no icon parameter.

2. **Action Cards** (`_build_action_cards_section()`) — two groups:
   - **Go To** (3 cards):
     - `Manage Library` — navigates to Library (index 1). Primary label in orange `#D17D34`, 16px, weight 500. No step number.
     - `Manage Crates` — navigates to Crates (index 2). Same label treatment.
     - `Organize Media` — navigates to Organize (index 3). Same label treatment.
     - **First-load highlight**: When `_is_classification_complete()` returns False, the Manage Library card renders with:
       - Border: `2px solid #428175`
       - Background: `#1a2e2b`
       - Icon at full teal opacity
       - Returns to standard appearance once classification is complete.
   - **YouTube import** (2 cards): `YouTube to MP4`, `YouTube to MP3` — built via `_IconActionCard`, matching the Go To cards' gray background / orange headline / muted-icon-lights-up-on-hover treatment (teal is reserved for the Manage Library highlight only; nothing else on the dashboard uses it). Icons are `assets/icons/icon-mp4.svg` (clapperboard) and `icon-mp3.svg` (eighth note) — dimmed `#2a2a2a` at rest, `#D17D34` on hover, same as the Go To cards' SVG recolor technique. There is no longer a "New Crate"/"New Smart Crate" card group on the dashboard — that functionality lives only in the Crates tab toolbar (see Crate Manager Architecture below).
   - **Organize Media footer**: an extra line below the description — `CrateSort's Organization Logic:` / `Your Library Folder > Media > Genre > Artist > Files` — rendered via `_WorkflowCard(footer=...)`, full-card-width (not confined to the text column), 12px font, 16.5px line-height set via rich-text `<div style="line-height:...">` since Qt's QSS `line-height` property is a silent no-op on plain `QLabel` text.

Dashboard has a `refresh()` method called when navigating to index 0 — re-runs duplicate detection and repopulates dashboard state. **Serato sync check (`_check_serato_sync()`) runs only in `_show_dashboard()` at session start — it is NOT called from `refresh()`.** This prevents CrateSort's own crate writes during a session from being flagged as external Serato changes.

3. **Recent Activity** (`_build_activity_section()`) — combined feed: crate changes, recently added tracks, and reorganization events (teal dot = reorg/addition, orange dot = rollback/removal). Last 30 days, capped at 10 items.

4. **Footer** (`_build_footer_bar()`) — last session timestamp + Serato sync status. Do not modify.

### Serato sync warning:

When changes are detected on launch, an amber banner appears with a "Review && Sync…" button (min-width 170px, `&&` required for literal ampersand in PyQt6). The `_ChangeReviewDialog` shows each change with timestamp and a **Revert** button. Revert marks the change as pending (row grays out, button becomes Undo). The primary action button updates dynamically via `_update_sync_btn_state()`: no reverts → **"Sync && Proceed"** (orange); some reverted → **"Apply && Proceed"** (orange); all reverted → **"Accept && Continue"** (teal). On Cancel: nothing written. `_can_revert()` returns True for both `crate_added` and `crate_removed` — removed crates are always revertable even when `prev_tracks` is empty (empty crate recreated from a `[]` list).

### Checkpoint system (`src/utils/checkpoint.py`):

- Schema: `{crate_path: [track_path, ...]}` — stores full track lists, not just counts.
- Backward compatible: old checkpoints with integer values are handled by `_count(val)` / `_track_list(val)` helpers.
- `detect_changes()` returns dicts with `prev_tracks` (list for revert) and `old_crate_path` (for rename revert).
- `_ChangeReviewDialog` uses `prev_tracks` to restore crate files on revert.

### Dashboard layout rule:

`_dashboard_layout` uses `addStretch()` at the end — do NOT add `setAlignment(AlignTop)` to it. The stretch absorbs extra space. Adding AlignTop conflicts with addStretch and causes gaps at large window sizes. Section widgets must use `setMinimumHeight`, not `setFixedHeight`, so they don't over-constrain the layout.

---

## Library Browser — Toolbar

`src/gui/library_browser.py`, `_build_toolbar()`. Left to right: search box (`_search`, "Search artist, title, album…"), **Clear Filters** (immediately next to the search box, not right-aligned), a stretch, then **Classify Library** pinned to the far right. Toolbar vertical padding is 16px top/bottom, matching the Crates toolbar.

There is no format/file-type dropdown and no "Add Tracks to Library" button — both were removed. The dropdown (`_format_cb`) was cut because native-macOS Qt style ignores the QSS box model for `QComboBox` (wrong rendered height regardless of `setFixedHeight`, plus its own native arrow instead of the QSS-defined one) — rather than keep working around a native-widget quirk for one dropdown, it was removed outright. "Add Tracks to Library" (a file-picker dialog + background scanner worker, `_AddTracksPickerDialog`/`_AddTracksWorker` in `main_window.py`) was removed because it was redundant: `_ScanWorker` already does a full folder walk on every library load, so files dropped straight into the library folder are picked up automatically next time it's opened — exactly the assumption already baked into the Organize tab's "Open Library Folder" button, which is the surviving, simpler pattern for adding tracks.

---

## Crate Manager — Current Architecture

### Toolbar (`_build_toolbar()`)

A single shared row above the crate/track splitter — not per-panel search boxes — containing, left to right:
- **Crate search** (`_crate_search`) — inside `crate_col`, a `QWidget` whose `setFixedWidth()` is kept in sync with the splitter's left-pane width (see "Splitter/toolbar sync" below). No per-widget stylesheet override; inherits the same global bordered/rounded `QLineEdit` style used everywhere else in the app.
- **Vertical divider** — a 1px `QFrame`, continuing the crate tree's `border-right` line up through the toolbar to the top of the view. Must stay pixel-aligned with the splitter handle.
- **Track search** (`_track_search`) — same left clearance (12px) as the crate search box has from the row's left edge.
- **＋ New Crate** (orange, `_on_new_crate()`) and **✦ Smart Crate** (teal, `_on_new_smart_crate()`, Pro stub), right-aligned, with a 16px gap between them (double the row's normal 8px inter-item spacing — deliberately wider to separate these two from the search boxes).

All controls are 36px tall. Toolbar vertical padding is 16px top/bottom (`row.setContentsMargins(0, 0, 12, 0)` on the outer row; each "column" sub-widget supplies its own 16px top/bottom margin internally so the divider itself can run full-bleed edge-to-edge).

**Splitter/toolbar sync** — `crate_col`'s width must track `self._splitter.sizes()[0]` live, or the divider drifts out of alignment with the actual crate/track panel boundary below it. Wired via `self._splitter.splitterMoved.connect(self._on_splitter_moved)`. Two failure modes discovered the hard way, both now fixed:
1. `QSplitter.setSizes([280, 900])` before first show is only a *request* — the splitter can settle on a different actual pixel width once laid out. A naive `QTimer.singleShot(0, ...)` right after construction fires too early, because `CrateManagerView` is built while still hidden inside its own internal `self._stack` (empty-state page 0 vs. main content page 1) *and* inside the main window's outer tab stack — at that point `splitter.sizes()` doesn't yet reflect final geometry.
2. The real "first visible" moment for the toolbar is inside `load()`, right after `self._stack.setCurrentIndex(1)` — *not* the outer view's `showEvent()`, which can fire earlier while the internal stack is still on the empty-state page. The sync call lives in both places now: deferred one tick (`QTimer.singleShot(0, self._on_splitter_moved)`) after `setCurrentIndex(1)` in `load()` (the real fix), and again in `showEvent()` as a safety net for revisits without a fresh `load()` call.

Separately: `crate_col`/`track_col` are plain `QWidget`s with an explicit `background: #252525;` stylesheet (needed — once the app has a global stylesheet, un-styled `QWidget`s default to painting solid black). This background rule does not cascade into child `QLineEdit`s and does not by itself affect `crate_col`'s fixed width; the width bug was purely the splitter-sync timing issue above, not a stylesheet/geometry interaction.

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

- **State 0: Landing Screen** — always shown on tab visit. Shows a history list of up to 3 recent reorganizations (`_history_layout`). Each history row shows date, file count, and either "Rolled back on [date]" or a red **Rollback** button. `_refresh_gate_screen()` is called on every `load()` and every `_on_back_to_dashboard()`. `load()` never auto-transitions to planning — user clicks "Plan Reorganization…".
- **State 1: Planning Screen** — `_PlanWorker` thread builds the plan.
- **State 2: Preview Screen** — animated stat cards + operations table.
- **State 3: Executing Screen** — copy-verify-delete progress.
- **State 4: Done Screen** — success or rollback-in-progress state. Has `self._done_back_btn` (re-enabled after rollback finishes) and `self._rollback_btn`. The detail line now shows crate path update status: "N crate(s) updated" on success, or "Crate paths not updated — use Repair Crate Paths in Settings" if `paths_rewritten == 0`.

### Organize gate / warning behavior

Organize shows a warning dialog when unclassified tracks are detected during plan building:
- Title: "Unclassified Tracks Detected"
- Body: "X tracks have no genre assignment and will be moved to an Unclassified folder in your Media directory."
- "Go Back to Library" (red) — navigates to Library
- "Proceed" (teal) — continues reorganization

Unclassified tracks go to `Media/Unclassified/` during reorganization. This is a valid destination, not an error state.

`_count_unclassified_tracks()` applies `library_edits.json` overrides via `session.apply_library_edits()` before counting — manual edits are factored in.

### Operations table action labels:

| Condition | Label | Color |
|---|---|---|
| Filename changed + folder changed | Move & Rename | `#d98c52` peach |
| Filename changed + folder same | Rename | `#c9a87a` warm amber |
| Metadata only + folder changed | Move & Tag | `#9fa4c7` lavender |
| Metadata only + folder same | Tag Update | `#9fa4c7` lavender |
| Neither | Move Only | `#e89ebb` pink |

### Organize plan cache (`_cached_plan`)

`OrganizeView` caches the last-built plan as `self._cached_plan`. When `load()` is called on nav to the Organize tab, if `_cached_plan` is not `None` and its `library_root` matches the current library, the Preview screen is restored directly — no re-plan required. The cache is **cleared** on: execute complete (success or failure), rollback complete, different library loaded. The cache is **preserved** on: Cancel & Go Back to Dashboard, any tab switch. This allows the user to plan once and return to review without waiting.

### Destination filename collision resolution

`build_plan()` runs a post-pass collision resolution step after all operations are constructed: it iterates over `operations` in order, and for any `op.destination_path` that has already been seen, appends a ` (N)` suffix (space + parens + integer starting at 2) to the filename stem before the extension. The loop increments `N` until the path is unique. After renaming, `destination_map` is rebuilt from the updated operations so the conflict detection below it reflects final paths.

**Suffix format**: `{stem} ({N}){ext}` — e.g. `St. Ides Commercial (2).mp4`. Space before paren, integer starting at 2. This matches the Export Crate to Folder spec.

If a collision somehow reaches `execute()` (e.g. a pre-existing file on disk), `execute()` no longer silently skips — it logs the operation to the rollback log with `status='skipped'` and `reason='destination_exists_hash_mismatch'`, saves the log, then continues. The Done screen surfaces any skipped files: *"X file(s) could not be moved — destination already existed. Check the log for details."*

### Signal disconnect safety

In `_start_plan_worker` and `_on_plan_ready`, all `.disconnect()` calls on PyQt6 signals are wrapped in `except (RuntimeError, TypeError): pass`. PyQt6 raises `TypeError` (not just `RuntimeError`) when `.disconnect()` is called on a signal with no active connections. Catching only `RuntimeError` allows `TypeError` to escape silently into the slot chain, blocking the `setCurrentIndex(_STATE_PREVIEW)` call and locking the GUI on the spinner. Both exception types must be caught on every `.disconnect()` call.

### Rollback from history

`_on_rollback_requested(log_path=None)` — accepts an optional `Path`. If a Path is passed (from history row), sets `_rollback_log_path = log_path`, transitions to State 4 in in-progress mode (labels set, rollback btn hidden, back btn disabled). Guard: `isinstance(log_path, Path)` distinguishes real Path from QPushButton's `checked=False` signal arg.

### reorg_completed signal

`OrganizeView.reorg_completed` pyqtSignal — emitted from `_on_back_to_dashboard()` only (not from cancel). Connected in MainWindow to `_on_reorg_completed()` which calls `_dashboard.start_scan(lib)`. This re-scans the library after a reorg so the Crates tab immediately reflects new file paths without requiring a restart.

### Plan persistence (_cached_plan)

`OrganizeView` stores the completed plan as `self._cached_plan` (initialized to `None` in `__init__`). On `load()`, if `_cached_plan is not None` and `cached_plan.library_root == current_library_path`, the Preview screen is restored directly from the cached plan — no re-planning required. Cache is cleared on: execute complete, execute error, rollback complete, library change. Cache is NOT cleared on: cancel, tab switch, or any other navigation.

---

## File Organizer — Current Architecture

`src/core/file_organizer.py`

### Serato running guard

`src/utils/serato_guard.py` — `is_serato_running() -> bool`. Uses `pgrep`/`tasklist`; never raises (returns False on failure). Called from `OrganizeView._warn_serato_running()` before both execute and rollback. Shows a branded dark modal (`#1a1a1a` bg, `#f1e3c8` text, red dismiss) and blocks the operation if Serato is detected. (commit ac301c3)

### Transaction integrity hardening (commit ac301c3)

- **Incremental rollback log saves**: `execute()` saves the log to disk before any file operations begin, after every successful `_execute_move()`, and in a `try/finally` that covers the crate-rewrite and `_sync_metadata_files()` tail. A crash mid-reorg always has a recoverable log.
- **Log-before-delete (`destination_written` status)**: `_execute_move()` logs the operation with `status='destination_written'` immediately after `tmp_dest.replace(destination)` — before `source_path.unlink()`. Rollback knows the destination file exists and removes it if the process was killed between those two steps.
- **Duplicate consolidation rollback uses copy**: consolidated duplicates logged with `'duplicate': True`. Rollback uses `shutil.copy2` (not `shutil.move`) so the surviving destination file stays intact.
- **Atomic JSON writes**: `_write_json_atomic(path, data)` module-level helper writes to `.tmp` then renames. Used by `_sync_metadata_files()` for both `classification_session.json` and `library_edits.json`.
- **Genre folder sanitization**: `_build_destination()` passes `genre_folder` through `sanitize_path_component()` after slash-to-colon replacement.
- **Windows MAX_PATH warning**: on `win32`, `build_plan()` sets `FileMoveOp.path_too_long = True` for destinations > 240 chars. Operations table appends `⚠ Path` to action label. `_on_execute()` shows confirmation dialog before starting worker if any warnings exist.
- **PathRewriter atomic set**: `rewrite()` snapshots each crate's bytes before modification. On any exception mid-loop, all already-written crates are restored from snapshots — Serato never sees a partially-applied rewrite.

### build_plan() scope (commit a1891e6)

`build_plan()` considers **every file in the library** as a plan candidate — not just files with session edits. Source of truth is a full library scan compared against the target Genre/Artist/Track structure. State filter was removed — all entries where `final_genre or proposed_genre` is a real genre (not empty/`'Unclassified'`/`'Untagged'`) are included. Files already in the correct structure are excluded as no-ops. Unclassified tracks are allowed to proceed and are mapped to the Media/Unclassified/ folder destination.

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

#### Subdirectory stems — implemented (commit 4bad7b9), flat destination fixed (commit 056883e)

`_find_stems_files()` (new, replaces singular `_find_stems_file()` for active moves) performs a recursive search from the audio file's parent directory. Returns `list[tuple[Path, Path]]` — absolute path + relative path from the audio file's parent. Stems destination is always **flat alongside the parent audio file**: `stems_dest = destination_parent / stems_source.name` — no subdirectory reconstruction at destination. `RollbackLog.log_move()` stores stems moves under a `stems` key — rollback reverses audio file first, then stems to their original relative position (which may include a subdirectory pre-reorg). Old-format rollback log entries fall back to same-directory search. Missing stems at rollback time log a warning and don't fail. Windows MAX_PATH check applied to stems destination paths. Singular `_find_stems_file()` retained unchanged — still used by legacy rollback fallback.

**Stems contract (locked):**
- Stems always land **flat** in the same directory as their parent audio file — no subdirectory at destination, ever
- Stems travel with their parent file wherever it goes — if the parent moves, the stem moves with it
- Stems are **never displayed** anywhere in CrateSort — Library, Crates, Classification, Organize operations table. Invisible to the user. Wrong file extension means the audio scanner never picks them up.
- The recursive search logic in `_find_stems_files()` is correct — only the destination calculation was changed

### Artist sort-form heuristic (`_looks_like_sort_form` in `classifier_view.py`)

`_looks_like_sort_form(artist)` determines whether a comma in an artist name is a "Last, First" sort separator (keep as-is) or a collaboration separator (split to primary artist).

**Current allowlist logic:**
1. If the part after the comma contains a space → `False` (collaboration, e.g. "2Pac, Thug Life")
2. If the part after the comma is in `_SORT_FORM_PARTICLES = {'the', 'a', 'an', 'jr', 'sr', 'jr.', 'sr.', 'ii', 'iii', 'iv'}` → `True` (sort-form, e.g. "Doors, The")
3. Otherwise → `False` (single-word collaboration suffix, e.g. "2Pac, Outlaws")

**This is a tight allowlist**, not a heuristic. Any single-word suffix not in the list is treated as a collaboration. Extend `_SORT_FORM_PARTICLES` only when a specific sort-form pattern is confirmed to exist in the library.

### Artist folder placement for consolidation variants

In `_build_destination()`, when an artist consolidation merge proposal has `use_subfolders=True` and `artist != winner`:
- **Correct**: variant is placed as a **sibling** under the genre folder — `Media/<genre>/<variant_folder>/`
- **Wrong (old bug, now fixed)**: variant was nested inside the winner's folder — `Media/<genre>/<winner_folder>/<variant_folder>/`

The winner folder is NOT part of the path for variants. Both winner and variant land directly under the genre folder as siblings.

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

### Destination collision handling (build_plan)

`build_plan()` runs a collision detection pass after all operations are built. Any two operations sharing the same destination path are resolved by appending ` (2)`, ` (3)` etc. to the filename stem of the later operation. The pass iterates until all destination paths in the plan are unique. This pass runs inside `build_plan()` before the plan is returned — never during execute.

### Silent skip prohibition

`execute()` must never silently skip a file. If `op.destination_path.exists()` is True and SHA-256 hashes differ, the operation is logged to the rollback log with `reason='destination_exists_hash_mismatch'` and a skipped counter is incremented. The Done screen surfaces the skipped count as a non-blocking warning if greater than zero.

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

### Root directory structure (locked)

Whatever location is designated as the library root — external drive, thumb drive, internal Music directory — contains exactly three sibling folders:

```
[Library Root]/
  Media/         ← all audio and video files, Genre/Artist/Track hierarchy
  _Serato_/      ← Serato's crate and database files (must exist — wizard confirms before proceeding)
  _CrateSort/    ← CrateSort internal data, logs, checkpoints (auto-created if absent)
```

`Media/`, `_Serato_/`, and `_CrateSort/` are always siblings. Nothing is nested inside another. The root is fully portable — the entire DJ library travels as one self-contained unit.

---

## Serato integration rules

- **Serato's edits always win** on startup sync. CrateSort absorbs changes, never overwrites.
- **Serato custom ID3 frames** (cue points, beat grids, loops, color tags, markers) are NEVER modified under any circumstances.
- **Crate file order** is only ever changed by explicit user drag reorder actions.
- **CrateSort owns crate structure.** Crate order, hierarchy, names — all controlled by CrateSort.
- **The `_Serato_` folder must live on the same drive as the media files.**
- **CrateSort never auto-creates the `_Serato_/` folder structure.**

### Session-scoped writes (locked rule)

CrateSort writes exclusively to the `_Serato_` folder found within the designated library root for the current session. It never reaches outside that root. It never touches any `_Serato_` folder it was not explicitly pointed at. This makes the app safe for use on a friend's drive — plug in any drive, load it as the session root, do the work, eject. The host machine's own Serato library is never touched.

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
- `AddTracksCommand` has an optional `stay_on_crate: Optional[str]` parameter. When set, `execute()` calls `_refresh(select=stay_on_crate)` instead of `_refresh(select=crate_path)` — the view stays on the source crate, not the target. `_add_tracks_to_crate()` (the drag-drop handler) passes `stay_on_crate=self._current_crate_path` so the user stays in the crate they were viewing while dragging.
- `_add_tracks_to_crate()` in `crate_manager.py` now routes through `AddTracksCommand` when `_undo_manager` is present — drag-drop track additions are fully undoable.
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
- **Classification tab is retired** — `ClassifierView` renamed to `_ClassifierViewLegacy`. Do not restore it as a nav destination. Do not import it in `main_window.py`.
- **`classification_accepted.flag`** — written only by Accept Reclassifications. Never written by individual genre edits. Never deleted by CrateSort automatically.
- **`isVisible()` guard on auto-classify** — `load()` only calls `_on_classify_clicked(auto_classify=True)` when `self.isVisible()` is True. This prevents the `_AnalyzeLibraryModal` from firing during background scans while the user is on the Dashboard.
- **`_AnalyzeLibraryModal` first-run path** — only shown when `classification_session.json` does NOT yet exist. When the session file exists, auto-classify enters classify mode directly with no modal. Never show the modal for a returning session.
- **`_ModalOverlay` event filter** — `removeFromParent()` must be called before `deleteLater()`. Skipping this leaves a dangling event filter on the main window. In `_CrateSortDialog`, this is handled automatically by `_cleanup_overlay` which is connected to `finished` — never bypass this by calling `hide()`/`deleteLater()` directly on a `_CrateSortDialog` without also calling `close()` first to emit `finished`.
- **Organize `.disconnect()` exception handling** — `_start_plan_worker` and `_on_plan_ready` must catch `(RuntimeError, TypeError)` on every signal `.disconnect()` call. `TypeError` alone is enough to silently kill the rest of the slot and freeze the GUI on the planning spinner.
- **Artist genre drives sidebar bucketing** — track genre tags never determine which sidebar bucket an artist appears in.
- **Five confidence states** — MATCHED, HIGH, MEDIUM, LOW, NONE. Never reduce back to three states.
- **Classify mode columns** — logical indices 12, 13, 14. Only visible during classify mode. Restored/hidden correctly on enter/exit.
- **`resizeColumnsToContents()`** — called after `_rebuild_tree()` and after classify columns are inserted. 60px minimum floor enforced.
- **`WA_StyledBackground` on `_ModalOverlay`** — `_ModalOverlay.__init__` must set `self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)`. Without it, the stylesheet `background-color` rule is silently ignored and the scrim renders transparent. Custom `QWidget` subclasses require this attribute to honor stylesheet backgrounds.
- **`overlays.py` is the single source of truth for all dialog patterns** — never recreate `_ModalOverlay`, `_CrateSortDialog`, `_ov_alert`, or `_ov_confirm` inline in any GUI file. Import from `cratesort.src.gui.overlays`.
- **`write_file_metadata()` never raises** — any call site in `library_browser.py` that does not check the return value is a bug. Always check the bool and handle failure by reverting the UI or showing a count-label warning.
- **`library_edits.json` staging is not replaced by disk writes** — both happen. The JSON staging is the Organize fallback; the disk write delivers immediate free-tier value. They are never mutually exclusive.
- **`_looks_like_sort_form()` uses an explicit allowlist** — it does NOT use a heuristic. Only `{'the', 'a', 'an', 'jr', 'sr', 'jr.', 'sr.', 'ii', 'iii', 'iv'}` trigger sort-form treatment. Any new suffix must be added to the allowlist explicitly.
- **Organize plan cache** — `_cached_plan` in `OrganizeView` is stored alongside `_cached_plan_mtime` (mtime of `library_edits.json` at plan-build time). On `load()`, if the edits file mtime has changed since the plan was built, the cache is invalidated. Also cleared on execute complete/fail, rollback, library change. Never cleared on cancel or tab switch.
- **Collision suffix format** — destination filename collisions in `build_plan()` are resolved with ` (N)` suffix (space before paren, integer ≥ 2). Do not use underscores, hyphens, or other separators.
- **`_looks_like_sort_form()` allowlist** — the sort-form heuristic in `classifier_view.py` uses `_SORT_FORM_PARTICLES = {'the', 'a', 'an', 'jr', 'sr', 'jr.', 'sr.', 'ii', 'iii', 'iv'}`. Only particles in this allowlist trigger sort-form treatment. Single-word collaboration names (e.g. "Outlaws") must never be treated as sort-forms. Do not remove or loosen this allowlist without explicit approval.
- **`_build_destination()` sibling rule** — when `use_subfolders=True` and `artist != winner`, the variant folder must be placed as a sibling under `genre_folder`, never nested inside the winner folder. The winner folder segment must not appear in the variant's destination path.
- **Destination collision handling** — `build_plan()` must detect destination filename conflicts and resolve them with sequential number suffixes (` (2)`, ` (3)`) before returning the plan. Every operation in the returned plan must have a unique destination path. `execute()` must never silently skip a file — any skip must be logged to the rollback log with `reason='destination_exists_hash_mismatch'`.
- **`write_file_metadata()` is the free tier write path** — this public function in `file_organizer.py` is the single entry point for immediate metadata writes to disk. It must never raise — always catch, log, return bool. Failed writes must never appear as successful edits in the UI. `library_edits.json` writes still happen alongside disk writes — they are not mutually exclusive. Style tags remain virtual/deferred and must not be written to disk by this function.
- **Accept Reclassifications refresh** — `_exit_classify_mode_accept()` must call `self.load(self._inventory, self._library_path)` after `_exit_classify_mode_cancel()` to fully rebuild session_genre, edits dict, and the artist tree. Partial rebuilds (_rebuild_tree alone, _load_edits alone) are insufficient because self._session_genre is not updated by those paths.
- **Crates tab async loading** — `_CrateLoadWorker(QThread)` in `crate_manager.py` handles all track data resolution off the main thread. `_track_content_stack` shows the loading overlay (index 1) during load; switches back to table (index 0) on `finished`. Progress bar is always determinate — `progress(done, total, label)` emitted per track. No spinners. Ever. `_start_load_worker()` cancels any running worker before starting a new one.
- **Crate name validation** — `_validate_crate_name(name)` blocks `/`, `\`, `%` in all name-entry paths (New Crate, New Subcrate, Rename). Must be called before any `CrateWriter` call. Returns error string or None.
- **Export Crate to Folder** — `_ExportCrateWorker` in `crate_manager.py` exports recursively, preserving subcrate hierarchy. Subcrate folders are prefixed with `_` (sorts above artist folders). `_count_export_tracks(crate_path)` counts recursively for accurate progress total. Pre-export confirmation dialog shown when crate has children. Filename collisions: `stem_2.ext`, `stem_3.ext`. Album art writes (`_write_album_art`, `_remove_album_art`) use `audio.save()` directly — this is a legitimate exemption from `write_file_metadata()` since they handle binary image data, not text metadata fields.
- **No spinners** — any loading state must use a determinate `QProgressBar` with `setRange(0, N)` + `setValue(done)`. `setRange(0, 0)` (indeterminate) is forbidden. Workers must emit `progress(int, int, str)` per item.
- **Color palette** — border color is `#444444` (never `#555555`). Muted text is `#a89b85` (never `#888`, `#666`, `#aaa`, `#555`, `#333`). All interactive elements must have hover states. These are enforced by Brandy (`/brandy`) and Annie (`/annie`).
- **Agent skills** — Brandy, Dez, Draper, and Annie are live local slash-command agents in `.claude/skills/`. Invoke with `/brandy`, `/dez`, `/draper`, `/annie`. Requires Claude Code restart to pick up after initial creation. AL and Cody are live A2A agents on Arora MCP.
- **Duplicate detection architecture** — `DuplicateDetector` in `duplicate_detector.py` classifies groups as `tier='true_duplicate'` (duration ±1s, bitrate ±32kbps, no variant keywords) or `tier='variant'` (remix/extended keywords, or spread exceeds thresholds). Winner scoring: `(crate_count, play_count, bitrate, meta_completeness, has_comment, has_stems)`. Detection runs synchronously in `DashboardWidget._show_dashboard()` after scan — pure Python, no I/O. `build_crate_count_map(crate_library)` builds the crate presence map. Pass it into `DuplicateDetector().detect(inventory, crate_count_map)`.
- **Duplicate consolidation** — `DuplicateConsolidator` in `duplicate_consolidator.py`. Critical order: `PathRewriter.rewrite()` (reroute all crate references) MUST complete before any loser file is deleted. Never delete first and reroute second. Logs to `RollbackLog` with `duplicate=True` for special rollback handling. SHA256 checksums on each deleted file.
- **Duplicate review flow** — `DuplicateReviewView` at `main_window._content` index 5. Not a nav item. Launched via `_on_duplicates_requested()` from dashboard. `done` signal returns to index 0 (dashboard). Dashboard shows orange `_build_dup_banner()` when `self._dup_groups` is non-empty after scan.
  - Copy rows use **radio buttons** (`QRadioButton` with `radio-checked.svg` / `radio-unchecked.svg` in `assets/icons/`) — never revert to `QCheckBox`.
  - `track_selected = pyqtSignal(str)` emitted on row click → connected to `_update_album_art` in `main_window.py` → sidebar artwork populates.
  - Header "Skip for Now" button is now **"Cancel — Don't Consolidate"**.
  - Tier 2 groups show an orange callout at card bottom: if duration difference > 2s or file size ratio > 1.5x, specific differences are surfaced; otherwise "may be different versions" fallback. Replaces the old cryptic metadata conflict text.
  - Tier 1 groups: metadata conflict note rewritten as plain English ("BPM differs between copies — the winner's value will be kept.").
  - Winner reason line appended with "— also has: comment, genre, BPM, artwork" when winner has exclusive metadata advantages over losers (`_winner_metadata_advantages()`). Em-dash separator throughout, `&&` not needed (no ampersand).
- **The Rinse** — duplicate review must happen before classification. If user classifies before rinsing, they may assign different genres to copies of the same song, creating a metadata conflict on consolidation. Dashboard banner enforces this order by surfacing duplicates immediately after scan.
- **Design with intent** — every feature must leave the library better than it was found. Duplicate detection doesn't just flag — it consolidates, reroutes crates, and preserves the DJ's history (play counts, cue points, comments) in the winner file. Phase C Full (deferred): `database_writer.py` for writing merged Serato metadata back to database V2.

---

## Monetization model (locked June 15 2026)

**The line: Free tier fixes the file. Paid tier moves the file.**

### Free tier — Library & Metadata
- Load library, view all media, run classification
- Correct artist assignments, fix track titles, fix filenames, fix genres, add artwork
- **All edits write directly to the file on disk immediately at the point of edit**
- The file does not move — only its contents and properties change
- This is real, complete value — not a demo or a crippled experience

### Paid Tier 1 — Crate Management
- Full crate manager: create, rename, delete, reorder, drag tracks between crates
- Smart crate builder
- Export Crate to Folder

### Paid Tier 2 — Organize
- Physical file relocation into Genre/Artist/Track folder hierarchy
- Filename normalization at OS level (file moves to its new name and location)
- Serato crate path rewriting after all moves
- Full restructure with rollback

### Architectural rule — metadata writes (critical)
Free tier edits (metadata, filename, genre, artwork) write directly to the file on disk immediately at the point of edit. The file does not move. Organize is a paid feature — its sole job is physical relocation: moving files into the Genre/Artist/Track folder hierarchy and updating all Serato crate paths accordingly.

`library_edits.json` must not gate metadata writes for free tier users. Its role going forward is Organize planning only — it records what physical moves need to happen, not what metadata changes are pending. Any code that defers a metadata write to library_edits.json instead of writing through to the file immediately is incorrect behavior for free tier edits.

### Implication for classify flow
When a free user clicks Accept Reclassifications, genre tags write to files on disk immediately. Real value is delivered without requiring Organize. The navigate-away guard dialog in classify mode should communicate: "You haven't accepted your classifications yet — your genre corrections won't be written to your files until you do."

### License check
Periodic, offline-tolerant. Lapsed subscription drops to free tier — never locks users out of their library or their metadata. The free tier must always function fully regardless of subscription state.


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

## Packaging & Distribution

**Status (July 2026): macOS beta packaging shipped. Unsigned, no notarization.** Windows/Linux not yet built.

**Pipeline**: `packaging/CrateSort.spec` (PyInstaller) builds `dist/CrateSort.app` from `packaging/run_app.py`, an entry point that just calls `cratesort.src.gui.main_window:main`. Bundles `cratesort/assets/` in full. Build from a dedicated venv (`.build-venv/`, gitignored) — never the system Python.

**Two real bugs fixed in `cratesort/pyproject.toml` during first packaging pass** (pre-existing, unrelated to packaging itself, but blocked `pip install -e .` entirely):
- `build-backend = "setuptools.backends.legacy:build"` doesn't exist → must be `"setuptools.build_meta"`.
- `serato-crate>=0.1.0` — PyPI only ever published `0.0.1` → constraint must be `>=0.0.1`.
- `yt-dlp` was used by `yt_import_dialog.py` but missing from `dependencies` entirely (only lived in `requirements.txt`) → added.

**App icon — locked decision**: The mascot's native SVG bounding box is 0.842:1 (taller than wide), never 1:1. macOS (Big Sur onward) automatically synthesizes a light background "card" behind any Dock/Finder icon whose artwork doesn't fill the square canvas — a transparent-background icon that leaves visible margins gets an OS-injected backdrop, which reads as an ugly, uncontrolled gray/white box. **Fix, locked**: bake the mascot onto a solid `#1a1a1a` opaque background (matches the app's own primary dark background color), contain-fit, centered, full canvas, **no crop of the mascot and no distortion of its aspect ratio**. Icon source lives at `cratesort/assets/icons/app/CrateSort.icns`, regenerated via `QSvgRenderer` (PyQt6) rasterizing `cs-logo-mascot-only.svg` at each required size, then `iconutil -c icns`. Never re-attempt a transparent/silhouette-only app icon on macOS — it will not render the way it looks in an image viewer.

**Uninstaller**: `packaging/uninstall.applescript`, compiled via `osacompile -o "Uninstall CrateSort.app" uninstall.applescript` into a real double-clickable `.app` (native dialogs, no Terminal window). Ships inside the DMG alongside `CrateSort.app`. Removes the app bundle (`/Applications` or `~/Applications`) and `~/Library/Preferences/com.jwbc.CrateSort.plist` only. **Never touches `_CrateSort/` folders or any user library data** — those live inside whatever folder the user pointed CrateSort at, not in any OS-standard app-data location. The compiled `.app` itself is a build artifact (gitignored) — only the `.applescript` source is committed.

**DMG**: `hdiutil create` → UDRW → mount → drop `.VolumeIcon.icns` + `SetFile -a C` on the volume for a custom volume icon → convert to UDZO. The DMG file itself also carries a custom Finder icon, attached via `sips -i` (self-icon) → `DeRez -only icns` → `Rez -append` → `SetFile -a C` on the `.dmg` file. Both use the same `CrateSort.icns`.

**Beta distribution caveat**: unsigned, not notarized. Testers must right-click → Open the first time (Gatekeeper "unidentified developer" warning), or run `xattr -cr` on the app.

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

The character is an anthropomorphic vinyl record with arms and legs, wearing headphones, with its face protruding from the center of the record label, sitting in or emerging from an orange milk crate. The character design is consistent across all CrateSuite products. The expression and hand gesture communicate each product's personality.

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

Most DJs carry their media on an external hard drive and rely on their laptop battery. When that battery dies, or the media drive is unexpectedly disconnected, macOS penalizes you with the dreaded "Disk Not Ejected Properly" warning. But the real trauma happens when you boot up Serato again.

Because the drive disconnected mid-session, Serato's database gets its streams crossed:
- Crates are shuffled randomly throughout the crate tree.
- Nested subcrates are completely reorganized or flattened (e.g., expanding `Hip-Hop` -> `Best Of` -> `Tupac` only to find the subcrates scrambled).
- Track paths get silently swapped. If two tracks share a song title (e.g., a Tupac track and a Beatles track with matching or similar titles), Serato's resolver crosses the streams. It will swap the Beatles song into the Tupac crate and vice-versa. 

The files on disk are completely untouched, but the database references are scrambled. No warning, no dialog, no alert. You only find out mid-set when you're rocking a gig, load up Method Man, hit play, and out comes a Dorothy Ashby harp instrumental.

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

## The "Carfax" model — Pre-flight gig verification

CrateSort is designed to be utilized as a routine pre-flight check, not just a one-time library organization chore. While a DJ might use CrateSort to execute physical directory restructures or metadata edits, the recurring loop is safety: **before every gig, you run your library through CrateSort before firing up Serato.**

This positioning establishes the app as a diagnostic scanner for your music library:
- **Zero Unknowns**: The startup scan checks the current state of files and crates against the local `checkpoint.json`. It acts as a history report (like a Carfax) showing exactly what changed, what drifted, and what needs attention.
- **Pre-flight Guarantee**: Running CrateSort before a gig guarantees that you will not load your library in the booth only to find broken file references ("holes") or scrambled subcrates. It verifies the database is fully aligned with what's actually on the drive.
- **Habitual Utility**: This changes CrateSort from a transactional utility (run once and close) to a habitual utility (run before every gig for peace of mind).

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

---

## Locked decisions — June 23 2026

- **`refresh()` must not call `_check_serato_sync()`** — sync check is session-start only (`_show_dashboard()`). Calling it from `refresh()` causes CrateSort's own crate writes to be falsely flagged as external Serato changes mid-session.
- **`_add_tracks_to_crate()` must use `AddTracksCommand`** — drag-drop track additions must go through the undo manager. Direct `writer.add_tracks()` calls in this method bypass the undo stack.
- **`AddTracksCommand.stay_on_crate`** — always pass `stay_on_crate=self._current_crate_path` from `_add_tracks_to_crate`. Omitting it navigates to the target crate on drop, disrupting the user's drag workflow.
- **`_flash_row_text()` must restore captured colors** — captures `item.foreground(c)` before flashing, restores from captured brushes. Never hardcode cream as the restore color — track rows are muted, Unclassified artist rows are red.
- **Rinse screen uses radio buttons** — `QRadioButton` with `radio-checked.svg` / `radio-unchecked.svg` in `assets/icons/`. Orange fill + black center dot for checked state. Never revert to `QCheckBox`.
- **`_can_revert()` for `crate_removed`** — always True regardless of `prev_tracks` content. Empty list recreates an empty crate; that is valid and revertable.
- **Duplicate detection in `refresh()`** — `_run_duplicate_detection()` called from `refresh()` so banners clear immediately when metadata is fixed mid-session.
- **`_count_unclassified_artists()` checks edits** — only counts artists with no `genre` in `self._edits`. Acknowledged-as-Unclassified artists (edits entry present) must not keep the Classify button active.
- **Tier 2 Rinse groups** — orange callout surfaces duration/size divergence. Users encouraged to fix metadata (which removes the flag on next scan) — no permanent dismiss mechanism exists by design.
- **Classify flow — Unclassified acknowledge** — `_exit_classify_mode_accept` writes `genre: 'Unclassified'` to edits for any remaining Unclassified artist with no existing entry. This is what allows the Classify button to disable after accept.
