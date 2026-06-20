# CrateSort — Auto-Enter Classify Mode on First Library Load

## Context

Run at **Sonnet, high effort**. Read `load()` and `_on_classify_clicked()` in `cratesort/src/gui/library_browser.py` completely before writing any code.

This is a small, targeted addition. One condition check, one method call. Do not touch anything else.

---

## Files in scope

- `src/gui/library_browser.py` — only

---

## The fix

At the end of the `load()` method in `LibraryBrowserView` (around line 420), after all other initialization steps (tree rebuilt, filters populated, sidebar populated, stack index set to 1), add the following check:

```python
        # Auto-classify on first load if no classification session exists yet
        if self._library_path:
            session_file = self._library_path / '_CrateSort' / 'classification_session.json'
            if not session_file.exists():
                self._on_classify_clicked()
```

This checks if `classification_session.json` exists for the current library (meaning it has never been classified in CrateSort). If it does not exist, automatically call `self._on_classify_clicked()` to enter classify mode.

If the file exists, do nothing (normal mode, user is in control).

---

## Locked rules

- This check runs ONLY at the end of `load()` — not on `scan_finished`, not on nav return, not anywhere else.
- Once `classification_session.json` exists, auto-activation never fires again for that library.
- Do not modify `_on_classify_clicked()` — call it as-is.
- Do not modify any other method.

---

## Verification checklist

Before marking complete:

1. Loading a fresh library with no `_CrateSort` folder or no classification session on disk immediately puts the Library browser into classify mode (proposed genre columns visible, classify banner shown).
2. After Accept Reclassifications, navigating away and returning opens the Library Browser in normal mode (no auto-classify).
3. Closing the app, reopening, and loading the same library loads in normal mode (no auto-classify).
4. Loading a different library that has been classified before opens in normal mode.
5. Loading a different library that has never been classified automatically activates classify mode.
6. No regression in manual Classify Library button behavior.
