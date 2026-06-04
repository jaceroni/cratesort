# CrateSort — Date Added: Fix Path Normalization (Prompt 28)

> **Run this at Sonnet high effort. Read `src/serato/database_reader.py` and `src/gui/crate_manager.py` completely before making any changes. Remove all debug prints from the previous prompt. Before writing any code, verify all imports.**

## Files to Read First

- `src/serato/database_reader.py`
- `src/gui/crate_manager.py`

---

## The Problem

Two distinct path format issues are causing Date Added lookup failures:

**Issue 1 — Mixed absolute and relative paths in database V2**
Some tracks are stored with absolute paths (e.g. `Users/jacebrown/Desktop/cratesort-test-library/MP3/Funk : Classic/The Gap Band/track.mp3`) while others use relative paths (e.g. `MP3/Funk : Classic/track.mp3`). The lookup key is always relative, so absolute-path entries never match.

**Issue 2 — Serato uses `\uf022` (U+F022) as a substitute for ` : ` in folder names**
Folder names containing ` : ` (space-colon-space) are stored in database V2 with `\uf022` instead (e.g. `MP3/Funk \uf022 Classic/` instead of `MP3/Funk : Classic/`). The lookup key uses the actual ` : ` character so these never match.

---

## The Fix

In `src/serato/database_reader.py`, after extracting each `pfil` path value, normalize it before storing in the dict:

1. Replace all occurrences of `\uf022` (U+F022) with ` : ` (space-colon-space)
2. If the path starts with the library root (absolute path), strip the library root prefix to make it relative. Since the database reader doesn't know the library root, store both the normalized path AND a version with just the relative portion (everything from `MP3/` or `Music Videos/` onward)
3. Normalize path separators to forward slash
4. Strip any leading slashes

The cleanest approach: build the lookup dict with TWO entries per track — one for the full normalized path and one for just the filename-relative portion starting from the first media folder (MP3/, Music Videos/, Sound FX/, etc.). This handles both absolute and relative path storage formats.

In `src/gui/crate_manager.py`, in `_populate_resolved_row()`:
- Try exact relative path lookup first
- If not found, try a normalized version where ` : ` is replaced with `\uf022` AND where `\uf022` is replaced with ` : ` 
- If still not found, show `—`

Remove all debug print statements added in the previous prompt.

---

## What NOT to Change

Do not change column indices, sort behavior, or any other functionality. Only fix the path normalization for the Date Added lookup.
