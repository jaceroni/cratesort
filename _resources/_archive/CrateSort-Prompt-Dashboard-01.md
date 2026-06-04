# CrateSort — Dashboard Redesign (Prompt 29)

> **Run this at Sonnet high effort. Read every referenced file completely before writing any code. Before writing any code, verify that every class, method, and module you reference is already imported in the target file. Add any missing imports before using them.**

## Files to Read First

- `src/gui/dashboard.py` — primary file, complete rewrite of the dashboard content
- `src/gui/main_window.py` — understand how the dashboard is loaded and navigated to
- `src/gui/theme.py` — color constants
- `src/serato/crate_reader.py` — for reading crate data to populate stats
- `src/serato/database_reader.py` — for recently added tracks data
- `src/core/scanner.py` — for library health data (missing metadata, unclassified tracks)

---

## Design Specification

The dashboard is a living, session-aware command center. Every time CrateSort opens, the dashboard tells the user what changed, what's new, and what needs attention. It replaces the current static stats-only view.

### Color palette (must match rest of app exactly)
- Background: `#1a1a1a`
- Panel background: `#2F2F2F`
- Row separator: `#383838`
- Darker row bg: `#222222`
- Cream text: `#f1e3c8`
- Muted text: `#888888`
- Very muted: `#555555`
- Orange accent: `#D17D34`
- Teal action: `#428175`
- All buttons: normal font weight (400), no bold

---

## Layout — Four Sections

### Section 0 — Top Action Bar (already exists, keep as-is)
- Library path + Change Library link
- Three action buttons: Classify Library (orange), Manage Crates (teal), Organize Files (teal)
- Do not change this section

### Section 1 — Stats Strip (replace current stats)

Three stat cells in a horizontal row, separated by `#383838` dividers:

- **Total Tracks** — count of all tracks in the scanned library
- **Crates** — total number of crates loaded from `_Serato_/`
- **Metadata Complete** — percentage of tracks that have artist, title, genre, and year filled in. Show in teal if above 90%, orange if below.

Display as large orange numbers (22px, weight 500) with small uppercase muted labels below.

### Section 2 — Changes Since Last Session

Header: "CHANGES SINCE LAST SESSION" with a teal badge showing the count (e.g. "4 changes"). If no changes, show "No changes since last session" in muted text and hide the badge.

Each change row contains:
- A colored dot: teal for additions, orange for removals, gray for renames/other
- Description text in cream (e.g. "3 tracks added to Jazz", "Crate renamed: Blues → Jump Blues")
- Source and time in muted text ("via Serato · today")
- A right arrow `›` in muted color

Clicking a row navigates to the affected crate in the Crates tab.

**How to detect changes:** Compare the current state of `_Serato_/Subcrates/` against a checkpoint saved at `_CrateSort/checkpoint.json`. The checkpoint stores:
- A dict of crate name → track count
- A list of all crate names
- Timestamp of last save

On launch, read the current state and compare against the checkpoint. Differences = changes. Save a new checkpoint after the comparison. If no checkpoint exists (first launch), create one and show no changes.

The checkpoint file lives at `[serato_dir]/../_CrateSort/checkpoint.json` (sibling of `_Serato_/`).

### Section 3 — Recently Added Tracks

Header: "RECENTLY ADDED TRACKS" with a teal badge showing count of tracks added in the last 30 days.

Pull data from `database_reader.read_track_add_dates()`. Sort by date descending. Show the 3 most recent tracks with:
- Music note icon
- Track filename (or title if available from scanner)
- Genre tag pill (muted background, muted text)
- Date added (YYYY-MM-DD)

Show a "View all ›" link in teal at the bottom if there are more than 3.

If no date data is available, hide this section entirely.

### Section 4 — Library Health

Header: "LIBRARY HEALTH" with an orange badge showing issue count. If no issues, show a teal badge saying "All clear".

Check for these issues using data already loaded by the scanner:
- Tracks missing genre tags — show count + "Fix in Library ›" button
- Tracks not found in any crate — show count + "View tracks ›" button  
- Possible duplicate tracks (same title + artist) — show count + "Review ›" button (placeholder for now if duplicate detection not built)

Each row:
- Orange warning icon (`⚠`)
- Issue description in cream
- Action button (small, `#383838` background, cream text, 4px radius)

If no issues detected, show a single row: "✓ Library looks healthy" in teal.

### Footer Bar

Thin dark bar at the bottom of the dashboard:
- Left: "Last session: [date/time]" in muted text
- Right: Green dot + "Serato library synced" in teal text

---

## Checkpoint System

Create `src/utils/checkpoint.py` (or add to an existing utils module) with:

`save_checkpoint(serato_dir: str, crate_data: dict) -> None`
- Writes `_CrateSort/checkpoint.json` with current crate names, track counts, and timestamp

`load_checkpoint(serato_dir: str) -> dict | None`
- Reads and returns checkpoint data, or None if no checkpoint exists

`detect_changes(current: dict, previous: dict) -> list[dict]`
- Compares current crate state against checkpoint
- Returns list of change dicts: `{type: 'added'|'removed'|'renamed', description: str, crate_path: str}`

---

## What to Remove from Current Dashboard

Remove these from the current dashboard view:
- Format breakdown section (MP3 count, M4A count, WAV count etc.)
- Genre distribution table
- The "Your library is classified" placeholder text panel

Keep:
- The top action bar with the three buttons
- The library path display

---

## General Requirements

- All text normal weight (400) — no bold anywhere except stat numbers (500)
- Row heights consistent with rest of app (36px)
- Alternating row colors where applicable: `#242424` / `#2a2a2a`
- All buttons: teal `#428175` or muted gray `#3a3a3a`, white text, 6px radius, normal weight
- Section headers: 11px, uppercase, letter-spacing 0.08em, muted color `#888`
- Never crash if data is unavailable — show graceful empty states
- Dashboard must load fast — do not block on slow operations. Use cached data where available.
