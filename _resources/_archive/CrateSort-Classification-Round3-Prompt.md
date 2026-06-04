# CrateSort — Classification View Round 3: Final Polish

## Context

The classification view has been through two rounds of improvements. The user 
has done extensive hands-on testing and identified remaining issues. This 
session addresses all of them.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

## Fixes

### 1. Font size — missed spots

The sidebar nav buttons (Dashboard, Library, Crates, Organize, Settings) and 
the classification view header text (title + subtitle) did not get the font 
size bump from the last round. Check EVERY text element in the entire app and 
make sure nothing was missed:
- Sidebar nav button labels
- View titles and subtitles
- Genre sidebar labels (left panel in classification view)
- Tooltip text
- Dialog text
- Toast/notification text
All should be proportionally increased to match the table text bump.

### 2. Remove left-side selection indicator entirely

There is a blue/colored bar on the left edge of selected rows. Remove it 
completely. The orange row highlight is sufficient to show selection state. 
No left-side indicator of any color — no blue, no teal, nothing. Just the 
orange row background.

Search the stylesheet and widget code for anything that paints a left 
border, left indicator, or selection bar on rows. Kill all of it.

### 3. Column dividers on selected rows

The column separator lines inside orange selected rows appear teal/green. 
They should be thin, subtle, dark lines (#2F2F2F or very dark). Nearly 
invisible — just enough to separate columns. Apply to both selected and 
unselected rows. Unselected rows can use #444444 (current border color). 
Selected rows use #2F2F2F.

### 4. Checkbox contextual styling

The checkbox needs to look different depending on the row background:

**On dark/unselected rows:**
- Unchecked: border #a89b85, transparent fill
- Checked: border #a89b85, fill #D17D34 (orange), checkmark #f1e3c8 (cream)

**On orange/selected rows:**
- Unchecked: border #2F2F2F (dark), transparent fill
- Checked: border #2F2F2F, fill #2F2F2F (dark), checkmark #f1e3c8 (cream)

The checkbox must always be clearly visible against its row background. 
Orange checkbox on orange row = invisible. Fix it.

Note: Qt stylesheets can't easily detect parent row selection state for 
indicator styling. If CSS alone can't handle this, use a custom delegate 
or manually update checkbox styling when selection changes via signal.

### 5. All columns resizable

Every column in the classification tree widget should be user-resizable by 
dragging column header edges. Set the resize mode to Interactive on ALL 
columns, not just one. Default widths should be wide enough to show the 
full column header text without clipping, and the Artist column should be 
generous enough for most artist names.

Use QHeaderView.ResizeMode.Interactive on all sections.

### 6. Clean column header names

Remove all slash/dual naming from column headers. Headers should be simple 
single-purpose labels:

- "Artist / Title" → **"Artist"**
- "Tracks / Duration" → **"Tracks"**
- "Confidence / Format" → **"Confidence"**
- "Proposed Genre / Genre Tag" → **"Proposed Genre"**
- "Current Genre" → stays as-is
- "Status" → stays as-is
- "File Path" → stays as-is

The track rows already show different data (title, duration, format, genre 
tag) in these columns — the context is obvious when you expand an artist. 
No need for dual labels.

### 7. Show comments on expanded track rows

Display the file's comment/notes metadata on expanded track child rows. 
Use the Current Genre column position for this (that column is blank or 
redundant for track rows since the genre is already shown in the Proposed 
Genre column position).

If the comment is empty, leave it blank. If it's long, truncate with 
ellipsis — the full comment is available via the copy feature (item 9) 
or tooltip on hover.

### 8. Aaron Neville still classified as Specialty

Aaron Neville's "Hercules" has genre tag "Sample" which was moved to 
JUNK_GENRES in the last round, but he's still showing as Specialty with 
HIGH confidence. Check why — the "Sample" tag should be ignored as junk, 
and with no valid genre tag and no style tags, Aaron Neville should be 
Unclassified (not Specialty). The purpose folder fix from the previous 
round should prevent _Samples from being used as a genre hint.

Debug this specific case and fix whatever is still causing it.

### 9. Double-click to copy cell content (track rows only)

On expanded track child rows, double-clicking any cell copies that cell's 
text content to the system clipboard. Show a brief visual flash on the cell 
(e.g., background quickly pulses lighter then returns to normal) to confirm 
the copy happened.

This only applies to track child rows. Artist parent rows keep the existing 
double-click behavior (expand/collapse).

Use QApplication.clipboard().setText() for the copy. For the flash, briefly 
change the cell background via a QTimer — 150ms flash, then restore.

### 10. System blue — final kill

This is the FOURTH time this has been requested. Qt system blue is STILL 
appearing somewhere. Do a comprehensive audit:

1. Search theme.py for every selection-related CSS rule
2. Add these if missing:
   ```
   QTreeWidget { selection-background-color: #D17D34; selection-color: #2F2F2F; }
   QTreeWidget::item:selected { background: #D17D34; color: #2F2F2F; border: none; outline: none; }
   QTreeWidget::item:selected:active { background: #D17D34; color: #2F2F2F; }
   QTreeWidget::item:selected:!active { background: #D17D34; color: #2F2F2F; }
   QTreeWidget:focus { outline: none; border: none; }
   QTreeWidget::item:focus { outline: none; border: none; }
   ```
3. Also check QTreeWidget::branch — Qt can paint blue indicators on 
   branch/expand areas
4. Check QPalette — set Highlight and HighlightedText colors at the 
   QApplication palette level, not just stylesheet
5. Set the palette BEFORE applying the stylesheet:
   ```python
   palette = app.palette()
   palette.setColor(QPalette.ColorRole.Highlight, QColor("#D17D34"))
   palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#2F2F2F"))
   app.setPalette(palette)
   ```
6. Launch the app and click every clickable thing. If ANY blue appears 
   anywhere, find it and kill it.

## What NOT to build

- No Library Browser view (next session)
- No Organize view
- No Crate Manager view  
- No Settings page
- No file moves or metadata writes to disk

## Testing

After implementing:
1. Delete classification_session.json
2. Launch app, load test library, classify
3. Check font sizes on sidebar, headers, labels — all proportionally larger
4. Click a row — orange background, dark text, NO left indicator, NO blue
5. Check column dividers on selected row — dark, not teal
6. Check/uncheck boxes on selected vs unselected rows — visible on both
7. Drag column header edges — all columns resizable
8. Verify clean column headers (no slashes)
9. Expand an artist — verify comments show on track rows
10. Check Aaron Neville — should be Unclassified, not Specialty
11. Double-click a cell on an expanded track — verify it copies and flashes
12. Click every widget in the app — verify zero blue anywhere

Launch and verify everything works.
