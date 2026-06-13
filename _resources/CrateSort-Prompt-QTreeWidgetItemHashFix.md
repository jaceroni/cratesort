# CrateSort — Fix: QTreeWidgetItem Hash Error in Library Reassignment

**Claude, high effort. Read every referenced file completely before writing any code.**

---

## The Error

When trying to reassign artists in the Library Browser, the app crashes with this traceback:
```
Traceback (most recent call last):
  ...
  File "/Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py", line 968, in _reassign_track
    modified_parents.add(parent_item)
TypeError: cannot use 'PyQt6.QtWidgets.QTreeWidgetItem' as a set element (unhashable type: 'QTreeWidgetItem')
```

Because `QTreeWidgetItem` is not hashable in PyQt6, we cannot add it to a Python `set`. This crash prevented the reassignment from completing, which is why:
- Reassignment did not stick (it crashed before saving edits).
- Only the first track appeared to move, or it glitched out.
- Empty folders remained behind.

---

## The Fix

We need to change `modified_parents` in `_reassign_track` from a `set` to a `list` (and check for uniqueness to avoid duplicate processing).

#### [MODIFY] [library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py)

- Around line 950, change the initialization of `modified_parents` to a list:
  ```python
          # 5. Move each track: tree removal + path-based list removal + edit persistence
          modified_parents: list[QTreeWidgetItem] = []
  ```
- Around line 966, check if `parent_item` is already in the list before appending:
  ```python
              parent_item.setText(LC_TRACKS, str(len(parent_tracks)))
              if parent_item not in modified_parents:
                  modified_parents.append(parent_item)
  ```

---

## Verification Steps

1. Run the app.
2. Select multiple tracks under an artist in the Library tab, right-click, and select "Reassign Artist".
3. Verify that the app does not crash, the tracks move, and the old folder is removed if empty.
4. Close and reopen the app. Verify that the reassignments persist.
