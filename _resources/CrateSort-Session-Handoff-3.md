# CrateSort — Session Handoff (Session 3)

This document brings the next planning chat up to speed on exactly where CrateSort development stands.

---

## What Was Accomplished This Session

### Dashboard Redesign & Animations
- Complete rewrite and styling of `src/gui/dashboard.py` (Dashboard stack index 2).
- Animated stat cards (`_AnimatedStatCard` widget class) for Total Tracks, Total Crates, Unique Artists, and Hours of Music, featuring count-up animations on load with cubic ease-out. Click to replay is also supported.
- Action cards (`_WorkflowCard` / `_ClickableCard` widget classes) for navigation (Change Library, Classify Library, Manage Crates, Organize Media) and creation (New Crate, New Smart Crate).
- Combined Recent Activity feed listing checkpoint changes (additions, removals, renames) and recently added tracks (last 30 days, capped at 10 items).

### Unified Launch Screen
- Context-aware launch screen directly in `DashboardWidget` stack index 0 (replaces popups).
- Shows mascot logo (`cs-logo-mascot-stacked.svg`), tagline, and context-dependent UI:
  - First-time users see "Select Music Library…" button.
  - Returning users see their last-loaded path, a primary "Load Library" button, secondary "Choose Different Library" button, and an "Always load without asking" checkbox.
- `_LaunchDialog` has been permanently deleted from the codebase.

### Dashboard Signal Wiring
- Connected the four new action card signals in `MainWindow` inside `src/gui/main_window.py`:
  - `crates_requested` $\rightarrow$ navigates to the Crates tab.
  - `organize_requested` $\rightarrow$ navigates to the Organize tab.
  - `new_crate_requested` $\rightarrow$ navigates to the Crates tab and calls `_on_new_crate()` on `CrateManagerView` (hasattr-guarded).
  - `new_smart_crate_requested` $\rightarrow$ navigates to the Crates tab and calls `_on_new_smart_crate()` on `CrateManagerView` (hasattr-guarded).

### Bug 2 Fixed
- Resolved path matching issues in `src/utils/checkpoint.py` via `_normalize_path` helper, resolving mounting, case, and trailing slash differences.
- Implemented `None` guards for failed scans to prevent false "tracks removed" reports.

---

## Current Punch List — Next Session

### 1. Real-Library Stress Test (High Priority)
- Point CrateSort at a real Serato library containing tens of thousands of tracks.
- Identify and resolve performance bottlenecks or read errors at scale.

### 2. Dialog Methods on CrateManagerView
- Build the `_on_new_crate()` and `_on_new_smart_crate()` methods on `CrateManagerView` in `src/gui/crate_manager.py` (which are currently hasattr-guarded on launch).

### 3. Organize View
- Design and build the "Organize" tab (index 3), which will handle actual file movements, directory structure reorganization, and cleanup.

### 4. Startup Sync Sequence
- Implement the sync review cycle (Amber $\rightarrow$ Change Review $\rightarrow$ Green) on application start, handling changes Serato has made since the last session.

---

## ⏸ Tabled: Performance Optimization (Research Complete — Do Not Lose)

Stress-tested against a real Serato library: **172 crates, 9,391 tracks in Hip-Hop alone.** Two specific bottlenecks identified and root-caused. No code written yet. Pick this up after the Organize tab.

### Bottleneck 1 — Crates Tab Initial Load: ~3 seconds

**Root cause:** `CrateManagerView.load()` calls `_clear_date_cache()` on every tab switch, forcing a full re-parse of the Serato `database V2` binary file (9,391+ track add-date entries) every single time. This is the dominant cost.

**Fix:** Move `_clear_date_cache()` out of `load()`. Only clear the cache in `_on_library_changed()` — i.e., when the library path actually changes, not on tab switch.

**File:** `src/gui/crate_manager.py` → `load()` method (~line 644).

---

### Bottleneck 2 — Large Crate Click: 1–2 seconds (e.g. Hip-Hop with 9,391 tracks)

**Root cause:** `_populate_track_table()` creates **9,391 × 14 ≈ 131,000 `QTableWidgetItem` objects** synchronously on the main thread in a single blocking call. The UI freezes until all are built.

**Fix:** Batch the row insertion. Populate the first 500 rows immediately, then use `QTimer.singleShot(0, ...)` to stream subsequent batches of 500. The table appears instantly; remaining rows load in the background without blocking the UI.

**File:** `src/gui/crate_manager.py` → `_populate_track_table()` method (~line 1239).

---

### What Is Fine — Do Not Touch
- Scroll performance in the table: zero lag even at 9,391 rows (Qt's virtual scroll is working correctly).
- Crate search filter: instant (hides items rather than rebuilding).
- Library Browser tree: fast (lazy-loads children on expand).
- Dashboard stat cards and activity feed: fast.

---

## Architecture Notes & Standing Rules

### File Structure & Serato Files
- CrateSort reads/writes to `_Serato_/` at the media drive root (never auto-creates it).
- `.crate` files contain only path data. Metadata and add dates come from the binary `database V2` file (UTF-16 BE).
- `neworder.pref` stores the display order of Serato crates.
- `collapsed.pref` stores crate expansion states.

### Column Constants (Track Panel)
Verify column indices before use:
* `0`: `#` (TC_POS)
* `1`: Title (TC_TITLE)
* `2`: Artist (TC_ARTIST)
* `3`: Album (TC_ALBUM)
* `4`: Duration (TC_DURATION)
* `5`: Genre (TC_GENRE)
* `6`: Style Tags (TC_TAGS)
* `7`: BPM (TC_BPM)
* `8`: Date Added (TC_DATE)
* `9`: Format (TC_FORMAT)
* `10`: Year (TC_YEAR)
* `11`: Bitrate (TC_BITRATE)
* `12`: Comments (TC_COMMENT)
* `13`: File Path (TC_PATH)

### Standing Rules (Always Apply)
- **Always run at high effort** to ensure thorough context reads.
- **Teal (`#428175`) = action, Orange (`#D17D34`) = selection**. Do not mix.
- **36px row height** app-wide for tables.
- **Reload-after-write**: reload the `.crate` from disk rather than manipulating table rows directly.
