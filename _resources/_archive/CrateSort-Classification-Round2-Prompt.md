# CrateSort — Classification View Round 2: UI Polish & Improvements

## Context

The classification view is functional. The user has done extensive testing 
and provided detailed feedback. This session addresses all UI and behavior 
improvements. Some are visual fixes, some are functional enhancements.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing so we get 
a fresh classification run.

## Fixes and improvements (in priority order)

### 0. Sidebar logo padding

The CrateSort wordmark logo in the sidebar header needs equal padding on 
all four sides. Currently the left/right spacing is good but top/bottom 
is too tight. Match the top and bottom padding to whatever the left and 
right padding is, so the logo has equal breathing room on all sides.

### 1. Kill ALL system blue — app-wide theme fix

Qt's default blue is still appearing in:
- Row selection highlights
- Checkbox checkmarks
- Any other widget that uses system selection/accent colors

In the app stylesheet (theme.py), override EVERY selection and highlight 
state globally. Search for any widget that could use system blue and kill it:

```
QTreeWidget::item:selected { background: #D17D34; color: #2F2F2F; }
QTreeWidget::item:selected:active { background: #D17D34; color: #2F2F2F; }
QTreeWidget::item:selected:!active { background: #D17D34; color: #2F2F2F; }
QCheckBox::indicator:checked { /* custom orange/cream checkbox */ }
QTreeWidget::indicator:checked { /* same */ }
```

Test by clicking rows, checking boxes, selecting items in every view. 
NO blue anywhere.

### 2. Selected row styling

