# CrateSort — Immediate Tree Rebuild on Genre Change

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt implements a targeted tree update and sidebar navigation selection when a user changes an artist's genre in `LibraryBrowserView`. The update must happen immediately without requiring the user to navigate away and return, and without doing a sluggish full tree rebuild.

---

## Files in scope

- `src/gui/library_browser.py` — primary

---

## Locked rules

- Teal `#428175` = action. Orange `#D17D34` = selection/CTA. Never swap.
- Tree top-level rows are flat artist items, filtered (shown/hidden) using the selected sidebar genre (`self._sidebar_genre`).
- All changes must be visual and in-place. Do not touch Serato metadata or comments.

---

## Detailed Specifications

### Generalized Post-Edit Navigation & Filtering

In `_populate_genre_sidebar()` (in `library_browser.py`), replace the specific `_was_uc` block at the end of the method (lines 795–822) with a generalized navigation and filter application block.

1. **Extract and Clear Post-Edit State**:
   Check if `self._last_edited_artist` and `self._last_assigned_genre` are set. If they are, extract them and clear them by setting both attributes back to `None`.

2. **Determine if Navigation is Required**:
   We should navigate the sidebar to follow the edited artist if:
   - The user is NOT currently viewing the "All" bucket (`self._sidebar_genre != 'All'`) AND
   - The user moved the artist to a different genre bucket than the current view (`self._sidebar_genre != dest_genre`).

3. **Navigate Sidebar**:
   If navigation is required:
   - Update `self._sidebar_genre` to `dest_genre`.
   - Iterate the items in `self._genre_sidebar_list`. Find the item matching `dest_genre`.
   - Set the current item using `setCurrentItem()`. Wrap this call inside `blockSignals(True)` / `blockSignals(False)` defensively to prevent signal feedback loops.

4. **Re-Apply Filter in All Cases**:
   Call `self._apply_filter()` at the end of the method. This updates row visibilities (hiding the artist from its old bucket and showing it in the new one, or keeping it visible in the "All" view) and refreshes counts and the bottom status labels in-place.

5. **Scroll & Highlight Moved Artist**:
   If navigation occurred, iterate through `self._tree.topLevelItem(i)` rows to locate the item matching `dest_artist`.
   - Clear current selection with `self._tree.clearSelection()`.
   - Set `setSelected(True)` on the matching top-level item.
   - Call `self._tree.setCurrentItem(top)` and `self._tree.scrollToItem(top)` to highlight and bring the item into focus.

---

## Cody's Pre-Flight & Blast Radius
- Verify QTreeWidget row heights (36px) and header heights (45px) remain intact.
- Confirm button colors and styles are untouched.
- Verify `_update_empty_state()` is called synchronously after edits (already in `_change_genre_for_selection()`).

---

## Verification checklist

1. Right-clicking an artist to change genre immediately updates the sidebar counts.
2. If changing the genre from a specific bucket (e.g. Hip-Hop/Rap to Funk/Soul), the sidebar selection follows the artist to the new bucket, the tree filters, and the artist is selected and visible.
3. If the change empties the old bucket, that bucket immediately disappears from the sidebar.
4. If the change is made while viewing the "All" bucket, the sidebar selection remains "All", the artist remains visible, its genre text is updated, and sidebar counts increment/decrement immediately.
5. If the change is made from the "Unclassified" bucket, it behaves identically (navigates and filters to the destination genre, and disappears from Unclassified).
6. Verify no regressions on Accept Reclassifications.
