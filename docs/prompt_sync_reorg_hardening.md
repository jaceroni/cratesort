# Prompt: Reorganization, Synchronization, and UI Hardening Sweep

## Goal
Implement a series of stabilization and synchronization fixes across the metadata, folder cleanup, Serato crate path updating, and UI warnings systems in CrateSort.

## Files in Scope
- `cratesort/src/gui/classifier_view.py`
- `cratesort/src/gui/organize_view.py`
- `cratesort/src/core/file_organizer.py`
- `cratesort/src/serato/path_rewriter.py`

---

## Detailed Specifications

### 1. Classification & Library View Synchronization
- **Metadata Propagation**: In `ClassificationSession.apply_library_edits` (in `classifier_view.py`), expand the sync logic so that track `title`, `comment`, and style `tags` edited in the Library tab (and saved in `library_edits.json`) are loaded and applied to the session's `TrackInfo` structures.
- **NFC Normalization**: Wrap all string-based path lookups in `apply_library_edits` (both dictionary keys and track paths) with Unicode NFC normalization (`unicodedata.normalize('NFC', path_str)`) to prevent macOS case/accent mismatches from bypassing overrides.
- **Current Genre Column**: In `ClassifierView._refresh_item_display`, change the text set on `COL_CURRENT` for the artist row from `entry.original_genres` to a dynamic, unique list of genres computed directly from the current `track.genre_tag` values of the artist's tracks. This ensures the column updates when a track or artist's genre is overridden.
- **Two-Way Edits Save**: When changing a track's genre (`_change_track_genre`) or editing style tags (`_edit_track_tags`) in the Classification screen, update the track's inline display values and write these changes to `library_edits.json` (under the track path key), ensuring the Library tab is synchronized in real-time.
- **Cleanup**: Remove the unused/dead `_apply_library_edits` method from `ClassifierView`.

### 2. Serato Crate Path Matching & MP4 Writing
- **Harden Crate Path Matching**: In `PathRewriter._process_crate` (in `path_rewriter.py`), modify the matching loop. If the track path stored in the `.crate` file does not match exactly, check if it ends with `/' + old_relative_path`. Normalize all paths to NFC and normalize backslashes to forward slashes before comparison. This handles duplicated or renamed library roots.
- **Preserve Path Formatting**: Reconstruct the new track path replacing the matched relative segment, while preserving:
  - Absolute vs relative path format.
  - The leading slash preference (e.g., if the original path in the crate started with `Users/...` without a leading `/`, strip the leading `/` from the rewritten path; if it started with `/Users/...`, preserve the leading slash).
- **MP4 Tag Initialization**: In `file_organizer.py`, add a helper `_ensure_mp4_tags(audio, ext)` to invoke `audio.add_tags()` if `audio.tags` is `None` for `.mp4`, `.m4v`, `.mov`, and `.m4a` files. Call it inside each MP4 tag writer so metadata edits can be successfully written to previously untagged video files.
- **Unicode NFC in Metadata Sync**: Update `_sync_metadata_files` in `file_organizer.py` to perform lookups and key replacements using NFC-normalized path string comparisons.

### 3. Warnings Details Dialog & Done Screen Reports
- **Warnings Stat Card Trigger**: In `organize_view.py`, add a `clicked = pyqtSignal()` to `_OrganizeStatCard`. Emit it when the card is left-clicked.
- **Warnings Detailed Dialog**: Create a branded `_WarningsDetailDialog(QDialog)` using the dark panel theme (`#2F2F2F` bg, `#f1e3c8` text, `#1a1a1a` read-only QTextEdit for scrollable contents).
- **Warnings Content**: Populate the dialog with:
  - Details of any destination conflicts (`plan.conflicts`).
  - Path length limit warnings (`plan.operations` where `op.path_too_long` is true).
  - Skinned/skipped protected directories (`plan.protected_skipped`).
- **Wired Connection**: In `OrganizeView`, connect `self._card_warnings.clicked` to open this dialog. Also, sum up `summary.conflict_count + summary.path_warnings + summary.protected_skipped` to update `self._card_warnings` with the total count.
- **Done Screen Skip Summary**: In `OrganizeView._on_exec_finished`, update the summary details to explicitly report how many files were skipped during execution (`len(result.skipped)`), preventing silent omissions of conflicted/pre-existing files.

### 4. Rollback Cleanup Hardening
- **Rollback Directory Purge**: In `RollbackLog._remove_empty_dirs` (in `file_organizer.py`), before attempting `dirpath.rmdir()`, check if the directory contains only hidden system files (like `.DS_Store` or `.Spotlight-V100`). If so, unlink/delete those hidden files first, then execute `dirpath.rmdir()`. This ensures empty category folders (like `Media/R&B`) aren't left behind.

---

## Cody's Pre-Flight & Blast Radius
- Verify that QTreeWidget/QTableWidget row heights (36px) and header heights (45px) remain intact.
- Confirm all button colors map to their designated roles: Teal (`#428175`) = action/confirm, Orange (`#D17D34`) = selection/CTA, Red (`#C75B5B`) = cancel/destructive.
- Ensure all QDialogs use branded stylesheets matching CrateSuite colors.
- Verify `reload-after-write` pattern in the crate manager is preserved.

---

## Acceptance Criteria
1. Modifying track names, style tags, or comments in Library correctly updates the corresponding track nodes when navigating back to the Classification view.
2. In-app classification genre overrides are properly written to `library_edits.json` and immediately show up in the Library browser.
3. Reorganizing a renamed library folder root correctly matches and rewrites all `.crate` track paths (showing N paths updated on the Done screen, not 0).
4. After executing reorganization, no files are marked as "not found" in the Crates tab.
5. Reorganizing video files (`.mp4`) with metadata edits correctly writes those edits to disk using Mutagen.
6. Rolling back a reorganization successfully removes the empty parent folders on disk (including those containing `.DS_Store`).
7. Clicking the Warnings card in the Preview screen pops up a detailed list of all plan warnings/conflicts.
