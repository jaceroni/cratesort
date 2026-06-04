# CrateSort — Launch Screen Redesign: Eliminate _LaunchDialog

**Sonnet, high effort. Read every referenced file completely before writing any code.**

---

## Overview

The current launch experience has two disconnected pieces: a branded welcome screen (stack index 0 in DashboardWidget) and a separate `_LaunchDialog` popup that appears on top of it for returning users. The popup looks cheap and breaks the visual experience. This prompt eliminates the popup entirely and folds the returning-user experience directly into the welcome screen.

---

## Files to Read First

Read these files completely before writing any code:
- `cratesort/src/gui/main_window.py` — full file
- `cratesort/src/gui/dashboard.py` — full file

---

## Change 1 — Swap the Logo SVG

In `dashboard.py`, find the `_LOGO_SVG` constant near the top of the file. Change it from:
```python
_LOGO_SVG = ... # currently points to cs-logo-lockup-horiz.svg
```
To point to:
```
assets/logos/cs-logo-mascot-stacked.svg
```

Use the same path resolution pattern already in place (relative to the source file or assets directory — match whatever pattern `_LOGO_SVG` currently uses). Increase the fixed size of the `QSvgWidget` to accommodate the stacked layout — `280 x 160` is a reasonable starting point, but use judgment based on the SVG's aspect ratio.

---

## Change 2 — Make `_build_welcome()` Context-Aware

Modify `_build_welcome()` in `dashboard.py` to accept an optional `saved_path: Path | None = None` parameter.

### When `saved_path` is None (first launch):
Render exactly as today:
- Mascot + stacked logo SVG (new, per Change 1)
- "Get your shit together." tagline
- Instruction text: "Select the root folder of your music library. CrateSort will scan all media files inside it, including subfolders."
- Single orange "Select Music Library…" button

### When `saved_path` is provided (returning user):
Render the same screen with different content below the tagline:
- **No instruction text**
- A muted label: "Last library:" followed by the path displayed in cream text, smaller font, word-wrap enabled, no box or frame around it — plain text only
- **Primary button**: "Load Library" — full width, orange (`#D17D34`), minimum height 42px. Clicking this loads the saved path directly (calls `self.start_scan(saved_path)` and emits `library_path_changed`)
- **Secondary button**: "Choose Different Library" — full width, dark panel style (`#2F2F2F` background, cream text, no orange), minimum height 42px, placed directly below the primary button with 8px gap. Clicking this calls `self._on_select_library()` as today.
- **Checkbox**: "Always load without asking" — `QCheckBox`, cream text, 12px font, placed below the secondary button with 12px gap. Unchecked by default. When checked and Load Library is clicked, saves `always_load_last = True` to QSettings before loading.

### Always load behavior:
- If the checkbox is checked when Load Library is clicked: save `always_load_last = True` to QSettings, then load the library. Next launch will skip this screen entirely (auto-load path in `__init__` handles this).
- If unchecked: save `always_load_last = False` to QSettings, then load the library. Dialog appears again next launch.

### Layout notes:
- All elements centered, same as today
- Keep `layout.setSpacing(20)` and `layout.setContentsMargins(60, 60, 60, 60)`
- Buttons should feel cohesive with the rest of the app — use the global button styles from `theme.py`, do not add inline button stylesheets here
- Do not put the path in a QFrame or any box — plain text only

---

## Change 3 — Update the Stack Initialization

In `DashboardWidget.__init__()`, the welcome screen is currently added to the stack with:
```python
self._stack.addWidget(self._build_welcome())   # 0
```

The welcome screen now needs to know the saved path at build time. Update this line to:
```python
saved_path = Path(self._settings.value('library_path')) if self._settings.value('library_path') else None
self._stack.addWidget(self._build_welcome(saved_path))   # 0
```

---

## Change 4 — Remove _LaunchDialog and _show_launch_dialog

In `main_window.py`:

### Delete entirely:
- The complete `_LaunchDialog` class (lines 744–808 approximately)
- The complete `_show_launch_dialog()` method

### Update `__init__()`:
Find this block:
```python
if saved_path:
    if always_load:
        self._dashboard.set_library_path(Path(saved_path))
    else:
        QTimer.singleShot(120, lambda: self._show_launch_dialog(Path(saved_path)))
else:
    self._update_status('', '')
```

Replace with:
```python
if saved_path and always_load:
    self._dashboard.set_library_path(Path(saved_path))
else:
    self._update_status('', '')
```

The welcome screen in the dashboard now handles the returning-user state directly. No dialog, no QTimer, no separate class needed. The stack will already be showing index 0 with the correct context-aware content because of Change 3.

### Remove the QTimer import if it is no longer used anywhere else in the file. Verify before removing.

---

## Verification Steps

After writing all changes, reason through these scenarios:

1. **First launch (no saved path)** → `_build_welcome(None)` → shows logo, tagline, instruction text, single "Select Music Library…" button. No popup.
2. **Returning user, always_load = False** → `_build_welcome(saved_path)` → shows logo, tagline, path, Load Library + Choose Different Library buttons, checkbox. No popup.
3. **Returning user, always_load = True** → `set_library_path()` called directly in `__init__()` → skips welcome screen entirely, goes straight to dashboard. No popup.
4. **Returning user checks "Always load without asking" and clicks Load Library** → `always_load_last = True` saved to QSettings → next launch hits scenario 3.
5. **Returning user clicks "Choose Different Library"** → folder picker opens → `always_load_last` reset to False → new path scanned.

---

## Constraints

- Do not modify any other dashboard sections or stack states
- Do not touch the scanning screen (stack index 1) or the stats dashboard (stack index 2)
- Do not add inline stylesheets to buttons — use global theme styles
- Do not put the library path in any kind of box, frame, or input field — plain text only
- Verify all imports — remove any that become unused after deleting `_LaunchDialog`
