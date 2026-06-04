# CrateSort — Edit Flash Fix

## Context

The Library Browser inline editing is working. The teal flash after 
committing an edit has two problems that need fixing.

---

## Fixes

### 1. Flash only when text actually changed

The teal flash currently fires every time the editor closes, even if 
nothing was modified. Fix:

- When the editor opens (double-click), capture the original cell text 
  as `_edit_original_value`
- When the editor closes (Enter or click-away), compare the current text 
  to `_edit_original_value`
- If they're DIFFERENT → commit the change AND flash
- If they're the SAME → close the editor quietly, no flash, no commit

This prevents false-positive flashes when the user just clicks into a 
cell to read it and clicks away.

### 2. Replace background overlay with text color flash

The current approach uses a semi-transparent teal overlay widget on top 
of the row. This looks muddy/ugly, especially over orange selected rows.

Replace entirely with a TEXT COLOR flash:
- When a change is committed, change the text color of every cell in 
  that row to teal (#428175) for 1.5 seconds
- After 1.5 seconds, revert text color back to the default cream (#f1e3c8)
- Use item.setForeground(col, QBrush(QColor('#428175'))) for each column
- Restore with item.setForeground(col, QBrush(QColor('#f1e3c8'))) via 
  QTimer.singleShot(1500, ...)

Remove the _flash_row_overlay method and the QFrame overlay approach 
entirely. Text color changes are rendered by Qt regardless of stylesheet 
rules (unlike background which gets overridden by stylesheets).

If setForeground is also overridden by the stylesheet, use the same 
overlay approach but at 100% opacity (#428175 solid) with the text 
painted in dark (#2F2F2F). But try setForeground first — it should work.

---

## Testing

1. Launch app, load library, go to Library view
2. Double-click a Title cell, DON'T change anything, click away → 
   verify NO flash
3. Double-click a Title cell, change the text, press Enter → verify 
   row text turns teal for 1.5 seconds then reverts to cream
4. Double-click a cell, change text, click away → verify same flash
5. Verify flash looks clean on both unselected (dark) and selected 
   (orange) rows
6. Verify no muddy overlay artifacts
