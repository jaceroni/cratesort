# CrateSort — Classification Complete Flag Fix

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt surgical-fixes how CrateSort determines if the library classification is complete. Instead of checking if there are artist overrides in `library_edits.json` (which can be created by manual right-clicks), it will check for the presence of a flag file written when the user explicitly clicks **Accept Reclassifications**.

---

## Files in scope

- `src/gui/library_browser.py`
- `src/gui/dashboard.py`

---

## Locked rules

- Do not touch `organize_view.py`.
- Do not touch individual right-click genre change handlers.
- Do not alter the content or format written to `library_edits.json`.
- Keep the `_CrateSort` directory path resolution logic consistent with the existing patterns in both files.

---

## Detailed Specifications

### 1. Update `_is_classification_complete` in `library_browser.py`

In `src/gui/library_browser.py` (around lines 697–712), replace the implementation of `_is_classification_complete(self) -> bool` to check for the flag file instead of reading `library_edits.json`:

```python
    def _is_classification_complete(self) -> bool:
        if not self._library_path:
            return False
        flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
        return flag_path.exists()
```

---

### 2. Update `_is_classification_complete` in `dashboard.py`

In `src/gui/dashboard.py` (around lines 674–688), replace the implementation of `DashboardWidget._is_classification_complete(self) -> bool` with the identical logic:

```python
    def _is_classification_complete(self) -> bool:
        if not self._library_path:
            return False
        flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
        return flag_path.exists()
```

---

### 3. Write flag file on Accept Reclassifications in `library_browser.py`

In `src/gui/library_browser.py`, inside the `_exit_classify_mode_accept(self) -> None` method (around line 1831), track whether the JSON save succeeded, and then write the flag file to disk:

```python
        edits_path.parent.mkdir(parents=True, exist_ok=True)
        save_success = False
        try:
            with open(edits_path, 'w', encoding='utf-8') as f:
                json.dump(edits, f, indent=2)
            save_success = True
        except Exception as exc:
            print(f'[LibraryBrowser] Failed to save accepted classifications: {exc}')

        if save_success:
            try:
                flag_path = self._library_path / '_CrateSort' / 'classification_accepted.flag'
                flag_path.parent.mkdir(parents=True, exist_ok=True)
                flag_path.touch()
            except Exception as exc:
                print(f'[LibraryBrowser] Warning: Failed to write classification accepted flag: {exc}')
```

Ensure this file touch is done only if the edits write succeeded.

---

## Cody's Pre-Flight & Blast Radius

- Confirm the `touch()` call does not throw unhandled exceptions if the disk is read-only (it must catch and print the warning).
- Ensure no other variables or states are affected.

---

## Verification checklist

1. Launch CrateSort on a new library (delete the `classification_accepted.flag` file if it exists).
2. Verify that:
   - On the **Dashboard**, the "Manage Library" action card is highlighted in orange.
   - Navigating to the **Library** browser triggers Classify mode automatically.
3. Make an individual right-click genre change to a track. Close and reopen the app.
4. Verify that:
   - "Manage Library" is *still* highlighted in orange on the Dashboard.
   - Navigating to **Library** *still* automatically triggers Classify mode.
5. In Classify mode, click **Accept Reclassifications**.
6. Verify that:
   - The file `_CrateSort/classification_accepted.flag` is created and exists.
   - The Dashboard "Manage Library" card returns to the standard highlight state.
   - Navigating to the **Library** browser no longer triggers Classify mode.
