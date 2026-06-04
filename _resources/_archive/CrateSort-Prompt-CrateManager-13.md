# CrateSort — Sub-Crate Background Color + Remove Debug Prints (Prompt 13)

> **Run this at Sonnet high effort. Read `src/gui/crate_manager.py` completely before making any changes. Make exactly the two changes described below and nothing else.**

## Files to Read First

- `src/gui/crate_manager.py` — only file to change

---

## Change 1 — Sub-Crate Default Background Color

Currently all unselected crates use `#2F2F2F` as their background (State A). Sub-crates need a darker background so they're visually grouped under their parent even when the parent isn't actively selected.

In `CrateItemDelegate.paint()`, after getting the `path` and `state` from the index, check if the item is a sub-crate by checking whether the index has a valid parent:

- If the item is a top-level crate AND state is A: use background `#2F2F2F`
- If the item is a sub-crate AND state is A: use background `#222222`
- All other states (B, C, D) keep their existing colors regardless of depth

To check if an item is a sub-crate in the delegate's `paint()` method, use `index.parent().isValid()`. If `index.parent().isValid()` is True, the item is a sub-crate.

Add a `BG_SUB = QColor('#222222')` constant to `CrateItemDelegate` alongside the existing color constants.

The bg color selection logic in `paint()` should be:

- state B → `BG_B`
- state C → `BG_C`  
- state D → `BG_D`
- state A AND sub-crate → `BG_SUB`
- state A AND top-level → `BG_A`

---

## Change 2 — Remove All Debug Print Statements

Remove every debug print statement that was added during troubleshooting. Search the entire file for lines containing any of these strings and remove them:

- `[paint]`
- `[State C]`
- `[Selection]`
- `[set_state_b]`
- `[Debug]`

Remove only the print statements themselves — do not change any surrounding logic.

---

## What NOT to Change

Do not touch drag logic, expand behavior, track panel, library browser, row heights, or any other view. Only make the two changes described above.
