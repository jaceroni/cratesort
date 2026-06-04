# CrateSort — Crate Manager Fixes

## Context

The Crate Manager is built and functional. User testing revealed 12 issues 
that need fixing.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fixes

### Fix 1: Search crates box needs clear button

The search field above the crate tree needs an "X" clear button to reset 
the search. When the user has searched for a crate, they need a quick way 
to clear the filter and see all crates again. Use QLineEdit's 
setClearButtonEnabled(True).

### Fix 2: Sub-crate expand indicator

Crates that contain sub-crates need a visible expand indicator (arrow or 
triangle) so the user knows they can double-click to reveal nested crates. 
Currently there's no visual distinction between a crate with sub-crates 
and one without.

Qt's QTreeWidget should show expand arrows automatically on items with 
children. If it's not showing, check setRootIsDecorated(True) and ensure 
child items are actually being added as children (not siblings).

### Fix 3: Crate tree collapsed by default

When first navigating to the Crates tab, the entire tree is expanded 
showing all sub-crates. This is overwhelming with 191 crates.

Fix: On initial load, collapse all items. Only show top-level crates. 
User expands what they want to see. Call self._tree.collapseAll() after 
building the tree.

### Fix 4: Loading/delay feedback for crate operations

There's a noticeable delay when:
- First clicking the Crates tab (loading all crate data)
- Creating, deleting, duplicating crates
- Adding tracks to crates

During these operations, the UI feels frozen with no feedback.

Fix:
a) When first loading the Crates tab, show a brief loading indicator 
   (same pattern as the library scan — progress text or spinner)
b) For crate operations (create, delete, duplicate, add tracks), show 
   a brief status message in the bottom bar: "Creating crate..." → 
   "Crate created" (with teal flash or color change for confirmation)
c) If an operation takes more than ~200ms, the UI should show that 
   something is happening

### Fix 5: Tree shouldn't re-expand after operations

After any crate operation (create, delete, duplicate, add/remove tracks), 
the crate tree completely re-expands showing all sub-crates and the 
user's selection is lost.

Fix: After operations that rebuild the tree:
1. Save the currently expanded items (list of expanded crate names)
2. Save the currently selected crate name
3. Rebuild the tree
4. Restore expanded state (only re-expand items that were expanded before)
5. Re-select the previously selected crate
6. Do NOT call expandAll() after rebuild

### Fix 6: Delete crate needs confirmation

Deleting a crate currently happens silently with no feedback. Add a 
confirmation dialog ONLY for crates that contain tracks:

- Empty crate: delete immediately, show brief status "Crate deleted"
- Crate with tracks: show confirmation "Delete crate '[name]' with 
  X tracks? The tracks will NOT be deleted from your library."
  Buttons: Cancel / Delete

### Fix 7: Remove from Crate doesn't work for original tracks

"Remove from Crate" works for newly added tracks but fails for tracks 
that were originally in the crate (from Serato).

Debug: The issue is likely that the remove operation is comparing track 
paths differently than how they're stored in the .crate file. Original 
tracks have absolute paths from the external drive, while the remove 
logic might be looking for paths relative to the test library.

Fix: When removing a track, match against the exact path as stored in 
the crate file, not a normalized or relative version.

### Fix 8: After deleting a crate, redirect to All Tracks

When a crate is deleted, the track list still shows the tracks from the 
deleted crate. This is confusing — the crate is gone.

Fix: After deleting a crate, automatically select "All Tracks" in the 
crate tree and show the All Tracks view. If All Tracks doesn't exist, 
clear the track list.

### Fix 9: Reassign Artist only shows artists from current crate

The Reassign Artist autocomplete in the Crate Manager only suggests 
artists that exist within the currently selected crate. It should 
suggest from the ENTIRE library (all scanned artists), same as the 
Library Browser.

Fix: Pass the full library artist list to the _ReassignArtistDialog, 
not just the artists in the current crate.

### Fix 10: Crate Manager must read genre overrides

Tracks displayed in the Crate Manager show raw file metadata genres 
instead of the user's overridden genres from classification/library edits.

Fix: When the Crate Manager resolves tracks against the scanned library, 
it must ALSO check:
1. library_edits.json for track-level genre overrides (keyed by file path)
2. library_edits.json for artist-level genre overrides (keyed by 
   __artist__<name>)
3. classification_session.json for classified genres

Priority: library_edits track override > library_edits artist override > 
classification session > raw file metadata.

This is the same enrichment logic the Library Browser uses. Reuse or 
import that logic rather than reimplementing.

### Fix 11: Crate name parsing — verify slash handling

User reported some crate names might not match Serato's display names 
(e.g., slashes in names). Verify that the crate reader correctly handles 
all special characters in crate names, especially `/` which could be 
confused with path separators.

Print a few crate names to console on load so we can verify they match 
what Serato shows.

---

## Testing

1. Click Crates tab — verify tree loads collapsed (not expanded)
2. Verify crates with sub-crates show expand arrow/indicator
3. Search for a crate name — verify filtering works
4. Clear the search with X button — verify all crates return
5. Click a crate with resolved tracks — verify genres match Library 
   Browser (overrides applied, not raw file tags)
6. Create a new crate — verify status feedback, tree doesn't fully 
   re-expand, new crate is selected
7. Add tracks to the new crate — verify they appear
8. Remove a track that was just added — verify it works
9. Remove a track that was originally in a crate — verify it works
10. Right-click a track → Reassign Artist — verify autocomplete shows 
    artists from full library, not just current crate
11. Delete the new crate — verify confirmation for non-empty crate
12. After deletion — verify redirect to All Tracks view
13. Delete an empty crate — verify no confirmation needed
14. Verify no UI freeze during operations (loading feedback visible)
15. Expand a few crates, select one, add a track — verify expanded 
    state and selection preserved after the operation
