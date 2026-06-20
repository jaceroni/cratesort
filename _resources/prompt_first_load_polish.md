# CrateSort — First Load Polish & Classification Completion Check

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

Four targeted fixes. Read the blast radius for each before touching anything.

---

## Files in scope

- `src/gui/dashboard.py`
- `src/gui/library_browser.py`
- `src/gui/main_window.py`
- `src/gui/organize_view.py`

---

## Locked rules

- Teal `#428175` = action. Orange `#D17D34` = selection/CTA. Never swap.
- A library is considered "classification complete" only when the user has explicitly accepted classifications — not just when the classifier has run.
- `resizeColumnsToContents()` and `resizeColumnToContents()` sets minimum widths — user adjustments via QSettings still persist after.
- Never touch Serato metadata, comments, or cue points.

---

## Fix 1 — Dashboard Manage Library card illuminates on first load

### `src/gui/dashboard.py`

When the user loads a library that has not yet had classification completed, the Manage Library action card should visually draw the user's eye — indicating this is where they should start.

#### Definition of "classification not yet completed"
Classification is complete when `library_edits.json` contains at least one `__artist__` key with a `genre` value. This means a user has explicitly confirmed at least one genre assignment.
If `library_edits.json` does not exist, or exists but contains zero `__artist__` genre entries — classification has not been completed.

Add `_is_classification_complete(self) -> bool` to `DashboardWidget` to perform this check.

#### Visual treatment
When classification is not complete, the Manage Library card gets a teal highlight treatment:
- Border: `2px solid #428175` (instead of standard muted border)
- A subtle teal glow or tint on the card background: `#1a2e2b` instead of `#2F2F2F`
- The large SVG icon on the right renders at full teal opacity (`#428175`) instead of dimmed

When classification is complete, the card returns to its standard appearance.

#### Implementation details
- **Remove direct QSettings check for library_path**: Update `DashboardWidget.__init__(self, parent=None, saved_path: Optional[Path] = None)` to accept `saved_path` as an optional parameter. In `__init__`, use the passed `saved_path` (NFC-normalized, resolved `Path`) to build the welcome screen instead of querying QSettings directly.
- **Card Highlight**: Modify `_build_action_cards_section(self)` to check `highlight_manage_library = not self._is_classification_complete()`. Pass `highlighted=highlight_manage_library` for the "Manage Library" card and `highlighted=False` for others.
- **Workflow Card Style**: Modify `_WorkflowCard` constructor:
  - Add `highlighted: bool = False` argument.
  - If `highlighted` is True:
    - Set the resting style `self.style_rest` to `'QFrame { background-color: #1a2e2b; border: 2px solid #428175; border-radius: 10px; }'`
    - Set the resting icon color `self.icon_dim` to `'#428175'`
  - Else:
    - Set `self.style_rest` to `self._STYLE_REST` and `self.icon_dim` to `self._ICON_DIM`.
  - In constructor, load the resting icon color: `self._load_icon_color(self.icon_dim)`.
  - In `leaveEvent(self, event)`, restore using `self.style_rest` and `self.icon_dim`.
- **Refreshed on navigation**:
  - Add `refresh(self) -> None` to `DashboardWidget` that updates the sync state and rebuilds dashboard cards:
    ```python
    def refresh(self) -> None:
        if self._library_path and self._summary is not None:
            self._check_serato_sync()
            self._populate_dashboard()
    ```

### `src/gui/main_window.py`

- In `_build_ui(self)`: Query `library_path` from settings, construct a `Path` if valid, and pass it to `self._dashboard = DashboardWidget(saved_path=saved_path)`.
- In `_on_library_changed_from_settings(self, path: Path) -> None`: Call `self._dashboard.set_library_path(path)` instead of `start_scan(path)`.
- In `_on_nav(self, index: int)`: When `index == 0` (Dashboard), call `self._dashboard.refresh()`.

---

## Fix 2 — Classify mode banner more prominent

### `src/gui/library_browser.py`

