# CrateSort — Wire New Dashboard Action Card Signals

**Sonnet, high effort. Read every referenced file completely before writing any code.**

---

## Files to Read First

Read these files completely before writing any code:
- `cratesort/src/gui/main_window.py` — full file
- `cratesort/src/gui/crate_manager.py` — full file (specifically looking for any existing new-crate or new-smart-crate dialog methods)

---

## Overview

Four new signals on `DashboardWidget` are currently unconnected in `main_window.py`. Wire them up following the exact same patterns used for the existing signal connections. No changes to `dashboard.py`.

---

## The Four Connections to Add

Add these four `.connect()` calls in `_build_ui()`, immediately after the existing three dashboard signal connections:

```python
self._dashboard.crates_requested.connect(self._on_crates_requested)
self._dashboard.organize_requested.connect(self._on_organize_requested)
self._dashboard.new_crate_requested.connect(self._on_new_crate_requested)
self._dashboard.new_smart_crate_requested.connect(self._on_new_smart_crate_requested)
```

---

## The Four Handler Methods to Add

Add these four methods to `MainWindow`, grouped with the other `_on_*` handler methods.

### `_on_crates_requested()`

Navigate to the Crates tab and load it if inventory is available:

```python
def _on_crates_requested(self) -> None:
    self._on_nav_by_id('crates')
```

`_on_nav_by_id('crates')` already handles setting the nav button highlight and calling `_on_nav(2)`, which loads the crate manager if inventory exists. No additional logic needed.

### `_on_organize_requested()`

Navigate to the Organize tab:

```python
def _on_organize_requested(self) -> None:
    self._on_nav_by_id('organize')
```

Organize is currently a placeholder (index 3). This just navigates there. When the Organize view is built in a future session, no changes to this handler will be needed.

### `_on_new_crate_requested()`

Navigate to the Crates tab, then trigger the new crate dialog:

```python
def _on_new_crate_requested(self) -> None:
    self._on_nav_by_id('crates')
    inv = self._dashboard._inventory
    lib = self._dashboard._library_path
    if inv and lib:
        self._crate_manager.load(inv, lib)
    if hasattr(self._crate_manager, '_on_new_crate'):
        self._crate_manager._on_new_crate()
```

The `hasattr` guard is mandatory — if the method doesn't exist on `CrateManagerView`, navigation still works and no error is thrown. Do not call `_on_new_crate()` without the guard.

### `_on_new_smart_crate_requested()`

Navigate to the Crates tab, then trigger the new smart crate dialog:

```python
def _on_new_smart_crate_requested(self) -> None:
    self._on_nav_by_id('crates')
    inv = self._dashboard._inventory
    lib = self._dashboard._library_path
    if inv and lib:
        self._crate_manager.load(inv, lib)
    if hasattr(self._crate_manager, '_on_new_smart_crate'):
        self._crate_manager._on_new_smart_crate()
```

Same `hasattr` guard pattern as above.

---

## Constraints

- Do not modify `dashboard.py`
- Do not modify any existing signal connections or handler methods
- Do not modify `_on_nav()` or `_on_nav_by_id()`
- If `CrateManagerView` already has `_on_new_crate()` or `_on_new_smart_crate()` methods, note them in the verification report but do not modify them
- Verify all four `.connect()` calls are placed after the existing three dashboard connections in `_build_ui()`

---

## Verification Steps

1. All four `.connect()` calls present in `_build_ui()` immediately after existing dashboard connections
2. All four handler methods exist on `MainWindow`
3. `_on_crates_requested` and `_on_organize_requested` use `_on_nav_by_id()` — not `_on_nav()` directly
4. Both new crate handlers include `hasattr` guards before calling dialog methods
5. No existing connections or handlers modified
