# CrateSort — Bug Fixes, Dashboard Polish & Library Browser View

## Context

The classification view is polished. A few bugs remain plus dashboard 
tweaks, then we're building the Library Browser view.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

---

## Part 1: Classification Bug Fixes

### Fix 1: Add dedicated Comments column to classification view

Comments need their own dedicated column that is ALWAYS visible — not 
hidden when rows are collapsed and appearing when expanded. The table 
columns should never shift or jump based on expand/collapse state.

Add a "Comments" column as the 6th column. Full column order:

1. Artist
2. Tracks  
3. Confidence
4. Proposed Genre
5. Current Genre
6. **Comments** (NEW)
7. Status
8. File Path

**Artist rows**: Comments column blank (or "—").
**Track rows**: Shows the file's comment/notes from ID3 metadata. Truncate 
long comments with ellipsis, full comment as tooltip on hover.

Column is resizable like all others. Default width ~120px.

Remove any previous approach that tried to stuff comments into the Current 
Genre column position on track rows.

### Fix 2: Artist genre change doesn't update display

When the user right-clicks an artist and changes genre (e.g., D'Angelo 
from Hip-Hop/Rap to Funk/Soul):

1. The Proposed Genre column text must update to show the new genre
2. The genre summary sidebar (left panel) must update counts — if artist 
   moved from Hip-Hop/Rap to Funk/Soul, Hip-Hop/Rap count decreases and 
   Funk/Soul count increases
3. This must work BEFORE approving — the "Edited" state should show the 
   new genre immediately
4. After approving, the genre should persist

The bug is that session state is updated but the QTreeWidgetItem text is 
not being refreshed in the Proposed Genre column.

---

## Part 2: Dashboard Polish

### Fix 3: Genre table — left-align header and add padding

In the dashboard genre distribution table:
- Left-align the "GENRE" column header text (currently centered)
- Add ~25px left padding to both the header and all genre row text
- The genre names and the header should be visually aligned with each other

### Fix 4: Tracks column — wider and centered numbers

- Increase the width of the "TRACKS" column slightly so numbers aren't 
  cramped against the edge
- Center-align the track count numbers under the "TRACKS" header

### Fix 5: Spacing around "What's next?" banner

Add ~50px of vertical space above the "What's next?" guidance banner 
(between the drag handle and the banner) and ~50px below it (between the 
banner and the ACTIONS header). Currently too tight on both sides.

### Fix 6: Remove orphan stems warning

If this wasn't fully removed in the last round, remove the "X orphan 
.serato-stems file(s) found with no matching audio" warning from the 
dashboard entirely. Users cannot act on it.

---

## Part 3: Library Browser View

### What this view is

The Library Browser replaces the "Library — Coming in the next session" 
placeholder in the sidebar. It shows every track in the library as a flat, 
searchable, sortable, filterable table. This is where the user goes to see 
everything CrateSort knows about their files.

### Layout

**Top bar**: Search field + filter dropdowns + Clear Filters button
**Main area**: Full-width table of all tracks

### Search and filter bar

- **Search field**: Real-time filtering as you type. Searches across artist, 
  track title, album, and filename. Case-insensitive.

- **Genre filter dropdown**: "All Genres" default, then each of the 12 
  CrateSort genres plus "Unclassified." Filters to tracks classified in 
  the selected genre. Uses classified genre if available, raw genre tag 
  if not.

- **Format filter dropdown**: "All Formats" default, then each format found 
  in the library (MP3, WAV, FLAC, M4A, MP4, M4V, etc.).

- **Confidence filter dropdown**: "All Confidence" default, HIGH, MEDIUM, 
  LOW, Unclassified.

- Filters stack — Genre: Blues + Format: MP3 shows only Blues MP3 files.

- **"Clear Filters"** text button to reset everything.

### Table columns

Flat list of every track (not grouped by artist):

1. **Artist** — from metadata
2. **Title** — track title from metadata
3. **Album** — album name from metadata
4. **Duration** — formatted M:SS
5. **Classified Genre** — CrateSort-assigned genre from classification 
   session. If not classified, show raw genre tag in muted/italic text 
   with "(raw)" suffix.
6. **File Genre** — raw genre tag currently in the file's metadata
7. **Format** — file extension (MP3, WAV, etc.)
8. **BPM** — if tagged, otherwise blank
9. **Year** — from metadata
10. **Bitrate** — in kbps
11. **Comments** — from metadata, truncated with tooltip
12. **File Path** — full path, truncated with tooltip

All columns:
- Sortable (click header to sort, click again to reverse)
- Resizable (drag column edges)
- Default widths wide enough to show content without excessive clipping

### Table behavior

- Loads all tracks from the scanner results on view activation
- If classification_session.json exists, enriches rows with classified genre 
  and confidence data
- Runs scanner in background thread if data isn't already loaded (show 
  progress indicator)
- Right-click context menu on any row:
  - "Show in Finder" — opens the file's folder (macOS: open -R, 
    Windows: explorer /select)
  - "Change Genre..." — change this track's classified genre
  - "Edit Tags..." — edit style tags
  - "Copy Artist" — copies to clipboard
  - "Copy Title" — copies to clipboard
  - "Copy File Path" — copies to clipboard
- Row selection: orange background with dark text (matching classification 
  view styling — same theme rules apply)
- Hover: subtle #383838 background on unselected rows
- No left-side selection indicator
- Checkbox column NOT needed — this is a browse view, not an approval view

### If no classification has been run

- "Classified Genre" column shows "Not classified" in muted text for all rows
- A subtle banner at the top: "Classification has not been run yet. Genre 
  assignments shown are from file metadata only. Run classification from 
  the Dashboard for CrateSort genre assignments."

### Performance

Use QTableView with a custom QAbstractTableModel instead of QTableWidget. 
This handles large libraries (10,000-50,000+ tracks) much better:
- Model holds the data, view only renders visible rows
- Sorting handled by QSortFilterProxyModel
- Filtering handled by the same proxy model
- Search also routes through the proxy model

For the test library (96 files) this is overkill, but it's the right 
architecture for real-world library sizes.

### Styling

- Same dark theme as the rest of the app
- Same font sizes as established
- Column headers: cream text on dark panel background
- Alternating row colors for readability (subtle: #1a1a1a and #222222)
- Selected rows: orange with dark text
- No system blue anywhere

---

## Testing

After implementing everything:

### Classification fixes:
1. Delete classification_session.json
2. Launch, load library, classify
3. Expand any artist — verify Comments column is visible with 8 columns total
4. Right-click D'Angelo → Change Genre → Funk/Soul
5. Verify Proposed Genre column updates immediately to Funk/Soul
6. Verify genre sidebar counts update
7. Approve D'Angelo — verify genre sticks

### Dashboard fixes:
8. Go to Dashboard
9. Verify GENRE header is left-aligned with ~25px padding
10. Verify track counts are centered in the TRACKS column
11. Verify spacing above and below "What's next?" banner
12. Verify no orphan stems warning

### Library Browser:
13. Click "Library" in sidebar — verify the browser loads (not placeholder)
14. Verify all tracks are listed in a flat table
15. Type in the search box — verify real-time filtering
16. Select a genre from the dropdown — verify filtering
17. Stack filters (genre + format) — verify they combine
18. Click a column header — verify sorting
19. Right-click a track — verify context menu with Show in Finder, 
    Copy options
20. If classification was run, verify classified genre column shows data
21. If not run, verify "Not classified" muted text and suggestion banner

Launch and verify everything works.
