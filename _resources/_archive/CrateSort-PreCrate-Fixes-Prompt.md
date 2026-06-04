# CrateSort — Pre-Crate Manager Final Fixes

## Context

User completed a full walkthrough. Most things are working. These are the 
last 6 items that need fixing before we move to the Crate Manager.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fixes

### Fix 1: Launch dialog being skipped on startup

When the app launches and finds a saved library path in QSettings, it 
should show the launch dialog asking "Load your previous library?" with 
options to load or choose a different one. Currently it skips straight 
to scanning.

Debug: Add a print statement at the top of the startup flow showing the 
value of the "always_load_last" QSettings key. If it's True, that's why 
the dialog is being skipped — reset it to False as the default.

The dialog should appear EVERY time unless the user explicitly checks 
"Always load my last library." If the QSettings key doesn't exist or 
is False, show the dialog. Only skip when it's explicitly True.

Check the QSettings key name and default value. Make sure:
```python
always_load = self._settings.value("always_load_last", False, type=bool)
if always_load:
    # Skip dialog, go straight to scan
else:
    # Show dialog
```

If the key was accidentally set to True during development, reset it.

### Fix 2: Artist genre change should NOT cascade to tracks in Classification

In the Classification view, when you right-click an artist and change 
their genre, it currently cascades the change to all track child rows. 
This should NOT happen.

Remove or disable the call to _cascade_genre_to_children in 
_change_entry_genre. The artist genre and track genres are independent:

- Changing an artist's genre = changing where the artist lives on disk
- Track genres = metadata on individual files, can vary within an artist

The Library Browser already has this correct behavior (artist genre 
changes don't cascade to tracks). The Classification view needs to match.

Also remove _cascade_genre_to_children from _batch_set_genre — same rule 
applies when using the Set Genre button.

NOTE: Keep the _cascade_genre_to_children method in the code (don't 
delete it) in case we want to offer it as an explicit "Apply genre to 
all tracks" option later. Just disconnect it from the automatic genre 
change flow.

### Fix 3: Multi-select tracks via Shift/Cmd+click

Enable multi-selection on track rows in BOTH the Classification view 
AND the Library Browser.

For the Classification view:
- The tree widget is currently SingleSelection mode (for the orange 
  highlight). Change the selection mode to ExtendedSelection.
- Artist rows still use checkboxes for batch actions (Approve Selected, 
  Set Genre at artist level)
- Track rows use Shift/Cmd+click for multi-select
- When multiple tracks are selected, right-click → Change Genre applies 
  to ALL selected tracks
- The Set Genre button at the top: if track rows are selected 
  (highlighted), apply to those tracks. If artist checkboxes are checked, 
  apply to those artists. Track selection takes priority if both exist.

For the Library Browser:
- Same behavior — ExtendedSelection mode
- Shift+click for range, Cmd+click for individual picks
- Right-click → Change Genre on any selected track applies to all 
  selected tracks
- Inline editing (double-click) should still work — double-clicking one 
  of the selected tracks opens the editor for that specific cell

### Fix 4: Artist-level genre changes in Library Browser don't persist

Changing an artist's genre via right-click → Change Genre in the Library 
Browser shows the change during the session but reverts after restart. 
No teal flash fires either.

The artist genre change handler in the Library Browser needs to:
1. Save the change to library_edits.json using a key like 
   `__artist__<artist_name>` with `{"genre": "new_genre"}`
2. Trigger the teal row flash to confirm the change
3. On Library Browser load, read artist-level genre overrides from 
   library_edits.json and apply them to artist rows

Check how track-level genre changes are saved (those work and persist) 
and replicate the same pattern for artist-level changes.

### Fix 5: Artist icon — person silhouette instead of circle

The current ◉ circle icon on artist rows doesn't communicate "this is 
an artist." Replace with a person/silhouette icon.

Best approach: create a simple person silhouette as a painted QPixmap. 
Draw a circle for the head and a curved shape for the shoulders — the 
universal "user avatar" shape. Render in muted color (#a89b85) at 14x14.

If painting is too complex, use one of these Unicode alternatives that 
render as a person shape:
- U+1F464 👤 (bust in silhouette) — may not render well at small sizes
- U+263A ☺ — too smiley
- Try: paint a simple filled circle (head) + filled arc (shoulders) 
  using QPainter on a QPixmap

```python
def _make_person_icon(self):
    px = QPixmap(14, 14)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#a89b85")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    # Head - circle
    p.drawEllipse(4, 0, 6, 6)
    # Shoulders - arc/ellipse
    p.drawEllipse(1, 7, 12, 10)
    p.end()
    return QIcon(px)
```

### Fix 6: Music note icon doesn't invert on selected rows

When a track row is highlighted orange, the ♪ icon stays cream/beige 
and is hard to see against the orange background. The icon needs to 
invert to dark (#2F2F2F) when selected.

The challenge: QTreeWidget item icons don't automatically change color 
based on selection state. Options:

**Option A (recommended):** Use QIcon with two states — normal mode and 
selected mode:
```python
icon = QIcon()
icon.addPixmap(normal_pixmap, QIcon.Mode.Normal)
icon.addPixmap(dark_pixmap, QIcon.Mode.Selected)
```
Create two versions of each icon — cream for normal, dark for selected. 
Qt will automatically switch between them based on selection state.

**Option B:** Connect to the selectionChanged signal and manually swap 
icons on selected/deselected items. More code, same result.

Go with Option A. Create both color variants for the person icon AND 
the music note icon, and set both modes on each QIcon.

---

## Testing

1. Launch app — verify launch dialog appears (not auto-scan)
2. Uncheck "Always load" if checked, load library
3. Close and reopen — verify dialog appears again
4. Check "Always load" — close and reopen — verify it skips dialog
5. Classify library
6. Change an artist's genre — verify tracks do NOT cascade
7. Expand artist — verify tracks still have their original genres
8. Shift+click to select multiple tracks in classification view
9. Right-click → Change Genre — verify it applies to all selected
10. Done → Library
11. Change an artist's genre in Library → verify teal flash
12. Close app, reopen, verify artist genre persisted
13. Shift+click multiple tracks in Library
14. Right-click → Change Genre — verify batch change works
15. Verify artist rows have person silhouette icon (not circle)
16. Verify track rows have music note icon in cream
17. Select a track row — verify music note inverts to dark
18. Deselect — verify it goes back to cream
