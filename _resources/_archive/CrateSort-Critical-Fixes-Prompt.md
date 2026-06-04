# CrateSort — Critical Classification & Pipeline Fixes

## Context

User completed a full start-to-finish walkthrough and found critical bugs. 
The most severe: classification changes (genre edits, approvals, artist 
reassignments) do NOT persist to the Library Browser. The entire 
classification workflow produces no lasting effect.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## PRIORITY 1 — CRITICAL PIPELINE FIX

### Fix 1: Classification changes must persist to Library Browser

THIS IS THE MOST IMPORTANT FIX. Everything else is secondary.

**The problem:** The user makes classification changes (genre edits, 
approvals, artist reassignments) in the Classification view. These 
appear to work in the classification UI. But when navigating to the 
Library Browser, NONE of the changes are reflected. The Library Browser 
shows raw file metadata (e.g., Albert King shows genre "Other" instead 
of the approved "Blues").

**Debug the full pipeline:**

1. Check if classification_session.json is being written correctly after 
   edits and approvals. Print its contents to console after an approval.

2. Check if the Library Browser reads classification_session.json on load. 
   Print what data it finds.

3. Check if the Library Browser's enrichment logic (matching session data 
   to scanner tracks) is working. The matching might fail due to path 
   differences, artist name normalization, or key mismatches.

4. The Library Browser should use the CLASSIFIED genre (from the session) 
   as the primary genre display, falling back to the raw file tag only 
   when no classification exists.

5. Verify the session JSON includes: artist name, proposed genre, approval 
   status, and a list of track file paths for each artist. The Library 
   Browser needs all of this to enrich its display.

**The fix must ensure:** After classifying and approving in the 
Classification view, navigating to the Library Browser shows the 
approved genres, not the raw file tags. Albert King shows "Blues" 
(approved), not "Other" (raw tag). Screamin' Jay Hawkins shows "Blues" 
(changed from Rock), not whatever the file says.

### Fix 2: Approval buttons skip "Edited" rows

The approval buttons work for "Pending" rows but SKIP rows with "Edited" 
status. Rows the user manually changed stay as "Edited" even after 
clicking Approve All.

Fix: ALL approval actions must approve rows regardless of current status:
- "Approve All" → approves EVERY row: Pending, Edited, AND Flagged
- "Approve All HIGH" → approves all HIGH confidence rows that are 
  Pending, Edited, OR Flagged  
- "Approve Selected" → approves all checked rows regardless of status
- Individual "Approve" → approves regardless of current status

The condition should be: if status != 'approved', set to 'approved'.

### Fix 3: "Done — Accept Remaining" doesn't actually approve

"Done — Accept Remaining" navigates away without approving remaining rows. 
Fix the flow:

1. Set ALL non-approved rows to "approved" (Pending, Edited, Flagged → 
   all become Approved)
2. Save the session data to classification_session.json
3. Navigate to the **Library** view (not Dashboard) — the natural next 
   step after classification is reviewing your library
4. Show a brief confirmation in the Library view: "Classification 
   complete — 61 artists approved"

---

## PRIORITY 2 — CLASSIFICATION ENGINE FIXES

### Fix 4: Artist-level genre blank when tracks have genres

Some artists have no proposed genre at the artist level despite their 
tracks having classified genres. The classifier's majority voting should 
populate the artist genre from track genres.

This may be caused by the "The" handler changing artist names after 
classification, creating a mismatch. Debug by checking if the classifier 
output uses "The Gap Band" but the display uses "Gap Band, The" and the 
lookup fails.

### Fix 5: Track-level proposed genre shows raw tag

Track child rows display the raw file genre tag (e.g., "Funk") in the 
Proposed Genre column instead of the CrateSort-classified genre (e.g., 
"Funk/Soul").

Fix: Track rows should show the artist's classified genre in the 
Proposed Genre column, NOT the raw file tag. The raw tag belongs in 
Current Genre only.