Increase the visual presence of the classify mode banner:
- **Height**: increase padding/margins of the layout to `12px` top/bottom, `14px` left/right (from current `7px` top/bottom).
- **Background**: `#1a3530` (deeper teal tint).
- **Left border accent**: `'QFrame { background: #1a3530; border-left: 3px solid #428175; border-bottom: 1px solid #2d4a44; }'`
- **Left side**: prepend a teal icon `⚡` before the text:
  ```python
  icon_lbl = QLabel('⚡')
  icon_lbl.setStyleSheet('color: #428175; font-size: 14px; background: transparent; border: none;')
  row.addWidget(icon_lbl)
  ```
- **Text**: font size `12px` (from `11px`), color `#7bbdad` unchanged.
- **Text content**: `"Classify mode active — review proposed genres and correct where needed."`
- **Right side buttons**: Cancel (muted) and Accept Reclassifications (teal) are left unchanged.

---

## Fix 3 — Auto-classify check uses classification completion, not session file existence

### `src/gui/library_browser.py`

Replace the `classification_session.json` existence check with a check for completed classification.

Add the helper method:
```python
def _is_classification_complete(self) -> bool:
    if not self._library_path:
        return False
    edits_path = self._library_path / '_CrateSort' / 'library_edits.json'
    if not edits_path.exists():
        return False
    try:
        import json
        edits = json.loads(edits_path.read_text(encoding='utf-8'))
        return any(
            k.startswith('__artist__') and v.get('genre')
            for k, v in edits.items()
        )
    except Exception:
        return False
```

Call `_is_classification_complete()` at the end of `load()`. If it returns False, call `_on_classify_clicked()`. If it returns True, do not auto-activate. Remove the old `classification_session.json` check entirely.

### `src/gui/organize_view.py`

In `_count_unclassified_tracks(self) -> int`:
Call `session.apply_library_edits()` after loading the session, so that manual classification edits are applied before counting. This ensures the warning count correctly matches the remaining unclassified tracks.

---

## Fix 4 — Column widths resize to content

### `src/gui/library_browser.py`

- At the end of `_rebuild_tree(self)`, if there is no user-saved header state in QSettings:
  - Trigger `self._tree.header().resizeSections(QHeaderView.ResizeMode.ResizeToContents)` followed by enforcing a minimum width floor of `60`px for each column:
    ```python
    min_width = 60
    for i in range(self._tree.columnCount()):
        if self._tree.columnWidth(i) < min_width:
            self._tree.setColumnWidth(i, min_width)
    ```
  - This resizing and floor must run inside a delayed single-shot timer (`QTimer.singleShot(100, ...)`), replacing `self._enforce_min_col_widths`.
- In `_enter_classify_mode(self, session)`:
  - Inside `_reorder_cls_cols()`, after visual reordering, resize the newly inserted columns `LC_CLS_PROPOSED`, `LC_CLS_CONF`, `LC_CLS_STATUS` to their content using `self._tree.resizeColumnToContents(col)`, and enforce a `60`px minimum width floor.
  - This preserves user-adjusted column widths loaded from `QSettings`.

---

## Verification checklist

Before marking complete:

1. **First load / Unclassified**:
   - Delete/rename `library_edits.json`. Start the app.
   - Verify:
     - Dashboard `Manage Library` card has a teal border, `#1a2e2b` tint background, and full-opacity teal icon.
     - Navigating to Library automatically triggers Classify mode.
     - Classify banner displays prominently (tall, deep teal bg, left border accent, `⚡` icon).
     - Columns auto-resize to content with a minimum floor of 60px (no clipping on "Proposed Genre", etc.).
2. **Leave Classify**:
   - Exit Classify mode without saving (click Cancel or navigate away and click "Leave Anyway").
   - Return to Library. Verify it triggers Classify mode again.
3. **Accept Classifications**:
   - In Classify mode, make a correction or accept classifications.
   - Verify:
     - `library_edits.json` is created with `__artist__` entries.
     - Return to Dashboard: Verify the `Manage Library` card has returned to its standard look (dark grey, no teal border, dimmed icon).
     - Return to Library: Verify Classify mode does NOT auto-trigger.
4. **Organize Warning**:
   - Go to Organize view. Verify the count of unclassified tracks correctly matches the number of remaining unclassified tracks (zero if all were classified).
5. **Column Width Persistence**:
   - Manually drag/resize columns in Library. Close the app and reopen. Verify user-defined widths persist, even after navigating back and forth.
