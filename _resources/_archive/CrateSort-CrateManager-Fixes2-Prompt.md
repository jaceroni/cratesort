# CrateSort — Crate Manager Fixes Round 2

## Context

Crate Manager is functional with most issues resolved. These are the 
remaining items from user testing.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fixes

### Fix 1: Sub-crate expand indicators not showing

Crates that contain sub-crates have no visible expand arrow or triangle. 
The user can't tell which crates are expandable without clicking each one.

setRootIsDecorated(True) is already set but indicators aren't rendering 
on collapsed items. The issue may be that Qt only shows indicators when 
items have children AND the tree hasn't been explicitly collapsed.

Try setting the child indicator policy on items that have children:
```python
if item.childCount() > 0:
    item.setChildIndicatorPolicy(
        QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
    )
```

This forces Qt to show the expand triangle even when collapsed.

### Fix 2: Track search within crates

Add a search field for filtering tracks within the currently selected 
crate. When viewing a crate's track list, the user needs to search by 
artist name or track title.

Add a search field above the track table (right panel), similar to the 
Library Browser's search. Real-time filtering as you type. Searches 
across Title, Artist, and Album columns. Include a clear button (X).

This is separate from the crate search on the left (which filters crate 
names). Left panel searches crates, right panel searches tracks within 
the selected crate.

### Fix 3: Remove from crate — loading feedback

Removing a track causes a brief freeze with no feedback. Add the same 
status feedback as other operations:
- Show "Removing track..." in the status bar
- After completion, show teal "Track removed" confirmation

### Fix 4: Crate tree state preserved after track removal

The crate tree collapses entirely after removing a track from a crate. 
The _save_tree_state / _restore_tree_state mechanism isn't being used 
during the remove operation.

Fix: The remove-from-crate handler must use _refresh() (which saves 
and restores tree state) instead of directly rebuilding. Or if it's 
already calling _refresh(), debug why the state isn't being preserved — 
print the saved expanded paths and the restored paths to console.

The crate the user was viewing must remain selected, and all previously 
expanded crates must stay expanded after the remove operation.

### Fix 5: Music note icon spacing — consistent across all views

The crate view's music note icon spacing (tighter, closer to track name) 
looks better than the library view's spacing. Update ALL views to use 
the same tighter spacing as the Crate Manager:

Check what pixmap width the Crate Manager uses for its music note icon 
and apply that same width in:
- Library Browser (_make_note_icon)
- Classification view (if it uses a similar icon)

All track rows across the entire app should have identical icon spacing.

---

## Testing

1. Launch app, load library, go to Crates
2. Verify crate tree is collapsed
3. Verify crates with sub-crates show expand arrows/triangles
4. Click a crate with tracks
5. Use the track search field — search for an artist name
6. Clear the search — verify all tracks return
7. Remove a track — verify "Removing..." feedback and teal confirmation
8. After removal — verify crate tree stayed in same expanded state
9. Verify the same crate is still selected after removal
10. Go to Library — verify music note spacing matches crates view
11. Compare track rows side by side between Library and Crates — 
    spacing should be identical
