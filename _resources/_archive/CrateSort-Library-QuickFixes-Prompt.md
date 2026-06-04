# CrateSort — Library Browser Quick Fixes

## Context

The Library Browser is nearly done. These are the last remaining issues 
from user testing.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

---

## Fixes

### 1. Edit commit flash not visible

The teal cell flash after committing an inline edit is either not firing 
or too subtle. Make it more obvious:

- Flash the ENTIRE ROW background teal (#428175), not just the individual 
  cell
- Duration: 1.5 seconds (was 800ms — too fast)
- Must be clearly visible against the dark row background
- After 1.5 seconds, restore the original row background

Test by: double-clicking a cell, typing something, pressing Enter. The 
entire row should visibly flash teal for 1.5 seconds.

### 2. Remove ALL album art confirmation dialogs

No confirmation dialogs for any album art operation:
- Drag image onto panel → replaces immediately, teal border flash
- Right-click "Replace Art..." → file picker → replaces immediately, 
  teal border flash
- Right-click "Remove Art" → removes immediately, teal border flash

No popups, no "are you sure", no cancel/yes dialogs. All operations are 
immediate with a teal flash confirmation.

Remove every QMessageBox or confirmation dialog related to album art.

### 3. Column minimum widths — debug and fix

The Duration column header is STILL being clipped despite the 
QFontMetrics enforcement. Debug this:

1. Print the measured width vs the actual column width for every column 
   to the console
2. Check if something is overriding the width after _enforce_min_col_widths 
   runs (another resize call, a layout pass, etc.)
3. Make sure _enforce_min_col_widths runs AFTER the tree is fully populated 
   and the widget has been shown/laid out
4. Try calling it with a short QTimer.singleShot(100, ...) delay after 
   the tree is built to ensure it runs after Qt's layout pass
5. Add extra padding — use horizontalAdvance(text) + 40 instead of + 24 
   to give more room

Every column header must be FULLY visible with NO clipping at any window 
size. This has been requested multiple times.

### 4. Default sort order — ascending (A to Z)

The library loads sorted by Artist descending (Z to A). Change to 
ascending (A to Z) as the default on first load.

Look for the initial sortByColumn call and change the sort order to 
Qt.SortOrder.AscendingOrder.

### 5. Verify previous fixes

- Inline editing: only Title, Album, Style Tags, BPM, Year, Comments 
  editable via double-click
- Genre and Artist NOT double-click editable
- Click-away auto-commits
- Escape cancels
- Album art panel position (below Settings, no divider line)
- Album art updates on track click in both views
- Right-click menus consistent
- No system blue

---

## Testing

1. Launch app, load test library, classify, go to Library
2. Verify sort is A-Z by default
3. Verify ALL column headers fully visible (especially Duration)
4. Double-click a Title cell, edit, press Enter — verify entire row 
   flashes teal for 1.5 seconds
5. Double-click another cell, edit, click away — verify row flashes
6. Press Escape while editing — verify no flash
7. Drag image onto art panel — verify immediate replacement, no dialog, 
   teal flash on panel
8. Right-click art panel → Remove Art — verify immediate removal, no 
   dialog, teal flash
9. Verify all previous fixes still hold
