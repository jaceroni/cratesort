# CrateSort — Classification Data Flow: Authoritative Fix

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt makes three surgical fixes to `library_browser.py` and `main_window.py` based on a full data flow audit. No new behavior is added. Follow the blast radius protocol — read the exact methods named before touching anything.

---

## Files in scope

- `src/gui/library_browser.py` — primary
- `src/gui/main_window.py` — nav guard hook

---

## Locked rules (do not deviate)

- An artist's genre is only trusted when it comes from a user-confirmed source: a `library_edits.json` artist override or a CrateSort classification session entry
- Raw ID3 genre tags from external sources are never trusted for sidebar bucketing
- No artist is considered classified until the user has explicitly run Classify Library and accepted proposals within CrateSort
- Teal `#428175` = action. Orange `#D17D34` = selection/CTA. Never swap.
- Red `#C75B5B` = destructive/cancel.

---

## Fix 1 — Remove Counter majority vote fallback from `_rebuild_tree()`

### `src/gui/library_browser.py`

In `_rebuild_tree()` (around line 656), remove the final track genre majority voting block (which collects track-level genres and runs a `collections.Counter` majority vote to resolve the artist's genre). 

The fallback chain in `_rebuild_tree()` must strictly become:
1. Artist override in `library_edits.json` — check `self._edits.get(f'__artist__{artist}', {}).get('genre')`
2. Classification session — check `self._classify_lookup(artist)` for `final_genre` then `proposed_genre`
3. Default to `''` — Unclassified, full stop

### Code details
- Remove the `Counter` vote calculation and any local import of `collections.Counter` within `_rebuild_tree()`.
- Ensure raw `rec.genre` reads are no longer used for artist-level bucketing.
- Track-level `rec.genre` reads for inline display (displaying the track's genre tag in the Genre column) remain fully intact and unaffected.

---

## Fix 2 — Navigate to destination genre bucket when Unclassified empties

### `src/gui/library_browser.py`

When the last artist is classified and leaves the "Unclassified" bucket, programmatically select the destination genre in the sidebar, filter the tree, and select/highlight the artist row.

### Implementation specs

1. Inside `LibraryBrowserView`, implement an unclassified counter helper:
   ```python
   def _count_unclassified_artists(self) -> int:
       _UC = {'', '—', 'Unclassified', 'Untagged'}
       count = 0
       for i in range(self._tree.topLevelItemCount()):
           item = self._tree.topLevelItem(i)
           genre = item.data(LC_GENRE, Qt.ItemDataRole.UserRole + 1) or ''
           if genre in _UC:
               count += 1
       return count
   ```
2. Store the context variables `self._last_edited_artist` and `self._last_assigned_genre` inside the edit methods before they trigger a sidebar refresh.
   - For single right-click changes (`_change_genre_for_selection()`):
     ```python
     self._last_edited_artist = artist  # or the last selected artist name
     self._last_assigned_genre = new_genre
     ```
   - For Accept Reclassifications (`_exit_classify_mode_accept()`):
     Set `self._last_edited_artist` to the last artist modified in the loop, and `self._last_assigned_genre` to their accepted genre.
3. In `_populate_genre_sidebar()`, capture the unclassified count at the very beginning (e.g. `was_uc_count = self._count_unclassified_artists()`).
4. At the end of `_populate_genre_sidebar()`, calculate the new count (e.g. `is_uc_count = self._count_unclassified_artists()`).
5. If `was_uc_count > 0` and `is_uc_count == 0` (meaning the bucket has just emptied):
   - Locate the item corresponding to `self._last_assigned_genre` inside `self._genre_sidebar_list`.
   - Programmatically select it: `self._genre_sidebar_list.setCurrentItem(item)`.
   - Trigger the tree filter: `self._sidebar_genre = self._last_assigned_genre` and call `self._apply_filter()`.
   - Iterate through the tree, find the top-level row matching `self._last_edited_artist`, clear any existing selection, select it (`item.setSelected(True)`), set it as current, and scroll to it: `self._tree.scrollToItem(item)`.
   - Reset the cached variables to `None`.

---

## Fix 3 — Warn on navigate-away if classify mode is active with unsaved changes

### `src/gui/library_browser.py` & `src/gui/main_window.py`

If the user enters classify mode, makes edits to proposed columns, and attempts to navigate away to another tab, prompt them with a confirmation modal dialog before allowing navigation.

### Changes in `library_browser.py`

1. Expose a helper method on `LibraryBrowserView`:
   ```python
   def has_unsaved_classify_changes(self) -> bool:
       return self._classify_mode
   ```
2. Implement a custom modal dialog `_UnsavedChangesDialog(QDialog)` in `library_browser.py` styled exactly to match CrateSuite's design language:
   - **Background**: `#1a1a1a`
   - **Text color**: `#f1e3c8`
   - **Window title**: "Unsaved Classification Changes"
   - **Body text**: "You have unsaved changes in Classify mode. If you leave now, your corrections will be lost."
   - **Buttons layout**: QHBoxLayout
     - Left button: "Leave Anyway" — styled with red background `#C75B5B`, cream text `#f1e3c8`, hover `#b24c4c`, connects to `self.accept()`.
     - Right button: "Stay and Finish" — styled with teal background `#428175`, cream text `#f1e3c8`, hover `#38706a`, connects to `self.reject()`.

### Changes in `main_window.py`

In `MainWindow._on_nav(self, index: int)` (around line 346), check if the current tab is the Library tab (index 1) and if the user is navigating to a different tab:
```python
        # Check for unsaved classify mode edits
        if self._content.currentIndex() == 1 and index != 1:
            if hasattr(self, '_library_browser') and self._library_browser.has_unsaved_classify_changes():
                from cratesort.src.gui.library_browser import _UnsavedChangesDialog
                dlg = _UnsavedChangesDialog(self)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    # Stay and Finish: restore check state of library tab button and return
                    self._nav_btns['library'].setChecked(True)
                    return
                else:
                    # Leave Anyway: exit classify mode and proceed
                    self._library_browser._exit_classify_mode_cancel()
```

---

## Verification checklist

Before marking complete:

1. Fresh library load with no `_CrateSort` folder — all artists land in Unclassified regardless of existing ID3 tags
2. Fresh library load with clean ID3 tags — same result as above, all Unclassified
3. After running Classify Library and clicking Accept Reclassifications — artists move to correct genre buckets
4. After Accept, navigating away and returning — artists remain in same genre buckets, no phantom moves
5. Single right-click genre change — sidebar updates immediately, artist stays in new bucket after nav round-trip
6. Last artist leaves Unclassified — sidebar navigates to destination genre bucket, artist is highlighted and visible in track table
7. Last artist leaves Unclassified via Accept Reclassifications — same destination navigation behavior
8. User in classify mode clicks a nav item — warning dialog appears
9. "Leave Anyway" — classify mode exits without saving, navigation proceeds
10. "Stay and Finish" — dialog dismisses, user remains in Library in classify mode
11. No `collections.Counter` genre resolution anywhere in artist-level bucketing logic
12. Track genre tags still display correctly in the Genre column for individual track rows — display is unaffected
13. Teal = action, Orange = CTA, Red = destructive — no role swaps
