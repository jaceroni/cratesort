# CrateSort — Library Browser Rebuild + Classification Fixes

## Context

The Library Browser was built as a flat track list in the last session. 
Based on extensive user testing, it needs to be rebuilt as an artist-nested 
view (matching the classification view pattern) with full inline editing. 
Several classification view and dashboard fixes are also included.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

---

## Part 1: Classification View Fixes

### Fix 1: Add dedicated Comments column

Add a "Comments" column that is ALWAYS visible (not hidden/shown based on 
expand state). Full column order for classification view:

1. Artist
2. Tracks
3. Confidence
4. Proposed Genre
5. Current Genre
6. **Comments** (NEW — always visible)
7. Status
8. File Path

Artist rows: blank. Track rows: file's comment metadata, truncated with 
tooltip. Column resizable, default ~120px.

### Fix 2: Artist genre change must update display

When right-clicking an artist and changing genre, the Proposed Genre column 
text must update immediately. The genre sidebar counts must also update. 
Currently the session state updates but the visible cell text does not 
refresh.

### Fix 3: Apply "The" handler in classification view

All artist names must display in sort form: "Natural Four, The" not 
"The Natural Four". "Futures, The" not "The Futures". The "The" handler 
from Phase 2 must be applied to artist names before displaying them in 
the classification view.

### Fix 4: Apply artist consolidation in classification view

"The Gap Band" and "Gap Band, The" are showing as separate entries. The 
artist consolidator must run as part of the classification pipeline before 
displaying results. Merge candidates should be consolidated automatically 
when they're clearly the same artist (like formatting differences), or 
flagged for user review when ambiguous.

### Fix 5: "Edit Tags..." → "Edit Style Tags..."

Rename the right-click option from "Edit Tags..." to "Edit Style Tags..." 
everywhere it appears in the classification view. The dialog title should 
also say "Edit Style Tags."

---

## Part 2: Dashboard Fixes

### Fix 6: Genre table — left-align header and add padding

- Left-align the "GENRE" column header
- Add ~25px left padding to header and all genre row text
- Align header and content visually

### Fix 7: Tracks column — wider and centered

- Increase TRACKS column width slightly
- Center-align track count numbers under the header

### Fix 8: Spacing around "What's next?" banner

Add ~50px vertical space above and below the guidance banner.

### Fix 9: Remove orphan stems warning (if still present)

Remove the orphan stems warning from the dashboard entirely.

---

## Part 3: Library Browser — Complete Rebuild

The current flat-list Library Browser needs to be rebuilt from scratch as 
an artist-nested view with full editing capabilities.

### Structure: Artist → Track nesting

Same expand/collapse pattern as the classification view:

**Artist rows (collapsed)** — one row per artist showing:
- Artist name (using "The" handler sort form)
- Track count
- Genre (the CrateSort-assigned genre, single column)
- Style Tags (user-created tags, if any)
- File Path (common path or "Multiple locations")

**Track rows (expanded)** — click/expand artist to see tracks:
- Title (from metadata)
- Album
- Duration (M:SS)
- Format (MP3, WAV, etc.)
- Genre (file's genre — useful to compare with artist-level classified genre)
- BPM
- Year
- Bitrate
- Style Tags
- Comments (from metadata, truncated with tooltip)
- File Path

### Filter bar

- **Search field**: Real-time filter across artist, title, album, filename. 
  Case-insensitive.
- **Genre filter dropdown**: "All Genres" default, then each CrateSort genre 
  plus Unclassified.
- **Format filter dropdown**: "All Formats" default, then each format found.
- **"Clear Filters"** button to reset.
- **NO confidence filter** — confidence is a classification-phase metric, 
  not relevant in the library browser.

### Single "Genre" column

Replace the previous "Classified Genre" and "File Genre" dual columns with 
ONE column called **"Genre"**. Shows the CrateSort-assigned genre if 
classification has been run. If not classified, shows the raw file genre 
tag in muted/italic text.

At the track level, show the file's actual genre tag (which may differ 
from the artist-level classified genre).

### "Style Tags" column

