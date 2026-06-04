# CrateSort — Remaining Fixes Before Crate Manager

## Context

User walkthrough is nearly complete. These are the final remaining issues.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fixes

### Fix 1: Genre change must apply to ALL visible selected items

Right-click → Change Genre on a multi-selection currently only applies 
to one item or only to tracks. It must apply to EVERY visible selected 
item.

**The rule: what's visible and selected is what gets changed.**

The _change_genre_for_selection method was added in the last round but 
there are still issues:
- Selecting multiple collapsed artists and changing genre only changes 
  the right-clicked one, not all selected
- Selecting artists + tracks only changes tracks, not artists

Debug _change_genre_for_selection: verify self._tree.selectedItems() 
is returning ALL selected items. Print the count and types to console.
Make sure the iteration processes every item:

```python
selected = self._tree.selectedItems()
print(f"[DEBUG] Selected items: {len(selected)}")
for item in selected:
    is_artist = item.parent() is None
    print(f"  {'ARTIST' if is_artist else 'TRACK'}: {item.text(0)}")
```

If selectedItems() is correct but only one item changes, the bug is in 
the loop body — likely an early return or break statement.

This must work in BOTH ClassifierView AND LibraryBrowserView.

### Fix 2: "Always load" needs a reset path

Once the user checks "Always load my last library," there's no way to 
undo it since the dialog never appears again.

Fix: Add a "Reset" or "Change Library..." option that's always 
accessible. Two approaches (do both):

a) The "Change Library..." link on the dashboard should also reset the 
   always_load_last QSettings flag to False. That way next launch will 
   show the dialog again.

b) In the future Settings view, add a toggle. For now, approach (a) 
   is sufficient.

### Fix 3: Classification and Library views must share data

Genre changes made in the Library Browser don't appear in the 
Classification view, and vice versa (after restart).

**Root cause:** Two separate data files — classification_session.json 
and library_edits.json — with no synchronization.

**Fix:** When a genre change is made in the Library Browser:
1. Save to library_edits.json (already working)
2. ALSO update classification_session.json — find the matching artist 
   or track entry and update its genre

When the Classification view loads, it should ALSO read 
library_edits.json and apply any genre overrides on top of the session 
data.

This ensures both views always show the same genres regardless of 
where the change was made.

Implementation:
- Add a helper function that writes to both files when a genre changes
- When ClassifierView loads/rebuilds, check library_edits.json for 
  any artist or track genre overrides and apply them
- When LibraryBrowserView changes a genre, also call 
  ClassificationSession.update_genre() or similar to write to the 
  session file

### Fix 4: Revert music note icon to original size

The music note icon got smaller and gained unnecessary right padding 
in the last fix (when both icons were changed to 18x14). 

Fix: Revert the music note icon back to 14x14 with original rendering. 
Only the artist/person silhouette icon should be 18x14 (with the extra 
4px right padding for spacing). The music note was properly sized and 
spaced before — undo the change to it.

### Fix 5: Remove cell border-radius artifacts

Selected rows show small dark dots at the corners of each cell. This 
is caused by border-radius on QTreeWidget::item creating rounded 
corners where the dark background peeks through.

Fix: Remove ALL border-radius from tree widget item styling:
```css
QTreeWidget::item {
    border-radius: 0px;
}
QTreeWidget::item:selected {
    border-radius: 0px;
}
```

Search the entire stylesheet in theme.py for any border-radius applied 
to QTreeWidget::item, QTreeView::item, QTableWidget::item, or similar 
selectors. Remove or set to 0. Cells should be sharp rectangles with 
no rounding.

---

## Testing

### Multi-select genre change:
1. Classification view: select 4 collapsed artists → Change Genre → 
   verify ALL 4 changed
2. Select artists + expanded tracks → Change Genre → verify ALL changed
3. Select only tracks → Change Genre → verify only tracks changed
4. Library Browser: repeat steps 1-3

### Data sync:
5. Change a genre in Library Browser
6. Go to Classification view → verify the change is reflected there
7. Change a genre in Classification view
8. Go to Library Browser → verify the change is reflected there
9. Close app, reopen → verify both views show consistent data

### Always load reset:
10. Click "Change Library..." on dashboard
11. Close app, reopen → verify launch dialog appears

### Icons:
12. Verify music note is back to original size (not tiny)
13. Verify artist silhouette has proper spacing
14. Verify music note spacing hasn't changed from original

### Cell corners:
15. Select multiple rows → verify no dark dots at cell corners
16. Orange fills edge to edge with no rounded corner artifacts
