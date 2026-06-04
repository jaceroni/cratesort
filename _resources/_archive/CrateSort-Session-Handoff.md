# CrateSort — Development Session Handoff

**Date:** May 31, 2026  
**Purpose:** This document summarizes everything discussed and built across 
an extensive planning/development conversation. Use it to continue CrateSort 
development in a new chat without losing context.

---

## Project Overview

**CrateSort** is a standalone desktop app (Python 3.x, PyQt6) that organizes 
a DJ's digital music library and manages their Serato DJ Pro crates. It's 
the digital counterpart to **CrateView** (vinyl collection management on 
WordPress). Together they form the **CrateSuite**.

**Tagline:** "Get your shit together."

**Dev directory:** `/Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort`  
**Test library:** `/Users/jacebrown/Desktop/cratesort-test-library`  
**Launch command:**
```
cd /Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort
PYTHONPATH=.. python3 src/gui/main_window.py
```

**Project plan:** CrateSort-Project-Plan-v5.md (locked)  
**Claude Code reference:** CLAUDE-CS.md (updated periodically)

---

## What's Been Built

### Engine Modules (all complete and tested)

| Module | File | Status |
|--------|------|--------|
| Scanner | `src/core/scanner.py` | ✅ Complete — walks directories, reads ID3 tags from all formats (MP3, WAV, FLAC, M4A, MP4, M4V), detects .serato-stems files, skips _Serato_ and DJ software directories |
| Genre Classifier | `src/core/classifier.py` | ✅ Complete — 13 parent genres (including Traditional), 400+ style-to-genre mappings, artist-level classification, three-tier confidence (style mapping → genre tag → folder hints), short-duration + purpose folder = Specialty rule, video files in purpose folders = Specialty |
| Filename Cleaner | `src/core/filename_cleaner.py` | ✅ Complete — strips track numbers, artist prefixes, remaster tags, sanitizes characters |
| "The" Handler | `src/utils/the_handler.py` | ✅ Complete — "The Doors" → "Doors, The" for sort/folder names, preserves full name in metadata |
| Metadata Fixer | `src/core/metadata_fixer.py` | ✅ Complete — proposes genre/style/sort-artist/year fixes, never touches comments or Serato frames |
| Artist Consolidator | `src/core/artist_consolidator.py` | ✅ Complete — detects name variants via substring, fuzzy, and pattern matching |
| Duplicate Detector | `src/core/duplicate_detector.py` | ✅ Complete — fast pass (metadata), deep pass (fingerprint) stubbed |
| File Organizer | `src/core/file_organizer.py` | ✅ Complete — copy-verify-delete with SHA-256, rollback logging, Serato path rewriting |
| Crate Reader | `src/serato/crate_reader.py` | ✅ Complete — reads all .crate files, builds hierarchy tree, 191 real crates tested |
| Crate Writer | `src/serato/crate_writer.py` | ✅ Complete — create, rename, duplicate, delete crates, add/remove tracks |
| Path Rewriter | `src/serato/path_rewriter.py` | ✅ Complete — updates crate file paths after file moves, dry-run mode |
| Normalizer | `src/utils/normalize.py` | ✅ Complete — shared normalization for artist/title comparison |

### GUI Views (built and iteratively polished)

