# CrateSort — Final Two Fixes Before Crate Manager

## Context

Nearly everything is working. Two remaining issues from user testing.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fix 1: Genre change must apply to ALL visible selected items

Currently, right-click → Change Genre on a multi-selection only applies 
to one item (the right-clicked item, or only tracks, or only the first 
artist). It must apply to EVERY selected item.

**The rule: what's visible and selected is what gets changed.**

- 4 collapsed artists selected → genre change applies to all 4 artists. 
  Hidden tracks underneath are NOT affected.
- 4 expanded artists with all tracks visible and selected → genre change 
  applies to all selected artists AND all selected tracks.
- 3 tracks selected under one artist → only those 3 tracks change.
- Right-click on ANY item in the selection → applies to the ENTIRE 
  selection, not just the right-clicked item.

**Fix in BOTH ClassifierView and LibraryBrowserView:**

The right-click Change Genre handler must:
1. Get ALL selected items via self._tree.selectedItems()
2. Open the Change Genre dialog ONCE
3. On confirm, iterate ALL selected items
4. For each item, check if it's an artist row or a track row
5. Apply the genre change appropriately:
   - Artist row → update artist-level genre, save to session/edits
   - Track row → update track-level genre, save to session/edits
6. Flash teal on all changed rows

Do NOT filter by item type — if the user selected it, change it. The 
only filter is visibility: if a track row isn't visible (parent artist 
is collapsed), it's not in selectedItems() and won't be affected. Qt 
handles this automatically — collapsed children can't be selected.

```python
def _on_change_genre(self):
    selected = self._tree.selectedItems()
    if not selected:
        return
    
    dialog = _ChangeGenreDialog(self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    
    new_genre = dialog.selected_genre()
    
    for item in selected:
        if item.parent() is None:
            # Artist row
            self._apply_genre_to_artist(item, new_genre)
        else:
            # Track row
            self._apply_genre_to_track(item, new_genre)
```

Test by:
1. Select 4 collapsed artists → Change Genre → verify all 4 changed
2. Expand all 4, select artists + tracks → Change Genre → verify all changed
3. Select only tracks → Change Genre → verify only tracks changed
4. Right-click on the LAST item in a selection → verify ALL items changed

This must work identically in both the Classification view and Library 
Browser.

## Fix 2: Person icon needs more right padding

The silhouette icon on artist rows is too close to the artist name text. 
The music note icon on track rows has better spacing.

Fix: Add a couple pixels of padding. Either:
- Increase the icon pixmap width from 14 to 18 (with transparent right 
  padding) so the icon itself has built-in spacing
- Or add a space character before the artist name text: 
  `item.setText(COL_ARTIST, f" {artist_name}")` — but this may affect 
  sorting

The cleaner approach is making the icon pixmap wider with transparent 
padding on the right side:
```python
# Instead of 14x14, make it 18x14 with the drawing in the left 14px
px = QPixmap(18, 14)
px.fill(Qt.GlobalColor.transparent)
# Draw the silhouette in the left portion as before
```

Apply the same approach to the music note icon so both have identical 
total widths and the text alignment is consistent between artist and 
track rows.

---

## Testing

1. Delete _CrateSort folder
2. Launch, classify library
3. Select 4 collapsed artists via Shift+click
4. Right-click on the 3rd one → Change Genre → Funk/Soul
5. Verify ALL 4 artists now show Funk/Soul
6. Expand all 4 artists
7. Shift+click to select all artists AND all tracks
8. Right-click → Change Genre → Rock
9. Verify ALL artists AND tracks show Rock
10. Select only 2 tracks under one artist
11. Right-click → Change Genre → Blues
12. Verify only those 2 tracks changed, artist unchanged
13. Switch to Library Browser
14. Repeat steps 3-12 in the Library Browser
15. Verify artist genre changes persist after restart
16. Verify track genre changes persist after restart
17. Check icon spacing — person icon should have same gap to text as 
    music note icon
