# CrateSort — Undo/Redo: Tab Switch + Button Style Fix (Prompt 18)

> **Run this at Sonnet high effort. Read `src/gui/main_window.py` completely before making any changes. Make exactly the two changes described below and nothing else.**

## Files to Read First

- `src/gui/main_window.py` — only file to change

---

## Change 1 — Auto-Tab Switch on Undo/Redo

When undo or redo is triggered, the app must automatically switch to the tab where the action originally occurred so the user can see what changed.

In `_do_undo()` and `_do_redo()`, after getting the command from the stack but before calling `undo()` or `execute()`:

1. Read `command.source_tab`
2. Compare to the currently active tab
3. If they differ, switch the active tab to `command.source_tab` programmatically — use whatever method `main_window.py` already uses to switch tabs (the same method the sidebar nav buttons use)
4. Then execute the undo/redo
5. Then update the footer with the teal status text

The tab switch must happen BEFORE the undo/redo executes so the user sees the result in the correct view.

---

## Change 2 — Undo/Redo Button Style: Solid Fill

The Undo and Redo buttons currently use an outline/border style with transparent background. Replace this with a solid filled button style matching the dashboard action buttons (Manage Crates, Organize Files).

**Active state (can undo/redo):**
- Background: solid teal `#428175`
- Text: cream `#f1e3c8`
- Border: none
- Border radius: 6px
- Font: same weight and size as the dashboard action buttons
- Cursor: pointer

**Inactive state (stack empty):**
- Background: solid muted gray `#3a3a3a`
- Text: muted cream `#7a7a7a`
- Border: none
- Border radius: 6px
- Not clickable (`setEnabled(False)`)

Apply via `setStyleSheet()` on each button. Call a helper method `_update_undo_buttons()` that sets the correct stylesheet based on `can_undo()` and `can_redo()` state — this method is already called after every push/undo/redo, just update what it sets.

Do not change button size, position, labels, or anything else about the buttons. Only change the visual style from outline to solid fill.

---

## What NOT to Change

Do not touch `src/gui/crate_manager.py`, `src/utils/undo_manager.py`, or any other file. Only `main_window.py`.