| View | File | Status |
|------|------|--------|
| Main Window | `src/gui/main_window.py` | ✅ Complete — sidebar nav, QStackedWidget, album art panel, QPalette overrides for system blue |
| Theme | `src/gui/theme.py` | ✅ Complete — dark background (#1a1a1a), cream text (#f1e3c8), orange accent (#D17D34), teal secondary (#428175) |
| Dashboard | `src/gui/dashboard.py` | ✅ Complete — stats cards, genre distribution, contextual tips, action buttons at top, Change Library link |
| Classification View | `src/gui/classifier_view.py` | ✅ Complete — artist-grouped results with review/edit workflow (NO approval process) |
| Library Browser | `src/gui/library_browser.py` | ✅ Complete — artist-nested view with inline editing, full right-click menus |
| Crate Manager | `src/gui/crate_manager.py` | ✅ Built, in polish phase — crate tree, track contents, CRUD operations |

### Data Persistence

- **classification_session.json** — stored in `_CrateSort/` inside the library directory. Contains classified genres, artist entries, track data.
- **library_edits.json** — stored in `_CrateSort/`. Contains user edits from the Library Browser (genre changes, title edits, BPM, style tags, artist reassignments).
- **QSettings** — stored at OS level under `com.jwbc.CrateSort`. Contains library path, window geometry, column state, "always load" preference.

### Cross-View Data Sync

Genre changes must sync between all views:
- Classification session → Library Browser → Crate Manager
- Library edits → Classification view → Crate Manager
- Priority: library_edits track override > library_edits artist override > classification session > raw file metadata

---

## Key Design Decisions (locked in)

### Genre Taxonomy — 13 Parent Genres
Blues, Country, Electronic, Funk/Soul, Hip-Hop/Rap, House, Jazz, R&B, 
Reggae, Rock, Seasonal, Specialty, **Traditional**

- "Pop" is NEVER a valid genre
- Synth-Pop and New Wave → Rock (not Electronic)
- Breakdance / Park Jams → Funk/Soul (not Hip-Hop/Rap)
- Disco → Funk/Soul
- Traditional = pre-rock vocal pop (Sinatra, Dean Martin, Brenda Lee, etc.)

### "The folder is the home, the crate is the connection"
- One physical copy of each file in its genre folder
- Serato crates are references/bookmarks connecting the same file to multiple contexts
- No more using physical folders as pseudo-crates
- Reorganization is optional — users who prefer their chaos get full visibility without file moves

### One home per artist
- Each artist classified into exactly one genre
- All tracks by that artist inherit the genre for folder purposes
- Track-level genres can differ (for metadata/crate purposes) but the artist genre determines the physical folder location

### Artist genre and track genres are INDEPENDENT
- Changing an artist's genre does NOT cascade to tracks
- Changing a track's genre does NOT affect the artist
- Both are set independently through the same right-click menu

### No approval workflow
- Classification is review-and-fix, not review-and-approve
- Moving forward = implicit approval
- Status column shows blank (untouched) or "Modified" (changed by user)
- "Accept & Go to Library" button saves state and navigates forward

### Comments and Serato metadata are sacred
- CrateSort NEVER touches the comment field
- Serato custom ID3 frames (cue points, beat grids, markers) are NEVER modified
- Only genre tags, style tags, sort-artist, and year are proposed for changes

### Featured artists
- "DJ Quik feat. Sugar Free" → primary artist is DJ Quik
- Track lives under DJ Quik's artist entry
- Featured artist info stays in track metadata

### Style tags are independent between artists and tracks
- Artist style tags describe the artist's overall identity (e.g., "Psychedelic Rock")
- Track style tags describe a specific song's character (e.g., "Folk Rock")
- Neither auto-propagates to the other — set each one deliberately
- Both are editable via right-click "Edit Style Tags..." on their respective rows
- Both are queryable for future smart crate filtering

---

## UX Rules (established through testing)

### Interaction Model
- **Single click** = highlight row orange (visual focus)
- **Double click on artist** = expand/collapse to show/hide tracks
- **Double click on track cell** = inline edit (for editable fields only)
- **Shift/Cmd+click** = multi-select tracks (for batch genre changes)
- **Checkboxes** = batch selection for artists (for Set Genre, Select All)
- **Right-click** = context menu (consistent across ALL views)
- Highlight, multi-select, and checkboxes are independent systems
- Genre change on multi-selection applies to ALL visible selected items
- Only what's visible and selected gets changed (collapsed tracks excluded)

### Editable vs Non-Editable Fields (Library Browser & Crate Manager)
**Editable via double-click:** Title, Album, Style Tags, BPM, Year, Comments  
**NOT editable via double-click:** Artist (right-click Reassign), Genre (right-click Change Genre), Duration, Format, Bitrate, File Path

### Right-Click Menus (consistent everywhere)
**Artist rows:** Change Genre..., Edit Style Tags..., Mark for Review  
**Track rows:** Reassign Artist... (with autocomplete), Change Genre... (13 genre dropdown), Edit Style Tags..., Show in Finder, Copy Artist, Copy Title, Copy File Path  
**Crate Manager adds:** Remove from Crate

### Visual Feedback
- **Teal text flash (1.5s)** on rows when an edit is committed
- **Status messages** in footer/bottom bar for operations (teal confirmation)
- Flash only fires when text actually changed (not on click-away with no edits)
- Click-away auto-commits, Escape cancels

### Row Type Icons
- **Artist rows:** Person silhouette icon (18x14 pixmap, muted #a89b85)
- **Track rows:** Music note ♪ icon (tighter spacing, muted #a89b85)
- Both icons invert to dark (#2F2F2F) when row is selected (orange background)

### Selection Styling (app-wide)
- Selected row: orange background (#D17D34), dark text (#2F2F2F)
- No left-side selection indicator
- No border-radius on cells (sharp rectangles)
- No system blue anywhere (QPalette overrides in main())
- Hover on unselected rows: subtle #383838
- Checkboxes: #666666 border, cream fill when checked

### Album Art Panel
- 170x170 in sidebar, below Settings nav button, above version number
- Updates when clicking any track in any view
- Clears to placeholder when navigating to Dashboard, Settings, or Organize
- Drag-and-drop image replacement (no confirmation dialog)
- Right-click: Replace Art..., Remove Art, Save Art As...

### Dashboard Layout (top to bottom)
1. "Library Dashboard" heading + library path + "Change Library..." link
2. Action buttons (Classify Library, Manage Crates, Organize Files)
3. Stat cards (Files, Artists, Genre Tags, Complete Metadata %)
4. Format breakdown
5. Genre distribution table (with drag handle, left-aligned headers, ~25px padding)
6. Contextual tips banner (always visible, content changes based on workflow state)

### Classification View Layout
- **Top bar left:** Search field (wide) → Select All → Set Genre
- **Top bar right:** (empty — no approval buttons)
- **Bottom bar:** ← Back to Dashboard | Accept & Go to Library
- **Status column:** blank or "Modified" only
- **Confidence column:** HIGH/MEDIUM/LOW only (no "Confirmed")

---

## Known Issues / In-Progress Fixes

These items were identified during testing and a fix prompt was already 
created but may not have been fully verified:

1. **Sub-crate expand indicators** — crates with children may not show 
   expand arrows. Needs setChildIndicatorPolicy.
2. **Track search within crates** — need a search field to filter tracks 
   in the right panel of the Crate Manager.
3. **Remove from crate — loading feedback** — brief freeze with no 
   feedback when removing tracks.
4. **Crate tree collapses after track removal** — expanded state and 
   selection should be preserved.
5. **Music note icon spacing inconsistency** — Library Browser spacing 
   should match the Crate Manager's tighter spacing.
6. **Collaboration detection false positives** — hyphenated names like 
   Jean-Jacques Perrey and A-F-R-O were being flagged. Fix was submitted 
   but verify it's working.
7. **Launch dialog** — "Always load my last library" can get stuck on. 
   "Change Library..." on the dashboard resets it. QSettings key: 
   `always_load_last` under `com.jwbc.CrateSort`.
8. **Library flash on arriving from Accept** — a delayed rebuild was 
   causing the tree to collapse. Fix was submitted.
9. **Duplicate tracks in crates** — the Add Tracks dialog allows adding 
   the same track multiple times to one crate. Must check for existing 
   tracks and prevent duplicates. Tracks already in the crate should be 
   grayed out in the Add Tracks dialog. CrateWriter should enforce 
   uniqueness as a safety net.
10. **Auto-select and scroll to newly added track** — after adding a track 
    to a crate, it should be highlighted and scrolled to center in the 
    track list so the user can see it immediately.
11. **Multi-select genre change applies to all visible selected items** — 
    right-click → Change Genre on a multi-selection must apply to EVERY 
    visible selected item (artists and tracks). Only what's visible and 
    selected gets changed. Implemented but verify working in all views.
12. **Artist-level genre changes in Library Browser must persist** — 
    changing an artist's genre in the Library Browser must save to 
    library_edits.json and trigger teal flash. Was fixed but verify.
13. **Classification view: no genre cascade** — changing an artist's 
    genre must NOT cascade to tracks. Artist and track genres are 
    independent. _cascade_genre_to_children was disconnected but verify.

---

## What's Next (in order)

### Immediate
- Verify latest Crate Manager fixes (sub-crate indicators, track search, 
  remove feedback, tree state preservation, icon spacing)
- Apply duplicate track prevention and auto-scroll fixes (prompt ready)
- Full Crate Manager walkthrough to confirm everything works
- Update CLAUDE-CS.md with current project state

### Next Build Targets
1. **Organize View** — the preview-approve-execute flow for file reorganization. 
   Wires up the File Organizer engine to a GUI showing every proposed 
   move, rename, and metadata change. User reviews and approves before 
   anything executes. Rollback available after execution.

2. **Settings View** — library path management, "always load" toggle, 
   taxonomy editor, "The" handler toggle, genre list customization.

3. **Smart Crate Builder** — visual rule builder for Serato smart crates. 
   Query by genre + style tags + year range + BPM range + comments. 
   Better than Serato's clunky rule UI.

4. **CLAUDE-CS.md Update** — needs a full refresh to capture everything 
   built since the last update.

5. **App Packaging** — PyInstaller → .app for macOS.

### Future / Roadmap
- Export engine (Serato, Pioneer/Rekordbox, Universal M3U)
- CrateView Bridge plugin
- Rekordbox and Engine DJ modules
- Subscription/licensing architecture
- Audio fingerprint deep pass for duplicate detection

---

## Style-to-Genre Mapping Table

The comprehensive mapping table is at:
`/mnt/user-data/outputs/CrateSort-Style-Genre-Map.md`

400+ styles mapped to 13 parent genres. Includes crossover rules, 
junk tag handling, "Pop" reclassification logic. This is baked into 
`classifier.py` as a Python dict.

---

## Brand Rules (strict)

- Always camelCase: **CrateSort**, **CrateView**, **CrateSuite**
- Never: "Crate Sort", "Crate View", "Crate Suite"
- Dark background (#1a1a1a) with warm accents
- Primary accent: Satsuma Orange (#D17D34)
- Secondary accent: Retro Teal (#428175)
- Text: Cream (#f1e3c8), Parchment (#f2dbb3), Muted (#a89b85)
- Headlines: Charter font (in assets/fonts/)
- Body: Open Sans or system sans-serif
- Logo SVGs in assets/logo/ (dark-background versions)

---

## Model & Effort Recommendations for Claude Code

- **Sonnet, low-to-medium effort:** CSS fixes, single-file changes
- **Sonnet, high effort:** Multi-file integrations, new views, engine modules
- **Opus, high effort:** Complex multi-step pipelines (not needed yet)

---

## Test Library Contents

The test library at `~/Desktop/cratesort-test-library/` contains:
- 96 files (70 MP3, 13 MP4, 4 M4A, 4 WAV, 4 M4V, 1 FLAC)
- 3 top-level directories: MP3/, Music Videos/, Sound FX/
- Mixed organization: genre folders, purpose folders (_Drops, _Unsorted, 
  _Samples, _Tributes), artist subfolders, loose files
- Real `_Serato_/` folder with 191 crates (copied from live DJ setup)
- Serato stems files (.serato-stems)
- Various problems to test: "The" artists, fragmented artist names, 
  dirty filenames, wrong genre tags, missing metadata, short DJ drops

---

## Important Technical Notes

- `setBackground()` on QTreeWidget items is overridden by stylesheets — 
  use `setForeground()` for text color flash or viewport overlay for 
  background flash
- `serato-crate` library drops osrt/ovct tags — use raw functions for 
  modifications
- Library Browser inline edits stored in `library_edits.json`, not 
  written to actual files yet (that's the Organize step)
- QPalette Highlight/HighlightedText must be set BEFORE stylesheet to 
  kill system blue
- Qt's `&` in button text is a mnemonic indicator — use `&&` for literal
- Right-clicking with ExtendedSelection can deselect multi-selection — 
  snapshot selection in context menu handler before menu opens
- Global `sys.excepthook` override in main() prevents slot exceptions 
  from calling abort()