Add a **"Style Tags"** column showing user-created style labels (Boom Bap, 
Jazzy Hip-Hop, Neo Soul, etc.). Editable via right-click "Edit Style Tags..."

### Inline editing (double-click)

Double-clicking any cell on a TRACK row opens it for inline editing:
- Artist, title, album, genre, BPM, year, comments — all editable
- Cell becomes a text input field
- Enter or click-away to confirm
- Escape to cancel
- Changes save to the session data

Artist rows: double-click expands/collapses (no inline editing on artist 
rows — use right-click for artist-level changes).

### Right-click context menu — CONSISTENT with classification view

**Artist rows** (same as classification view):
- Approve
- Change Genre...
- Mark for Review

**Track rows** (same as classification view):
- Reassign Artist...
- Change Genre...
- Edit Style Tags...
- Show in Finder
- Copy Artist
- Copy Title
- Copy File Path

Same menus, same options, everywhere. No view-specific differences.

### Column behavior

- ALL columns resizable by dragging header edges
- ALL columns sortable by clicking headers
- **Columns draggable/reorderable** — user can drag column headers to 
  rearrange order. Use QHeaderView.setSectionsMovable(True). Column order 
  persists between sessions via QSettings.
- **Minimum column widths** — every column must be at least wide enough to 
  show its full header text without clipping
- ALL content left-aligned (headers and cell content). No right-aligned 
  numbers, no centered text.

### Album art panel in sidebar

Add a **170x170px area** in the sidebar, below the navigation buttons. 
When any track is selected (clicked) in ANY view (library, classification, 
crates, etc.), this panel shows the track's embedded album art.

- Read album art from the file's ID3 tags via mutagen
- Scale to fit the 170x170 area while maintaining aspect ratio
- If no art embedded, show a placeholder (muted vinyl record icon or the 
  CrateSort mascot silhouette)
- Updates whenever a track is selected in any view
- The scanner should be updated to extract embedded art (as raw bytes or 
  a QPixmap) and store it on the TrackRecord

### If no classification has been run

- Genre column shows raw file genre tag in muted/italic
- A subtle banner at top: "Classification has not been run. Genres shown 
  are from file metadata. Run classification from the Dashboard."

### Performance

Use QTreeWidget (matching classification view) rather than QTableView. 
The artist-nesting pattern works naturally with QTreeWidget. For large 
libraries, lazy-load child track rows on expand rather than pre-building 
all children.

---

## Part 4: App-wide consistency

### Left-align everything

All column headers and cell content across ALL views (dashboard, 
classification, library) should be left-aligned. No right-aligned numbers, 
no centered text except where explicitly noted (dashboard stat card numbers 
can stay centered).

### Same theme rules everywhere

- Selected rows: orange background (#D17D34), dark text (#2F2F2F)
- No left-side selection indicator anywhere
- Hover on unselected rows: #383838
- No system blue anywhere
- Checkboxes: #666666 border, cream fill when checked
- Font sizes: 14px body, 20px headings, 12px muted

---

## Testing

### Classification fixes:
1. Delete classification_session.json
2. Classify library
3. Verify Comments column visible (8 columns total)
4. Change D'Angelo's genre to Funk/Soul — verify column updates immediately
5. Verify "The" artists show in sort form (Natural Four, The)
6. Verify no duplicate Gap Band entries
7. Right-click a track — verify "Edit Style Tags..." (not "Edit Tags...")

### Dashboard fixes:
8. Genre header left-aligned with padding
9. Track counts centered
10. Spacing around guidance banner
11. No orphan stems warning

### Library Browser:
12. Click Library in sidebar — verify artist-nested view loads
13. Expand an artist — verify tracks show underneath
14. Search for an artist — verify real-time filtering
15. Filter by genre — verify it works
16. Double-click a track cell — verify inline editing
17. Right-click artist row — verify artist context menu
18. Right-click track row — verify track context menu
19. Drag a column header — verify reordering works
20. Verify all content left-aligned
21. Click a track — verify album art appears in sidebar panel
22. Verify no system blue, correct selection colors

Launch and verify everything works.
