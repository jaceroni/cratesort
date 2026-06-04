# CrateSort — Global Button Press State + Add Tracks Loading Feedback (Prompt 21)

> **Run this at Sonnet high effort. Read `src/gui/theme.py`, `src/gui/main_window.py`, and `src/gui/crate_manager.py` completely before making any changes. Before writing any code, verify that every class, method, and module you reference is already imported in the target file. Add any missing imports before using them.**

## Files to Read First

- `src/gui/theme.py` — where global styles should live
- `src/gui/main_window.py` — where global stylesheet is applied to the app
- `src/gui/crate_manager.py` — for the Add Tracks loading feedback only

---

## The Problem

Button pressed states are inconsistently applied across the app. The dashboard buttons have a working pressed state. Dialog buttons, undo/redo buttons, and other buttons do not. This is a design consistency failure.

The fix must be global — defined once, inherited everywhere — not patched per-dialog.

---

## Change 1 — Global QPushButton States in theme.py

In `src/gui/theme.py`, find where the global application stylesheet is defined. Add or update the global QPushButton rules to include consistent hover and pressed states for all button variants used in the app.

The global rules must cover:

Teal action buttons (background #428175):
- Default: background #428175, color #ffffff, font-weight 400, border-radius 6px, border none
- Hover: background #4f9688
- Pressed: background #2d6358

Muted gray cancel buttons (background #3a3a3a):
- Default: background #3a3a3a, color #f1e3c8, font-weight 400, border-radius 6px, border none
- Hover: background #4a4a4a
- Pressed: background #2a2a2a

Disabled buttons:
- background #2a2a2a, color #666666

These rules must be applied at the QApplication level via QApplication.setStyleSheet() or equivalent so every QPushButton in the entire app inherits them automatically — dialogs, sidebar buttons, dashboard buttons, undo/redo buttons, everything.

If individual dialogs or widgets are overriding these global styles with local stylesheets that omit the pressed state, remove the redundant local QPushButton rules and let the global stylesheet handle it. Only keep local rules that are truly specific to that widget (background color variants, size, etc.) and ensure they include :hover and :pressed states.

---

## Change 2 — Add Tracks Dialog: Immediate Loading Feedback

In `src/gui/crate_manager.py`, find `_AddTracksDialog`. When the user clicks "Add Selected":

1. Immediately disable the "Add Selected" button and change its text to "Adding..."
2. Disable the Cancel button
3. Call QApplication.processEvents() to force the UI to repaint before the operation runs
4. Execute the track addition
5. Dialog closes normally after completion

This gives immediate visual confirmation that the click registered during the 2-3 second operation.

---

## What NOT to Change

Do not change dialog logic, validation, text content, layout, or sizes. Do not change the dashboard button styles that are already working correctly — use them as the reference for what the global style should look like. Only standardize button states globally and add the Add Tracks loading feedback.
