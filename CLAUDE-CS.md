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
- **Orange button fill**: `#aa6326` (darkened 2026-07-30 — see below)
- **Selected crate / warm brown**: `#573d26`
- **Teal action color**: `#428175`
- **Red / cancel / destructive (non-button)**: `#C75B5B`
- **Red button fill**: `#c35050` (darkened 2026-07-30 — see below)
- **Row separator**: `#383838`
- **Grid lines**: `#383838`
- **Branch connector lines**: `#4a4a4a`

### Color rules (critical)

- **Teal (`#428175`) = action.** Drag indicators, status confirmations, active Undo/Redo buttons, teal flashes on inline edits. White button text already clears WCAG AA (4.54:1) unchanged.
- **Orange (`#D17D34`) = selection / CTA for non-button uses** (selected crate highlight, step numbers, icon fills, accent text/borders). **Button fills use the darkened `#aa6326` instead** — white text on the original brighter orange only hit 3.14:1, failing WCAG AA's 4.5:1 minimum; `#aa6326` clears it (4.64:1). Hover `#925521`, pressed `#7e491c`.
- **Red (`#C75B5B`) = cancel / undo / destructive for non-button uses** (error text, accents). **Button fills use the darkened `#c35050` instead** — same AA-contrast reasoning as orange (white text on `#C75B5B` was 4.17:1, still short of 4.5:1). Hover `#b03c3c`, pressed `#973434`. No exceptions.
- **Never swap teal and orange roles.**
- **All button text is white (`#ffffff`), never cream.** Cream on any of the three fill colors above fails or barely clears AA contrast — cream is reserved for text on dark panel/background surfaces, not button fills. Locked 2026-07-30.
- **Button labels use `&`, never the word "and."** Matches the existing PyQt6 `&&`-escaping convention for literal ampersands.

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

**Scanning-in-progress gate (added July 2026):** `MainWindow._is_scanning_in_progress()` returns `dash._library_path is not None and dash._summary is None` — true from the moment a library is picked until the background scan populates `_summary`. While true, `_apply_nav_state()` disables **every** nav item except Dashboard (index 0), including Settings — this is a distinct condition from the disk-based `_get_app_state()` check (which only looks at whether a `_Serato_` folder exists on disk and cannot tell "already scanned" apart from "scan in flight"). `_apply_nav_state(self._get_app_state())` must be re-invoked immediately after any call to `dashboard.set_library_path()`/`start_scan()` that doesn't go through the dashboard's own `library_path_changed` signal (see `_on_library_changed_from_settings`), or the nav bar will show stale enabled state while a new scan is running.

After reorg or rollback completes, `OrganizeView.reorg_completed` fires → `MainWindow._on_reorg_completed()` → `_dashboard.start_scan(lib)` to rebuild inventory with new file paths.

**Nav order is locked.** Organize stays at the end — it is a destination, not a routine step.

---

## Launch Screen Architecture

The launch screen is a context-aware single screen — no popup dialog. It lives in `DashboardWidget._build_welcome()` as stack index 0.

### First launch (no saved library path), copy updated 2026-08-28:
- Shows `cs-logo-mascot-stacked.svg` logo, tagline
- Heading (14px, weight 600, cream, +1px line leading): "Point CrateSort to your `_Serato_` folder and media."
- Second line (12px, muted `#a89b85`, +3px line leading, +3px bottom margin for button separation): "They must be in the same location for the app to function — this is usually the root of your media drive."
- Button: "Select `_Serato_` Folder & Media Location" (no ellipsis — a longer label here visibly crowded the button)
- Disclaimer (11px, muted, +1px line leading): "⚠ Beta build — back up your library before organizing."
- This wording deliberately implies the ideal folder structure (one folder containing both media and `_Serato_` as siblings) without hard-requiring it — see Nav state rules above for what happens when `_Serato_` isn't found at the picked location (only Crates gets gated, not the whole app). Multi-location selection (separate `_Serato_` + media-drive paths) was considered and **declined** 2026-08-28 — sell the single-folder benefit in copy instead.

