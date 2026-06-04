# CrateSort — Final Fixes Before Crate Manager

## Context

User completed a thorough walkthrough and found remaining bugs and UX 
improvements. These must all be resolved before moving to the Crate Manager.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## CRITICAL: App crash on Cancel during scan

Clicking Cancel during the startup library scan crashes the app with 
SIGABRT. The crash originates from a QTimer callback firing after the 
cancel handler has already cleaned up state.

From the crash log:
```
Exception Type: EXC_CRASH (SIGABRT)
QTimerInfoList::activateTimers() → pyqt6_err_print() → QMessageLogger::fatal() → abort()
```

A Python exception is occurring inside a Qt timer-triggered slot callback. 
PyQt6's default error handler calls fatal() which aborts. The cancel 
handler likely disconnects signals or destroys objects, then a pending 
QTimer.singleShot fires and tries to access destroyed state.

Fix:
1. Wrap ALL QTimer.singleShot callbacks in try/except to prevent crashes
2. In the cancel handler, cancel/invalidate any pending timers before 
   cleaning up state
3. Use a `_cancelled` flag that timer callbacks check before executing
4. Set a global PyQt exception hook so unhandled exceptions in slots 
   show an error dialog instead of calling abort():
   ```python
   def exception_hook(exc_type, exc_value, exc_tb):
       traceback.print_exception(exc_type, exc_value, exc_tb)
   sys.excepthook = exception_hook
   ```
   Add this in main() before QApplication is created.

---

## PERSISTENCE FIXES

### Fix 1: Track-level genre changes STILL don't persist from classification

THIS IS THE FOURTH TIME. The cascade from _cascade_genre_to_children 
updates the QTreeWidgetItem display text but does NOT update the 
underlying TrackInfo.genre_tag in the ArtistEntry data structure.

VERIFY THE FIX BY DOING THIS:
1. After _cascade_genre_to_children runs, print each track's genre_tag 
   to console
2. After the session saves, read the JSON file back and print the track 
   genres to console
3. After the Library Browser loads, print what _track_overrides contains

The fix must update the ACTUAL DATA, not just the display widget. 
Something like:
```python
# In _cascade_genre_to_children:
for i, track in enumerate(entry.tracks):
    track.genre_tag = new_genre  # Update the DATA
    if i < item.childCount():
        item.child(i).setText(COL_GENRE, new_genre)  # Update the DISPLAY
```

Do NOT just update the QTreeWidgetItem text. The data must change.

### Fix 2: Reassign Artist in Library Browser doesn't persist

When reassigning a track to a different artist via right-click in the 
Library Browser, the change shows during the session but reverts after 
closing and reopening.

The reassignment needs to be saved to library_edits.json. Store it as:
```json
{
  "file_path": {
    "reassign_artist": "new_artist_name",
    "original_artist": "old_artist_name"
  }
}
```

On Library Browser load, apply reassignment overrides when building the 
artist tree — move the track to the reassigned artist group.

### Fix 3: Library Browser inline edits don't close on single-click away

The edit box only closes when double-clicking another editable cell. It 
should close on ANY click outside the editor.

Fix: Install an event filter on the tree widget's viewport that catches 
MouseButtonPress events. If a click occurs outside the active editor's 
geometry, commit and close the editor.

```python
def eventFilter(self, obj, event):
    if event.type() == QEvent.Type.MouseButtonPress:
        if self._edit_widget and obj == self._tree.viewport():
            click_pos = event.position().toPoint()
            if not self._edit_widget.geometry().contains(click_pos):
                self._commit_active_editor()
                return False  # Let the click also process normally
    return super().eventFilter(obj, event)
```

---

## STYLE TAG FIXES

### Fix 4: Track style tags must NOT propagate to artist row

When adding a style tag to a track, it currently also appears on the 
parent artist row. Style tags must be completely independent:

- Track tags describe a specific song's character
- Artist tags describe the artist's overall identity
- Neither auto-propagates to the other

Fix: When saving a track's style tags in _edit_style_tags(), ensure 
it ONLY writes to the track-level data, not the artist-level data. 
Check if the code is using the parent item to store tags — it should 
only modify the child track item.

### Fix 5: Artist-level style tags (independent editing)

Artists should have their own editable style tags accessible via 
right-click on an artist row → "Edit Style Tags..."

This uses the same tag editor dialog but saves to artist-level data 
(not track-level). The artist's style tags are stored separately from 
any track tags.

Add "Edit Style Tags..." to the artist-level right-click context menu 
in BOTH the Classification view and Library Browser. Currently it only 
exists in the track-level menu.

---

## UX IMPROVEMENTS

### Fix 6: "Change Library..." opens to current library path

When clicking the "Change Library..." link on the dashboard, the 
directory picker should start at the current library's parent directory:

```python
QFileDialog.getExistingDirectory(
    self, 
    "Select media library folder",
    str(Path(current_library_path).parent)  # Start here
)
```

### Fix 7: Launch dialog on startup

When the app launches and finds a saved library path in QSettings, it 
should show the launch dialog asking whether to load the previous library 
or choose a new one. Verify this is actually working — the user reported 
it skips straight to scanning without asking.

Check if the "Always load my last library" flag was accidentally set to 
True, or if the dialog code path is being skipped. The dialog should 
appear every time unless the user explicitly checked "Always load."

### Fix 8: Row type icons in Library Browser

Add icons to distinguish artist rows from track rows:

- **Artist rows**: small person/silhouette icon (16x16)
- **Track rows**: small vinyl disc or music note icon (16x16)

Icons should be rendered in muted color (#a89b85), subtle and 
non-competing with text. Place them at the start of the first column 
(Artist column) using QTreeWidgetItem.setIcon().

If custom SVG icons aren't available, use Unicode characters as 
placeholders:
- Artist: 👤 or ◉ 
- Track: ♪ or ◎

These can be replaced with proper SVG icons later.

---

## Testing

### Crash test:
1. Launch app
2. As library starts scanning, click Cancel
3. Verify app does NOT crash — returns to welcome screen gracefully

### Persistence:
4. Delete _CrateSort folder and library_edits.json
5. Launch, classify, change genres on several artists
6. Done → Library
7. Expand artists — verify track genres match what you set (not raw tags)
8. Reassign a track to a different artist in Library
9. Edit a track title in Library
10. Add a style tag to a track
11. Add a style tag to an artist (different from track tag)
12. Close app completely
13. Reopen → go to Library
14. Verify genre changes persisted on tracks
15. Verify artist reassignment persisted
16. Verify title edit persisted
17. Verify track style tag persisted AND is NOT on the artist
18. Verify artist style tag persisted AND is independent from tracks

### UX:
19. Click "Change Library..." — verify picker opens at current library path
20. Verify launch dialog appears on startup (if "Always load" not checked)
21. In Library, verify artist rows have person icon
22. Verify track rows have disc/music note icon
23. Double-click a cell to edit, then single-click elsewhere — verify 
    editor closes immediately
24. Verify clicking on a different row closes any active editor

ALL 24 steps must pass.
