# CrateSort — Classification View Round 4: Final Cleanup

## Context

The classification view has been through three rounds of polish. These are 
the last remaining items before we move on to building new views.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Delete any existing classification_session.json before testing.

## Fixes (4 items)

### 1. Remove orphan stems warning from dashboard

The dashboard currently shows "3 orphan .serato-stems file(s) found with 
no matching audio." This is diagnostic information that the user cannot 
act on. Remove this warning from the dashboard entirely. If orphan stems 
info is needed in the future, it belongs in a diagnostic or settings view, 
not the main dashboard.

### 2. Remove dead space on left side of rows

The left-side selection indicator was removed in the previous round, but 
the padding/margin/indentation that reserved space for it still remains. 
There is a large empty gap between the left edge of the table and the 
checkbox on each row.

Collapse this space. Look for:
- QTreeWidget indentation settings (setIndentation — set to 0 or minimal)
- Left padding/margin in stylesheet rules for QTreeWidget::item
- QTreeWidget::branch styling that reserves space
- Any margin-left or padding-left on item styles

The checkbox should sit close to the left edge of the row with minimal 
padding (4-8px max). Currently there's roughly 30-40px of dead space 
that needs to go.

### 3. Checkbox stable on hover over selected row

When hovering on an orange selected row, the checkbox border turns orange 
and the fill disappears, making the checkbox invisible against the orange 
background.

Fix: The checkbox styling must remain constant regardless of hover state. 
Add explicit hover rules that maintain checkbox visibility:

```css
QTreeWidget::indicator:hover {
    /* same as non-hover state */
    border: 1px solid #666666;
    background: transparent;
}
QTreeWidget::indicator:checked:hover {
    border: 1px solid #666666;
    background: #f1e3c8;
}
QTreeWidget::item:selected QTreeWidget::indicator {
    border: 1px solid #666666;
    background: transparent;
}
QTreeWidget::item:selected QTreeWidget::indicator:checked {
    border: 1px solid #666666;
    background: #f1e3c8;
}
```

Note: If Qt doesn't support the nested selector 
`QTreeWidget::item:selected QTreeWidget::indicator`, handle it via a 
custom item delegate or by connecting the selectionChanged signal to 
manually update indicator styles. The key requirement: the checkbox must 
ALWAYS be visible regardless of row selection or hover state.

### 4. Remove double-click to copy

The double-click to copy cell content feature on track rows is being removed. 
It's inconsistent since artist rows use double-click for expand/collapse. 
Remove the itemDoubleClicked handler that copies text and flashes the cell. 
Double-click should only do expand/collapse on artist rows and nothing on 
track rows (or also expand/collapse the parent).

### 5. Verify all previous fixes hold

Quick check that nothing from rounds 1-3 regressed:
- Orange selection with dark text (no blue anywhere)
- No left-side indicator
- All columns resizable
- Clean column headers (no slashes)
- Comments show on expanded track rows
- Double-click copies cell content on track rows
- Font sizes correct throughout
- Checkboxes visible on both dark and orange rows (non-hover)

## Testing

1. Delete classification_session.json
2. Launch app, load test library
3. Verify NO orphan stems warning on dashboard
4. Click Classify Library
5. Check left side of rows — minimal padding before checkbox
6. Select a row (orange) — hover over it — checkbox stays visible
7. Check/uncheck boxes on selected rows — always visible
8. Verify all previous fixes still work

## Important

This is the LAST polish pass on the classification view. Fix these 4 items 
and confirm. After this, we move to building the Library Browser view.