When a row is clicked/selected:
- Background: #D17D34 (orange)
- Text: #2F2F2F (dark) — NOT cream/white, it's too heavy on orange
- Left indicator: teal (#428175)
- Selection shows IMMEDIATELY on click — not after moving cursor away
- Hover state does NOT override selection. Hover on unselected rows is a 
  subtle background shift (#383838). Hover on a selected row keeps the 
  orange.

### 3. Expanded parent row — no orange fill

When an artist row is expanded to show tracks, the parent row should NOT 
turn solid orange just because it's expanded. The expand/collapse is already 
visually clear from the child rows appearing. Only the CLICKED/SELECTED row 
gets orange, and only when actively selected — not as a persistent state 
from expanding.

### 4. Checkbox styling — app-wide

Override all checkbox styling in theme.py:
- Unchecked: border color #a89b85 (muted), transparent fill
- Checked: fill color #D17D34 (orange), checkmark color #f1e3c8 (cream)
- On orange selected rows: border #2F2F2F (dark), checkmark still cream
- No blue anywhere
- Checkboxes should be clearly visible against both dark and orange backgrounds

### 5. Increase base font size — app-wide

Bump all font sizes up ~2px proportionally:
- Body/table text: 13px (was ~11px)
- Headings: 18px (was ~16px)  
- Small/muted text: 11px (was ~9px)
- Sidebar nav: proportional increase
- Status bar: proportional increase
Apply to everything — tables, sidebar, dialogs, buttons, status bar.

### 6. Rename "Current Tags" column to "Current Genre"

The column currently labeled "Current Tags" shows the existing genre 
metadata from the file, not user-created tags. Rename to "Current Genre" 
to avoid confusion with the tags/styles concept.

### 7. Redesign expanded track rows

When an artist row is expanded, the child track rows currently show 
confusing data that doesn't align with column headers. Redesign:

Track rows should show these fields aligned to the parent columns:
- **Artist column** → Track title (from metadata, not filename)
- **Tracks column** → Duration (formatted M:SS)
- **Confidence column** → Format (MP3, WAV, M4V, FLAC, etc.)
- **Proposed Genre column** → Current genre tag on this file
- **Current Genre column** → (leave blank or show style tags if any)
- **Status column** → (leave blank — status is artist-level)
- **File Path column** → Full file path

Do NOT show the filename separately if it's redundant with the track title. 
The filename is already visible in the file path column.

### 8. Visual state tracking for edited rows

Four states with distinct visual treatment in the Status column:
- **Pending** — muted text color (#a89b85). Default state after classification.
- **Edited** — teal (#428175). User has changed genre, reassigned artist, or 
  modified something but hasn't approved yet.
- **Approved** — soft green (#6B9E78). User confirmed the classification.
- **Flagged** — amber (#D4A04A). Marked for review later.

When a user changes anything on a row (genre, artist reassignment), the 
status automatically shifts to "Edited" (not "Pending"). This way you can 
scan the Status column and immediately see what you've touched.

### 9. Reassign Artist — autocomplete from existing artists

The Reassign Artist dialog's text field should autocomplete as you type:
- Case-insensitive search against all existing artist names in the library
- Dropdown suggestions appear as you type, showing the established 
  capitalization (e.g., type "d'a" → shows "D'Angelo")
- Selecting from the list uses the exact existing name
- If no match exists, whatever the user types becomes the canonical name
- NO forced Title Case, NO autocorrect — respect artist identity 
  (MF DOOM stays caps, eazy-E stays lowercase)

### 10. Reassign Artist — build proper tree structure

Bug fix: When "Reassign Artist" creates a new artist entry, it must 
immediately create the expandable tree structure with child track row(s). 
Currently the new entry is flat and not expandable until the classifier 
is re-run. The new artist entry should be expandable immediately after 
reassignment.

### 11. Reassign Artist — feedback after action

After reassigning a track:
- Show a brief toast notification: "Track moved to artist: [name]"
- Auto-expand the destination artist row so the user can see the track 
  landed correctly
- If the source artist group is now empty, remove it from the list

### 12. Reassign Artist — protect metadata notice

Add a small note at the bottom of the Reassign Artist dialog:
"Only the artist grouping will change. Your comments, cue points, and 
Serato data are never modified."

### 13. Editable tags/styles via right-click

Add "Edit Tags..." to the track-level right-click context menu. Opens a 
small dialog where the user can:
- See current style/tag metadata on the track
- Add new tags (free-text input)
- Remove existing tags
- Tags are stored as style metadata, separate from genre

This is the foundation for user-created tags that will power crate 
suggestions later. For now, just the ability to view and edit tags on 
individual tracks.

### 14. Featured artist parsing in classifier

Update the classifier to parse featured artist patterns and extract the 
primary artist:
- "DJ Quik feat. Sugar Free" → primary artist: DJ Quik
- "DJ Quik ft. Sugar Free" → primary artist: DJ Quik  
- "DJ Quik featuring Sugar Free" → primary artist: DJ Quik
- "Artist, Artist" → primary artist: first name (before comma)

The primary artist determines genre classification and grouping. Featured 
artist info stays in the track metadata. The track appears under the 
primary artist's group in the classification view.

For entries like "D'Angelo, AZ, DJ Premier" where it's ambiguous, continue 
flagging as collaboration for user review (already implemented in the 
previous session).

### 15. Genre-level approval in sidebar

In the genre summary sidebar (left panel), add a right-click context menu 
on each genre with:
- "Approve All in [Genre]" — approves every artist classified in this genre

This allows quick genre-level batch approval without selecting individual 
artists.

## What NOT to build

- No Library Browser view (next session)
- No Organize view (future)
- No Crate Manager view (future)
- No Settings page (future)
- No file moves or metadata writes to disk

## Testing

After implementing:
1. Delete classification_session.json from the test library
2. Launch the app, load test library, click Classify Library
3. Verify NO blue anywhere — click rows, check boxes, select items
4. Verify selected rows are orange with dark text, immediate on click
5. Verify expanded parent rows don't turn orange
6. Verify checkboxes use orange/cream, not blue
7. Verify font sizes are comfortably larger
8. Verify "Current Genre" column name (not "Current Tags")
9. Expand an artist — verify track rows show title, duration, format, 
   genre, file path aligned properly
10. Right-click a track and use "Reassign Artist" — type a partial name 
    and verify autocomplete suggests existing artists
11. After reassigning, verify the new entry is immediately expandable
12. Verify toast notification appears after reassign
13. Change a genre on an artist — verify status shows "Edited" in teal
14. Approve an artist — verify status shows "Approved" in green
15. Right-click a track and try "Edit Tags..."
16. Right-click a genre in the sidebar and try "Approve All in [Genre]"

Launch and verify everything works.
