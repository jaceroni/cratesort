# CrateSort — Bug 2 Fix: Checkpoint Change Detection

**Sonnet, high effort. Read every referenced file completely before writing any code.**

---

## What to Fix

Two targeted patches to `src/utils/checkpoint.py` and one line in `src/gui/dashboard.py`. No structural changes. No new files.

---

## Patch 1 — Path Normalization in `detect_changes()`

### The problem
`detect_changes()` compares current crate paths against stored checkpoint paths using a direct key lookup (`path in prev_crates`). If the path format shifts slightly between sessions — different drive mount point, macOS case difference, trailing slash variance — the lookup fails silently and the crate falls through to the "new crate" bucket instead of being recognized as an existing crate with a track count change.

### The fix
Before any comparison in `detect_changes()`, normalize all paths from both `current` and `prev_crates` using a helper function. Apply this normalization consistently to every path lookup in the function.

Write a private helper `_normalize_path(path: str) -> str` that:
- Converts to a `Path` object and back to string (resolves separator differences)
- Lowercases on case-insensitive filesystems (use `sys.platform` to detect macOS/Windows)
- Strips trailing slashes

Build a normalized version of `prev_crates` at the top of `detect_changes()` — do not modify the original. Use the normalized dict for all comparisons. This way the reporting still uses the original paths, but matching is robust.

---

## Patch 2 — Failed Scan Guard

### The problem
In `dashboard.py`, when a `.crate` file fails to scan, its track count is stored as `0` in `current_crates`. On the next session, `detect_changes()` sees the crate went from (say) 47 tracks to 0 and reports "tracks removed" — which is a false positive caused by a read error, not a real change.

### The fix

**In `dashboard.py`:** Change the failed scan assignment from `0` to `None`:
```python
current_crates[str(crate_file)] = None  # failed scan — exclude from diff
```

**In `detect_changes()` in `checkpoint.py`:** Add guards in both directions:
- Skip any entry where the current count is `None` (failed scan this session)
- Skip any entry where the previous count was `None` (failed scan last session — do not report as "tracks added" when it successfully scans this time)

Both guards must be applied before any count comparison logic runs.

---

## Verification Steps

After writing the fix, reason through these three scenarios and confirm the logic handles each correctly:

1. **Crate scanned successfully both sessions, track count increased** → should appear in Changes as `tracks_added`
2. **Crate failed to scan this session (None)** → should be silently skipped, no change reported
3. **Crate failed to scan last session (previous = None), succeeds this session** → should be silently skipped, not reported as "tracks added"
4. **Crate path format shifted slightly between sessions** → normalization kicks in, correctly matched, count diff computed normally

---

## Constraints

- Read `src/utils/checkpoint.py` and `src/gui/dashboard.py` completely before writing any code
- Do not change the checkpoint data schema (still `{crate_path: track_count}`)
- Do not change when or where `save_checkpoint()` is called
- Do not touch any other dashboard sections
- Verify all imports before using any new modules (`sys`, `pathlib.Path` if not already imported)
