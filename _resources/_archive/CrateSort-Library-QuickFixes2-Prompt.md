# CrateSort — Library Browser Quick Fixes

## Context

Two issues found during Library Browser testing.

---

## Fixes

### 1. Deselect row before flashing on Enter

When the user commits an edit by pressing Enter, the row stays selected 
(orange background with dark text). The teal text flash is invisible 
against the orange because the selected-state styling overrides the text 
color.

Fix: After committing an edit via Enter (or click-away while the row is 
still selected), deselect the row BEFORE triggering the text flash:

```python
# After committing the edit...
item.setSelected(False)
self._tree.clearSelection()
# Now flash the text
self._flash_row_text(item)
```

This ensures the row has a dark background when the teal text flash 
fires, making it clearly visible. The user can re-select the row 
afterward if they want — the flash is a brief 1.5-second confirmation.

### 2. Track-level right-click actions not working in Library Browser

When right-clicking a track (expanded child row) in the Library Browser:
- "Change Genre..." — nothing happens (should open genre dropdown)
- "Reassign Artist..." — nothing happens (should open reassign dialog 
  with autocomplete)
- "Edit Style Tags..." — works correctly
- "Show in Finder" — works correctly
- "Copy Artist/Title/Path" — works correctly

The menu items are showing but the handlers for Change Genre and 
Reassign Artist are not connected or not implemented in the Library 
Browser view.

Fix: Wire these actions to working handlers in library_browser.py:

**Change Genre (track level):**
- Open the same genre dropdown dialog used in the Classification view 
  (the 12 CrateSort genres)
- On selection, update the track's genre in the display and in the 
  session/edit data
- Flash the row teal to confirm

**Reassign Artist (track level):**
- Open the same Reassign Artist dialog used in the Classification view 
  (text input with autocomplete from existing artists)
- On confirm, move the track from its current artist group to the new 
  artist group (existing or newly created)
- If the source artist group is now empty, remove it
- The destination artist group should be immediately expandable with 
  the track visible inside
- Flash the destination row teal to confirm

These should use the same dialog classes already built for the 
Classification view. Import and reuse them — don't rebuild.

---

## Testing

1. Launch app, load test library, classify, go to Library
2. Double-click a cell, edit, press Enter — verify row deselects and 
   text flashes teal
3. Expand an artist, right-click a track → "Change Genre..." — verify 
   genre dropdown opens and changing genre updates the display
4. Right-click a track → "Reassign Artist..." — verify dialog opens 
   with autocomplete, reassigning moves the track to the correct artist
5. Verify "Edit Style Tags..." still works
6. Verify "Show in Finder" still works
7. Verify copy actions still work
