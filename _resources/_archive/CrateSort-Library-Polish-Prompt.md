# CrateSort — Library Browser Polish + Album Art

## Context

The Library Browser was rebuilt with artist-nesting, inline editing, and 
album art panel. User testing revealed several issues that need fixing.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

---

## Fixes

### 1. Inline edit boxes don't close properly

When a user double-clicks a cell to edit it and then clicks away (or clicks 
another cell), the text input box stays visible with its border showing. 
This results in ugly lingering input fields with clipped text/descenders.

Fix: When the edit is committed (Enter, click-away, or focus lost), the 
editor widget must be completely removed and the cell must revert to normal 
display. If the user clicks another cell to edit, the previous edit box 
must close first. At no point should more than one edit box be visible.

Also ensure that the edit box properly sizes to show the full text without 
clipping descenders (letters like g, j, p, q, y). The edit box height 
should accommodate the font's full line height.

Test by: double-clicking 5 different cells in sequence. Only the most 
recently clicked cell should have an edit box. All previous cells should 
look normal.

### 2. Cover art panel position

Move the album art panel UP in the sidebar. Current position is at the 
very bottom above the version number — too hidden.

New position: directly below the Settings nav button (last nav item). 
Give it equal padding on all four sides matching the left/right spacing. 
The version number stays at the very bottom of the sidebar, below the 
art panel.

Layout order in sidebar from top to bottom:
1. CrateSort logo
2. Nav buttons (Dashboard, Library, Crates, Organize, Settings)
3. Album art panel (170x170, with equal padding all sides)
4. Version number (at very bottom)

### 3. Column minimum widths — actually enforce them

Columns are STILL clipping header text on initial load (Duration, Format 
visible in screenshots). This has been requested multiple times.

Use QFontMetrics to measure each header label's pixel width, add ~20px 
padding, and set that as the minimum column width. Do this at widget 
initialization, AFTER setting the header labels and font size.

```python
fm = self._tree.header().fontMetrics()
for col in range(self._tree.columnCount()):
    text = self._tree.headerItem().text(col)
    min_width = fm.horizontalAdvance(text) + 24  # 24px padding
    current = self._tree.columnWidth(col)
    if current < min_width:
        self._tree.setColumnWidth(col, min_width)
```

Every column must show its FULL header text without any clipping on first 
load. Test at default window size.

### 4. Genre field — not editable via double-click

Genre changes must ONLY happen through the right-click "Change Genre..." 
dropdown (locked to the 12 CrateSort genres). Double-clicking the Genre 
cell should NOT open an inline editor.

Same for Artist — changes only through right-click "Reassign Artist..." 
with autocomplete.

Fields editable via double-click (free text):
- Title
- Album
- Style Tags
- BPM (numeric validation)
- Year (numeric validation)
- Comments

Fields NOT editable via double-click:
- Artist (right-click "Reassign Artist..." only)
- Genre (right-click "Change Genre..." only)
- Duration (read-only, calculated from audio)
- Format (read-only, file property)
- Bitrate (read-only, file property)
- File Path (read-only, file location)

When the user double-clicks a non-editable field, nothing happens (no 
editor opens). Or optionally, show a brief tooltip: "Use right-click to 
change genre" / "Use right-click to reassign artist."

### 5. Drag-and-drop album art replacement

Enable drag-and-drop on the sidebar album art panel:

- User drags an image file (JPG, PNG) onto the panel
- Show confirmation dialog: "Replace album art for [track title]?"
- On confirm: write the image to the file's ID3 tags via mutagen
  - MP3: APIC frame (type=3 front cover, encoding=0, mime from file)
  - M4A/MP4/M4V: covr atom
  - FLAC: Picture block
  - WAV: APIC frame if ID3 header exists
- Scale/optimize the image before embedding (max 500x500, JPEG quality 85)
  to avoid bloating file sizes with huge images
- Update the panel display immediately with the new art
- Log the change (store old art bytes for rollback capability)

Implementation:
- Enable drag on the art panel: setAcceptDrops(True)
- Override dragEnterEvent to accept image mime types
- Override dropEvent to handle the file
- Use mutagen to write the embedded art

### 6. Album art right-click context menu

Right-clicking the album art panel shows:
- **"Replace Art..."** — opens a file picker (JPG, PNG filter) for users 
  who prefer browsing to drag-and-drop. Same write logic as drag-and-drop.
- **"Remove Art"** — strips embedded cover art from the file with 
  confirmation: "Remove album art from [track title]?" Panel reverts to 
  placeholder.
- **"Save Art As..."** — saves the currently displayed art to a file on 
  disk. Opens save dialog. Useful for extracting art.

Only show these options when a track is selected and the panel is showing 
art (or placeholder). If no track selected, right-click does nothing.

### 7. Album art panel — connect to classification view too

The album art panel should update when tracks are selected in ANY view, 
not just the Library Browser. If the classification view emits a signal 
when a track child row is clicked, connect that to the same 
_update_album_art handler.

Test by: clicking a track in the Library Browser (art updates), switching 
to classification view, clicking a track there (art should also update).

---

## Testing

1. Delete classification_session.json
2. Launch app, load test library, classify
3. Switch to Library
4. Double-click a Title cell — edit box appears, type something, click 
   away — edit box disappears cleanly, no lingering
5. Double-click 5 cells in sequence — only one edit box visible at a time
6. Double-click Genre cell — nothing happens (not editable)
7. Double-click Artist cell — nothing happens (not editable)
8. Double-click BPM cell — edit box appears (editable)
9. Verify all column headers fully visible, no clipping
10. Check album art panel position — below Settings, above version number
11. Click a track with cover art — verify it shows in the panel
12. Drag a JPG onto the art panel — verify confirmation dialog
13. Confirm — verify art updates in panel
14. Right-click the art panel — verify Replace/Remove/Save options
15. Switch to classification view — click a track — verify art updates
16. Close app, relaunch — verify no lingering edit boxes or visual artifacts

Launch and verify everything works.
