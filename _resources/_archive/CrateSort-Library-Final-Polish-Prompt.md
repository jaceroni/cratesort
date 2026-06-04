# CrateSort — Library Browser Final Polish

## Context

The Library Browser is functional with artist-nesting, inline editing, 
album art panel, and drag-and-drop art replacement. This is the final 
polish round before a full start-to-finish walkthrough.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

---

## Fixes

### 1. Cell flash on edit commit

After an inline edit is committed (Enter or click-away), the cell 
background should briefly flash teal (#428175) for ~800ms then return 
to normal. This is the visual confirmation that the change was saved.

Implementation: after committing the edit, set the cell's background to 
teal via setBackground(QBrush(QColor("#428175"))), then use 
QTimer.singleShot(800, ...) to restore the original background.

### 2. Click-away auto-commits

If the user has modified text in an active editor and clicks elsewhere 
(another cell, another row, empty space), the edit should auto-commit 
(same as Enter) and flash teal. The editor must close immediately — no 
lingering open editors.

The ONLY way to cancel an edit is pressing Escape, which reverts to the 
original text with no flash.

Summary:
- Enter → commit, close, flash teal
- Click away / focus lost → commit, close, flash teal
- Escape → cancel, close, revert, no flash

### 3. Remove divider bar above album art panel

There's a white/light horizontal line between the nav buttons and the 
album art panel. Remove it entirely. Replace with ~50px of empty space 
between the Settings nav button and the art panel. Space is the separator, 
no line needed.

Look for any QFrame, border-bottom, border-top, or separator widget 
between the nav buttons and the art panel and remove it.

### 4. Remove album art replacement confirmation

When dragging an image onto the album art panel, do NOT show a 
confirmation dialog. Just replace the art immediately. Same when using 
"Replace Art..." from the right-click menu — open file picker, select 
image, write immediately.

After replacement, flash the art panel border teal for ~800ms to confirm 
the change took.

KEEP the confirmation dialog ONLY for "Remove Art" from the right-click 
menu, since that's destructive. Simple dialog: "Remove album art from 
[track title]?" with Cancel and Remove buttons.

### 5. Column minimum widths — verify

Confirm that the QFontMetrics column width enforcement from the previous 
round is actually working. Every column header must be fully visible 
without clipping at default window size. If any headers are still clipped, 
debug and fix.

### 6. Verify all previous fixes hold

Quick check that nothing regressed:
- Inline editing only on allowed fields (Title, Album, Style Tags, BPM, 
  Year, Comments)
- Genre and Artist NOT editable via double-click
- Right-click menus consistent between classification and library views
- Album art updates when clicking tracks in both views
- "The" handler applied to artist names
- No system blue anywhere
- Orange selection with dark text
- No left-side selection indicator

---

## Testing — Full start-to-finish walkthrough

This is the complete flow test. Go through every step:

1. Delete classification_session.json
2. Launch app — verify launch dialog asks to load library or choose new
3. Load test library — verify scan runs with progress indicator
4. Dashboard appears — verify stats, genre table, guidance banner
5. Click "Classify Library" — verify classification runs with progress
6. Classification view — verify artists grouped by genre
7. Verify "The" artists in sort form (Gap Band, The — one entry)
8. Verify Comments column visible (8 columns)
9. Change D'Angelo's genre to Funk/Soul — verify column updates
10. Approve a few artists — verify status changes
11. Click "Back to Dashboard"
12. Click "Library" in sidebar
13. Verify artist-nested view with all tracks
14. Click a track — verify album art shows in sidebar
15. Double-click a Title cell — edit, press Enter — verify teal flash
16. Double-click an Album cell — edit, click away — verify auto-commit 
    and teal flash
17. Double-click a Genre cell — verify nothing happens
18. Press Escape while editing — verify cancel, no flash
19. Right-click artist → Change Genre — verify dropdown
20. Right-click track → Edit Style Tags — verify dialog
21. Right-click track → Show in Finder — verify it opens the folder
22. Drag an image onto album art panel — verify immediate replacement 
    with teal flash, no confirmation dialog
23. Right-click art panel → Remove Art — verify confirmation appears
24. Search for an artist — verify filtering
25. Filter by genre — verify filtering
26. Verify no system blue anywhere throughout the entire flow
27. Close app, relaunch — verify library path remembered

Report any issues found during the walkthrough.