### Fix 6: Add "Traditional" as 13th genre

Add "Traditional" everywhere:
- Classifier genre list and style-to-genre mapping
- All genre dropdowns in all views
- Genre sidebar in classification view
- Styles mapping to Traditional: Traditional Pop, Vocal Pop, Standards, 
  Easy Listening, Vocal, Crooner, Big Band Vocal, Lounge Vocal, 
  Adult Contemporary, Middle of the Road, Novelty
- Matches CrateView's existing taxonomy

### Fix 7: Video files in purpose folders → Specialty

Video files (MP4, M4V, MOV, AVI) in folders matching purpose patterns 
(movie clips, commercials, clips, films, visuals) should be classified 
as Specialty. Exclude from artist-level genre voting. Same logic as the 
short-duration drops rule but triggered by video format + purpose folder.

---

## PRIORITY 3 — UI IMPROVEMENTS

### Fix 8: Approval completion feedback

When any batch approval runs, show visible confirmation:
- Flash the progress counter green (#6B9E78) for 2 seconds
- Or show a toast: "All artists approved" / "12 artists approved"
- The user needs clear feedback that something happened

### Fix 9: Confidence → "Confirmed" after approval

Once an artist is approved, change the Confidence column from 
LOW/MEDIUM/HIGH to **"Confirmed"** in green (#6B9E78). The engine's 
initial confidence is irrelevant after user verification.

### Fix 10: Auto-scroll to follow moved items

When a genre change causes an item to relocate due to sort order, 
auto-scroll the view to center on that item:
```python
self._tree.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)
```

### Fix 11: Batch genre change — two access points

(a) Right-click when multiple artists are checked → "Change Genre..." 
applies to ALL checked artists.

(b) "Set Genre" dropdown button in the top action bar, LEFT side near 
the search field. Select artists, click Set Genre, pick genre, all 
selected get that genre.

### Fix 12: Select All / Deselect All toggle

Toggle button in the top action bar, LEFT side near search. "Select All" 
checks every row, text flips to "Deselect All". Clicking again unchecks.

### Fix 13: Top bar layout — two zones

Left zone (near search): Search → Select All/Deselect All → Set Genre
Right zone (existing): Approve All HIGH → Approve Selected → Approve All

Editing tools left, approval actions right.

### Fix 14: Edit commit flash — verify working

The teal text flash on edit commit was fixed last session. Verify it's 
still working. If the row flash is still not visible, the 
setForeground approach may also be blocked by stylesheets. Fall back to 
a toast message at the bottom of the view: "Changed: [field] → [new value]"

---

## Testing

### Critical pipeline test (MOST IMPORTANT):
1. Delete classification_session.json
2. Launch app, load test library
3. Click Classify Library
4. Change a few artists' genres (e.g., Albert King → Blues)
5. Click Approve All
6. Verify ALL rows show "Approved" (none stuck as "Edited")
7. Click Done — Accept Remaining
8. Verify it navigates to Library (not Dashboard)
9. In Library, expand Albert King → verify genre shows "Blues" (not "Other")
10. Check other changed artists — verify their genres reflect what you 
    set in classification
11. Close app, relaunch, go to Library — verify changes persisted

### Classification engine tests:
12. Verify no artists have blank Proposed Genre when their tracks have 
    genres
13. Verify track-level Proposed Genre shows CrateSort genre, not raw tag
14. Verify "Traditional" appears in all genre dropdowns
15. Verify video clips in purpose folders classify as Specialty

### UI tests:
16. Approve All → verify progress counter flashes green
17. Approved artists → verify Confidence shows "Confirmed"
18. Change genre on sorted list → verify view scrolls to follow the item
19. Check multiple artists → Set Genre → verify batch change works
20. Select All → verify all checked → Deselect All → verify all unchecked
21. Verify top bar layout: editing tools left, approval tools right

Launch and verify everything works. Fix 1 (pipeline persistence) is the 
gate — nothing else matters if changes don't persist.
