# CrateSort — Classification Simplification & Remaining Fixes

## Context

After extensive user testing, the approval workflow in the classification 
view is being removed entirely. The act of reviewing and moving forward 
IS the approval. This session simplifies the classification UI and fixes 
remaining issues.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## MAJOR CHANGE: Remove the approval workflow

The classification screen is a review-and-fix tool, NOT an approval tool. 
The user reviews the results, fixes what's wrong, and moves on. Moving 
forward = implicit approval. No explicit approval step needed.

### What to remove:

1. **All approval buttons** — remove "Approve All HIGH", "Approve Selected", 
   and "Approve All" from the top bar entirely

2. **All approval status tracking** — remove the Pending/Approved/Edited/
   Flagged/Confirmed status system. Remove the state field from 
   ArtistEntry or stop using it for display. Remove _do_approve, 
   _approve_all, _approve_all_high, _approve_selected, 
   _approve_all_in_genre methods (or leave them as dead code if removing 
   is risky — but remove all UI references)

3. **Status column content** — simplify to show only "Modified" (in teal 
   #428175) on items the user has changed (genre change, artist reassign, 
   etc.). Everything else shows blank. No more Pending/Approved/Edited/
   Flagged/Confirmed labels.

4. **Confidence column** — goes back to showing only the engine's 
   confidence: HIGH (green), MEDIUM (amber), LOW (red). Remove the 
   "Confirmed" override that replaced confidence after approval. The 
   confidence is useful info for the user to spot items needing attention.

5. **Progress counter** — remove "X of Y artists approved" from the top 
   right. Replace with a simple count: "54 artists · 96 tracks" (just 
   informational, matches the genre sidebar's "All" entry).

6. **Genre sidebar approval indicators** — remove any green/amber dots 
   or approval-related indicators from the genre list. Keep just genre 
   name + artist count + track count.

7. **"Done — Accept Remaining" button** — rename to **"Accept & Go to 
   Library"**. It no longer needs to approve anything — it just saves 
   the current state and navigates to the Library Browser. If the user 
   has made changes, they're already saved. The button is essentially 
   "I'm done reviewing, take me to my library."

### What to keep:

- Genre changes via right-click and Set Genre button (these are edits, 
  not approvals)
- Artist reassignment
- Style tag editing
- Select All / Deselect All
- Search
- The "Modified" status indicator on changed items
- The genre sidebar with counts
- Confidence column (HIGH/MEDIUM/LOW only)
- "Back to Dashboard" button

### Updated top bar layout:

**Left side:** Search field (expanded to fill available width)
**Right side:** [Select All] [Set Genre...]

That's it. No approval buttons. Clean and simple.

### Updated bottom bar:

**Left side:** [← Back to Dashboard]
**Right side:** [Accept & Go to Library]

### Updated flow:

1. User clicks "Classify Library" from dashboard
2. Classification runs, results appear
3. User reviews — changes genres, reassigns artists as needed
4. Items the user changed show "Modified" in the Status column
5. When done, user clicks "Accept & Go to Library"
6. App saves state and navigates to Library Browser

---

## OTHER FIXES

### Fix: Remove collaboration arrow (↗) from artist names

The ↗ arrow suffix on artist names is confusing. Remove it from all 
artist name displays. The collaboration detection can still flag items 
in the Status column as "Collaboration" if needed, but remove the arrow 
from the artist name text.

Search for the ↗ character and the code that appends it to artist names. 
Remove all instances.

### Fix: Collaboration false positives on hyphenated names

Jean-Jacques Perrey is being flagged as a collaboration because of 
hyphens in the name. The collaboration detector should NOT flag:
- Hyphenated first names (Jean-Jacques, Mary-Kate, Anne-Marie)
- Hyphenated last names
- A-F-R-O (stylized name with hyphens)

Only flag actual collaboration indicators: feat., ft., featuring, vs., 
and commas that separate distinct artist names (not commas in "Last, 
First" sort format).

### Fix: Music note icon spacing

The music note icon still has slightly too much space before the track 
name. Reduce the pixmap width from 11px to about 9px (25% reduction 
from current). The person silhouette at 18px is correct — don't touch.

---

### Fix: Library flashes and resets when arriving from Accept

When the user clicks "Accept & Go to Library" from the classification 
view, the Library Browser loads. But after the user starts expanding 
artists, the screen flashes and the entire tree rebuilds, collapsing 
all expanded rows. This only happens when arriving via the Accept button, 
NOT when navigating to Library via the sidebar.

Cause: likely a delayed signal, timer, or duplicate rebuild trigger 
from the classification accept flow. The Library is being rebuilt twice — 
once on navigation, then again from a delayed callback.

Fix: Find and remove the duplicate rebuild. Check:
- _on_classifier_done — does it trigger a library reload on a timer?
- Does the "done" signal chain cause load() to be called twice?
- Is there a QTimer.singleShot in the accept flow that triggers a 
  second rebuild?

The Library should build its tree exactly ONCE when navigated to, and 
never rebuild unless the user explicitly triggers a rescan or the 
underlying data changes.

---

## Testing

1. Delete _CrateSort folder
2. Launch app, load library, classify
3. Verify NO approval buttons anywhere (no Approve All HIGH, no 
   Approve Selected, no Approve All)
4. Verify top bar: wide search field + Select All + Set Genre on right
5. Verify bottom bar: Back to Dashboard + Accept & Go to Library
6. Verify Status column is blank for untouched items
7. Change a genre on an artist — verify Status shows "Modified"
8. Verify Confidence shows HIGH/MEDIUM/LOW (not Confirmed)
9. Verify no progress counter saying "X of Y approved"
10. Verify no ↗ arrows on any artist names
11. Verify Jean-Jacques Perrey and A-F-R-O are NOT flagged as 
    collaborations
12. Click "Accept & Go to Library" — verify it navigates to Library
13. Verify music note icon spacing is tighter
14. Go back to classification — verify state was saved (your changes 
    are still there)
15. From classification, click "Accept & Go to Library"
16. Immediately start expanding artists in the Library
17. Verify the screen does NOT flash/reset/collapse — tree stays stable
