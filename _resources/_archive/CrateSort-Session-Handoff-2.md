# CrateSort — Session Handoff

This document brings the next planning chat up to speed on exactly where CrateSort development stands.

---

## What Was Accomplished This Session

### Crate Manager — Major Polish (Prompts 1–16)
The Crate Manager went through an extensive polish cycle. All of these are confirmed working:

- `#` position column — numeric sort, auto-width, always default sort on open
- Sort persistence — global across all crates and survives all operations
- Drag to reorder tracks within track panel — teal drop indicator, writes to `.crate` file, reload-after-write pattern
- Drag tracks from track panel to a different crate — duplicate prevention, teal feedback
- Drag to reorder crates in crate tree — writes to `neworder.pref`
- Drag sub-crate to top level — working
- Reparent crate into another (hover-to-expand) — working
- Delete key + modal confirmation for tracks and crates
- Parent crate track panel shows combined total of own + all sub-crate tracks
- `#` column numeric sort (integer UserRole, not string sort)
- Sub-crate expand indicators
- Parent crate track counts include sub-crate totals
- Crate tree fully styled with `CrateItemDelegate` — all four states working
- Sub-crate darker background grouping (`#222222`)
- Row heights consistent app-wide (36px)
- Full grid borders across all track listing views
- Library hover and selection branch states edge-to-edge
- Alternating row colors across all views
- Tab switch preserves crate tree expanded state and selection
- Column width persistence via QSettings
- Separator lines between crate tree rows
- Tree state preserved after every operation

### Crate Order Written to Serato
- `crate_writer.py` — `write_crate_order()` writes to `_Serato_/neworder.pref` (UTF-16 BE)
- `crate_reader.py` — `read_crate_order()` reads from `neworder.pref` on startup
- Validated end-to-end: CrateSort reorders crates → `neworder.pref` updated → Serato respects order on next launch ✅
- Replaces the old `crate_order.json`-only approach

### Undo/Redo System (Phase 1)
- `src/utils/undo_manager.py` — Command pattern, 10-state stack, global across tabs
- 8 command classes: AddTracksCommand, RemoveTracksCommand, ReorderTracksCommand, CreateCrateCommand, DeleteCrateCommand, RenameCrateCommand, ReorderCratesCommand, ReparentCrateCommand
- Undo/Redo buttons in sidebar below album art — teal when active, gray when inactive
- Cmd+Z / Cmd+Shift+Z keyboard shortcuts
- Auto-tab switch when undoing cross-tab action
- Teal footer text describes what was undone/redone
- Confirmed working for all Crate Manager actions

### Modal Dialog Polish
- All dialogs: normal weight text (400), more padding, consistent button styles
- `_NameInputDialog` replaces all `QInputDialog.getText()` calls — full-width buttons
- Global QPushButton pressed/hover states defined in `theme.py` — consistent across entire app
- `_AddTracksDialog` — "Adding..." loading state on click

### Date Added Column
- `src/serato/database_reader.py` — new module, parses Serato `database V2` binary format
- Extracts `uadd` (Unix timestamp) per track, keyed by `pfil` (file path)
- Path normalization handles: `\uf022` (U+F022) → ` : `, absolute vs relative paths, BOM, mixed separators
- Track panel column 8 (TC_DATE) now populated — YYYY-MM-DD format, sorts chronologically via UserRole
- Confirmed working for all resolved tracks including those in folders with special characters

### Dashboard Redesign
- Complete rewrite of `src/gui/dashboard.py`
- New sections: Stats Strip, Changes Since Last Session, Recently Added Tracks, Library Health, Footer Bar
- Removed: Format breakdown, Genre distribution table, static placeholder text
- `src/utils/checkpoint.py` — checkpoint system for session-to-session change detection
- Change detection: crate renames (heuristic), new crates, removed crates, track count changes
- Confirmed: rename detection ✅, new crate detection ✅

### Serato Library Architecture (Locked Decision)
- `_Serato_/` must live on the same drive as media files
- CrateSort reads from and writes to `_Serato_/` at the media root
- CrateSort never auto-creates `_Serato_/` — shows guided message if not found
- Serato auto-detects `_Serato_/` at the root of any connected drive volume
- Validated full round-trip: CrateSort writes → Serato reads on next launch ✅