**Launch-card layout hardening (2026-08-28):** the welcome column lives in a `QScrollArea` (`setWidgetResizable(True)`, no frame, h-scrollbar off) so a short window scrolls instead of crushing/overlapping the card copy. The fixed-size logo (`QSvgWidget`, 240×254) is scaled down toward half size by `_fit_welcome_logo()` on every `resizeEvent` when vertical space runs out — guarded by `_logo_anim_active` so it doesn't fight the grow-in / scan-exit animations. Card copy uses the local `_leaded(text, px, color, *, bold, extra)` helper: QLabel/QSS has no line-height, so each label is rich text with an explicit fixed `line-height: (QFontMetrics.lineSpacing() + extra)px`, and **`font-size` stays in the stylesheet string** — a bare `setFont()` is overridden by QSS once `setStyleSheet()` is called (this silently inflated the disclaimer once). Text never clips: `_fit_welcome_text()` floors every wrapped label's `minimumHeight` to its real `heightForWidth()` on show and on resize, because the height-for-width chain from the scroll area down is unreliable. The card is centred by a stretch `QHBoxLayout` row, **not** `addWidget(card, alignment=…)` — the alignment flag severs height-for-width and the labels clip.

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
- The dedicated full-page "Scanning library…" screen (former stack index 1, `_build_scanning()`) has been **removed entirely** (July 2026). `DashboardWidget._stack` is now only 2 states: `0 = welcome`, `1 = dashboard` (shown both while a scan is pending and once it's ready — see Dashboard Architecture below).

### Nav state rules

**Three effective states:**

**No library loaded:**
- Dashboard: Active
- Library: Disabled (visible, reduced opacity, tooltip: "Load a library to get started.")
- Crates: Disabled (same tooltip)
- Organize: Disabled (same tooltip)
- Settings: Active

**Library loaded, scan in progress** (added July 2026 — picking a library no longer blocks the app on a blank scanning screen):
- Dashboard: Active — shows immediately with the YouTube-import and local-conversion cards fully usable, since neither depends on the library scan
- Library, Crates, Organize, **and Settings**: all disabled, tooltip: "Scanning your library — this tab will be available once the scan finishes." (Settings has nothing useful to offer at this point either — see `MainWindow._is_scanning_in_progress()`.)
- The "Manage Library / Manage Crates / Organize Media" cards on the dashboard itself are also grayed out (`_WorkflowCard.set_disabled(True)`) for the same reason, even though the tab click would be a no-op anyway.

**Library loaded, scan complete, `_Serato_` folder found:**
- All nav items: Active
- No classification gate on any nav item
- Organize shows warning dialog if unclassified tracks exist — does NOT hard block

**Library loaded, scan complete, no `_Serato_` folder found (added 2026-07-30):**
- Library and Organize: **Active** — neither has a real dependency on Serato (Library edits write tags directly via mutagen; Organize's `FileOrganizer` already guards every Serato-specific step with `if plan.serato_dir and plan.serato_dir.exists()`)
- Crates: **Disabled**, tooltip "Serato folder not found at this library location." — this is the only tab that actually needs `_Serato_` to do anything (reads/writes crate files). `CrateManagerView.load()` also has its own independent empty-state check for this (`serato_dir.exists()` → empty-state page, "No Serato library found. Go to Settings to load a library that contains a `_Serato_` folder.")
- `MainWindow._apply_nav_state()` implements this as three explicit states (1/2/3) rather than the old `state <= 2` collapse that used to disable Library/Crates/Organize together — see `_get_app_state()` docstring for the exact state numbers.

Stale library path (saved in QSettings but no longer exists on disk): path and `always_load_last` both cleared from QSettings immediately; welcome screen shown in first-launch state (commit 739c97e).

---

## Classification Architecture

**Classification is a mode inside the Library tab, not a separate screen.**

The Library tab is the single unified environment for all track and artist editing. Classification is triggered by a "Classify Library" button in the Library toolbar.

### Classify mode behavior

- "Classify Library" button (teal, `#428175`) lives in the Library toolbar — a manual fallback entry point; classify-mode review now also **auto-opens** on `load()` whenever there's something genuinely new to review (see "Classify Library button" below), so the button itself is rarely the primary way in.
- Clicking it (or the auto-trigger) runs `_ClassifyWorker` in the background if no session exists yet, then enters classify mode
- **Column architecture, corrected 2026-08-06**: only **Proposed Genre** (LC_CLS_PROPOSED, logical index 12) is classify-mode-exclusive — hidden outside active review, populated solely by `_populate_classify_columns()`. **Confidence** (LC_CLS_CONF, index 13) and **Status** (LC_CLS_STATUS, index 14) are both **permanent, always-visible columns**, populated solely by `_make_top_level_item()`/`_rebuild_tree()`, in and out of classify mode alike, with static header labels that are never re-labeled at runtime. This replaces an earlier design where LC_CLS_CONF was dual-purpose (showed "Confidence" during review, relabeled to "Status" outside it) — that broke the moment settled rows started keeping their persistent Status visible *during* active review too (a Status-type value like "✎ Edited" would render under a header literally reading "Confidence"). See "Confidence column" / "Status column" below for what each actually shows.
- These columns are visually repositioned adjacent to the Genre column via `moveSection` on entering classify mode
- **`_enter_classify_mode()` re-entrancy guard (fixed 2026-08-11):** `load()` calls `_enter_classify_mode()` on *every* visit to Library while anything's unclassified — not just the first time. The header-state snapshot (`self._pre_classify_header_state = header().saveState()`, taken so exit can restore the user's real column order) and the `moveSection` reorder now only run on genuine first entry (`already_active = self._classify_mode`, checked before setting `self._classify_mode = True`); re-triggers while already active are a no-op for header state. Before this fix, any re-trigger (e.g. a new unclassified track appearing from a Serato sync) would re-snapshot the *already-classify-reordered* layout as the new "pre-classify" baseline, silently discarding the user's actual manual column order (e.g. a dragged File Path column) the next time they exited classify mode — looked exactly like a random, unexplained column-order bug that "fixed itself" once classification was fully accepted (which stopped the repeated re-trigger).
- A classify mode banner appears below the toolbar: teal background `#1a3530`, left border `3px solid #428175`, padding 12px, ⚡ icon, 12px text
- "Accept Reclassifications" button (teal) saves all proposals to `library_edits.json` (writing both the artist-level edit AND, since 2026-08-06, a per-track edit for every track successfully written to disk — see Free Tier Write-Through below) and exits classify mode
- "Cancel" button exits classify mode without saving — Confidence/Status are untouched by cancel (they were never touched by classify-mode painting in the first place, so there's nothing stale to revert)

### Auto-classify — first load, and any later load with something new to review (corrected 2026-08-06)

When `load()` runs and **either** `_is_classification_complete()` is `False` (nothing accepted yet — first-ever load) **or** `_count_unclassified_artists() > 0` (see below — a genuinely new proposal exists for a previously-acknowledged-Unclassified artist), **and** `self.isVisible()` is `True`, `_on_classify_clicked(auto_classify=True)` is called automatically. The `isVisible()` guard prevents the modal from firing during background scans while the user is on the Dashboard — it only triggers when the user has explicitly navigated to Library.

**Why the `_count_unclassified_artists() > 0` clause was added**: originally this only fired once, ever, per library (gated purely on the accepted flag) — after the first Accept, the review banner never auto-opened again, only the manual toolbar button could re-open it. That was a deliberate design decision at the time, on the premise that nothing could change the classifier's own read of a track without a manual genre override (which never writes to the file). Style Tags (see below) broke that premise — a user can add a Style Tag with zero genre override and get a genuinely different classifier proposal on the next launch, with no way to see it without this clause. **This must stay a zero-click surface** — Jace's explicit standing requirement across several correction rounds — do not reintroduce a design where the user has to notice and click a button to see a new proposal exists.

`_on_classify_clicked` takes `checked: bool = False, auto_classify: bool = False`. The manual toolbar button passes `checked` (Qt signal arg); `auto_classify` is always passed as a keyword.

**Auto-classify path (two sub-cases):**

1. **Session already exists** (`classification_session.json` found): loads it, calls `apply_library_edits()`, enters classify mode directly — no modal shown.

2. **No session** (first-run): shows the `_AnalyzeLibraryModal` takeover and runs `_ClassifyWorker` in the background.

**Manual toolbar path** (`auto_classify=False`): same existing behavior — if session exists, enter classify mode directly; otherwise disable the button, run the worker, reconnect to `_on_classify_finished` / `_on_classify_error`.

### Classify mode navigate-away guard dialog (corrected 2026-08-07)

When the user tries to navigate away from Library while in classify mode, `_UnsavedChangesDialog` (`library_browser.py` — **not** `_UnsavedClassifyDialog`, a name that never existed in code) appears, triggered from `main_window.py`'s `_on_nav()` via `has_unsaved_classify_changes()`. That check is just `self._classify_mode` — it fires whenever classify mode is active at all, including the very first auto-triggered review on a fresh library, not only after the user has actually touched anything.
- **Headline**: "Classifications Not Saved"
- **Body**: "You haven't accepted your classifications yet — your genre corrections won't be written to your files until you do. You can always come back and finish later."
- **Primary button (teal)**: "Stay && Finish" (Qt double-ampersand — a single `&` is a mnemonic marker and silently disappears from the rendered label; this exact bug shipped once already, watch for it in any new button text)
- **Secondary button (red)**: "Leave Anyway" — exits classify mode, allows navigation

**"Leave Anyway" does not lose anything.** It only calls `_exit_classify_mode_cancel()`, which clears the transient Proposed Genre column and hides the classify banner — `classification_session.json` was already persisted by the dashboard's classify phase independent of this UI flag, and nothing in `library_edits.json` is touched. The review simply reopens next visit since nothing was Accepted. The body copy above was rewritten 2026-08-07 after it was found to claim "your corrections will be lost" (literally false) and to reference "Classify mode" (internal jargon the user never opted into — this review auto-opens with no click required, see "Auto-classify" above).

This dialog is the only navigate-away guard for classify mode. Do not add additional dialogs or change these labels without explicit approval.

### Classify mode banner copy (locked, updated 2026-07-30)

The classify mode banner reads:
> "Here's your library as we see it: sorted and grouped by artist. Double-click an artist row to reveal associated files. Right-click a file to approve or edit artist association. This step ensures that your files are classified correctly. All folders and filenames echo what is seen here. If you're unsure, mark it Unclassified. You can always come back and change it."

Rendered as rich text with `line-height: 19px` (was 16.5px — increased 2026-07-30, felt too tight). No em dash — Brandy's "no em dashes in UI copy" rule applies; use a colon or restructure instead.

Do not change this copy without explicit approval.

### _AnalyzeLibraryModal (first-run classify UI)

Three classes live in `library_browser.py`, inserted before `LibraryBrowserView`:

**`_AnimatedStatCardWidget(QFrame)`** — stat card with a 16ms QTimer that eases a numeric counter toward `_target_value` using `step = max(1, int(diff * 0.15))` (positive diff) / `min(-1, int(diff * 0.15))` (negative diff). Cards: `#1a1a1a` background, `1px solid #444444` border, 8px radius.

**`_ModalOverlay`** — now lives in `src/gui/overlays.py`. See **Dialog & Overlay Architecture** section below.

**`_AnalyzeLibraryModal(_CrateSortDialog)`** — inherits `_CrateSortDialog` from `overlays.py` (overlay scrim + bounce animation handled by base class). **`setFixedWidth(720)` only — height is NOT fixed** (rebuilt 2026-07-30; the old `setFixedSize(520, 320)` fought the base class's own `adjustSize()`-based sizing and squeezed the stat cards below their minimum height, causing overlapping/clipped text at real-world DPI). Inner `QFrame#modal_container` (`#2F2F2F`, 1px `#444444` border, 12px radius) provides the visual surface. Contains:
- Headline "Analyzing Library…" + subtitle
- Row of **5** `_AnimatedStatCardWidget` cards, in this order (grouped so related numbers read together — file-count story first, then the artist/genre payoff): **Files Analyzed → Files Recognized → Files Unrecognized → Artists Recognized → Genres Recognized**. All five are live and real — the old 3-card version's "Corrections Made" card is gone; it always showed a hardcoded 0 (`# TODO: real-time comparison signal not yet available`) and was removed rather than kept faking data. Card title labels have `setWordWrap(True)` so they're never clipped regardless of DPI-driven dialog padding.
- Footer note (always visible, neutral `#a89b85` styling, no warning icon): "This stage not only helps you find and sort your files, but it will help determine where your files go during the Organize stage." **Sizing, 2026-07-31:** it's a small note, not full-width body text — `setFixedWidth()` to 68% of the dialog's DPI-derived content width (same `pad` formula as `_create_dialog_layout`), centered via `Qt.AlignmentFlag.AlignHCenter` on `layout.addWidget(...)`. Note it's `setFixedWidth`, not `setMaximumWidth` — a word-wrapped `QLabel`'s `sizeHint()` largely ignores a maximum-width ceiling, so a max-width cap alone visibly did nothing at two different values before this was caught; only a fixed width actually constrains the wrap.
- `QStackedWidget` (fixed 45px height, no layout jump):
  - Page 0: 4px `QProgressBar` (`#383838` bg, `#428175` chunk), determinate from first progress tick
  - Page 1: "Review Results" button (180×36px, teal)
- `review_requested = pyqtSignal()` — emitted by the button. **Fixed 2026-07-31:** the button was always `setEnabled(True)` (default) — clicking it during analysis was only prevented incidentally by it sitting on the hidden `QStackedWidget` page, not by an actual disabled state. Now explicitly `setEnabled(False)` on construction, flipped to `True` only in `on_classification_complete()`.

**API:** `update_stats(files_analyzed, files_recognized, files_unrecognized, artists_recognized, genres_recognized)`, `update_percent(percent)`, `on_classification_complete()` (switches stack to page 1).

**Data flow (rewritten 2026-07-30):** `_ClassifyWorker.progress` now emits `(done, total, info)` where `info` is a dict — `{'artist', 'track_count', 'genre', 'recognized'}` — computed per-artist in `_ClassifyWorker.run()` (classifier_view.py) right after that artist's genre vote resolves, not before. `recognized = proposed_genre != 'Unclassified' and overall_conf != 'NONE'`. `library_browser.py`'s `_on_auto_classify_progress` accumulates: `_processed_files_count` (running total), `_recognized_files_count` (only when `recognized`), `_seen_genres` (a set, only when `recognized` — `Unclassified` is never counted as a "genre recognized"). This replaced an older, now-removed pre-compile step (`_auto_artist_tracks_map`/`_auto_dj_tools_count`) that duplicated the worker's own grouping logic just to know track counts per artist — no longer needed since the worker reports `track_count` directly.

**Cleanup — real bug fixed 2026-07-30:** `_cleanup_auto_classify_ui()` used to call `modal.close(); modal.deleteLater()` back to back. `_CrateSortDialog.done()` does **not** synchronously emit `finished` — it starts a 384ms exit animation and only calls the real `super().done()` (which emits `finished` → triggers `_cleanup_overlay()`, the scrim teardown) once that animation completes via `_finish_close`. Calling `deleteLater()` immediately after `close()` destroyed the dialog (and its `_exit_anim`) before the animation could finish, so `finished` never fired and the click-blocking `_ModalOverlay` scrim was left on screen forever. **Fix:** `modal.finished.connect(modal.deleteLater); modal.close()` — deletion now waits for the real close to complete. This pattern (don't `deleteLater()` a `_CrateSortDialog` immediately after `close()`) applies to any future code closing one of these dialogs outside the normal `accept()`/`reject()` button-click path.

### Modal subtitle copy (locked, updated 2026-07-30)

> "If your library is big, this'll take a while. We're scanning all of your media files to see if the metadata is correct. You'll be able to approve, deny, and edit our suggested changes next."

### Overlay rendering requirement

`_ModalOverlay` must have `self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)` set in `__init__` to render its stylesheet background color. Without it the scrim is invisible. This is a known PyQt6 behavior for custom `QWidget` subclasses.

### Classify Library button — hidden, not disabled, when nothing's left (updated August 2026, corrected 2026-08-06)

`_refresh_classify_btn()` is called at the end of every `load()`. It **hides** the Classify Library button (`setVisible`, not `setEnabled`) when `_count_unclassified_artists()` returns 0 — same "hide a dead-end action rather than show it muted" convention used for `_consolidate_btn` on the duplicate-review screen. The button is now mostly a manual fallback — the auto-trigger above (`load()`) opens the same review automatically whenever this count is nonzero, no click required.

**`_count_unclassified_artists()` logic, corrected 2026-08-06** — counts an artist as needing review when:
- it's currently displaying as Unclassified, **AND**
- either it has no `library_edits.json` entry at all (never touched), **or** its entry is itself just the literal `'Unclassified'` acknowledgment (see below) **and** the current classify session (`self._session_genre`) now has a genuinely different, real proposal for it.

A **deliberate genre override** (`Change Genre…`, `Reassign Artist…`, or `✓ Approve` — any real, non-Unclassified value in `library_edits.json`) is always considered handled and never re-counted, regardless of what the classifier proposes later.

**Why this changed**: the original version treated *any* existing `genre` key as "handled," including the literal `{'genre': 'Unclassified'}` acknowledgment write `_exit_classify_mode_accept` makes for anything left unresolved at Accept time. That conflated "the user consciously decided this stays Unclassified" with "the user hasn't decided anything, we just silently noted that." Once Style Tags gave the classifier a way to produce a genuinely new, better proposal on a later launch, that conflation meant the artist could never resurface — not in this count, not in the Accept-time write logic, not in the classify-mode repaint logic (three separate call sites all had to be fixed the same way, see `[[project_recent_fixes]]` memory for the full incident writeup). **The fix pattern, apply everywhere this distinction matters**: `existing_genre in {'', '—', 'Unclassified', 'Untagged'}` is an acknowledgment, not a decision — only a real, non-Unclassified `existing_genre` is a protected deliberate choice.

**A "Reclassify Library" active button (replacing the muted state) was built, tested, and then explicitly reverted in an earlier session — still correctly reverted, but the reasoning below needed a caveat added 2026-08-06.** The idea: once nothing's unclassified, turn the dead button into an active one that forces a fresh classification pass. Rejected after direct discussion because it provided no real value at the time: the dashboard already reruns classification automatically on *every single app launch* (`_start_classification_phase`), and the only hypothetical extra value — catching a manual "Change Genre…" mis-edit — didn't hold up, since "Change Genre…" never writes to the audio file, so the classifier's own read of a track never changed just from a user overriding its genre. **That reasoning is still correct as far as it goes** — but it assumed nothing could ever change the classifier's own proposal without a manual override. Style Tags are exactly that missing case, and the fix wasn't to bring the button back — it was to make the *existing* auto-trigger and Status system correctly re-surface artists when the classifier's own proposal genuinely changes (see above and "Style Tags feed classification" below). Do not re-add a manual Reclassify button; the zero-click auto-surfacing is the correct fix for what that button would have been for.

`_exit_classify_mode_accept` still writes `genre: 'Unclassified'` to the edits dict for any remaining Unclassified artist with no existing entry before saving — this acknowledges them, but per the fix above, that acknowledgment no longer permanently blocks a later real proposal from resurfacing.

### Classification complete definition

Classification is complete when `_CrateSort/classification_accepted.flag` exists on disk. This flag is written ONLY when the user clicks Accept Reclassifications. Individual right-click genre edits do NOT set this flag.

`_is_classification_complete()` checks for this flag file. It does NOT check `library_edits.json` entry counts or `classification_session.json` existence.

### Confidence column — permanent, five-tier while pending, frozen to MATCHED once settled (redesigned 2026-08-07)

Confidence is a **permanent** column (see column architecture above), populated in `_make_artist_item()` (`library_browser.py`). Before an artist is settled it shows the classifier's live raw tier, re-read every classify pass. **Once an artist is settled (Approved or Edited), Confidence always reads MATCHED — the original tier is discarded, not preserved.**

This is a deliberate reversal of the original design, which froze the *original* tier forever as a standing "quality/audit signal" (any Approved row that wasn't MATCHED/HIGH was meant to be a candidate for a second look). That reasoning was scrapped 2026-08-07 after real-world testing showed the actual effect: a fully-reviewed, fully-Approved library kept flashing LOW/NONE/red at the user on every visit, which reads as "this library is still dirty" — the opposite of the intended signal, and especially wrong for a manual Edit/override, where the pre-edit tier (e.g. NONE, for an artist the classifier had zero signal on) has no bearing on a human's deliberate decision. Jace's call: **only a genuinely undecided (Pending) artist should ever show its original tier.** A future "reset classification" feature may reintroduce a way to see the original tier again on demand — not built yet.

| Tier | Meaning | Color |
|---|---|---|
| MATCHED | Existing ID3 tag matches taxonomy exactly, **or** the artist has been Approved/Edited (frozen, regardless of original tier) | `#f1e3c8` (cream) |
| HIGH | Genre tag resolved via style map, or a user Style Tag resolved via style map — **pending only** | `#428175` (teal) |
| MEDIUM | Style-token analysis (comment/genre/Style Tag fields) — **pending only** | `#9fa4c7` (lavender) |
| LOW | Limited signal, user should review — **pending only** | `#D17D34` (orange) |
| NONE | No usable data, user must decide — **pending only** | `#C75B5B` (red) |

**Implementation**: `_apply_library_genre()` and `_exit_classify_mode_accept()` both write `'confidence': 'MATCHED'` into the artist's `library_edits.json` entry at the same moment they write `'genre'` — this is the freeze. `_frozen_confidence(artist)` reads it back; `_make_artist_item()` prefers it over a fresh `_classify_lookup()` read whenever present. `_derive_persistent_status()` deliberately does **not** use `_frozen_confidence()` — it needs the classifier's live natural confidence to detect the one case Accept never writes an edit for (raw tag already valid); reusing the frozen value there would collapse Edited into Approved for every settled artist, since a frozen MATCHED would short-circuit before the genre-comparison logic runs. **Backfill/migration**: `_make_artist_item()` also freezes on the fly for any settled artist whose stored `confidence` is missing *or* isn't `'MATCHED'` (`frozen != 'MATCHED'`, not `not frozen`) — the latter check exists because an earlier, short-lived build of this feature froze the *original* tier instead of MATCHED, and that stale data needs upgrading too, not just artists with no frozen value at all. `_rebuild_tree()` batches these into one `_save_edits()` call rather than one per artist.

MATCHED entries are not written to `library_edits.json` on Accept — their existing tag is their classification, so there's nothing to accept. Both `_count_unclassified_artists()` and `_populate_classify_columns()` account for this explicitly (see their respective sections) — a MATCHED artist never accumulates a real edits entry, so any "is this settled" check that only looks for an edits entry must also special-case `confidence == 'MATCHED'`.

### Status column — permanent, four-state, ground truth is `library_edits.json` only (corrected 2026-08-06)

Status is a **permanent** column, populated solely by `_derive_persistent_status()` (`library_browser.py`), called from `_make_top_level_item()`/`_rebuild_tree()` — never from classify-mode's own painting.

| State | Meaning | Color |
|---|---|---|
| ◔ Pending | No explicit accepted-genre edit exists yet for this artist (and it isn't MATCHED) | `#a89b85` (muted) |
| ✓ Approved | MATCHED (always), or an explicit `library_edits.json` genre exists and equals the classifier's current proposal | `#6B9E78` (green) |
| ✎ Edited | An explicit `library_edits.json` genre exists and differs from the classifier's current proposal (deliberate override, e.g. Change Genre) | `#D4A04A` (warm gold — moved off `#428175` teal 2026-08-06, see below) |
| △ Unclassified | An explicit `library_edits.json` genre exists and is itself in the Unclassified set (the Accept-time acknowledgment write) | `#C75B5B` (red) |

**Critical, repeatedly-relearned lesson — the ground truth is `library_edits.json`, never the displayed genre.** `_rebuild_tree()` pre-fills an artist's *displayed* genre (`LC_GENRE`, and the `current_genre` value derived from it) from the classifier's own raw proposal (`_classify_lookup`) for anything not yet accepted — this is a deliberate "preview" behavior, not a bug. But it means comparing the displayed genre against the classifier's proposal (`current_genre == proposed_genre`) is **trivially true before any real decision has ever been made**, because both sides trace back to the same source. This exact mistake was made and had to be un-made **three separate times** in one session (`_count_unclassified_artists()`, `_exit_classify_mode_accept()`'s write-trigger condition, and `_derive_persistent_status()` itself) before landing on the correct rule: any "is this settled / was this genuinely accepted" check must read `self._edits.get(f'__artist__{artist}', {}).get('genre')` directly — never compare two genre strings that can both be pre-fill artifacts. Do not reintroduce a `current_genre == proposed_genre` (or equivalent) check anywhere in this file without first asking whether `current_genre` could be an unaccepted pre-fill.

**Edited color note**: was originally `#428175` (the same locked Teal used for Confidence-HIGH and the app's general "action" color everywhere else) — collided visually and semantically with two other meanings on the same screen. Moved to `#D4A04A` (theme.py's existing `warning`/gold token) 2026-08-06, confirmed zero other live collisions in the Library screen at the time.

### Style Tags feed classification (added 2026-08-06)

Right-click → Edit Style Tags (on a track or an artist row) stages a comma-separated tag list in `library_edits.json` only (`_apply_library_tags`) — **never written to the actual file**, `write_file_metadata` has no `tags` field support (see Write-Through table below). These tags now feed back into classification as a real signal, closing a gap where they were purely cosmetic before:

- `GenreClassifier.classify()` (`classifier.py`) gained a new **Tier 2**, inserted between "genre tag is already valid" (Tier 1, unchanged, always wins outright) and "genre tag resolved via style map" (now Tier 3): each user Style Tag is looked up directly in `STYLE_MAP`; a hit resolves at **HIGH** confidence. This can only ever fill a gap left by Tier 1 — it never runs if the file's own tag already resolved, so a Style Tag can never override a concrete existing tag. `STYLE_MAP` already had relevant precedent for exactly this "don't blindly trust a substring" concern before Style Tags existed — e.g. `"funk rock": "Rock"` (not Funk/Soul) — confirmed with Jace this is the intended non-absolute semantics before building.
- Non-matching Style Tags still aren't wasted — they're appended to the candidate-text pool for Tier 4's (renumbered) token-vote analysis (MEDIUM confidence), alongside comment/genre fields.
- `_ClassifyWorker.run()` (`classifier_view.py`) loads `library_edits.json` once per classify pass and merges both track-level and artist-level (`__artist__{name}`) tags into a `style_tags_by_path` dict, passed through `GenreClassifier.classify_all(tracks, style_tags_by_path=...)`.
- Since classification already reruns automatically on every launch, a Style Tag added in one session resolves on the *next* launch's classify pass — surfaced automatically via the zero-click auto-trigger above, no manual reclassify needed.

### Tier ordering and DJ Tools bucketing — two real bugs fixed 2026-08-07

**Tier 1 (exact tag match) now runs before the short-clip/purpose-folder pre-check in `classifier.py`.** It used to run *after* — a file under 30s sitting in a folder matching `_SHORT_SPECIALTY_FOLDERS` (`drops`, `__drops`, `artists`, `fx`, etc.) was forced to `Specialty`/HIGH unconditionally, even when its own tag was already an exact, valid parent genre that Tier 1 would have matched at MATCHED. Confirmed live: two DJ-drop files already tagged exactly `Specialty` were permanently capped at HIGH no matter what write-through did to the tag, because the pre-check never let Tier 1 run at all. Rule going forward: an exact tag match always wins outright, checked before any duration/folder heuristic.

**Video files in purpose folders now require `no_artist` before bucketing into DJ Tools ("Fix 7", `classifier_view.py` `_ClassifyWorker.run()`).** The video branch checked `rec.is_video` + path-matches-`_VIDEO_PURPOSE` (`commercials`, `_commercials`, `clips`, `films`, `visuals`, etc.) with no artist check at all — unlike the very next block (the equivalent audio-side DJ Tools check), which correctly requires `no_artist` first. Any video with a perfectly valid `©ART` tag sitting in e.g. a `_Commercials` folder had that real artist silently discarded and got dumped into the generic "DJ Tools (untagged)" bucket. Confirmed live against two commercial `.mp4` files with clean, complete metadata (real `©ART`, valid `©gen`) that CrateSort's scanner read correctly — the bug was purely in this grouping step, not tag-reading. Fixed by adding the same `no_artist` requirement the audio path already has.

**`_DJ_TOOLS_FOLDER_PATTERNS` (`classifier_view.py`) now includes `'dj tools'`.** Without it, a track correctly bucketed into DJ Tools on first scan (matched a *source*-folder pattern like `generic`/`__drops`) fell out on every scan *after* Organize moved it into its destination `Media/.../DJ Tools (untagged)/` folder — that destination folder name itself never matched any pattern in the set. It would then reclassify as a brand-new "Unknown Artist" and Organize would propose moving it again, an infinite reclassify/reorganize churn for any DJ Tools track once organized. The pattern-match is a plain substring check against the full lowercased path, so `'dj tools'` also matches the literal `DJ_TOOLS_LABEL` destination folder (`'DJ Tools (untagged)'`) without needing an exact-string reference.

### Artist genre fallback chain (in _rebuild_tree)

0. Film & TV carve-out (added 2026-09-04) — a video (`rec.is_video`) whose ancestor folder is "Film & TV"/"Film and TV" is grouped separately by show/movie title, never reaching steps 1-3, and defaults to `Film & TV` unless overridden by step 1.
1. Artist override in `library_edits.json` — key format `f'__artist__{artist}'`
2. Classification session `final_genre` or `proposed_genre` from `_classify_lookup(artist)`
3. Taxonomy-validated ID3 majority vote — only accepts exact matches against the 14 valid parent genres (case-insensitive). Invalid tags ("Pop", "Alternative Rock", "Hip Hop") are rejected.
4. Default to `''` — Unclassified

Raw ID3 tags are only trusted at Step 3 if they match one of the 14 valid parent genres exactly. No other fallback.

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
- "Stay & Finish" (teal) — dismisses dialog, keeps user in Library

### Unclassified genre

Unclassified is a valid, selectable genre in the right-click Change Genre menu. It is a deliberate "flag for later" choice. During Organize, unclassified tracks go to `Media/Unclassified/Artist/Track` — same hierarchy as other genres. Organize shows a warning dialog (not a block) when unclassified tracks exist.

---

## Dialog & Overlay Architecture

All custom dialogs in CrateSort are built on the canonical classes in `src/gui/overlays.py`. **Never recreate these patterns inline.**

### `_ModalOverlay(QWidget)` — `overlays.py`
Full-window child of the main window. Style: `rgba(26, 26, 26, 217)` + `WA_StyledBackground`. Installs an event filter on the parent window; on `Resize`, updates geometry and re-centers the dialog. `mousePressEvent` accepts to block click-through. `removeFromParent()` removes the event filter before deletion. `set_modal(widget)` registers the dialog for centering.

### `_CrateSortDialog(QDialog)` — `overlays.py`
Base class for every CrateSort dialog. In `__init__`:
- Sets `FramelessWindowHint | Tool` (changed 2026-07-31 from `| Dialog`) and `WA_TranslucentBackground`
- Creates `_ModalOverlay` over `parent.window()`, calls `set_modal(self)`, shows overlay
- Installs `self` as an event filter on the parent window, re-raising `self` (and the overlay) on `WindowActivate`/`Show` — belt-and-suspenders on top of the `Tool` flag itself, see below
- Connects `self.finished` → `_cleanup_overlay` (removes both the overlay's event filter and this one, hides, `deleteLater`)

**Stay-on-top fix, 2026-07-31:** dialogs could end up stuck behind the main app window (click away, dialog vanishes behind it). First attempt added `Qt.WindowType.WindowStaysOnTopHint` — wrong fix, that keeps the dialog above *every* window on the desktop system-wide, including other apps. Correct fix: `Qt.WindowType.Tool` instead of `Qt.WindowType.Dialog`. On macOS, Tool windows are floating panels the OS keeps above their *owning app's* other windows natively, and auto-hides them when the app itself loses focus to a different app — exactly "stay above my app, not the whole desktop," enforced by the window server rather than by us reacting to activation events after the fact. See `project_pyqt_gotchas` memory for the full writeup if revisiting this.

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

**Known gap, found 2026-08-07, not yet fixed**: `write_file_metadata()` returns `True` whenever mutagen opens the file and `.save()` doesn't throw — it never checks whether `_write_metadata_tag()`/the per-format `_write_*` helper actually matched a branch and changed anything. For an unsupported extension (anything outside the three format groups above, e.g. `.ogg`), this is a silent no-op reported as success. Confirmed real by testing directly against files, but not the root cause of the bug that prompted the investigation (see next paragraph) — left as a known latent issue.

### Write-through call sites in `library_browser.py`

| Method | Field written | Failure behavior |
|---|---|---|
| `_commit_active_editor` | `title/album/bpm/year/comment` | Reverts cell display; 5s warning in `_count_label`; staging in `library_edits.json` always preserved |
| `_reassign_track` | `artist` | Single warning after all tracks; partial success accepted |
| `_apply_library_genre` (shared by `_change_genre_for_selection`, `_approve_artist`, and undo/redo via `LibraryGenreChangeCommand`) | `genre` (all tracks for artist or track) | Disk-failure count flashed via `_flash_disk_failure`; partial success accepted |
| `_exit_classify_mode_accept` | `genre` (all accepted tracks) | Same; flag file still written |

**Real bug fixed 2026-08-07 — "Change Genre…" silently never wrote to disk.** The artist-row and track-row context menus' "Change Genre…" action both dispatch to `_change_genre_for_selection()`, the single live write path for manual genre overrides. It was calling `_apply_library_genre(edits_map, {})` — a hardcoded empty `disk_map` — so it only ever staged `library_edits.json`, never touched the actual file, even though the UI flashed success and Status showed Edited/Approved. Meanwhile `_change_artist_genre` and `_change_track_genre` (now deleted) had the *correct* disk-write logic but had zero call sites anywhere — dead code that never got wired to the menu that needed it. Fixed by building a real `disk_map` (track path → new genre, covering every track under an artist-row selection or the track itself for a track-row selection) directly inside `_change_genre_for_selection()`, matching the working pattern `_approve_artist` already used, then deleting the two orphaned methods as fully redundant. Caught via direct reproduction against a real test file (`write_file_metadata()` worked correctly in isolation; the menu action just never called it) — another instance of this codebase's known dead-code pattern, see `[[feedback_verify_ui_reachability]]`.

**`_approve_artist` (added 2026-08-06)** — right-click → Approve on an artist row. Applies the classifier's *current proposed genre* (`_classify_lookup`) through the exact same `_apply_library_genre` write path as Change Genre, just sourcing the value from the classifier instead of a dialog. **Was a completely dead menu item before this fix** — the QAction was added to the context menu but the dispatch `if/elif` chain never checked for it, so clicking did nothing. `'⚑ Mark for Review'` was found dead in the same menu at the same time (traced `ArtistEntry.state == 'flagged'` — only ever set/read inside `_ClassifierViewLegacy`, dead code) and removed outright rather than built out, confirmed with Jace.

**In-memory sync rule:** after every successful `write_file_metadata()`, update the corresponding `TrackRecord` field directly (`rec.title = new_val`, `rec.genre = new_val`, etc.). Never trigger a full re-scan.

**`library_edits.json` is not replaced.** Both the disk write and the JSON staging write happen. They are not mutually exclusive. The JSON staging acts as the Organize fallback for any disk-write failures.

**Per-track genre staging, added 2026-08-06 — `_exit_classify_mode_accept` and `_apply_library_genre` both now stage a per-track `library_edits.json['<path>']['genre']` entry for every track that successfully writes to disk, not just the artist-level `__artist__X` entry.** Every other track-level field (title/album/comment/bpm/year) already worked this way; genre was the one exception, and it was a real, user-visible bug: `_make_track_child`'s displayed genre reads `self._edits.get(path, {}).get('genre', self._track_overrides.get(path, rec.genre or '—'))` — track-level edits are checked *first*, ahead of `self._track_overrides` (a one-time snapshot from classify-session-load time that's never refreshed). Without the per-track stage, a successful disk write was real but invisible in the tree until a full relaunch+rescan replaced the stale `_track_overrides` snapshot. Both call sites now build their edits dict and save it *after* the disk-write loop (not before), so the per-track stage lands in the same save as everything else.

---

## Scanner Architecture (reworked 2026-09-01 — process isolation)

`src/core/scanner.py` + `src/core/parallel_tag_reader.py` + `src/core/scan_worker_proc.py`. Full write-up: `[[project-scan-process-isolation]]`.

**Why:** a `mutagen` tag read that wedges in an uninterruptible kernel wait (macOS 26 FSKit exFAT stalling, failing drive) blocks the pure-Python read *and* can't be broken by any in-process mechanism. A `QThread` isn't enough. Only SIGKILL on a separate process recovers.

**`LibraryScanner.scan()` is 3 phases:**
1. `_walk` — collect media file paths only, no file opens. Polls `is_cancelled()`.
2. Split cache hits (built in-process from `scan_cache`) vs files that need a tag read.
3. `ParallelTagReader(workers=3, per_file_timeout=15.0)` reads the rest across worker **processes**. A worker that doesn't return a file within the timeout is `kill()`ed, that file is marked `read_error`, a replacement worker spawns, the scan continues. Fallbacks if `spawn` is unavailable: thread-isolation, then sequential.

- `read_one_file(path, ext) -> dict` is THE single tag-read code path (used in-process and inside workers).
- `LibraryScanner.__init__(..., is_cancelled=None, workers=None, per_file_timeout=None)`. **Cancel now stops a scan mid-flight.**
- **Progress callback signature is `(done: int, total: int, label: str)`**; `total == -1` during discovery. `_ScanWorker.progress` is `pyqtSignal(int, int, str)`.
- `_configure_scan_logging(root)` attaches a `RotatingFileHandler` to the `cratesort` logger → `<library>/_CrateSort/logs/scan.log` (per-directory + per-error lines; the last line names any stall file). `_write_unreadable_report()` → `<library>/_CrateSort/logs/unreadable-files.txt`, removed on a clean scan.
- Unreadable files → `self._unreadable` on the dashboard → persistent amber `_build_unreadable_banner()` → "Show List" opens `_UnreadableFilesDialog` (`src/gui/unreadable_dialog.py`).
- **Packaging:** `multiprocessing.freeze_support()` is the first statement in `packaging/run_app.py` and in `main_window.main()`. `CrateSort.spec` `hiddenimports` lists both new core modules. Under `spawn`, workers re-import `__main__`, so any standalone script that runs a scan MUST have an `if __name__ == "__main__":` guard.
- Diagnostic: `cratesort/tests/diagnose_scan_hang.py` (read-only, prints each path before reading, SIGALRM watchdog) — the tool that found the FSKit stall. `cratesort/tests/run_parallel_reader.py` — happy-path + FIFO-hang watchdog test.

---

## Dashboard Architecture

`src/gui/dashboard.py` — session-aware command center. Stack index 1 in `DashboardWidget` (index 2 no longer exists — see Launch Screen Architecture above).

`_populate_dashboard(scanning: bool = False)` is the single entry point that rebuilds `_dashboard_layout` from scratch (clears all children via `deleteLater()`, then rebuilds). It branches into one of two completely different renders depending on `scanning`:

### Pending render (`scanning=True`) — shown the instant a library is picked

Rendered immediately by `_start_scan_now()`, before the background `_ScanWorker` has produced any data (`self._summary`/`self._inventory` are reset to `None`/`[]` first).

1. **Scanning banner** (`_build_scanning_banner()`, restructured 2026-08-10 per user mockup) — replaces the stat-cards section entirely (no zero-value stat cards — that reads as broken, not "in progress"). A single panel, two-row grid layout (not the old single horizontal row):
   - **Top row**: the pulsing mascot (`cs-logo-mascot-only.svg`, fixed at **84×100** — matches the SVG's real `1063.39×1262.43` viewBox aspect ratio; forcing it to a square visibly squashes the art, since `QSvgWidget` stretches to fill its exact box with no aspect-ratio preservation — `QGraphicsOpacityEffect` + `QPropertyAnimation` looping 0.3→1.0→0.3 opacity, `InOutSine`, 1100ms, `setLoopCount(-1)`, the app's standard "busy but not a spinner" indicator, see Motion system below), sitting in its own fixed-width left column (`LEFT_COL_WIDTH = 132`), beside the 5 stat cards (`cards_row`).
   - **Bottom row** (restructured 2026-09-02): one `QHBoxLayout` with `setContentsMargins(28, 0, 24, 0)` holding — `self._scan_count` (a fixed **360px** `_ElidingLabel`, `elide=ElideRight` so the "N of M" count survives and only the filename tail trims), then **`_ScanActivityBeam`** (stretch=1), then the Cancel button (`self._scan_cancel` → `_on_cancel_scan`). The 28px left inset lands the status text on the *drawn crate* left edge; the 24px trailing inset lands Cancel's right edge on the last stat card's (matching `cards_row`'s trailing `addSpacing(24)`). The status text used to be on its own row below this one, which left dead vertical space. Progress text is one line: `Reading tags — N of M  ·  <file>`.
   - `_ElidingLabel(text, parent, elide=ElideMiddle)` (dashboard.py, above `_ScanWorker`) — elides each line to `contentsRect().width()`; used only for `_scan_count`.
   - Wrapper `QWidget`s used purely for layout are plain widgets and need an explicit `background: transparent` stylesheet, or they render as solid black patches once the app's global stylesheet is active — see PyQt gotcha #3.
   - `_on_cancel_scan` also resets `self._welcome_logo`'s size back to `_LOGO_W`×`_LOGO_H` before flipping the stack back to index 0 — `start_scan()`'s exit animation (`_play_logo_exit`) shrinks that logo to ~0px on the way into a scan, and nothing else restores it, so without this the welcome screen shows an invisible mascot after Cancel.

   **`_ScanActivityBeam(QWidget)`** (dashboard.py, module level, above `DashboardWidget`) — a bounded comet of light that ping-pongs back and forth in a fixed-width track, via a single `QVariantAnimation` (0.0→1.0→0.0 through `setKeyValueAt(0.5, 1.0)`), `InOutSine`, 1800ms loop, `setLoopCount(-1)`. Track is **6px tall inside a 10px-tall widget** (the extra height is padding for the glow to bloom into without clipping — see gotcha #12 below on why the glow radius must be hard-capped against this, not just scaled off it). Comet width is `max(16, track_width * 0.17)`, drawn as a **symmetric** `QLinearGradient` — transparent teal → teal → bright gold peak at the midpoint → teal → transparent teal, same both directions, deliberately no directional "head"/"tail" — plus a small radial glow centered on the peak (`glow_r = min(_TRACK_H*0.9, _WIDGET_H/2 - 1)`, a hard cap so its diameter can never exceed the widget height). The whole comet **fades via `painter.setOpacity()` toward each end of the track** (a parabola in position — 0 at both ends, 1 at center — applied only to the comet+glow, drawn after the track background), so it's brightest crossing the middle and dims approaching either wall. **This is NOT a progress bar and must never be redesigned to look like one** — it never grows, never reaches 100%, always returns to start. That's what keeps it compliant with the locked no-fake-progress rule below: it claims "still alive," never "X% done." Deliberately distinct from the locked progress-bar spec (8px, hard-edged teal fill, determinate) so it can't be mistaken for a real determinate bar. Started via `.start()` right after being added to the bottom row; there is no matching `.stop()` call on scan completion (consistent with the pre-existing mascot animation, which also isn't explicitly stopped — the banner is simply swapped out of view).

   **Do not use an image/PNG asset for this comet.** A full redesign attempt (Aug 2026) replaced the gradient with a designed PNG comet — including off-screen ping-pong masking phases, a 180°-flip for direction changes, and elastic/spring easing — and was **explicitly abandoned and reverted** to the plain gradient above after repeated rendering problems the user couldn't get past (additive-blend color banding, an 8-bit indexed source PNG that couldn't be fixed in code, glow-taller-than-widget clipping, several rounds of animation-timing bugs). See `[[project_pyqt_gotchas]]` #9–12 and `[[project_recent_fixes]]` for the full story before reaching for an image asset here again.
2. **Action Cards**, rendered via `_build_action_cards_section(scanning=True)` — same section as the ready state (see below), except the 3 "Go To" cards are passed `card.set_disabled(True)` (see `_WorkflowCard.set_disabled()`) since they depend on scan data. The YouTube-import and local-conversion cards are **not** disabled — neither needs the library scan to function.
3. No activity feed, no footer — both depend on scan/sync data that isn't ready yet.

### Ready render (`scanning=False`) — shown once the post-scan chain reaches `_after_post_scan_analysis`

**Post-scan chain (2026-09-02, now threaded so no animation ever parks — see `[[project-scan-process-isolation]]` §4c):** `_on_scan_finished` → `self._bg_overlay` (`_BgSteps` QThread runs `_apply_serato_overlay`) → `_after_overlay` → classify (`_classification_is_current()` → skip, else `_ClassifyWorker`) → `_show_dashboard` → `self._bg_post` (`_BgSteps` runs `_check_serato_sync` + `_run_duplicate_detection` + `_detect_stragglers`) → `_after_post_scan_analysis` → `_populate_dashboard(scanning=False)` (widget build only, stays on main thread). The scanning screen (pulsing mascot + comet) stays up the whole ~1.5s. `_BgSteps(parent, [(label, callable), …])` emits `done()`; refs `self._bg_overlay`/`self._bg_post` are `None`-init'd, held on `self`, `wait()`ed in `_on_cancel_scan`. `_timed()` wraps each step → `[timing] <step>: <ms>` in scan.log.

1. **Stat Cards** (`_build_stat_cards_section()`) — four cards: Total Tracks, Total Crates, Unique Artists, Hours of Music. Count-up animation on load. No icon labels — numbers and labels only. `_AnimatedStatCard(target, suffix, label)` — note: no icon parameter.

2. **Action Cards** (`_build_action_cards_section(scanning=False)`) — three groups, separated by dividers (16px clear space each side, matching the divider above this whole section — `vbox.addSpacing(6)` on top of the inner layout's uniform 10px spacing):
   - **Go To** (3 cards):
     - `Manage Library` — navigates to Library (index 1). Primary label in orange `#D17D34`, 16px, weight 500. No step number.
     - `Manage Crates` — navigates to Crates (index 2). Same label treatment.
     - `Organize Media` — navigates to Organize (index 3). Same label treatment.
     - `_WorkflowCard.setMinimumHeight(184)` (was 230 — cut 20% on 2026-08-29 per Jace). Inside the card, `row.addSpacing(18)` sits between the description text column and the 100×100 icon so the copy can't run under the icon and the text container is ~10% narrower.
     - **First-load highlight**: When `_is_classification_complete()` returns False (and the dashboard isn't in the pending/scanning render), the Manage Library card renders with:
       - Border: `2px solid #428175`
       - Background: `#1a2e2b`
       - Icon at full teal opacity
       - Returns to standard appearance once classification is complete.
   - **YouTube import** (2 cards, left-to-right): `YouTube to MP3` (icon `icon-mp3-2.svg`, "Convert URL to audio file · VBR"), `YouTube to MP4` (icon `icon-mp4-2.svg`, "Convert URL to video file · VBR"). Opens `_YTImportDialog(fmt, ...)` — see YouTube Import & Local Conversion Tools below.
   - **Local conversion** (2 cards, left-to-right, directly below the YouTube row so MP3-output cards line up over MP3-output cards and MP4-output over MP4-output): `Audio to MP3` (icon `icon-convert.svg`, "Convert existing audio file · 320kbps") and `Video to MP4` (same icon, "Convert existing video file · H.264"). Opens `_ConvertDialog(mode, ...)`.
   - All `_IconActionCard`s share the Go To cards' gray background / orange headline / muted-icon-lights-up-on-hover treatment (teal is reserved for the Manage Library highlight only). Icons use the same dim `#2a2a2a`-at-rest / `#D17D34`-on-hover SVG recolor technique — **except** each icon is now sized by its own aspect ratio (`_svg_aspect_ratio()`, parses the SVG's `viewBox`), locked to a fixed height with proportional width, never forced into a square — the two newer icon sets (`icon-mp3-2.svg`/`icon-mp4-2.svg` are portrait, `icon-convert.svg` is landscape) would visibly stretch/squish under the old fixed-square sizing. There is no longer a "New Crate"/"New Smart Crate" card group on the dashboard — that functionality lives only in the Crates tab toolbar (see Crate Manager Architecture below).
   - **Organize Media footer**: an extra line below the description — `CrateSort's Organization Logic:` / `Your Directory Selected on Startup > Media > Genre > Artist > Files` — rendered via `_WorkflowCard(footer=...)`, full-card-width (not confined to the text column), 12px font, 16.5px line-height set via rich-text `<div style="line-height:...">` since Qt's QSS `line-height` property is a silent no-op on plain `QLabel` text.

Dashboard has a `refresh()` method called when navigating to index 0 — re-runs duplicate + straggler detection and repopulates dashboard state (always `scanning=False`; `refresh()` no-ops if `_summary is None`). Unlike `_show_dashboard`, `refresh()` still runs those **synchronously on the main thread** — fast now (~0.4s) but a candidate for the `_BgSteps` treatment. **Serato sync check (`_check_serato_sync()`) runs only in `_show_dashboard()` at session start — it is NOT called from `refresh()`.** This prevents CrateSort's own crate writes during a session from being flagged as external Serato changes.

**Classification cache-skip (2026-09-02):** `_start_classification_phase()` calls `_classification_is_current()` — true when `classification_session.json` exists, is newer than `library_edits.json`, and its track-path set exactly equals the current inventory. When true it skips the whole classify phase (worker + the ~7.7 MB session rewrite) and goes straight to `_show_dashboard`. `_ClassifyWorker.run()` also does `self.usleep(200)` every 20 artists so a genuine first-run classify doesn't GIL-freeze its own progress screen.

**Classifier version stamp (2026-09-04):** the cache-skip above compares files, not code — it had no way to know when `classifier.py`'s own logic changed (e.g. adding the Latin genre), so a user with an existing session would silently keep stale results forever, across app updates, with no in-app way to force a refresh. Surfaced when Jace added Latin mid-session and it didn't show up on reopen — same root cause as an earlier "gotta clear the cache" incident, and would have bitten a real user updating from an older build the exact same way. Fixed with `CLASSIFIER_VERSION` (`classifier.py`) — bump it whenever a change would change what genre a track lands in. `ClassificationSession` stamps itself with this on creation (`classifier_version` field, defaults to the current constant), persists it in `save()`/`load()`, and `_classification_is_current()` now also requires `data.get('classifier_version', 0) == CLASSIFIER_VERSION` — a missing field (pre-dates this fix) or an old value both read as stale and force a fresh classify pass automatically, no button, no manual file deletion. A standalone "Reclassify Library" button was considered and deliberately declined (see `settings_view.py`'s already-orphaned `_on_reset_classification()`/`_on_clear_library_edits()`, wired to nothing) — Jace's call: this dev-loop scenario isn't something a real end user hits, and the version stamp already covers the real-user upgrade case automatically.

3. **Recent Activity** (`_build_activity_section()`) — combined feed: crate changes, recently added tracks, and reorganization events (teal dot = reorg/addition, orange dot = rollback/removal). Last 30 days, capped at 10 items.

4. **Footer** (`_build_footer_bar()`) — last session timestamp + Serato sync status. Do not modify.

### Serato sync warning (redesigned 2026-08-11):

When changes are detected on launch, an amber banner appears with a **"Review && Sync"** button (no ellipsis, min-width 170px, `&&` required for literal ampersand in PyQt6). Title: "Serato Crate Changes Detected." Body: "Things have changed since your last session on `MM/DD/YY` at `H:MM AM/PM`. Please review the changes below before your next session:" — single sentence, no leading zero on the hour (`.strftime('%I:%M %p').lstrip('0')`).

`_ChangeReviewDialog` shows each change as a row with a **two-option `QRadioButton` pair** (exclusive `QButtonGroup` per row, first option checked by default) — **not** push buttons, and **not** generic "Keep"/"Undo" labels. The label text is looked up per change-type from `_RADIO_LABELS` and states the concrete resulting outcome for the crate/tracks themselves:

| change type | option 1 (default) | option 2 |
|---|---|---|
| `crate_added` | Keep Crate | Delete Crate |
| `crate_removed` | Leave Removed | Restore Crate |
| `renamed` | Keep New Name | Revert Name |
| `tracks_added` | Keep Tracks | Remove Tracks |
| `tracks_removed` | Leave Removed | Restore Tracks |

**Why not "Approve"/"Remove" or "Keep"/"Undo":** both read as ambiguous or actively misleading next to a *removal*-type change — "Approve"/"Remove" both sound destructive ("does Remove mean remove the crate, or remove the change?"), and generic "Keep"/"Undo" still requires inferring an implicit object ("keep the crate, or keep the removal?"). This was **not just a copy nitpick** — a user genuinely lost a real crate to a misclick under the old "Approve"/"Remove" wording: selecting "Remove" on a `crate_added` row calls `_execute_revert()`, which does `Path(crate_path).unlink()` — an unconfirmed, silent, permanent delete. Any future per-row destructive choice in this app must state the concrete outcome per option, not a generic verb. Row backgrounds/borders do **not** change color based on selection (explicit user feedback — a color-shifting cell read as broken/inconsistent); the radio's own checked/unchecked indicator (`radio-checked.svg`/`radio-unchecked.svg`) is the only state signal.

The bottom button is a **static "Apply && Continue"** (orange) regardless of how many rows are marked for revert — it no longer cycles through "Sync && Proceed" / "Apply && Proceed" / "Accept && Continue" text+color based on `_pending_reverts` count (removed along with `_update_sync_btn_state()` — that 3-way cycle was itself a source of the same "what does this word mean here" confusion). On Cancel: nothing written. `_can_revert()` returns True for both `crate_added` and `crate_removed` — removed crates are always revertable even when `prev_tracks` is empty (empty crate recreated from a `[]` list).

Dialog sizing: `setMinimumWidth(540)` only — no forced minimum height (was `setMinimumSize(540, 480)`, which left a large dead gap below a single-row change list since the row-scroll area had `stretch=1` and was forced to fill the fixed 480px floor). The row-list `QScrollArea` has `setMaximumHeight(300)` (scrolls past ~6 rows) and `setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)` (a horizontal scrollbar was transiently appearing on row-state changes — layout-recompute artifact, not real overflow).

### Checkpoint system (`src/utils/checkpoint.py`):

- Schema: `{crate_path: [track_path, ...]}` — stores full track lists, not just counts.
- Backward compatible: old checkpoints with integer values are handled by `_count(val)` / `_track_list(val)` helpers.
- `detect_changes()` returns dicts with `prev_tracks` (list for revert) and `old_crate_path` (for rename revert).
- `_ChangeReviewDialog` uses `prev_tracks` to restore crate files on revert.

### Dashboard layout rule:

`_dashboard_layout` uses `addStretch()` at the end — do NOT add `setAlignment(AlignTop)` to it. The stretch absorbs extra space. Adding AlignTop conflicts with addStretch and causes gaps at large window sizes. Section widgets must use `setMinimumHeight`, not `setFixedHeight`, so they don't over-constrain the layout.

---

## YouTube Import & Local Conversion Tools (added July 2026)

Four dashboard cards, two dialogs, all built on ffmpeg (bundled, not system-installed — see Packaging below).

### `src/gui/yt_import_dialog.py` — `_YTImportDialog(fmt, library_path, genres, artists, parent)`

Downloads a YouTube URL and converts it to `mp3` (best available audio, via yt-dlp's `FFmpegExtractAudio` postprocessor) or `mp4` (up to 1080p, H.264/AAC, manual ffmpeg re-encode with a `scale=w='min(1920,iw)'...` filter). Actual quality is often lower than those ceilings — see the YouTube client-fallback note below. Has a full metadata form (Artist/Title/Album/Year/Genre with autocomplete) and a MusicBrainz lookup that offers to fill in canonical tags after download. **Artwork picker lives here** (`ARTWORK (OPTIONAL)` section, right after the metadata form, before the destination picker) — a "Choose Image…" button + 48×48 thumbnail preview + Clear button, wired to `embed_artwork()` in `_finish()`. This is the *only* converter with an artwork picker: YouTube downloads never carry embedded art, whereas local WAV/MOV files already have whatever artwork the source file had, carried over automatically (see `_ConvertDialog` below) — **do not add an artwork picker to `_ConvertDialog`**, that was tried and explicitly reverted per user direction.

**YouTube anti-bot / client fallback (2026-08-31):** YouTube gates its normal (`web`/`tv`) player responses behind a **PO token** yt-dlp can't mint — an unauthenticated request hits "Sign in to confirm you're not a bot", a cookie-authenticated one hits "The page needs to be reloaded", and `ios`/`mweb`/`web_safari` return storyboards only. The one client that still yields a stream is `android`, but *only with no cookies attached*. `_YTWorker._download_with_fallback(yt_dlp, tmpdir, base_opts)` branches on the worker's `quality` ('fast' | 'best'), set from the dialog's **QUALITY combo** (`_QUALITY_LABELS` / `_QUALITY_VALUES`, `_ArrowComboBox` above the `YOUTUBE LOGIN` combo, **default index 0 = 'fast'**, not persisted — always opens on Fast). `quality == 'fast'`: a single pass with the `android` client (cookies stripped) — ~360p / ~96 kbps AAC but one request, ~5s, no doomed HD attempts. `quality == 'best'`: three passes — **(1)** site default + browser cookies (best quality when PO enforcement is off); **(2)** `web_embedded` + cookies — the usual way past "this video may be inappropriate for some users" (age-gate), no-op for normal videos; **(3)** `android` fallback. Between passes it emits `progress(0, 'Retrying')`, or `'Retrying at lower quality'` on the last. `android` can't fetch age-restricted content at all under either setting. Both `_run_mp4` and `_run_mp3` build a `base_opts` (format string + `progress_hooks`) and hand it to the helper instead of calling `ydl.download()` directly. The mp4 format string ends `.../best[height<=1080]/best` so a progressive-only fallback still satisfies selection.

*Full-quality fix (bundling a PO-token provider) is tabled — see `docs/future-features.md` → General/UX. yt-dlp nightly does not fix it; 2026.8.19 is the latest stable.*

**Back-to-back imports (2026-08-31):** nothing locks after a successful save. `_finish()` sets `self._save_complete = True`, re-enables the URL field / metadata fields / Import button, hides the progress row, and relabels the secondary button *Done*. To go again the user just pastes a new URL — the first keystroke triggers `_on_url_changed` → `_clear_after_save()` (clears the stale result + metadata + artwork, resets `_save_complete`, relabels *Done* back to *Cancel*); the debounced auto-fetch then repopulates. `_on_import()` also clears `_save_complete` defensively. Done → `_on_cancel` (which just `reject()`s when nothing is running); Escape does the same. The chosen destination folder persists across dialog opens in `QSettings` key `yt_dest_dir` (falls back to `library_path`, then `~/Downloads`; ignores a saved path that no longer exists). Button styles are module constants `_IMPORT_BTN_STYLE` / `_PASSIVE_BTN_STYLE`. (There is deliberately **no** "Import Another" button — an earlier build had one, replaced because locking the URL field behind a button made no sense.)

**`YOUTUBE LOGIN` combo (`_ArrowComboBox`, below `QUALITY`):** *Don't use a login* (default) / Safari / Chrome / Firefox / Edge / Brave / Chromium / `Cookie file…`. This is **not a sign-in flow** — there is none. It reuses the YouTube session from a browser the user is *already* signed into, by reading that browser's cookies; `_YTImportDialog._cookie_opts()` resolves the choice to `{'cookiesfrombrowser': (name,)}` or `{'cookiefile': path}`, passed to both workers' `cookie_opts` ctor arg (used by the metadata fetch and by the 'best'-quality cascade's passes 1–2). It is **not** a reliable unblock on its own — it helps the metadata auto-fill get past the bot wall, and *can* restore full quality on sessions/videos where PO enforcement is off, but the `android` fallback is what actually makes downloads work. The browser choice is **not persisted** — the combo always opens on *Don't use a login*, and `__init__` purges any `yt_cookies_browser` value left by older builds. (Persisting it re-fired a macOS keychain / "access data from other apps" prompt and a cookie read on every metadata fetch, for a control that rarely helps.) A chosen `cookies.txt` is session-only. `_humanize_yt_error()` collapses the bot-check / page-reload / no-format walls into one message ("Set YOUTUBE LOGIN above…") and suggests a later retry; the unreadable-login wall and the age-restriction wall get their own messages. `_on_metadata_failed()` surfaces `Needs a YouTube login to auto-fill` in the URL-row status. Changing the browser re-triggers the metadata fetch. Practical notes: Firefox is the most reliable cookie source; Safari needs the app to hold Full Disk Access; Chrome-on-macOS cookies are often unreadable (App-Bound Encryption) — the `Cookie file…` fallback (browser-extension export) covers those.

### `src/gui/convert_dialog.py` — `_ConvertDialog(mode, parent)`

Batch-capable local file converter, `mode` is `'wav_mp3'` or `'video_mp4'`:
- `wav_mp3`: WAV/AIFF → MP3, 320kbps CBR (libmp3lame). Dialog title "Convert Audio to MP3".
- `video_mp4`: MOV/MKV/AVI/WMV/WEBM/FLV/M4V/MPG/MPEG → MP4, H.264/AAC 192k, CRF 18, `-preset fast`, even-dimension scale filter only (no resolution cap — unlike the YouTube path, this is the user's own master footage, so original resolution is preserved).

Output always saves next to the source file (same folder, same stem, new extension) — never a destination picker. Collision-safe naming via `_unique_output_path()` (`song.mp3` → `song (1).mp3` → …). Originals are **never** modified or deleted.

**Metadata & artwork carryover** (`src/utils/metadata_copy.py`):
- `copy_audio_tags(src, dst)` / `copy_video_tags(src, dst)` — copy every ID3 frame / MP4 atom from source to the freshly-converted file, including embedded artwork, **except** Serato's own GEOB analysis caches ("Serato Analysis", "Serato Markers2", "Serato BeatGrid", etc.) — these encode exact sample positions in the *original* audio, which shift once re-encoded, so carrying them over verbatim would show Serato stale/incorrect cue points until it re-analyzes anyway. This exclusion is deliberate, confirmed with the user — never "fix" it by including them.
- `embed_artwork(dst, fmt, artwork_path)` — used only by `_YTImportDialog` (see above). `fmt` is `'mp3'`/`'mp4'` (not the convert-dialog mode strings).

**Progress**: worker emits real percentages parsed from ffmpeg's `-progress pipe:1` + `-stats_period 0.1` output (increased from ffmpeg's default ~0.5s tick to ~0.1s specifically so short conversions don't feel like a stuck-then-jump — see Motion system below). Duration is read from the *same* ffmpeg process's own stderr banner (merged into stdout, parsed for `Duration: HH:MM:SS`), not a separate probe call — one less subprocess, one less place to fail. **ffmpeg's own log output is decoded with `errors='replace'`, never strict** — real-world files carry non-UTF-8 metadata (camera/encoder strings) that would otherwise crash the read loop mid-conversion while ffmpeg itself keeps running in the background, producing a fully valid output file alongside a false "failed" error. This was a real shipped bug — don't reintroduce strict decoding on this stream.

Failure messages are translated via `friendly_ffmpeg_error()` (`ffmpeg_tools.py`) — recognizes "already exists", "permission denied", "no such file or directory", "no space left on device", "read-only file system" and rewrites them in plain language; falls back to the raw ffmpeg detail for anything unrecognized. Never show a bare exit code to the user.

### ffmpeg subprocess hygiene (applies to both dialogs)

Every ffmpeg `Popen` call must include `stdin=subprocess.DEVNULL` and `-nostdin` — without this, ffmpeg can block forever waiting for stdin input that will never come (a well-known class of "ffmpeg just hangs" bug, especially likely when launched from a terminal that has a real stdin). This was the root cause of an early "app froze" report.

---

## Library Browser — Toolbar

`src/gui/library_browser.py`, `_build_toolbar()`. Left to right: search box (`_search`, "Search artist, title, album…"), **Clear Filters** (immediately next to the search box, not right-aligned), a stretch, then **Classify Library** pinned to the far right. Toolbar vertical padding is 16px top/bottom, matching the Crates toolbar.

There is no format/file-type dropdown and no "Add Tracks to Library" button — both were removed. The dropdown (`_format_cb`) was cut because native-macOS Qt style ignores the QSS box model for `QComboBox` (wrong rendered height regardless of `setFixedHeight`, plus its own native arrow instead of the QSS-defined one) — rather than keep working around a native-widget quirk for one dropdown, it was removed outright. "Add Tracks to Library" (a file-picker dialog + background scanner worker, `_AddTracksPickerDialog`/`_AddTracksWorker` in `main_window.py`) was removed because it was redundant: `_ScanWorker` already does a full folder walk on every library load, so files dropped straight into the library folder are picked up automatically next time it's opened — exactly the assumption already baked into the Organize tab's "Open Library Folder" button, which is the surviving, simpler pattern for adding tracks.

### Tab-switch load caching (2026-09-02)

`_on_nav` calls `library_browser.load()` / `crate_manager.load()` on **every** visit, each
rebuilding the whole tree — which also janked the screen-slide animation running alongside it.
Both `load()` methods now take a disk-state signature (`_library_load_signature` /
`_crate_load_signature` — inventory identity + `len` + mtimes of the classification session,
`library_edits.json`, `.crate`/`.scrate` files, `neworder.pref`, consolidation logs) and
early-return when it's unchanged and the tree is already populated. Any classify run, inline
edit, crate reorder, smart-crate change, Rinse consolidation, or rescan (new inventory object)
bumps the signature, so real changes still reload. library_browser's deliberate no-early-return
behaviour is preserved by including the session-file mtime.

### Footer path (status bar left slot)

`main_window._status_library` shows the connected library path by default, and swaps to the
**selected track's full path** while a track is selected in Library or Crates (via the existing
`album_art_requested` / `_update_album_art` hook, guarded by `_status_showing_file` so status
messages don't clobber it). Reverts on leaving those tabs, on library change, and on selecting
a non-track row — `LibraryBrowserView.track_deselected` / `CrateManagerView.track_deselected`
→ `_restore_status_library_path`. The Library tree's first column header is **"Artist / Title"**
(expanded artist rows show track titles there).

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

### Track table — virtualized (QTableView + `_TrackTableModel`, 2026-09-03)

The track table was migrated from `QTableWidget` to a virtualized `QTableView` backed by
`_TrackTableModel(QAbstractTableModel)`. Reason: on a ~20k-track library the old widget
materialized ~13 cols × 20k `QTableWidgetItem`s synchronously on the main thread (the "All
Tracks" default view) — a 5–7s beachball. The model just holds the row dicts the
`_CrateLoadWorker` already produces off-thread; `set_rows()` is a `beginResetModel`/
`endResetModel` (~5ms).

- `_ReorderableTable` is now a `QTableView` subclass. Its drag-reorder / cross-widget drag /
  hand-drawn teal drop-line are unchanged; they read row order from `model.index(r,c).data(role)`
  instead of cells. `_ORIG_PATH_ROLE` = the crate's stored track-reference string; `UserRole` =
  the resolved absolute path.
- Sorting is in the model (`_TrackTableModel.sort` — reorders `_rows`, remaps persistent
  indexes so selection survives; numeric keys for `#`, BPM, Year, Bitrate, Duration, Date).
  `setSortingEnabled(True)` stays on the view; `_on_header_clicked` → `_persist_current_sort`
  unchanged.
- Search filter still uses `QTableView.setRowHidden` (per-row-index). **`set_rows()` does NOT
  clear those flags the way `setRowCount(0)` used to** — every (re)load must call
  `_clear_row_hidden()` or a prior crate's filter leaks by index into the next crate.
- Inline edit: `setIndexWidget` instead of `setCellWidget` (`_set_cell_editor`). Now-playing /
  hover-play icons are a `DecorationRole` on the model, driven by `set_now_playing` /
  `set_hover_row`. The post-edit row "flash" is a transient `ForegroundRole` (`set_flash` +
  `QTimer`). `EditTrackMetadataCommand` patches via `model.find_row_by_path` + `model.set_display`.
- Cell reads throughout `crate_manager.py` go through model accessors: `track_path_at(row)`,
  `orig_path_at(row)`, `display_at(row, col)`, `find_row_by_path(path)`.

### CrateReader hardening (2026-09-03)

- **Resolution is in-memory, not filesystem.** `_resolve_single` used to call `Path.exists()`
  per crate-track reference (× every track × every crate, twice) — ~6s on a 190-crate / 20k
  library on a media drive, for counts nothing in the GUI consumes. It now matches against an
  NFC-normalized `set` of the scanned inventory plus an unambiguous-basename count index. The
  filesystem fallback is kept only for the no-inventory (CLI/test) path.
- **macOS AppleDouble sidecars ignored.** Writing a `.crate` onto exFAT/SMB makes macOS drop a
  `._<name>.crate` next to it; `rglob('*.crate')` matched those and produced phantom crates.
  Any file whose name starts with `._` is skipped in `CrateReader`, `SmartCrateReader`,
  `PathRewriter`, and `crate_writer.read_crate_order`'s name set.
- **Serato system crates hidden.** Serato DJ's Stems feature auto-creates (and re-creates)
  `_Serato_/Subcrates/Serato Stems/Stems.crate`. `CrateReader.read()` drops any crate whose
  top-level path segment is in `_SERATO_SYSTEM_CRATES` (`{'serato stems'}` — extend as needed),
  plus anything nested under it, and scrubs it from parents' `children` lists. CrateSort has
  no code path that *creates* a named crate — every `.crate` write is a user action.

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

## Rinse (Duplicate Review) — Architecture (reworked 2026-09-02)

`src/gui/duplicate_review_view.py` — full-screen takeover launched from the dashboard stat
card. `QStackedWidget`: 0 = results, 1 = consolidation progress, 2 = celebration. Detector
(`core/duplicate_detector.py`) produces two tiers — `true_duplicate` (red) and `variant`
(orange). Consolidation runs through `core/duplicate_consolidator.py` on a `QThread`.

**Copy rule (locked):** never "delete" — the flow is *consolidation*. The confirm dialog and
its button say "Consolidate".

**Model — opt-in, per group:**
- Every group renders as a cheap collapsed **strip** (`_build_collapsed_card`: tier dot, song,
  "N copies · frees X", a self-painted disclosure chevron `_DisclosureButton`). Building 200+
  full cards up front froze the app; only groups in `self._expanded` get the full body.
- An open card: one **radio** picks the copy to keep; every other copy is consolidated into it
  (no per-copy checkbox — that was tried and cut as confusing). **Accept This Group** locks the
  group's choices in and collapses it *in place* — no auto-jump to another group. **Keep All —
  Don't Ask Again** dismisses the group (persisted by fingerprint).
- Sticky header: `X of Y groups reviewed` + teal bar, and a filter pill row (All / True
  duplicates / Possible variants / Needs review / Accepted) with live counts. True Duplicates
  section header carries **Accept all remaining true duplicates**.
- `_apply_card_change(idx)` rebuilds one card widget in place; full `_populate_results()` only
  on load and filter switch. `hideEvent` tears down all result widgets, `showEvent` rebuilds
  from the intact review state — so navigating away from Rinse is cheap, and
  `main_window._switch_content` skips its `grab()` slide-snapshot for the Rinse view.
- `consolidator.consolidate()` accepts `(group, winner, losers)` triples as well as the legacy
  `(group, winner)` pairs.

`_DisclosureButton` and the Rinse chevron are **self-painted** (`QPainter.drawPolyline`) — the
`⌄`/`⌃` glyph chars don't render in the app font. See PyQt gotchas #24.

---

## Organize View — Current Architecture

`src/gui/organize_view.py` — `QStackedWidget` across 5 states:

- **State 0: Landing Screen** — always shown on tab visit. Shows a history list of up to 3 recent reorganizations (`_history_layout`). Each history row shows date, file count, and either "Rolled back on [date]" or a red **Rollback** button. `_refresh_gate_screen()` is called on every `load()` and every `_on_back_to_dashboard()`. `load()` never auto-transitions to planning — user clicks "Plan Reorganization…".
- **State 1: Planning Screen** — `_PlanWorker` thread builds the plan.
- **State 2: Preview Screen** — animated stat cards + operations table.
- **State 3: Executing Screen** — copy-verify-delete progress.
- **State 4: Done Screen** — success or rollback-in-progress state. Has `self._done_back_btn` (re-enabled after rollback finishes) and `self._rollback_btn`. The detail text is now **two lines** (`'\n'.join(lines)` into the plain-text `_done_detail` QLabel, fixed 2026-08-11 — previously a single string joined with a literal double-space `'  '`, which word-wrapped into an awkward mid-line gap instead of a real line break): line 1 is the moved/failed/skipped summary, line 2 is always the crate path update status on its own line — "N crate(s) updated" on success, or "Crate paths not updated — use Repair Crate Paths in Settings" if `paths_rewritten == 0`.

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

### Cancel + slow-file hardening (2026-09-02, before Jace's first real 20k-track reorg)

The move loop runs in `_ExecutionWorker(QThread)`, so a drive stall freezes only the progress bar, not the app; combined with the per-file rollback log, a force-quit mid-reorg is fully recoverable. Process isolation (scanner-style) was judged overkill for `shutil` syscalls. Two additive safeguards:
- **Working Cancel** — `_ExecutionWorker.cancel()` sets a flag; `FileOrganizer.execute(plan, progress_callback, should_cancel=None)` polls it before each file and breaks at that clean boundary. The post-move steps (crate rewrite / cleanup / metadata sync) then run over just the `completed` prefix, so a cancelled run is consistent. New `ExecutionResult.cancelled: bool`. `execute()` emits `progress_callback(total, total, '__finalizing__')` after the loop; `OrganizeView._on_exec_progress` uses that sentinel to disable Cancel during the un-interruptible crate-write phase and show "Updating Serato crates…". Done screen: "Reorganization stopped — N moved, run again to finish or Rollback". **Cancel cannot interrupt a single `shutil.copy2` wedged in uninterruptible I/O** — it takes effect once that op returns.
- **Slow-file indicator** — `OrganizeView._on_exec_tick` (1s QTimer, started in `_on_execute`, stopped in `_on_exec_finished`/`_on_exec_error`) tracks time on the current file; after 15s the step label becomes "…still working (M:SS). Your drive may be slow; Cancel stops after this file."

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

## Genre taxonomy (15 parent genres)

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
| Latin | Banda, Bachata, Corrido, Cumbia, Mariachi, Merengue, Norteño, Ranchera, Salsa, Tejano, Vallenato (added 2026-09-04) |
| Orchestral | Classical, Symphony, Philharmonic, Concerto, Opera, Aria, Requiem, Sonata, Overture, Choral, Chamber Orchestra, Film Score (added 2026-09-04) |
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
- Reggaeton → Reggae, not Latin (resolved ambiguity, pre-dates the Latin bucket).
- A bare `"soundtrack"` genre/style tag does NOT route to Orchestral — too many OSTs are pop/rock song compilations, not composed scores. Only specific classical/score terms (`classical`, `symphony`, `film score`, `opera`, etc. — see `STYLE_MAP` in `classifier.py`) do. This is separate from the `Film & TV` content-type bucket, which is video-file + folder triggered and unrelated to audio-only orchestral scores.
- All genre and style terms: Title Case.
- Artist genre changes never cascade to tracks. Style tags are fully independent between artists and tracks.

### Film & TV — a content-type bucket, not a genre (added 2026-09-04)

`Film & TV` (`FILM_TV_GENRE` in `classifier_view.py`) is deliberately **not** in `PARENT_GENRES` — it's a content type, not a music genre, and doesn't count toward the 14 above or the "Why Only These Genres?" explainer. It still gets its own top-level `Media/Film & TV/<Show or Movie>/` folder and its own sidebar bucket in Library (the sidebar builds itself from whatever genre strings exist on entries, so no separate wiring was needed there).

**Trigger**: any video file (`rec.is_video`) whose ancestor folder is literally named "Film & TV" or "Film and TV" (case-insensitive) — checked against `rec.path.parts`, not a substring match. This is deliberately folder-based, not tag- or artist-based: a "Music Videos" folder gets zero special treatment and flows through normal per-artist genre classification exactly like audio.

**Why this needed to be structural, not just a per-track tag**: the existing pipeline groups tracks by canonical artist-name string, then majority-votes ONE genre across the whole group (`classifier_view.py` `_ClassifyWorker`, and separately `library_browser.py` `_rebuild_tree` for the Library tab tree). A movie or TV show can share its title with a real recording artist — the flagship case being **Scarface** (the rapper) vs. *Scarface* (the movie) — and if the video were only tagged `genre='Film & TV'` per-track while staying grouped under artist "Scarface", the group's majority vote (or the tab's ID3-vote fallback) would still overwrite it with whatever the rapper's audio tracks vote for. The fix pulls Film & TV videos out **before** artist grouping happens at all, in both places independently:
- `classifier_view.py` `_ClassifyWorker.run()`: folder-flagged videos are grouped by show/movie title (`_film_tv_title()` — prefers the artist/©ART tag, falls back to the leading `" - "`-delimited filename segment) into their own `ArtistEntry` objects, `is_film_tv=True`, genre forced to `Film & TV`, never entering the artist-name vote pool.
- `library_browser.py` `_rebuild_tree()`: same folder+`is_video` carve-out, independently, since this tree does its own artist-name grouping over `self._inventory` rather than consuming `ClassificationSession` results directly.

`ArtistEntry.is_film_tv` (persisted in `classification_session.json`) exists specifically so name-keyed lookup dicts fed by `session.entries` (`_session_genre`, `_session_artists` in `library_browser.py`) can **skip** Film & TV entries — since their genre is always deterministic and never needs voting/lookup, letting them into those dicts risked one silently overwriting a same-named real artist's classification (that IS the Scarface bug, just relocated one layer down). A manual "Change Genre" override on a Film & TV title (e.g. filing "Menace to Society" under Hip-Hop/Rap on purpose) is still respected — it's read the same way as any artist's `__artist__{name}` genre edit.

**Known residual edge case**: per-artist manual edits (Change Genre, Edit Style Tags, confidence-freeze) share a single `__artist__{name}`-keyed storage convention across ~15 call sites in `library_browser.py`. If a movie/show title is *identical* to a real artist's name AND the user manually edits either one via those actions, the edit could bleed into both (they share the storage key). This is far narrower than the original bug — it now requires an exact name collision **and** manual per-artist editing on it, rather than firing automatically — but it hasn't been closed. Would need each of those ~15 sites re-keyed by `(name, is_film_tv)` to fully close; tabled rather than done blind.

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
2. If changes detected: shows amber banner and `_ChangeReviewDialog` with a per-row, type-specific radio pair (see Serato sync warning section above — not generic Revert buttons)
3. User can mark individual changes for revert before syncing
4. On "Apply && Continue": reverts execute, checkpoint saves with track lists, re-scan triggers

---

## Undo/Redo System

- `src/utils/undo_manager.py` — Command pattern, 10-state stack, global across tabs
- 9 command classes: `AddTracksCommand`, `RemoveTracksCommand`, `ReorderTracksCommand`, `CreateCrateCommand`, `DeleteCrateCommand`, `RenameCrateCommand`, `ReorderCratesCommand`, `ReparentCrateCommand`, `EditTrackMetadataCommand`
- `AddTracksCommand` has an optional `stay_on_crate: Optional[str]` parameter. When set, `execute()` calls `_refresh(select=stay_on_crate)` instead of `_refresh(select=crate_path)` — the view stays on the source crate, not the target. `_add_tracks_to_crate()` (the drag-drop handler) passes `stay_on_crate=self._current_crate_path` so the user stays in the crate they were viewing while dragging.
- `AddTracksCommand` also has `reload_tracks: bool = True`, forwarded to `_refresh(reload_tracks=...)` in **both** `execute()` and `undo()`. `_refresh(reload_tracks=False)` still rebuilds the crate tree (so counts update) but skips `_load_selected_key()` — the track table is left exactly as-is. `_add_tracks_to_crate()` passes `reload_tracks=False` when `_current_crate_path == _ALL_TRACKS_KEY` and the drop target is a different crate: every dragged track is already in All Tracks so the set can't change, and repopulating would only reshuffle rows (All Tracks is ordered by first-containing-crate, so a newly-added membership jumps the track to that crate's position) and lose the scroll position. Reported by Jace during 2026-08-29 testing as tracks "disappearing" from the bottom of All Tracks after a drag — they had only re-sorted, never moved; nothing was ever removed from the source crate or disk (the drop path is purely additive via `writer.add_tracks`). Follow-up option noted, not done: give All Tracks a stable sort (artist/title or Serato add-date) independent of crate membership.
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
- **Scanner process isolation** (2026-09-01, `[[project-scan-process-isolation]]`) — tag reads go through `ParallelTagReader` worker **processes**, never back to a plain in-thread `mutagen` loop; a `QThread` can't survive an uninterruptible FSKit-exFAT read stall. `read_one_file(path, ext)` is the ONE tag-read code path (in-proc + worker). `multiprocessing.freeze_support()` MUST be the first statement in `packaging/run_app.py` and `main_window.main()`, and `CrateSort.spec` `hiddenimports` MUST list `parallel_tag_reader` + `scan_worker_proc`. Any standalone script that calls a scan needs an `if __name__ == "__main__":` guard (spawn re-imports `__main__`). Scanner progress callback + `_ScanWorker.progress` signal are `(done:int, total:int, label:str)` — `total == -1` means discovery.
- **`_BgSteps` post-scan threading** — the post-scan analysis (`_apply_serato_overlay`, `_check_serato_sync`, `_run_duplicate_detection`, `_detect_stragglers`) runs in `_BgSteps` QThreads (`self._bg_overlay`, `self._bg_post`), never synchronously in `_show_dashboard`/`_on_scan_finished` — a synchronous block there parks every animation and reads as a lock-up. Both refs are held on `self` and `wait()`ed in `_on_cancel_scan`. `_populate_dashboard` (widget build) stays on the main thread.
- **Serato path comparison must fold U+F022** — Serato encodes a "/" in a Finder folder name as private-use U+F022; `os.walk` yields ":". Any code matching a Serato ptrk against an on-disk/scanned path must normalise (see `straggler_detector._canon_path` and `PathRewriter._process_crate`). Don't reintroduce a raw string compare.
- **Organize Cancel contract** — `FileOrganizer.execute(..., should_cancel=None)` polls before each file and stops at a clean boundary; post-move steps then run over the `completed` prefix only. `ExecutionResult.cancelled` and the `progress_callback(total, total, '__finalizing__')` sentinel (disables Cancel during crate writes) must be preserved. Cancel is not expected to interrupt an in-flight wedged `shutil` syscall — the per-file `RollbackLog` save is what makes force-quit safe.
- **Color palette** — border color is `#444444` (never `#555555`). Muted text is `#a89b85` (never `#888`, `#666`, `#aaa`, `#555`, `#333`). All interactive elements must have hover states. These are enforced by Brandy (`/brandy`) and Annie (`/annie`).
- **Agent skills** — Brandy, Dez, Draper, and Annie are live local slash-command agents in `.claude/skills/`. Invoke with `/brandy`, `/dez`, `/draper`, `/annie`. Requires Claude Code restart to pick up after initial creation. AL and Cody are live A2A agents on Arora MCP.
- **Duplicate detection architecture** — `DuplicateDetector` in `duplicate_detector.py` classifies groups as `tier='true_duplicate'` (duration ±1s, bitrate ±32kbps, no variant keywords) or `tier='variant'` (remix/extended keywords, or spread exceeds thresholds). Winner scoring: `(crate_count, play_count, bitrate, meta_completeness, has_comment, has_stems)`. Detection runs in the `_bg_post` `_BgSteps` thread off `_show_dashboard()` after scan — pure Python, no I/O (~0.16s for 700+ groups over 19.7k tracks). `build_crate_count_map(crate_library)` builds the crate presence map. Pass it into `DuplicateDetector().detect(inventory, crate_count_map)`.
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

**Status: macOS beta packaging shipped — 0.1.0-beta (2026-07-12), 0.1.1-beta (2026-07-31), 0.1.2-beta (2026-08-28), 0.1.3-beta (2026-08-28), 0.1.4-beta (2026-08-28), 0.1.5-beta (2026-08-31). Unsigned, no notarization.**

**NEXT: 0.1.6-beta — not yet cut.** Scan/organize robustness pass (2026-09-01→02, `[[project-scan-process-isolation]]`): killable worker-process pool for tag reads (FSKit-exFAT stall no longer freezes the scan), 3-phase scanner, scan.log + unreadable-files banner/dialog, classification cache-skip, `detect_stragglers` 3.24s→0.21s, `_BgSteps` off-thread post-scan analysis, scanning-banner one-line layout, Organize Cancel + slow-file indicator. `packaging/run_app.py` + `CrateSort.spec` already carry the `multiprocessing.freeze_support()` + `hiddenimports` changes needed for the frozen build. Bump `info_plist` to `0.1.6` and run the usual pipeline. Blocked on Jace's real Manage-Library + Organize test passing.

0.1.5-beta ships the YouTube-import PO-token-wall rework: QUALITY combo (default Fast = one `android` pass), client-fallback cascade, `YOUTUBE SIGN-IN` → `YOUTUBE LOGIN` relabel + no-persist, no-lock-after-save retry flow — see "YouTube Import & Local Conversion Tools" above. Version bumped in `packaging/CrateSort.spec` `info_plist` only; DMG built via the documented one-off pipeline (staging dir → UDRW → volume icon → UDZO → JXA icon extraction from the built `.app` → `NSWorkspace.setIcon` on the `.dmg`). Windows/Linux not yet built. 0.1.4-beta ships the launch-screen copy + layout pass: new first-run wording ("Point CrateSort to your `_Serato_` folder and media." / "They must be in the same location for the app to function — this is usually the root of your media drive." / button "Select `_Serato_` Folder & Media Location"), `_leaded()` rich-text line-leading helper, and the launch-card layout hardening (scroll-area wrapper, responsive logo via `_fit_welcome_logo()`, anti-clip `_fit_welcome_text()`, stretch-row centring instead of an alignment flag) — see Launch Screen Architecture above. Version bumped in `packaging/CrateSort.spec` `info_plist` only, same pipeline. No dedicated build script exists yet — every step below (including the DMG staging/icon steps) is run as one-off shell commands each time; worth scripting if this becomes routine. 0.1.1-beta bumped `packaging/CrateSort.spec`'s `info_plist` version fields only — same pipeline, no packaging-process changes.

**Pipeline**: `packaging/CrateSort.spec` (PyInstaller) builds `dist/CrateSort.app` from `packaging/run_app.py`, an entry point that just calls `cratesort.src.gui.main_window:main`. Bundles `cratesort/assets/` in full. Build from a dedicated venv (`.build-venv/`, gitignored) — never the system Python.

**Two real bugs fixed in `cratesort/pyproject.toml` during first packaging pass** (pre-existing, unrelated to packaging itself, but blocked `pip install -e .` entirely):
- `build-backend = "setuptools.backends.legacy:build"` doesn't exist → must be `"setuptools.build_meta"`.
- `serato-crate>=0.1.0` — PyPI only ever published `0.0.1` → constraint must be `>=0.0.1`.
- `yt-dlp` was used by `yt_import_dialog.py` but missing from `dependencies` entirely (only lived in `requirements.txt`) → added.

**ffmpeg bundling (added July 2026)**: `imageio-ffmpeg` ships a real ffmpeg binary inside its wheel — no system Homebrew install, no network fetch at runtime, no separate download step. `cratesort/src/utils/ffmpeg_tools.py:get_ffmpeg_path()` resolves it via `imageio_ffmpeg.get_ffmpeg_exe()`, falling back to bare `'ffmpeg'` on `$PATH` only if the package is somehow unavailable. `packaging/CrateSort.spec` must include `*collect_data_files('imageio_ffmpeg')` in `datas=[...]` (via `PyInstaller.utils.hooks.collect_data_files`) or the packaged `.app` silently falls back to a system ffmpeg that won't exist on a clean install — this was the actual bug behind the pre-existing YouTube-import feature depending on Homebrew ffmpeg with nobody noticing. Only `ffmpeg` is bundled this way, not `ffprobe` — `ffmpeg_tools.py:get_media_duration()` parses duration from ffmpeg's own stderr banner instead of shelling out to ffprobe.

**App icon — locked decision**: The mascot's native SVG bounding box is 0.842:1 (taller than wide), never 1:1. macOS (Big Sur onward) automatically synthesizes a light background "card" behind any Dock/Finder icon whose artwork doesn't fill the square canvas — a transparent-background icon that leaves visible margins gets an OS-injected backdrop, which reads as an ugly, uncontrolled gray/white box. **Fix, locked**: bake the mascot onto a solid `#1a1a1a` opaque background (matches the app's own primary dark background color), contain-fit, centered, full canvas, **no crop of the mascot and no distortion of its aspect ratio**. Icon source lives at `cratesort/assets/icons/app/CrateSort.icns`, regenerated via `QSvgRenderer` (PyQt6) rasterizing `cs-logo-mascot-only.svg` at each required size, then `iconutil -c icns`. Never re-attempt a transparent/silhouette-only app icon on macOS — it will not render the way it looks in an image viewer.

**Uninstaller**: `packaging/uninstall.applescript`, compiled via `osacompile -o "Uninstall CrateSort.app" uninstall.applescript` into a real double-clickable `.app` (native dialogs, no Terminal window). Ships inside the DMG alongside `CrateSort.app`. Removes the app bundle (`/Applications` or `~/Applications`) and `~/Library/Preferences/com.jwbc.CrateSort.plist` only. **Never touches `_CrateSort/` folders or any user library data** — those live inside whatever folder the user pointed CrateSort at, not in any OS-standard app-data location. The compiled `.app` itself is a build artifact (gitignored) — only the `.applescript` source is committed.

**DMG**: `hdiutil create` → UDRW → mount → drop `.VolumeIcon.icns` + `SetFile -a C` on the volume for a custom volume icon → convert to UDZO.

**DMG file's own Finder icon — locked method (fixed 2026-08-04, do not use the old `sips -i`/`DeRez`/`Rez` technique described in earlier versions of this doc):**
The raw `CrateSort.icns` asset is a flat, sharp-cornered square — it has no rounding baked into its pixels. The polished rounded-squircle-with-shadow look only exists because **macOS auto-composites that treatment onto real `.app` bundle icons specifically** (Dock/Finder behavior for genuine application bundles, on any Mac, every time — not something baked into the icon file). The legacy `sips -i` (self-icon) → `DeRez -only icns` → `Rez -append` trick used for 0.1.0-beta happened to carry over an already-masked bitmap; attempting the identical steps for 0.1.1-beta produced a flat, unmasked icon instead — that tool chain is unreliable and not the actual source of the correct look.

**Correct, locked approach**: build `dist/CrateSort.app` *first*, then grab Finder's actual rendered (auto-masked) icon straight off that real bundle, and use that bitmap — not the raw asset — as the DMG file's custom icon:
```javascript
// extract_app_icon.jxa — run via: osascript -l JavaScript extract_app_icon.jxa
ObjC.import("Cocoa");
var icon = $.NSWorkspace.sharedWorkspace.iconForFile("/absolute/path/to/dist/CrateSort.app");
icon.setSize($.NSMakeSize(1024, 1024));
var rep = $.NSBitmapImageRep.imageRepWithData(icon.TIFFRepresentation);
var pngData = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
pngData.writeToFileAtomically("/tmp/rendered_app_icon.png", true);
```
Then downscale that 1024×1024 PNG into the standard iconset sizes with `sips -z <h> <w> src.png --out iconset/icon_<size>.png` (16/32/128/256/512, each with an `@2x` double-size variant), pack with `iconutil -c icns iconset -o dmg_icon.icns`, and apply it to the `.dmg` via the modern `NSWorkspace.setIcon` API (not the legacy resource-fork trick):
```javascript
ObjC.import("Cocoa");
var image = $.NSImage.alloc.initWithContentsOfFile("/tmp/dmg_icon.icns");
$.NSWorkspace.sharedWorkspace.setIconForFileOptions(image, "/absolute/path/to/dist_dmg/CrateSort-X.Y.Z-beta.dmg", 0);
```
If Finder still shows the old icon after this, it's a cache issue, not a data issue — `killall Finder; killall Dock` forces a refresh.

**Not yet verified**: whether the volume icon (`.VolumeIcon.icns`, shown when the DMG is mounted at `/Volumes/CrateSort`) has the same flat-vs-masked problem — that step still just copies the raw `CrateSort.icns` directly and was never compared side-by-side the way the DMG file's own icon was. Worth checking next time before assuming it's fine.

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

**The locked "elastic/spongy" signature (July 2026 — supersedes the old generic "cubic ease-out" language below for anything that reveals or dismisses).** The user validated this extensively across dialogs, context-adjacent transitions, and page navigation, and was explicit that every "something appears, then later leaves" moment in the app must share the *exact same* spring quality, not just a similar vibe:
- **Entrance**: `QEasingCurve.Type.OutBack`, overshoot `3.0`, animating the element in from ~55–70% of its final size/position, duration ~320ms. Grows past 100%, settles back — the "pop."
- **Exit**: `QEasingCurve.Type.InBack` (the mirror curve), same overshoot, duration 20% *slower* than the entrance (e.g. 320ms entrance → 384ms exit) — it should feel like the same spring running in reverse, not a different, cheaper animation. Never a plain opacity fade for something that bounced in.
- **Reference implementation**: `_CrateSortDialog` in `overlays.py` — `run_bounce_animation()` (entrance, `showEvent`) and `done()` (exit, overrides `QDialog.done()` to defer the real close until the shrink finishes, so `exec()` doesn't return until the animation completes). Every custom dialog in the app inherits this for free.
- **Danger/warning dialogs** (red accent — errors, destructive confirms, unsaved-changes warnings) deliberately use a *subtler* variant: overshoot `1.0` instead of `3.0`, i.e. barely any spring. This is intentional, not an oversight — confirmed with the user that bouncy/playful motion feels tonally wrong on a delete-confirmation or error. Controlled by `_CrateSortDialog._elastic` (default `True`; set `False` for the subtle variant).
- **Position-based motion needs a much smaller overshoot than size-based motion.** The same `3.0` overshoot that feels great shrinking/growing a dialog's *size* reads as a jarring, too-strong "lean the wrong way before committing" when applied to *position* (e.g. a page sliding left/right). For any horizontal/vertical slide, use overshoot `0.8`, not `3.0` — this was corrected live after the first attempt at the sidebar tab transition felt wrong.
- **Native OS elements cannot be animated.** Native file/folder pickers (`QFileDialog.getOpenFileName` etc.) and native `QMenu` context menus render outside Qt's control on macOS — there is no programmatic hook to attach a `QPropertyAnimation` to either. Don't promise motion on these; the fix (if ever built) is a fully custom replacement widget, not a tweak. (A custom animated context-menu replacement for Library/Crates/Tracks right-click menus was requested and confirmed but **not yet built** as of this writing — see `docs/future-features.md`.)
- **Hover states**: All interactive elements respond to hover. Teal buttons get darker on hover — never lighter. Orange elements warm slightly on hover. Never use a hover state that conflicts with the color role rules.
- **Modals and confirmations**: Every destructive action requires a modal confirmation before executing. Modal style is consistent — dark background, cream text, teal confirm, red cancel. No exceptions.
- **Status feedback**: Every significant operation produces a status message. Teal text for success/completion. Amber for in-progress or warnings. Red for failures. Status clears on next operation.
- **Loading/busy states that have no calculable percentage** (e.g. file-discovery scanning, where the total isn't known up front) must **never** use `QProgressBar.setRange(0, 0)` (indeterminate/spinner) — this is a hard rule, not a preference. Use the pulsing-mascot pattern instead: `cs-logo-mascot-only.svg` behind a `QGraphicsOpacityEffect`, `QPropertyAnimation` on `opacity` looping 0.3→1.0→0.3 via `setKeyValueAt`, `InOutSine` easing, ~1100ms, `setLoopCount(-1)`, paired with a live count/status label. Reference implementations: `convert_dialog.py`'s conversion progress and `dashboard.py`'s `_build_scanning_banner()`.
- **Mascot animation**: Must honor rubber hose principles — bouncy easing, squash and stretch, fluid elastic movement. Never linear, never mechanical, never stiff.

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

The motion system is shared across CrateSuite products, but CrateSort has specific motion needs based on its interactions. **See "Motion and interaction — CrateSuite system" above (Brandy section) for the exact locked curve/overshoot/duration numbers — this section covers where and how those get applied inside CrateSort specifically.**

**Rubber hose principle for UI**: The rubber hose drawing style (flexible, bouncy, organic) informs how CrateSort's UI moves — not how it looks. A modal that bounces in feels alive. A page that springs into place feels physical. A stat card that counts up feels like it's working. These are small moments that add up to a premium feel — and per direct user validation, they must all read as *the same* spring, not a family of similar-but-different ones.

**Every reveal/dismiss moment in the app uses the locked OutBack(in)/InBack(out) recipe**, not just modals:
- **Dialogs** — `_CrateSortDialog` (see Brandy section). Size-based, overshoot 3.0 (or 1.0 for danger/warning dialogs).
- **Sidebar tab navigation** (`MainWindow._switch_content()`, `main_window.py`) — a coordinated push, not a plain crossfade (a flat fade was tried first and explicitly rejected as feeling "cheap"/"off-brand" — don't reintroduce it). Direction is derived from sidebar position: Dashboard is conceptually "the top of the totem pole," so moving to a tab further down the sidebar (e.g. Dashboard → Library → Crates → Organize) pushes the outgoing page out to the **right** while the incoming page enters from the **left**; moving back up the list reverses both. Both sides animate together (`QParallelAnimationGroup`) using snapshot overlays (`grab()`'d pixmaps, not the live widgets — avoids fighting `QStackedLayout`'s own geometry management). Position-based, overshoot **0.8** (not 3.0 — see the Brandy section's note on why position needs a much smaller value than size), 384ms.
- **Scan → dashboard reveal** (`DashboardWidget._populate_dashboard`, transition from the pending render to the ready render) — same coordinated-push technique as tab navigation, rotated to the vertical axis: outgoing content drops away downward, incoming content rises up from above. Same 0.8 overshoot, 384ms.
- **Welcome-screen logo** (`_build_welcome()`) — grows in from 55% on launch (OutBack, overshoot 3.0, 320ms) and shrinks away to near-zero when the user picks a library, before the scan-pending dashboard appears (InBack, overshoot 3.0, 384ms) — this one *is* size-based (a logo growing/shrinking), so it correctly uses the larger overshoot, unlike the page-transition slides above.

Apply rubber hose energy to:
- Modal/page entrance and exit (see above)
- Drag initiation (slight scale-up on the ghost pixmap as it lifts)
- Drop confirmation (brief scale pulse on the receiving element)
- Stat card count-up animations (cubic ease-out, not linear — this is the one place a plain non-bouncy ease-out is still correct, a count-up shouldn't overshoot past its target number)

Never apply rubber hose energy to:
- Destructive confirmations — these should feel deliberate, not playful (subtle-overshoot dialog variant, not a different animation family)
- Error states — these should feel immediate and clear
- The actual *value* of a loading indicator — a busy/scanning state should never fake progress or bounce its percentage. It's fine (and now standard, see the mascot-pulse pattern above) for a *decorative* "still alive" indicator next to a real, honest progress readout to have bounce/spring energy — the rule is about not faking the data, not about banning all motion during a wait. **Worked example (2026-07-30): `_ScanActivityBeam`** in `dashboard.py` — a bounded comet that sweeps back and forth next to the real file-count readout on the scanning banner. It never grows, never reaches 100%, always returns to start — it asserts "still working," never "X% done." This is the reference case if this question comes up again: decorative liveliness cues are fine, simulated measurement is not.

**Duration guidelines (updated July 2026 — these are the actual shipped, validated numbers, not aspirational targets):**
- Micro-interactions (flash, highlight, hover): 100–150ms
- Entrance animations (dialogs, logo, mascot loop cycle): 320ms (or 1100ms for the continuous mascot pulse loop, which is intentionally slower since it's ambient, not a one-shot reveal)
- Exit animations (dialogs, page transitions, logo shrink): 384ms — always ~20% slower than the matching entrance, not the same number
- Data transitions (count-up, progress): 300–600ms
- Nothing exceeds 600ms for a one-shot reveal/dismiss unless it's a deliberate progress indicator or the ambient mascot loop

---

## Layout architecture — future-aware rules

**The media player shipped (July 2026).** `PlaybackBar` occupies the lower third of the app — global `MainWindow` chrome (added below `content_row` in `central`'s own `QVBoxLayout`), survives tab switches, audio + music video support. See "Locked decisions — July 2026 (playback bar...)" below for the full architecture.

**Rules (still apply — this is why the rollout was painless):**
- Never use `setFixedHeight` on the main window or any top-level container in a way that would prevent the player bar from being added.
- Leave a minimum of 80–100px of architectural headroom at the bottom of every view for the player bar.
- No critical UI elements in the bottom 80px of any current view — that space belongs to the player.
- The player does not feel bolted on. It feels like it was always there.

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

## Locked decisions — July 2026 (converters, dashboard-during-scan, motion system)

- **No accent bar on dialogs** — `_create_dialog_layout()` used to draw a 4px colored bar at the top of every dialog card; removed entirely per direct user feedback ("distracting, doesn't add anything"). Do not re-add it.
- **Dialog padding is DPI-derived, not a fixed pixel guess** — `_create_dialog_layout()` computes margins from `QApplication.primaryScreen().physicalDotsPerInch()` (not `logicalDotsPerInch()` — macOS reports a fixed legacy 72 there regardless of the real screen, which would undershoot a true physical inch). Current multiplier is `dpi * 0.7 * 0.8` (an inch, then dialed back 30%, then another 20%, each step a direct user request) — symmetric on all four sides. Dialogs auto-grow their minimum width (`pad*2 + 320` content floor) so this padding never crushes content on dialogs tuned around the old, smaller margins.
- **WAV→MP3/MOV→MP4 conversion never gets an artwork picker; YouTube import does** — confirmed explicitly after building it in the wrong place first. Local conversions inherit whatever artwork the source file already has (`copy_audio_tags`/`copy_video_tags`); YouTube downloads have none to inherit, so that's the one place a manual picker makes sense.
- **Video-conversion input formats are broad on purpose** — MOV, MKV, AVI, WMV, WEBM, FLV, M4V, MPG/MPEG all convert to MP4. Don't narrow this back to MOV-only.
- **Serato's own GEOB analysis tags are deliberately excluded from metadata carryover** — see YouTube Import & Local Conversion Tools section above. This is a considered exclusion, not a bug.
- **ffmpeg subprocess must always pass `stdin=subprocess.DEVNULL` + `-nostdin`** — prevents an ffmpeg-hangs-forever class of bug. Applies to every ffmpeg `Popen` call in the codebase (both `yt_import_dialog.py` and `convert_dialog.py`).
- **ffmpeg log output must be decoded with `errors='replace'`, never strict** — non-UTF-8 metadata in real-world files will otherwise crash the progress-read loop mid-conversion while ffmpeg keeps running, producing a valid file alongside a false failure report.
- **`imageio-ffmpeg` must be in `packaging/CrateSort.spec`'s `datas` via `collect_data_files`** — omitting it means the packaged `.app` silently depends on a system ffmpeg that won't exist on a clean install.
- **Dashboard is never fully blocked by the library scan again** — `_populate_dashboard(scanning=True)` renders immediately with YouTube/conversion cards live and only the Go-To cards + Library/Crates/Organize/Settings nav disabled. Do not reintroduce a blocking full-page "Scanning…" state — it was deliberately removed because a ~20k-file library scan could otherwise lock users out of unrelated tools for a long time.
- **`_WorkflowCard.set_disabled(True)` is the only card type with a disabled state** — `_IconActionCard` (YouTube/conversion) never gets disabled; it has no dependency on scan data.
- **See the Motion sections (Brandy + Dez) above for the full locked animation spec** — OutBack/InBack overshoot values, which contexts get 3.0 vs 0.8 vs 1.0, and the pulsing-mascot pattern that replaces indeterminate progress bars. This was extensively iterated and validated live with the user this session — treat the numbers there as final, not a starting point to re-tune from scratch.

## Locked decisions — July 2026 (playback bar, video window, rounded-corner containers)

- **`PlaybackController` (`playback_controller.py`) owns the single `QMediaPlayer`/`QAudioOutput` pair.** `PlaybackBar` and `FloatingVideoWindow` both subscribe to it rather than touching `QMediaPlayer` directly — state is never duplicated between the two. It has no concept of "next/previous"; that's tree-traversal logic in `library_browser.py`/`main_window.py`.
- **`QVideoWidget` cannot be masked, clipped, or reliably z-ordered against sibling Qt widgets.** It renders through a native child window that composites above ordinary Qt widgets regardless of `raise_()`. The inline video panel (`_InlineVideoPanel` in `main_window.py`) is built on `QGraphicsView`/`QGraphicsScene`/`QGraphicsVideoItem` instead — this paints through Qt's normal scene-graph compositor and can be layered/clipped like any other item. Do not reintroduce a bare `QVideoWidget` anywhere corners/overlays/z-order matter.
- **`RoundedCornerOverlay` (`theme.py`) is the standard technique for rounding a `QLabel`/pixmap/video panel.** QSS `border-radius` only rounds a widget's own background — a pixmap or video frame drawn on top of it is unaffected. The overlay paints the four corner-covers AND the border stroke from one identical `QPainterPath` in a single `paintEvent` — drawing them from two separately-computed curves creates a halo/fade seam at the boundary. Used by the sidebar art panel (`_ArtPanel`), the inline video panel (`_RoundedFrameItem`, the `QGraphicsItem` equivalent for scene-based content), and the playback bar's mini thumbnail.
- **The playback bar's mini thumbnail (56px) additionally needs `label.setMask(QRegion(...))`, not just the overlay.** The overlay-only technique worked for the 170px art panel and the video panel but would not clip the 56px mini thumbnail in the real running app despite passing every offscreen pixel test — see `project_pyqt_gotchas` gotcha #5 in memory for the full debugging trail. `setMask()` clips the widget's actual shape at the window level and is the more robust mechanism; use it (paired with the overlay for the border stroke) for any new small clipped thumbnail, not the overlay alone.
- **Locked radius values**: large sidebar art panel + inline video panel = 5px. Playback bar mini thumbnail = 4px. These went through two rounds of correction (initially 24px, halved to 12px, cut another 25% to 9px, then another 50% to 5px) — the brief settled on "slightly rounded," not a pronounced curve. Treat these as final, not a starting point.

## Locked decision — Launch Serato (Crates toolbar)

- **`CrateManagerView.launch_serato_requested` (pyqtSignal)** — emitted by a teal "▶ Launch Serato" button on the Crates toolbar (right end, past a spacing gap from New Crate/Smart Crate — a deliberately different kind of action, "I'm done organizing, let's go perform," not another crate-creation tool). `MainWindow._on_launch_serato_requested()` handles it.
- **The handoff sequence**: re-snapshot current crate state via `DashboardWidget._check_serato_sync()` (re-reads every `.crate` file fresh and calls `save_checkpoint()` — the same call the app already makes at session start) so the next launch's Carfax-style diff is measured from the exact moment of handoff → attempt `serato_guard.launch_serato()` (`open -a "Serato DJ Pro"` on macOS) → only if that succeeds does CrateSort call `self.close()` and quit. **On failure, CrateSort does not quit** — it shows a friendly `_ov_alert` instead ("couldn't find Serato, your crates are saved, open it manually"). Never leave the user with neither app open.
- **`overlays.py` → `_LaunchingSeratoDialog` / `show_launching_serato_dialog(parent, do_work)`** — the first place the mascot appears as a full animated character in-app (previously it only pulsed as a loading indicator). Built on `QGraphicsScene`/`QGraphicsView`/`QGraphicsSvgItem` (`QGraphicsSvgItem` inherits `QGraphicsObject`, so its `scale`/`rotation` properties are directly animatable via `QPropertyAnimation` — no widget-rotation workaround needed). Two looping `QPropertyAnimation`s in parallel: scale 0.92↔1.18 (900ms) and rotation ∓8° (700ms), both `InOutSine`, `setLoopCount(-1)` — the "grow and wiggle" brief. `do_work` is injected as a callback (checkpoint save + the actual Serato launch) so `overlays.py` stays free of subprocess/checkpoint imports; it runs ~700ms into the modal's life, between the "Saving your crates…" and "Launching Serato…" status text. Non-interactive by design — `keyPressEvent`/`closeEvent` are both swallowed so the sequence can't be interrupted mid-handoff.

## Locked decisions — August 2026 (incremental library scan)

- **The problem:** `LibraryScanner.scan()` (`scanner.py`) was a fully unconditional walk-and-reparse — every launch re-opened and re-read tags from every single audio file via mutagen, no caching of any kind. Fine at a 100-track test library; a real ~30k-track library took 20-30 minutes on every single app launch, not just the first. Identified as a product-blocking issue, not a nice-to-have.
- **Two independent layers, because file-mtime caching alone doesn't cover the real failure mode:**
  1. **Per-file cache** (`cratesort/src/core/scan_cache.py`, new module) — `<library_path>/_CrateSort/scan_cache.json`, keyed by absolute path → `{size, mtime, <tag/audio fields>}`. `LibraryScanner` (`scanner.py`) loads this at the start of `scan()` and, in `_scan_file()`, skips the expensive `mutagen.File()` parse entirely when a file's current `stat().st_size`/`st_mtime` match the cached values — reconstructing the `TrackRecord` straight from cached data instead. **A file that previously errored is always retried fresh, never permanently cached as broken** — a read error can be transient (permissions, a momentarily-locked file). No changes to `LibraryScanner`'s public API or any caller; the speedup is entirely internal. First-ever scan (no cache file yet) behaves identically to the old unconditional scan.
  2. **Serato-database overlay** (`_apply_serato_overlay()` in `dashboard.py`, run in the `_bg_overlay` `_BgSteps` thread off `_on_scan_finished()` right after `self._inventory` is set; classification waits on it because it reads `rec.comment`) — BPM/comment edited live in Serato often never touches the audio file's own tags at all (most DJs don't have "write tags to file" enabled in Serato), so file-mtime caching alone would never see that edit. Serato already stores these fields in its own `database V2` (small, fast to parse regardless of library size), so they're read fresh from there every launch, independent of file-cache state, and take precedence over the file's own tag when Serato has an entry for that track. **Genre is deliberately excluded from this overlay** — see the real bug this caused, below.
- **Serato `database V2` TLV field names — confirmed empirically against real Serato-written files, not guessed:** `tbpm` (BPM, UTF-16BE text), `tgen` (genre, UTF-16BE text), `tcom` (freeform comment, UTF-16BE text), `utpc` (play count, uint32 BE). **`database_reader.py`/`database_writer.py` previously read/wrote play count as `uply` — that tag does not exist in any real Serato database file tested; it silently never matched, meaning Serato play counts were empty/wrong everywhere in the app (e.g. duplicate-review "PLAYS: N"). Fixed to `utpc` as part of this same pass.** `TrackDbEntry` (`database_reader.py`) now carries `bpm`/`genre`/`comment` alongside the existing `add_date`/`play_count`.
- **Matching Serato's stored path against a scanned file uses `_normalize_pfil_keys()` on both sides, trying every candidate key — not a single direct `rec.path.as_posix()` lookup.** Serato's own `pfil` value only agrees with a freshly-scanned absolute path when the library's root folder hasn't moved since Serato last wrote its database; a renamed library folder or a remounted external drive changes the absolute prefix but not the media-relative portion (e.g. `MP3/Genre/Artist - Title.mp3`). The pre-existing `crate_count_map`/`play_count_map` lookups elsewhere (`duplicate_detector.py`, `dashboard.py._run_duplicate_detection`) still use the fragile direct-lookup form — not touched this pass, flagged as a related latent gap, not fixed.
- **"Force Full Rescan"** — Settings → Maintenance row (`settings_view.py`, same confirm→act→toast pattern as the other maintenance actions), calls `scan_cache.clear_cache(library_path)`. The escape hatch for the one residual case neither layer above catches: a tag changed by some third tool that writes directly to the file without going through Serato, without a size/mtime change (essentially never happens in practice, but the button exists so a user is never stuck).
- **`LibraryBrowserView._new_track_paths`** (a pre-existing, never-populated "◆ new" track marker) was deliberately left alone this pass to keep scope on scan speed — see `docs/future-features.md` for the wire-up note; the incremental scan's "added paths" are exactly the data that feature needs.

**Real bug found and fixed the same day — Serato overlay was silently reverting every accepted classification.** `_apply_serato_overlay()` originally overlaid BPM/genre/comment from Serato's database. Genre should never have been included: "Accept Reclassifications" (`library_browser.py`) writes the newly-classified genre to the audio file's own tag via `write_file_metadata()`, but never touches Serato's own `database V2` — so Serato's database still has whatever genre it had *before* classification. On the very next app launch, the overlay read that stale Serato genre and overwrote the correctly-classified, freshly-written file tag with it — meaning every accepted classification reverted itself the moment the app was reopened, with no error, no warning, nothing. Confirmed empirically: a track classified `"FX" → "Specialty"` and correctly written to disk reverted straight back to `"FX"` the instant the overlay ran on the next scan. **Fix: genre removed from `_apply_serato_overlay` entirely** — BPM and comment stay, since those have no other authoritative source and genuinely can change live in Serato mid-set; genre is different, CrateSort's own classification/Accept workflow owns it authoritatively and Serato has no equivalent "edit genre live" feature to justify overlaying it. **Any future work that touches this overlay must not re-add genre** without solving the ownership conflict first (e.g. only overlaying Serato's genre for tracks with zero classification history in CrateSort at all).

## Locked decisions — August 2026 (classification merged into initial scan)

- **The problem:** the app appeared to scan the library twice — once on library load (dashboard comet + stat cards), and again the first time "Manage Library" was clicked (a separate "Analyzing Library" popup with its own 5 stat cards). These were genuinely different computations (`LibraryScanner.scan()` — real disk/tag read — vs. `_ClassifyWorker`/`GenreClassifier` — pure in-memory artist/genre grouping), but the popup's copy and similarly-shaped cards read as duplicate work to the user.
- **Fix:** `dashboard.py._start_classification_phase()` now chains `_ClassifyWorker` automatically right after the file scan finishes (and after this session's Serato-metadata overlay — see above — so classification sees the freshest BPM/genre/comment, not stale file tags), still on the same scanning screen. The scanning banner's single big file-count number was replaced with the same 5-stat-card row the popup used (Files Analyzed/Recognized/Unrecognized, Artists Recognized, Genres Recognized). Once both phases finish, `classification_session.json` already exists on disk, so the existing skip-logic in `LibraryBrowserView._on_classify_clicked` opens straight into the classified library on first Library visit — no popup, no second "scanning" experience.
- **`_AnimatedStatCardWidget` moved from `library_browser.py` into `overlays.py`** — it's now shared between the dashboard's scanning-phase cards and the Library tab's `_AnalyzeLibraryModal` (kept as a fallback, see below), rather than defined twice.
- **`ClassifyProgressTally` (new class, `classifier_view.py`)** — extracts the per-artist tally math (dedupe by artist name, accumulate files-analyzed/recognized/unrecognized, track seen genres) that used to be hand-rolled once inside `library_browser.py`'s `_on_auto_classify_progress`. Both the dashboard flow and the Library-tab fallback now call the same `.add(info) -> dict` method. Note: its `artists_recognized` field means artists *processed* (deduped by name), not filtered by recognized — preserving the original modal's established (if slightly misleading) semantic rather than silently changing its meaning.
- **`_ClassifyWorker` gained real cooperative cancellation** (`classifier_view.py`) — previously had none at all. `self._cancelled` is checked at 3 points (top of the per-artist loop, before the DJ Tools bucket, right before `finished.emit(session)`) so cancelling mid-classification actually stops wasted work and never emits/saves a session for a run the user backed out of — not just a "swallow the final emit" pattern like `_ScanWorker` uses.
- **`dashboard._classifying` closes a real nav-lock race.** `main_window._is_scanning_in_progress()` previously only checked `dash._summary is None` — but `_summary` is set the instant the file scan finishes, before classification even starts. Without this flag, clicking a nav tab during the classification phase would incorrectly read as "not scanning" and could spawn a second `_ClassifyWorker` over the same inventory while the dashboard's own worker was still running and about to write the same session file. Now: `dash._library_path is not None and (dash._summary is None or dash._classifying)`.
- **Cancel-during-classification is fully wired**: `dashboard._on_cancel_scan()` and `MainWindow.closeEvent()` both stop `_classify_worker` the same way they already stopped `_worker` (cancel → disconnect `finished` → `wait()`). Verified empirically (real `QThread`s through a real Qt event loop): cancelling mid-classification leaves no stray `classification_session.json` and doesn't crash.
- **Copy constraint (unchanged from original plan):** the dashboard's classification-prep phase must never imply classification is "done" or "accepted" — that's still the separate "Accept Reclassifications" step on the Library screen (`_exit_classify_mode_accept`), untouched by this change. Phase-2 caption reads "Preparing artist & genre associations…", never past-tense/finality language.
- **`_AnalyzeLibraryModal` (`library_browser.py`) is kept, not deleted** — it's the fallback for the case the dashboard-side classification never ran or errored (no session file yet when Library is opened). Confirmed still triggers and still completes correctly.
- **Bundled fix:** a verbose debug `print()` dump in `ClassificationSession.save()` (every artist/track, first 5/3) was removed — it used to only fire when a user manually triggered classification from the Library tab; with classification now running automatically on every first-time scan, it would have fired far more often and just added terminal noise.

## Locked decision — August 2026 (persistent classification Status column, SUPERSEDED 2026-08-06 — see below)

- **The problem:** the Library tab's "Confidence" and "Status" columns only ever existed during active classify-mode review — both got hidden the instant the user exited, via Cancel or Accept. That meant the moment "Accept Reclassifications" was clicked, every trace of "was this auto-matched or manually fixed" vanished from the UI, leaving no way to do an ongoing visual sweep ("click Blues in the sidebar, confirm every artist there is actually vetted").
- **Original fix (now superseded, kept for history):** `LC_CLS_CONF` was made a dual-purpose, always-visible column — Confidence during active review, relabeled to Status outside it, via `headerItem().setText()`. `LC_CLS_STATUS` (index 14) was left defined but fully unused, purely to avoid a `QHeaderView.restoreState()` section-count mismatch.
- **Why it broke, 2026-08-06:** once settled rows started keeping their persistent Status visible *during* active review too (see "Column architecture, corrected 2026-08-06" near the top of this Classification Architecture section), a single shared header could no longer describe the column's actual mixed content — a Status-type value like "✎ Edited" could render under a header literally reading "Confidence." Jace: *"I don't think we have an option... we have to address that."*
- **Current fix — see "Column architecture, corrected 2026-08-06" and the Confidence/Status column sections above for the full current design.** Short version: `LC_CLS_CONF` and `LC_CLS_STATUS` are now both permanent, separately-headed, single-purpose columns, populated only by `_make_top_level_item()`/`_rebuild_tree()`. `LC_CLS_STATUS` is no longer inert — the restoreState section-count concern that justified leaving it unused no longer applies, since it was never actually removed as a column, just given a real, permanent job.
- **`_derive_persistent_status()` also had to be corrected a second time, same day** — see "Critical, repeatedly-relearned lesson" in the Status column section above. The original version's `current_genre == proposed_genre` comparison (both already loaded by `load()`, as this section originally described) turned out to be trivially true before any real Accept had ever happened, since `current_genre` is itself pre-filled from the same classifier proposal. This produced "✓ Approved" on a library that had never been touched. Fixed by checking `library_edits.json` directly instead of comparing two genre strings; added a new **◔ Pending** state for "no explicit accepted-genre edit exists yet."

## Locked decision — August 2026 (track-level "recently merged" indicator)

- **The problem:** duplicate consolidation ("Rinse Your Library") already wrote a durable per-merge record (`_CrateSort/duplicate_consolidation_<timestamp>.json`) but nothing ever read it back — the moment the celebration screen was dismissed, the Library tab gave no indication that any specific track had just absorbed duplicate copies. Full design in `docs/plan-recently-merged-indicator.md`.
- **Scope note:** this is deliberately a track-level indicator, separate from the artist-level classification Status column above — consolidation happens per audio file, classification is an artist-wide judgment. Not an extension of Status.
- **`read_recent_merges(library_path, within_days=30)`** (new, `duplicate_consolidator.py`) — read-only, mirrors `organize_view.py._refresh_gate_screen`'s existing `reorganization_log_*.json` precedent: globs every `duplicate_consolidation_*.json` under `_CrateSort/`, keeps only `moves` entries with `duplicate: true` and `status: 'completed'` whose `executed_at` falls within the last 30 days, and aggregates by NFC-normalized `destination` path (mirrors `file_organizer.py`'s `_nfc_path`/`path_rewriter.py`'s normalization precedent) into `{count, most_recent}`. Unlike Organize's UI history cap of 3 files, reads **all** matching logs — this is a data lookup, not a history list. A winner merged across more than one Rinse run over time aggregates its count/most-recent correctly rather than only reflecting the last file read.
- **Wired into `library_browser.py`**: `load()` calls `read_recent_merges()` once per load into `self._recent_merges`, alongside the existing `self._session_genre`/`self._edits` loading block. `_make_track_child` looks up the NFC-normalized track path and, if present, applies the indicator — mirrors the existing `is_new` pattern exactly (glyph prefix on the title, whole-row `setForeground` across every column, a tooltip on `LC_ARTIST`) rather than a new column-based mechanism.
- **Color/glyph — checked with Brandy before finalizing (this was a brand call, not a code one):** `#D17D34` (locked orange accent, "selection highlight / non-button accent" — the only remaining true locked-palette hex not already spent on a row-status use) with a `⟳` prefix glyph (distinct from `is_new`'s `◆`). Brandy flagged in passing that the two existing comparison colors (`#5c9d94` new-track teal-ish, `#c9a87a` unclassified-but-tagged amber) are themselves undocumented derivatives, not in the actual locked palette table — pre-existing drift, not touched this pass.
- **Precedence when states collide:** unclassified (red/amber) still wins over both `is_new` and "recently merged" — an unclassified track needs action, this is just an FYI. Between `is_new` and "recently merged," merged wins (rarer, more specific information) — implemented as a plain `if merge_info / elif is_new / else` inside the already-classified branch of `_make_track_child`.
- **Explicitly not in scope:** no artist-level rollup, no settings UI for the 30-day window (hardcoded), no changes to `duplicate_consolidator.py`'s write path or the celebration screen — purely additive read-side plumbing on data that already existed.
- **Verified (headless, real `QTreeWidgetItem`/`TrackRecord`, not mocked):** a synthetic log within the 30-day window on a real temp library produces the correct indicator/tooltip/count on the winner's row; a second log older than 30 days for the same track is correctly excluded from the count; two logs referencing the same winner (NFD path in one, NFC in the other) aggregate into one combined `count`/most-recent rather than colliding or double-counting incorrectly.

## Locked decision — August 12 2026 (Convert Audio to MP3 — M4A support, tag-copy fix, video pixel-format fix)

- **The problem, reported by Jace:** "Convert Audio to MP3" wouldn't let him select `.m4a` files in the file picker, despite the feature being understood as "any audio file." Root cause in `convert_dialog.py`'s `_MODES['wav_mp3']`: `exts`/`filter` only ever listed `.wav`/`.aiff`/`.aif` — M4A was simply never added. Fixed: added `.m4a` to both `exts` and the `QFileDialog` filter string.
- **Real bug found while fixing the above, not yet reported by Jace — `copy_audio_tags()` (`metadata_copy.py`) would have silently dropped all metadata from an M4A source.** The function assumed every source has ID3-style frames (`frame.FrameID`) copied 1:1 onto the destination MP3's ID3 tags — true for WAV/AIFF/MP3 sources, but M4A tags are plain MP4 atoms (`\xa9nam`, `\xa9ART`, `covr`, etc.), not `Frame` objects. `frame.FrameID` on a plain atom value raises `AttributeError` on the very first tag, outside any try/except in the loop — propagates up and gets caught by the caller's broad `except Exception: logger.warning(...)`, so the MP3 file itself converts fine but title/artist/album/artwork all silently vanish. Fixed by branching on `isinstance(src_file.tags, MP4Tags)`: MP4 sources now go through a new `_copy_mp4_tags_as_id3()` that maps the common atoms (`\xa9nam`→TIT2, `\xa9ART`→TPE1, `\xa9alb`→TALB, `\xa9gen`→TCON, `\xa9day`→TDRC, `\xa9wrt`→TCOM, `\xa9grp`→TIT1) onto ID3 text frames and `covr` cover art onto an `APIC` frame; WAV/AIFF/MP3 sources keep the original `_copy_id3_tags()` path unchanged. Verified end-to-end with a real tagged M4A test file run through the actual conversion pipeline (ffmpeg convert → `copy_audio_tags`) — title/artist/album/cover art all confirmed present in the resulting MP3's ID3 tags via a fresh mutagen read.
- **Compression-quality audit, prompted by Jace asking to confirm "best compression, no artifacts/glitching" across both converter modes.** Tested against the actual bundled `imageio-ffmpeg` binary (not system ffmpeg), not just read by inspection:
  - **Audio → MP3**: already at the format ceiling. 320kbps CBR is MP3's maximum bitrate. Verified: a 96kHz source downsamples cleanly to 48kHz with no aliasing/warnings; a 5.1 surround source downmixes cleanly to stereo automatically; no gain/normalization is applied anywhere in the path, so no clipping risk. No change made — already correct.
  - **Video → MP4: real bug found and fixed.** `_convert_one()`'s video args never pinned `-pix_fmt`, so a 10-bit source (common from modern phones — HDR capture, ProRes, 10-bit HEVC) encoded out as H.264 **High 10** profile instead of standard 8-bit — a profile most players and hardware decoders don't support, a plausible real-world cause of playback glitches or files that simply won't open. Reproduced live: a synthetic 10-bit HEVC test source converted through the unmodified pipeline came out `h264 (High 10) yuv420p10le`; adding `-pix_fmt yuv420p` to the args changed the same conversion to `h264 (High) yuv420p` — universally compatible. Fix applied in `_convert_one()`'s video-mode `args` list.
  - **Not changed, flagged as optional:** video mode uses `-preset fast`. At a fixed CRF, preset only trades file-size efficiency for encode speed — it does not affect visual quality/artifact risk (crf 18 already targets "visually lossless" regardless of preset). Left as-is; a slower preset would shrink output files further at the cost of longer conversions, Jace's call if wanted later.

## Locked decision — August 22 2026 (Smart Crate: manual refresh + Year date rules; dashboard stat-card/mascot consolidation)

**Smart Crate "Check for New Files" — manual refresh, right-click menu next to Edit Rules.** Built after Jace hit a real Serato Live Update problem live in a set: a BPM-sorted smart crate visibly reshuffled/renumbered while loading a track mid-set, because Live Update re-evaluates continuously and Serato has no way to pause it selectively. Rather than force a choice between "static, goes stale" and "live, can reshuffle under you mid-set," this adds a third path: re-runs `match_tracks()` (`core/smart_crate_engine.py`) against the crate's already-saved rules and the current inventory, writes the refreshed track list through the existing undoable `UpdateSmartCrateRulesCommand` (rules/match_all/live_update untouched, only `tracks` differs), status bar shows `+N/-M` or "No new files" (no-op write when nothing changed). Mirrors what Serato's own UI requires for a manual resync (Edit Smart Crate → Save with no rule changes) but one click, no dialog.

**Year field gained numeric `is before`/`is after` comparisons (`RuleComparison.STR_DATE_BEFORE`/`STR_DATE_AFTER`) — additive, not a replacement.** Serato's `.scrate` format already defines these tags; nothing in CrateSort exposed them, so there was no way to build a decade/date-range rule (e.g. `Year is after 1989 AND Year is before 2000`). **The first implementation replaced Year's original text comparisons (`contains`/`is`/etc.) with only the two new ones — Jace caught this before it shipped**: a real saved crate (`Year is 1979`) would have silently had its rule rewritten to something else the next time it was opened and re-saved, since the comparison dropdown couldn't find its old value in the new, narrowed list. Fixed: `comparisons_for_field(YEAR)` returns the original four plus the two new ones, union not replacement. **Standing rule going forward, any time a rule/format touching Serato's native file types is extended: additive only, never narrow an existing option a real saved file might already reference** — full reasoning in `[[feedback_additive_serato_format_changes]]` (Claude memory).

**Live Update checkbox restyled — was a flat color fill with no checkmark.** `_SmartCrateRuleDialog` was inheriting a global `theme.py` `QCheckBox::indicator:checked` rule that just filled the box solid orange with `image: none` — read as "just a color block," not a toggled state. Fixed by wiring the dialog's checkbox to the same `checkbox-checked.svg`/`checkbox-unchecked.svg` icons Settings and the Dashboard already use (real checkmark glyph, not a fill).

**`_ArrowComboBox` popup-clipping fix, `overlays.py` — affects every dropdown in the app, not just this dialog.** Popup width was left to Qt/QSS auto-sizing to content, which can't be trusted (same class of unreliability as the `::down-arrow` self-paint fix) — longer items like "does not contain" rendered clipped a character short. Fixed by computing the popup's width explicitly from real font metrics in `showPopup()` before opening it.

**Dashboard stat cards — two independently-built, visually divergent components consolidated into one.** The scanning banner's 5 progress cards (`_AnimatedStatCardWidget`, `#1a1a1a` bg, centered text) and the post-scan "Your Library" row's 4 summary cards (`_AnimatedStatCard`, `#2F2F2F` bg, left-aligned) were two separate classes rendering the same conceptual thing differently — so the whole stat-card block visually flipped (color, alignment, and the enclosing panel) the instant a scan finished, plus the mascot vanished entirely. Confirmed FLAGGED by Dez (invoked mid-session for a standards read) — one frame, content-only changes. Fix: `_AnimatedStatCard` deleted; post-scan cards now render from `_AnimatedStatCardWidget` (gained `start_animation(duration_ms)` one-shot eased count-up + optional `clickable` replay alongside its existing live-increment `update_target()` mode); the post-scan row is now wrapped in the same enclosing `QFrame` panel (`#2F2F2F`/`#383838`) the scanning banner already used, via a shared `_build_mascot(pulsing: bool)` helper that both states call — pulsing during a scan, settled at opacity 1.0 once loaded, same position (left) in both states. The only things that legitimately still differ between the two states: the 5-vs-4 metrics shown, and the comet activity beam only running during an active scan.

**Widening the stat cards by 6px surfaced a real Qt layout lesson (`[[project_pyqt_gotchas]]` #19).** A content-margin bump provably changed the card's isolated `sizeHint()` by exactly 6px but had **zero** effect on the real rendered app — the cards' default `Preferred` size policy was already stretching them to consume 100% of the row's surplus width, so there was no "floor" left for a small padding increase to push against. Root-caused by measuring the actual `_build_stat_cards_section()`/`_build_scanning_banner()` output at a realistic window width (1660px), not just the isolated widget's `sizeHint()`. Correct fix: reserve a fixed 24px trailing gap via `addSpacing()` — an unrestricted `addStretch()` was tried first and overshot badly (800px+ dead zone at that same width). Result matches the mascot box's own internal left inset almost exactly (42px measured left vs. 43px measured right), applied identically to both rows.

## Locked decision — August 28 2026 (library review pass)

**Dialog keyboard standard — Enter commits, Escape cancels, everywhere.** Every custom dialog (`_CrateSortDialog` subclass) and `_ov_*` helper: the primary action button is `setDefault(True)` + `setAutoDefault(True)`, the cancel button is `setAutoDefault(False)`, and every `QLineEdit` in the form wires `returnPressed` → the commit handler. **Warning/danger dialogs invert this — the SAFE option is the default** so Return can never be a shortcut past a warning or into a delete (`_UnsavedChangesDialog` → "Stay & Finish"; `_UnclassifiedWarningDialog` → "Go Back to Library"; `_ov_confirm` with `confirm_danger=True` → the cancel button). Progress/worker dialogs (`_ExportProgressDialog`, `_ConvertDialog`, `_YTImportDialog`) route Escape through their own `_on_cancel` (not bare `reject()`, which left the worker running). **Confirm on Escape/Cancel when real work would be lost**: a running conversion/download, or a *new* `_SmartCrateRuleDialog` with rules already entered (editing an existing crate is exempt — bailing = no change, and it's undoable). Triggered by Jace hitting it live: right-click a track → type a style tag → Enter → dialog closed without saving. Full standing rule: `[[feedback_dialog_keyboard_standard]]` (Claude memory).

**Library "now playing" marker.** The track row currently loaded in the playback bar keeps the play-triangle icon (in place of the ♪) even when unhovered — same dual-state colouring as the note icon (orange `#D17D34` unselected, dark on selection). `LibraryBrowserView.set_now_playing(path)`, driven from `main_window` by `PlaybackController.now_playing_changed`, so it tracks direct row clicks, the hover-play icon, and skip next/prev alike. The "what icon does a row show when not hovered" decision lives in `_resting_track_icon()` and is used by hover-leave *and* row construction, so the marker survives re-filtering / re-sorting the list. Stopping playback does not clear it (matches the playback bar's own behaviour).

**Library tree state persists across tab switches, within a session.** Expanded artists + the current selection are snapshotted (`_save_tree_state`) before `load()` rebuilds the tree on each nav into Library, and re-applied (`_restore_tree_state`, incl. scroll-to-centred) after — mirroring `CrateManagerView`. Session-lived (`_session_expanded_artists`, `_session_selected`), reset only on a library change or app restart. Also: double-clicking an artist to expand it now *keeps it selected* (was force-deselected) — matches the crate tree.

**Crate tree icons.** `CrateItemDelegate` draws a Serato-style isometric crate icon left of every crate name — `assets/icons/icon-crate.svg` (orange) for regular, `icon-crate-smart.svg` (teal) for smart; "All Tracks" gets none. The magic **wand is gone from the tree** (kept only on the top-right "New Smart Crate" button). A smart crate's **left colour bar is no longer always-on** — it shows the teal bar only when selected, exactly as a regular crate shows the orange bar only when selected. The "Save Crates & Launch Serato" button lost its trailing ` ↗`.

**Dashboard mascot is interactive after a scan.** Rebuilt on `QGraphicsView`/`QGraphicsSvgItem` (like `_LaunchingSeratoDialog`). Hovering the settled mascot does a one-shot grow + wiggle; clicking it replays all four "Your Library" stat-card count-ups. The pulsing scan-phase mascot is unchanged.

**"Why Only These Genres?" — genre-sidebar explainer.** A muted-beige `ⓘ Why Only These Genres?` link (→ teal on hover) sits directly beneath the last genre row (the sidebar list is `AdjustToContents`, not stretched). Opens `_GenreLogicDialog` — four eyebrow+paragraph sections (RECORD SHOP LOGIC / OK, BUT WHY SO LIMITED? / LEVERAGE STYLE TAGS / GENRES BECOME FOLDERS), with a "Click here" disclosure in section 1 that expands/collapses the full 13-genre list inline. Copy is Jace's, verbatim. Spacing is locked (headline→section 30px, eyebrow→paragraph 8px, between sections 16px) and the sizing had to be done by hand — see `[[project_pyqt_gotchas]]` #20 (wrap-label `sizeHint` mis-measures width → `QVBoxLayout` inflates the inter-section gaps; fix is `setFixedWidth` on every body label + compute dialog height from individual widget sizeHints + `setFixedHeight`/drop-constraint on each toggle).

## Locked decision — August 27–28 2026 (Rinse manual-test fixes + track-row playback normalization)

Source: `_resources/rinse-testing-findings-2026-08-27.md` (Jace's manual Rinse dry-run) plus a follow-on playback pass. Nothing committed yet at time of writing — 7 files modified, 6 new (`gui/inline_edit.py`, `gui/track_icons.py`, 4 test files). pytest is not installed in the dev venv; every test was verified by direct execution and placed under the configured `testpaths` for later.

**Rinse #1 — duplicate detection no longer drops a pair when its metadata is edited.** `DuplicateDetector` only ever compares two files if their `(normalize_artist, normalize_title)` tuple is *exactly* equal — it's a dict key, no fuzzy match. Audio signals (duration/bitrate/size) only pick the *tier* (`true_duplicate` vs `variant`) of an already-formed group; they never form one. So appending `(Bootleg)` to one copy's title moved it to a different bucket and the pair vanished from the dashboard count entirely (not reclassified — gone; the banner counts `summary.total_groups`, both tiers). Root cause was `normalize_title()` stripping only an **allow-list** of known suffixes (`(Original Mix)`, `(Remaster)`, years, `ft.`…). Fix (`utils/normalize.py`): strip **any** trailing `(...)` / `[...]` group, with a guard so a title that is *only* a bracketed group (`(Intro)`) keeps its text. Rationale: for duplicate *bucketing*, an over-merge still surfaces to the user (shown as a variant in the review list); an under-merge hides the file. Does **not** fix a user rewriting the core title text itself — only audio fingerprinting would, and that's out of scope. Test: `tests/test_normalize.py`.

**Rinse #2 — consolidation no longer leaves a crate pointing at the same file twice.** When one crate referenced both the winner and a loser of a duplicate group, `PathRewriter.rewrite()` rewrote both `ptrk` entries to the winner and never deduped, leaving two identical rows. Fix (`serato/path_rewriter.py`): new `_dedupe_track_refs(data)` collapses `otrk` entries whose resolved `ptrk` (NFC + `U+F022`→`:` normalized) is already seen, keeping the first occurrence's position; every non-track tag (`vrsn`/`osrt`/`ovct`) passes through untouched. Called in `_process_crate` after the rewrite, before backup + atomic write. **Scoped to crates this pass already modifies** — not a global every-`.crate`-write invariant (that would back up and rewrite crates Rinse didn't otherwise touch, bloating the rollback log). Test: `tests/test_path_rewriter.py`.

**Rinse #3 — Library and Crates track lists now share one row height AND one inline-edit widget.** They had drifted: Crates table locked rows to 36px via `verticalHeader().setDefaultSectionSize/Min/Max`, the Library `QTreeWidget` had **no** row-height setting so its rows auto-sized to ~28px (font + icon + QSS `::item` padding) and the double-click editor's descenders clipped.
- `TRACK_ROW_HEIGHT = 36` now lives in `theme.py` (new "Dimensions" section). Crates uses the constant; Library pins every row to it via `item.setSizeHint(LC_ARTIST, QSize(-1, TRACK_ROW_HEIGHT))` in **both** `_make_artist_item` and `_make_track_child` — a per-item size hint, because a `QStyledItemDelegate.sizeHint()` override proved unreliable in the running app (`[[project_pyqt_gotchas]]` #21). `_TrackRowHeightDelegate` is kept as belt-and-suspenders.
- The inline editor is one shared widget: `gui/inline_edit.py::make_inline_editor(text, on_commit, on_cancel)` + `INLINE_EDIT_QSS`. A `QLineEdit` 36px tall with a QSS `margin: 4px 0` that insets the visible box to a 28px vertically-centred pill in both screens. Escape→cancel / Return→commit / editingFinished→commit wired inside the helper.
- For the tree editor to sit flush at the row top (so the shared QSS centres it the same as `setCellWidget` does in the table), the Library tree's `QTreeWidget::item` rule dropped its vertical padding → `padding: 0px 4px 0px 2px`. Row text stays centred (the removed padding was symmetric). See `[[project_pyqt_gotchas]]` #22 for the `setItemWidget` vs `setCellWidget` asymmetry that forced this.

**Track-row playback is a real play/pause toggle in both screens, via one shared path.** Previously the Library hover-play icon always restarted; there was no equivalent in Crates at all.
- `PlaybackController.play_or_toggle(rec)` — if `rec.path` matches `current_track` → `toggle_play_pause()`, else `play(rec)`. A second click pauses, a third resumes, never a reload.
- `gui/track_icons.py` (new) — the three row glyphs shared by both screens: `note_icon()` (rest), `play_icon()` (hover / loaded-but-paused), `pause_icon()` (loaded + playing). 9×14, dual-state Normal/Selected, module-cached. Replaces the per-file painted `_make_note_icon`/`_make_play_glyph_icon`.
- **Library**: hover/click routes through `play_or_toggle`; `_row_icon_for(path, hovered)` drives the 3-state glyph; `set_playing_state(bool)` refreshes the loaded row on every player state change; `_is_playing` tracked on the view.
- **Crates**: new `play_requested = pyqtSignal(object)`; `setMouseTracking(True)` on the track table + viewport; in `eventFilter`, hover over **any column of the row** (`_hover_row_at`) swaps the note→play glyph — matching Library — while the **click** to play is confined to the note-icon's ~24px zone (`_title_icon_row_at`, `_TITLE_ICON_HIT_WIDTH`). The whole press→release gesture is swallowed in the icon zone so it never selects the row or starts a row drag-reorder. `set_now_playing(path)` / `set_playing_state(bool)` + `_refresh_now_playing_marker()` keep the marker correct across crate switches and re-sorts. Unresolved rows (`_resolve_track` → None) have no play affordance.
- **`main_window.py`**: `_crate_manager.play_requested` → `_on_play_requested`, which now calls `play_or_toggle` and only does the album-art / video-panel work when the track actually changes. `PlaybackController.playback_state_changed` → new `_on_playback_state_changed` fans `set_playing_state(playing)` to **both** views; `_on_now_playing_changed` now also calls `_crate_manager.set_now_playing`.
- Test: `tests/test_track_playback_icon.py` (shared glyphs cached/distinct; `play_or_toggle` routing; both views' 3-state glyph; Crates whole-row hover vs icon-zone click; `play_requested` payload).

### Consolidation ↔ Organize interaction (confirmed behavior, for the knowledge base)

Walked through in detail with Jace 2026-08-28. This is user-facing truth, not just implementation:

- **Rinse consolidation does not move or rename anything.** It deletes the loser file(s), leaves the winner exactly where it is on disk (even buried deep), rewrites every `.crate` reference from the loser's path to the winner's real path (in place, written to disk immediately, with a backup in `_CrateSort_Backups/` and a rollback log), and merges the loser's play count → `database V2`, comment → winner's tag, cue points → winner's markers.
- **A crate "adopts" the winner even if the winner was never manually added to that crate.** What gets repointed is the *loser's* reference, wherever it lives. `PathRewriter` scans every `.crate` file, not just ones already containing the winner. So the crate keeps its track — the pointer just follows the audio to the surviving file. The alternative (crate left with a dead reference to the deleted file) never happens: the rewrite runs *before* the delete.
- **Winner selection favors the in-crate copy, but only as a tiebreaker.** Priority: format (FLAC/WAV/AIFF > lossy) → bitrate → file size → metadata completeness → `crate_count` → stems → clean filename. So if the never-in-a-crate copy is objectively better (lossless vs MP3), it wins and the crate is *upgraded* to point at the better file.
- **You do NOT need to run Organize after Rinse.** The crate is intact and playable the instant Rinse saves. Quit CrateSort, open Serato, the crate loads and every track resolves. The `.crate` files are the source of truth for crate membership — Serato re-reads them fresh on every launch, there is no Serato-side cache that can override or un-rewire them.
- **If you *do* run Organize afterward**, it moves files into `Media/<genre>/<artist>/` and rewrites every crate reference to follow each move (`FileOrganizer._update_crate_paths` → `PathRewriter`, keyed off the actual completed moves). The two stages compose cleanly because each one persists its crate rewrites to disk and the next stage re-reads fresh: `OrganizeView` re-reads all `.crate` files via `CrateReader(serato_dir).read()` at plan-build time, and `_on_rinse_done` forces a full re-scan of the inventory. No stale in-memory `CrateLibrary` is carried across the Rinse → rescan → Organize boundary.
- **Order isn't fragile.** Rinse-before-Organize is the intended flow, but either order is safe because both stages read crates fresh from disk and write back to disk.
- Edge cases: neither copy in any crate → nothing to rewrite, loser just deleted. Each copy in a *different* crate → both crates repoint to the winner, both keep the track. Both copies in the *same* crate → both refs rewrite to the winner, then deduped to one row (Rinse #2 fix, `_dedupe_track_refs`).
- Serato-side asterisk (not a CrateSort issue, not a breakage): if the winner is a file Serato genuinely never analyzed, Serato generates its waveform/beatgrid the first time it loads that crate — a few silent seconds. Cue points survive because they were merged into the file itself.

---

## Locked decision — August 28 2026 (Straggler gather — bring out-of-library crate tracks in)

**Problem.** CrateSort scans one folder tree; Serato resolves crate `ptrk`s anywhere on the volume, so working DJs have crate tracks in `~/Downloads`, `~/Music`, Desktop, etc. Those showed as greyed "Not found in library" rows with no way — free or Pro — to bring them in (`FileOrganizer` skips anything failing `_is_under_root`). First surfaced while drafting `docs/first-run-walkthrough.md`; shipped a first version the same day so Jace's large-library test wasn't blocked by it. Design decisions with Jace: **pre-flight dialog** (not a full-screen view like Rinse), **move** (copy → sha256 verify → delete original), destination **loose at `<library>/Media/`** — never a named holding folder, because `file_organizer._remove_empty_dirs()` runs after every Organize and would auto-reap it (the "folder appears then vanishes" jank). **Free tier, no gate.**

**New files:**
- `core/straggler_detector.py` — pure logic. `Straggler(source_path, size, crate_refs, crate_names)`; `detect_stragglers(current_crates, library_root, serato_dir, known_library_paths=None)` reuses the `{str(crate_file) → [ptrk]}` dict the Dashboard already builds in `_check_serato_sync()` — **does not re-read crates**. `known_library_paths` (dashboard passes `{str(r.path) for r in self._inventory}`) is the disk-free in-library test: both sides go through `_canon_path()` (NFC + fold **U+F022 → ':'** — Serato encodes a "/" in a Finder folder name that way, `os.walk` yields ":") and a set-membership check; a real `.exists()` stat only happens on a miss. This took `detect_stragglers` from **3.24s → 0.21s** on Jace's 42,790-ref library (see `[[project-scan-process-isolation]]` §4a/§6). For a ptrk not in the set and not on disk under `library_root`, locates the real file via `Path(ref)` then `Path('/' + ref)`; if it exists and is not under `library_root`, it's a straggler. `library_drive_root()` derives the volume-root prefix from any ptrk that *does* resolve in-library (fallback: `/Volumes/<name>` or `/`). Dismiss list `_CrateSort/dismissed_stragglers.json` mirrors `duplicate_dismissals.py` (`load/save/add_dismissed_stragglers`).
- `gui/straggler_dialog.py` — `_GatherStragglersDialog` (per-source-folder checkboxes, live summary line, "Don't ask me to move these files again", `selected_stragglers` read after `exec()`), `_GatherProgressDialog` (determinate bar + result screen, Close disabled until done), `_GatherWorker(QThread)`.

**`_GatherWorker` flow:** `mkdir Media/`; open a `RollbackLog` at `_CrateSort/reorganization_log_<ts>.json` with a new `kind: 'straggler_gather'` discriminator; per file — `shutil.copy2` → `_sha256` verify (mismatch → delete copy, record failure) → `unlink()` original → append a `status: 'completed'` move entry → `rlog.save()`; then one `PathChange(old=ptrk, new=<dest rel to drive root>)` per unique ref, `PathRewriter(serato_dir).rewrite(...)`, `rlog.log_crate_backup()` each backup. Reuses `_sha256` + `RollbackLog` from `file_organizer`, `PathChange`/`PathRewriter` from `path_rewriter`. Same log format as Organize, so **rollback works for free** via `OrganizeView` history (`FileOrganizer.rollback()` handles plain completed moves + `crate_backup_paths`).

**Dashboard wiring (`dashboard.py`):** `self._straggler_list`; `_detect_stragglers()` called in `_show_dashboard()` and `refresh()` right after `_run_duplicate_detection()` (needs `_current_crates`, populated by `_check_serato_sync()` first); orange `_build_straggler_banner()` rendered after the dup banner when the list is non-empty; `_open_straggler_gather()` runs the dialog → worker → `_GatherProgressDialog.exec()` → `start_scan()`. `_build_activity_section()` and `organize_view._refresh_gate_screen()` branch their labels on `kind == 'straggler_gather'`. **No `main_window.py` changes** — Dashboard owns this dialog like it owns `_ChangeReviewDialog`.

**Resolver wrong-match fix (shipped alongside, applies regardless):** the filename + fuzzy-substring-stem fallbacks in `_CrateLoadWorker._resolve()` / `_ExportCrateWorker._resolve()` / `CrateManagerView._resolve_track()` (crate_manager.py) and `CrateReader._resolve_single()` could silently bind a crate ref to an *unrelated* same-ish file (e.g. a straggler outside the library). Now: `_inventory_by_name` stores `None` for any basename shared by 2+ files, so `.get(name)` name-only resolution refuses to guess; the `stem in cs or cs in stem` substring block is deleted everywhere; `crate_reader` requires exactly one `p.name == fname` match. Honest side effect: a few refs that used to fuzzy-"resolve" now read as unresolved — which is what the straggler banner then addresses.

**2026-08-29 copy + layout pass (Jace):** banner is `N Potential Duplicates Found in Your Library` / straggler banner `N Track(s) In Your Crates Has/Have Been Found Outside of Your Library` (verb agrees with count), sub `CrateSort can only manage files in the directory selected on startup • Bring them in to manage them.`, banner button **Move Them In**. Dialog headline **Move Tracks Into Library**, primary button **Move N Files In** / **Move Files In** at zero, "Not Now" and primary on their own row *below* the dismiss checkbox. Summary line: `N files • X MB will be moved from: <folder(s)>` when something is checked, plain `Select tracks to move them into your library.` when nothing is (no phantom "0 files" count). All checkboxes use `checkbox-checked.svg`/`checkbox-unchecked.svg` via the local `_style_checkbox()` helper — **never the bare theme-default orange indicator fill** (Jace has flagged this repeatedly; see `[[feedback_...]]` pattern). The folder list `QScrollArea` is `setFixedHeight(min(300, rows.sizeHint()+2))` with a `showEvent` recompute — a QScrollArea's default Expanding vertical policy otherwise stretched it to fill the dialog and left a big gap under one or two rows.

**Fast-follows (documented, not built):** per-file review UI (currently per-source-folder), cross-`/Volumes` straggler location, a Cancel button on the progress dialog, mid-eliding very long non-`~` source paths in the folder rows.

**Tested:** synthetic end-to-end (`detect_stragglers` → move → `PathRewriter` → re-detect shows 0; backups written), resolver unit checks (unique resolves, ambiguous/fuzzy do not), offscreen dialog construction + copy + checkbox QSS + scroll fit at 1/2/6/15 folders, headless `MainWindow` boot. pytest still not in the dev venv — verified by direct execution.
