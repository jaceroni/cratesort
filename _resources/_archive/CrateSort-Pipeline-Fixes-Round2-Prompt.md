# CrateSort — Classification & Library Pipeline Fixes Round 2

## Context

User completed another full walkthrough after the previous critical fixes. 
Several bugs remain in the classification-to-library pipeline and UI 
behavior. These must be resolved before moving to the Crate Manager.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

---

## CRITICAL FIXES

### Fix 1: Genre change on artist doesn't cascade to track rows

When an artist's genre is changed (via Set Genre button or right-click 
Change Genre), the artist row updates but the track child rows underneath 
do NOT update their Proposed Genre column.

Fix: After changing an artist's genre, immediately loop through all child 
track items and update their Proposed Genre column to match the new artist 
genre:

```python
for i in range(item.childCount()):
    child = item.child(i)
    child.setText(COL_GENRE, new_genre)  # or whatever the correct column
```

This must happen in real-time whenever the parent genre changes, not just 
on initial tree build.

### Fix 2: Track-level genre changes don't persist to Library Browser

When a track's genre is individually changed in the classification view 
(via right-click Change Genre on a track row), that change does NOT appear 
in the Library Browser. The Library Browser shows the raw file genre tag 
for tracks instead of the overridden genre.

Artist-level genre changes DO persist. Track-level changes do not.

Debug:
1. Check if track-level genre overrides are being saved to 
   classification_session.json (they might only save artist-level data)
2. Check if the Library Browser enrichment reads track-level overrides 
   from the session file
3. The session data structure may need to store per-track genre overrides 
   alongside the artist-level genre

Fix: The session JSON should store track-level overrides (keyed by file 
path). The Library Browser should check for track-level overrides first, 
fall back to artist-level genre, then fall back to raw file tag.

### Fix 3: "Approve Selected" uses highlight instead of checkboxes

"Approve Selected" currently approves the highlighted/orange row instead 
of rows with checked checkboxes. This is inconsistent with "Set Genre" 
which correctly uses checkboxes.

Fix: "Approve Selected" must approve all rows with checked checkboxes, 
not the highlighted row. All batch action buttons (Approve Selected, 
Set Genre, Select All) should consistently use checkboxes as their 
selection source.

### Fix 4: Library Browser artist rows not enriched

After classification and approval, artist rows in the Library Browser 
show blank genre. Only the track rows show data (from file metadata).

Fix: The Library Browser must apply classification session data to artist 
rows, not just track rows. For each artist in the session file, the 
matching artist row in the Library Browser should display:
- Genre (the approved/classified genre from the session)
- Any other classification data (confidence → "Confirmed" if approved)

The matching should use the same canonical name lookup that was fixed in 
the previous session (sort-form, primary name, raw string).

### Fix 5: Cancel button on startup scan doesn't work

Clicking Cancel during the library scan dismisses the UI but the library 
loads anyway. Cancel should:
1. Actually stop the scanner thread (emit a cancel signal, check for 
   cancellation in the scan loop)
2. Return to the welcome screen / launch dialog where the user can 
   choose a different library or re-scan

### Fix 6: No way to change library after initial load

Once a library is loaded, there's no way to switch to a different 
directory without quitting the app.

Add a "Change Library..." option:
- In the Dashboard, add a small text link or button near the library 
  path display: "Change Library..."
- Clicking it opens the directory picker (same as initial setup)
- After selecting a new directory, re-scan and return to the dashboard
- Also clear or archive the current classification session since it 
  won't match the new library

---

## UI FIXES

### Fix 7: Remove orange row highlight from classification view

Clicking a row in the classification view should NOT highlight it orange. 
The orange highlight serves no purpose here:
- Double-click expands/collapses
- Checkboxes select for batch actions
- Right-click opens context menus

Remove the selection highlight entirely from the classification tree 
widget. One approach: set selection mode to NoSelection on the tree 
widget, since selection isn't used for anything.

Keep orange highlight in the Library Browser where it indicates the 
active track for the album art panel.

### Fix 8: DJ Tools (untagged) — clean up display

The "DJ Tools (untagged)" entry has a Unicode icon/special character in 
the artist name. Remove it — just plain text "DJ Tools (untagged)".

### Fix 9: Approval feedback improvements

After "Approve All" or any batch approval:
- The progress counter should visibly change — flash green or change to 
  a completion message like "All 61 artists approved ✓"
- If the user clicks "Done — Accept Remaining" and there were items to 
  approve, show a brief confirmation before navigating

### Fix 10: Confidence → "Confirmed" verification

Verify that after approval, the Confidence column actually shows 
"Confirmed" in green. The previous fix claimed this was implemented 
but the user reported still seeing LOW on approved rows. Double-check 
that _refresh_item_display is being called after approval state changes.

---

## Testing — Full pipeline walkthrough

This is the definitive test. Every step must pass:

1. Delete classification_session.json
2. Launch app
3. Load test library
4. Click Classify Library
5. Use "Set Genre" to change several artists' genres
6. Expand those artists — verify track rows ALSO show the new genre
7. Change one individual track's genre via right-click
8. Check some artists, click "Approve Selected" — verify CHECKED rows 
   are approved (not just highlighted row)
9. Click "Approve All" — verify ALL rows become Approved including 
   any Edited ones
10. Verify Confidence shows "Confirmed" on approved rows
11. Verify progress counter shows completion feedback
12. Click "Done — Accept Remaining"
13. Verify navigation goes to Library (not Dashboard)
14. In Library: verify artist rows show approved genres (not blank)
15. In Library: expand artists — verify tracks show the genres set in 
    classification (not raw file tags)
16. Verify the individual track genre change from step 7 persists
17. Close app, relaunch
18. On startup scan, click Cancel — verify it stops and returns to 
    welcome/launch screen
19. Reload the library — verify classification data persists from 
    the previous session
20. Verify no orange highlight on rows in classification view
21. Verify DJ Tools entry has no special character icon

ALL 21 steps must pass. Fix 1-4 (pipeline) are the gate.