---

## Current Punch List — Next Session

### Dashboard (High Priority)
1. **Bug 2 — Track additions to existing crates not showing in Changes** — detection logic exists in checkpoint.py but not triggering correctly. Needs debug pass.
2. **Clicking change rows** — should navigate to the affected crate in Crates tab. Currently placeholder `›` arrows with no action.
3. **Recently Added Tracks threshold** — currently hidden if fewer than 3 matches in 30 days. May need to lower threshold or show a different message for small libraries.
4. **Bug 3 (future)** — Track metadata changes (artist, title, BPM edits in Serato) not detected. Requires per-track hashing in checkpoint. Not in scope yet.

### Crate Manager (Lower Priority)
5. **Undo/Redo Phase 2** — extend undo/redo to Library, Classification, and Organize tab actions
6. **Smart Crate Builder** — visual rule builder (genre + style + year + BPM range)
7. **Startup sync sequence** — Amber → Change Review → Green on every launch (not yet built)

### Upcoming Major Features
8. **Organize view** — the next major tab to build. Genre classification, folder restructuring, metadata cleanup.
9. **Stress test with real library** — point CrateSort at full Serato library (tens of thousands of files) and see what breaks at scale before building more.

---

## Architecture Notes for Next Session

### File structure additions this session
```
src/
  serato/
    database_reader.py    ← NEW: parses Serato database V2 for track add dates
  utils/
    checkpoint.py         ← NEW: session checkpoint for change detection
    undo_manager.py       ← NEW: Command pattern undo/redo system
```

### Serato file format findings (research confirmed)
- `.crate` files: only contain `ptrk` (track path). No timestamps, no metadata.
- `database V2`: TLV binary format, UTF-16 BE. Contains `uadd` (add timestamp), `pfil` (file path), and full track metadata per `otrk` record.
- `neworder.pref`: UTF-16 BE text. One `[crate]CrateName%%SubcrateName` entry per line between `[begin record]` and `[end record]`. This is Serato's canonical crate display order.
- `collapsed.pref`: tracks which parent crates are expanded/collapsed in Serato UI.
- Serato uses `\uf022` (U+F022 private-use) as a substitute for ` : ` in folder names within database V2 paths.

### Column constants — track panel (TC_*)
| Index | Constant | Name |
|-------|----------|------|
| 0 | TC_POS | # |
| 1 | TC_TITLE | Title |
| 2 | TC_ARTIST | Artist |
| 3 | TC_ALBUM | Album |
| 4 | TC_DURATION | Duration |
| 5 | TC_GENRE | Genre |
| 6 | TC_STYLE | Style Tags |
| 7 | TC_BPM | BPM |
| 8 | TC_DATE | Date Added |
| 9 | TC_FORMAT | Format |
| 10 | TC_YEAR | Year |
| 11 | TC_BITRATE | Bitrate |
| 12 | TC_COMMENT | Comments |
| 13 | TC_PATH | File Path |

**Always verify column indices before use — they shift when columns are added.**

### Prompts written this session
- CrateSort-Prompt-CrateManager-01 through 16 (crate manager polish)
- CrateSort-Prompt-UndoRedo-01, 02 (undo/redo system)
- CrateSort-Prompt-Dialogs-01, 02, 03 (dialog polish)
- CrateSort-Prompt-SeratoOrder-01 (neworder.pref write)
- CrateSort-Prompt-Research-01 (Serato file format research)
- CrateSort-Prompt-DateAdded-01 through 05 (Date Added column)
- CrateSort-Prompt-Dashboard-01, 02 (dashboard redesign)

---

## Standing Rules (Always Apply)

- **Always run Claude Code at Sonnet high effort** — medium effort causes incomplete reads and bugs
- **Every Claude Code prompt goes in an .md file** — never paste inline code blocks in chat
- **Verify imports before using any class** — add missing imports before using them
- **All track table operations use reload-after-write** — never manipulate table rows directly
- **Teal (`#428175`) = action. Orange (`#D17D34`) = selection.** Never swap.
- **36px row height** — app-wide standard, update all views simultaneously if changed
- **CrateSort is the single writer. Serato is the reader.**
- **`_Serato_/` must live on the same drive as media files**
- **Never auto-create `_Serato_/`** — show guided message instead
