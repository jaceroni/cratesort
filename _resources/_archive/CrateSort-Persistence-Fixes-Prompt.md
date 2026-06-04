# CrateSort — Critical Persistence & Interaction Fixes

## Context

User found multiple persistence and interaction bugs during a full 
walkthrough. These are blocking progress to the Crate Manager.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## CRITICAL PERSISTENCE FIXES

### Fix 1: Track-level genre changes from classification STILL don't persist

THIS IS THE THIRD TIME THIS BUG HAS BEEN REPORTED. It must be fixed.

**The problem:** When an artist's genre is changed in the classification 
view and cascades to track child rows, only the ARTIST-level genre 
persists to the Library Browser. The TRACK-level genres revert to the 
raw file metadata.

**Root cause:** _cascade_genre_to_children updates the display text on 
the QTreeWidgetItem but does NOT update the underlying track data in the 
ClassificationSession / ArtistEntry data structure. When the session is 
saved to JSON, the track genre fields still contain the old raw values.

**The fix must do ALL of these:**
1. When _cascade_genre_to_children runs, ALSO update each track's genre 
   in the ArtistEntry data: `entry.tracks[i].genre_tag = new_genre` (or 
   whatever field stores the track's classified genre)
2. When a track's genre is individually changed via right-click, update 
   the track data in the ArtistEntry
3. When the session is saved to JSON, track-level genre overrides must 
   be included in the file
4. When the Library Browser reads the session JSON, it must use the 
   track-level genre from the session, not the raw file metadata
5. VERIFY by: changing a genre in classification → going to Library → 
   expanding the artist → confirming the track shows the NEW genre

Print the session JSON contents to console after saving so we can 
verify the data structure includes track genres.

### Fix 2: Library Browser edits don't persist between sessions

All inline edits in the Library Browser (title, album, BPM, year, 
comments, style tags) are lost when the app is closed and reopened. 
The edits exist in memory (_edits dict) but are never written to disk.

**Fix:** Save Library Browser edits to a persistent file. Options:

Option A (recommended): Save _edits dict to a JSON file alongside the 
classification session (e.g., `library_edits.json` in the _CrateSort 
data directory). Load on startup, apply to display.

Option B: Write edits directly to the file's ID3 tags via mutagen. This 
is the "real" fix but more dangerous — save for the Organize step.

**Go with Option A for now.** Save edits to JSON, load on startup. The 
actual metadata write to ID3 tags happens during the Organize step when 
the user explicitly triggers it. This matches the "propose then approve" 
pattern used throughout the app.

The edits JSON should store: file_path → {field: new_value} for each 
edited field. On Library Browser load, apply these overrides to the 
display.

### Fix 3: Library Browser genre edits don't persist

Same root cause as Fix 2 — genre changes made via right-click in the 
Library Browser are stored in memory but lost on restart. Include genre 
edits in the same persistence mechanism (library_edits.json).

---

## INTERACTION FIXES

### Fix 4: Bring back orange row highlight in classification view

Fix 7 from the previous round (NoSelection mode) went too far. Clicking 
a row in the classification view now shows no visual feedback at all — 
the user can't tell what they're interacting with.

**Bring back the orange highlight on click.** But make it purely visual — 
it does NOT affect batch actions. The rule is:

- **Single click** → highlights the row orange (visual focus indicator)
- **Double click** → expands/collapses artist row
- **Checkbox** → selects for batch actions (Approve Selected, Set Genre)
- **Right-click** → opens context menu

The highlight and checkboxes are independent systems. Highlighting a row 
does not check its checkbox. Checking a checkbox does not require the 
row to be highlighted. Batch actions (Approve Selected, Set Genre) ONLY 
look at checkboxes, never at the highlighted row.

Change selection mode back from NoSelection to SingleSelection. Keep 
the batch action logic using checkboxes (already fixed in the previous 
round).

### Fix 5: Library Browser — single click expanding artists

In the Library Browser, a single click on an artist row is expanding it 
to show tracks. This should require a DOUBLE click. 

- **Single click on artist row** → highlights it orange, updates album 
  art panel (if the artist has a representative image)
- **Double click on artist row** → expands/collapses to show/hide tracks
- **Single click on track row** → highlights it orange, updates album 
  art panel

Check if there's an itemClicked signal connected that's calling 
expandItem or if the tree widget has some auto-expand behavior enabled. 
The expand/collapse should only happen on double-click (itemDoubleClicked).

---

## CLARIFICATION (not a bug)

### Classification session retention across app restarts

The user noted that the classification screen still shows "Approved" 
after closing and reopening the app. THIS IS CORRECT BEHAVIOR. The 
classification session file (classification_session.json) saves your 
work so you don't have to redo it. When you reopen the app and go to 
classification, it loads your previous session with all approvals intact.

If the user wants to start fresh, they delete the session file or we 
add a "Reset Classification" button.

---

## Testing

### Pipeline persistence (MOST IMPORTANT):
1. Delete classification_session.json and library_edits.json
2. Launch app, load test library, classify
3. Change D'Angelo's genre to Funk/Soul
4. Verify tracks under D'Angelo ALSO show Funk/Soul
5. Approve all
6. Click Done — Accept Remaining → goes to Library
7. In Library, expand D'Angelo → verify tracks show Funk/Soul (NOT the 
   raw file tag)
8. Edit a track title in the Library (e.g., change "Cold Feet" to 
   "Cold Feet Blues")
9. Edit a track's BPM
10. Close the app completely
11. Reopen the app, go to Library
12. Verify D'Angelo's tracks still show Funk/Soul
13. Verify the title edit ("Cold Feet Blues") persisted
14. Verify the BPM edit persisted

### Interaction:
15. Go to Classification view — click a row — verify orange highlight
16. Verify clicking does NOT expand the row (only double-click expands)
17. Check a checkbox — verify orange highlight and checkbox are independent
18. Click Approve Selected — verify it uses checkboxes, not highlight
19. Go to Library — click an artist — verify orange highlight, NOT expand
20. Double-click artist — verify it expands
21. Click a track — verify orange highlight and album art updates

ALL 21 steps must pass.
