# CrateSort — Crate Manager Quick Fixes

## Context

Two additional issues found during Crate Manager testing.

---

## Fixes

### Fix 1: Prevent duplicate tracks within a crate

The Add Tracks dialog currently allows adding the same track multiple 
times to one crate, creating duplicate entries. This must not happen.

Two layers of protection:

**a) Add Tracks dialog:** Tracks already in the crate must be grayed 
out and uncheckable in the Add Tracks dialog. The dialog already has 
logic for this (specified in the original build prompt) but it's not 
working. Debug why — the check is probably comparing paths incorrectly 
(resolved path vs original crate path mismatch).

**b) CrateWriter safety net:** Before writing tracks to a .crate file, 
deduplicate the track list. If a path already exists in the crate, 
skip it. This prevents duplicates even if the UI check fails.

### Fix 2: Auto-select and scroll to newly added track

After adding a track to a crate via the Add Tracks dialog, the track 
should be:
1. Highlighted (selected) in the track list
2. Scrolled to center of the viewport

Currently the screen flashes after adding and the user has to manually 
search through the crate to find the new track.

Fix: After the crate is refreshed with the new track, find the row 
matching the newly added track's path, select it, and scroll to center:

```python
# After refresh, find and select the new track
for row in range(self._table.rowCount()):
    item = self._table.item(row, COL_TITLE)
    if item and item.data(Qt.ItemDataRole.UserRole + 1) == added_path:
        self._table.selectRow(row)
        self._table.scrollToItem(item, 
            QAbstractItemView.ScrollHint.PositionAtCenter)
        break
```

If multiple tracks were added at once, scroll to the first one added.

---

## Testing

1. Open a crate with existing tracks
2. Right-click → Add Tracks → try to add a track already in the crate
3. Verify it's grayed out / uncheckable in the dialog
4. Add a new track that's NOT in the crate
5. Verify the track appears in the list, is highlighted, and centered 
   on screen
6. Verify no duplicate entries exist in the crate
