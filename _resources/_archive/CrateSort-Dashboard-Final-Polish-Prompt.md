# CrateSort — Dashboard & Icon Final Polish

## Context

Final polish items before moving to the Crate Manager build.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fixes

### Fix 1: Reduce music note icon spacing

The gap between the music note icon and the track name is too wide. 
The person silhouette icon spacing is correct — don't touch that.

Reduce the music note pixmap width from 14px to about 11px (or whatever 
brings the spacing in line — roughly 25% reduction). The icon drawing 
stays the same size, just less transparent padding on the right.

### Fix 2: Album art clears when leaving Library/Classification

When the user navigates away from the Library Browser or Classification 
view (to Dashboard, Crates, Organize, or Settings), the album art panel 
should reset to the placeholder image.

In main_window.py, connect the sidebar navigation so that switching to 
any view OTHER than Library or Classification calls the art panel's 
reset/clear method. Show the placeholder (music note or vinyl icon) 
instead of lingering art from a previous selection.

```python
def _on_nav(self, index):
    # ... existing view switching ...
    if index not in (1, 5):  # Not Library or Classification
        self._art_panel.clear()  # or show placeholder
```

### Fix 3: Move action buttons to top of dashboard

Relocate the three action buttons (Classify Library, Manage Crates, 
Organize Files) from the bottom of the dashboard to the TOP, directly 
below the library path and "Change Library..." link, above the stat 
cards.

Remove the "ACTIONS" label — the buttons are self-explanatory.

Layout order from top to bottom:
1. "Library Dashboard" heading
2. Library path + "Change Library..." link + "Serato library detected"
3. **Action buttons row** (Classify Library, Manage Crates, Organize Files)
4. Stat cards (Files, Artists, Genre Tags, Complete Metadata)
5. Format breakdown
6. Genre distribution table (with drag handle)
7. Contextual tips banner (always visible)

### Fix 4: Tips always visible, contextual content

Remove the show/hide toggle and the "Show tips" link. The tip banner 
at the bottom of the dashboard is always visible.

Make the content contextual based on the user's workflow state:

**State 1 — No classification done:**
"What's next? Classify your library to assign genres to each artist. 
This step only analyzes and tags — no files will be moved or renamed 
until you choose to organize."

**State 2 — Classification done, library not organized:**
"Your library is classified. Browse your collection in the Library tab, 
manage your Serato crates, or organize your files when you're ready."

**State 3 — Classification done and organized:**
"Your library is organized. Use style tags to add detail to your tracks, 
or build crates to prepare for your next set."

Determine the state by checking:
- Does classification_session.json exist with approved entries? → 
  classified = True
- Has the organizer been run? (Check for a flag in QSettings or a 
  reorganization log file) → organized = True
- Neither → state 1. Classified only → state 2. Both → state 3.

### Fix 5: Remove "ACTIONS" label

Remove the "ACTIONS" text header that was above the buttons. The buttons 
speak for themselves. No label needed.

---

## Testing

1. Launch app, load library
2. Dashboard: verify buttons are at the top (below path, above stats)
3. Verify no "ACTIONS" label
4. Verify tip banner is visible at bottom with appropriate message
5. Classify library → Done → go to Dashboard
6. Verify tip message changed to state 2 content
7. Go to Library, click a track — verify album art shows
8. Go to Dashboard — verify album art cleared to placeholder
9. Go back to Library — verify art shows when clicking a track
10. Go to Settings — verify art cleared
11. Check music note spacing — tighter than before, comfortable gap
12. Verify person silhouette spacing unchanged
