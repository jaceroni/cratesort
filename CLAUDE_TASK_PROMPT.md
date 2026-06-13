# Handoff to Claude Code: Reorganization History, Rollbacks, & Continuous Reorg Path Sync

Please execute the following tasks sequentially to implement persistent rollback history on the Organize tab, track rolled-back states, support path synchronization for continuous incremental reorganizations, and integrate events into the Dashboard's Recent Activity list.

Before starting, review [CLAUDE-CS.md](file://CLAUDE-CS.md) to align with all project architecture guidelines (e.g. Teal action color `#428175`, Orange selection color `#D17D34`).

---

### Task 1: Continuous Reorganization Path Sync for Metadata Files

**File**: [file_organizer.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/core/file_organizer.py)

When files are moved during a reorganization, their paths change. This makes the paths stored inside `classification_session.json` and `library_edits.json` stale. On subsequent rescans, CrateSort fails to match the tracks to their classification records or user edits. We must synchronize these JSON files with the new paths.

1. Add a helper function `_sync_metadata_files(library_root: Path, path_mapping: dict[Path, Path]) -> None` at the module level in `file_organizer.py`:
   ```python
   def _sync_metadata_files(library_root: Path, path_mapping: dict[Path, Path]) -> None:
       """
       Update file paths in classification_session.json and library_edits.json
       to keep them in sync with moved files.
       """
       if not path_mapping:
           return

       # 1. Update classification_session.json
       session_file = library_root / '_CrateSort' / 'classification_session.json'
       if session_file.exists():
           try:
               with open(session_file, encoding='utf-8') as f:
                   data = json.load(f)
               
               updated = False
               for entry in data.get('entries', []):
                   for track in entry.get('tracks', []):
                       track_path = Path(track['path'])
                       if track_path in path_mapping:
                           track['path'] = str(path_mapping[track_path])
                           updated = True
               
               if updated:
                   with open(session_file, 'w', encoding='utf-8') as f:
                       json.dump(data, f, indent=2)
                   logger.info("Synced classification_session.json paths with moved files.")
           except Exception as exc:
               logger.error("Failed to sync classification_session.json: %s", exc)

       # 2. Update library_edits.json
       edits_file = library_root / '_CrateSort' / 'library_edits.json'
       if edits_file.exists():
           try:
               with open(edits_file, encoding='utf-8') as f:
                   edits = json.load(f)
               
               new_edits = {}
               updated = False
               for k, v in edits.items():
                   k_path = Path(k)
                   if k_path in path_mapping:
                       new_edits[str(path_mapping[k_path])] = v
                       updated = True
                   else:
                       new_edits[k] = v
               
               if updated:
                   with open(edits_file, 'w', encoding='utf-8') as f:
                       json.dump(new_edits, f, indent=2)
                   logger.info("Synced library_edits.json paths with moved files.")
           except Exception as exc:
               logger.error("Failed to sync library_edits.json: %s", exc)
   ```

2. Update `FileOrganizer.execute()` to construct a path mapping of completed moves and call `_sync_metadata_files` right before saving the rollback log:
   ```python
           # Sync metadata files (classification_session.json, library_edits.json)
           path_mapping = {op.source_path: op.destination_path for op in completed}
           _sync_metadata_files(self._library_root, path_mapping)

           rlog.save()
   ```

3. Update `RollbackLog.rollback()` to:
   - Record the rollback timestamp in log data:
     ```python
     self._data['rolled_back_at'] = datetime.now().isoformat()
     ```
   - Call `_sync_metadata_files` with `dest_to_src` (mapping destination reorganized paths back to original source paths):
     ```python
             # Sync metadata files (classification_session.json, library_edits.json)
             library_root = Path(self._data.get('library_root', ''))
             _sync_metadata_files(library_root, dest_to_src)

             self.save()
     ```

---

### Task 2: Redesign the Organize Landing Screen (State 0)

**File**: [organize_view.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/organize_view.py)

1. **Gate Screen Layout Redesign**: In `_build_gate()` (around line 392), change the UI structure so it acts as a landing screen with two toggleable panels and a previous reorganizations container.
   - Create a vertical layout with margins `(120, 80, 120, 80)`.
   - Define a sub-widget `self._gate_needs_class_widget` containing the rich text label instructions pointing to the Classifier (the existing message/note widgets).
   - Define a sub-widget `self._gate_ready_widget` showing a message: `"Classification session ready! Click below to analyze your library and prepare the reorganization plan."` and a primary Teal action button `"Plan Reorganization…"` (Teal background `#428175`, height 40px, width 220px). When clicked, it should call `self._on_plan_clicked(session_path)`.
   - Add a horizontal separator line (height 1px, color `#383838`).
   - Add a history section with a title: `"Recent Reorganizations"` (styled `#f1e3c8` with proper font weight/size).
   - Add a vertical layout container `self._history_layout` where rows will be dynamically loaded.

2. **Implement History Scanning & Rendering**:
   Write a private method `_refresh_gate_screen(self)` that:
   - Checks if `classification_session.json` exists, showing `self._gate_ready_widget` and hiding `self._gate_needs_class_widget` (or vice-versa).
   - Clears any existing items inside `self._history_layout`.
   - Scans the `_CrateSort` folder for files matching `reorganization_log_*.json`.
   - Sorts logs from newest to oldest (by filename / descending sorting).
   - Displays up to the 3 most recent runs. For each run, read the JSON contents:
     - Show the date/time (parse `executed_at` ISO string, format nicely, e.g. `June 12, 2026 at 06:50 PM`).
     - Show the number of files moved (the count of `moves` with `"status": "completed"`).
     - If the key `"rolled_back_at"` exists:
       - Show a status string: `Rolled back on [Date]` in a muted gray/brown tone.
       - Do *not* show a Rollback button.
     - If it is not rolled back:
       - Show a "Rollback" button (styled `#d9534f` or similar danger/secondary color) next to the log entry. Connecting its `clicked` signal should pass the specific log file Path.
   - If no logs exist, hide the history header or display a muted `"No reorganization history found."` label.

3. **Update `load()` to default to the Gate screen**:
   Modify `load()` so it always calls `_refresh_gate_screen()` and sets the stack index to `_STATE_GATE` (State 0). The automatic transition straight to planning is disabled.

---

### Task 3: Support Rollback Executed from History

**File**: [organize_view.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/organize_view.py)

1. In `_build_done()`, store the `"Back to Dashboard"` button as `self._done_back_btn` so it can be enabled/disabled programmatically.
2. Modify `_on_rollback_requested(self, log_path: Optional[Path] = None)`:
   - Accept an optional `log_path`. If not provided, default to `self._rollback_log_path`.
   - If `log_path` is passed, set `self._rollback_log_path = log_path` and transition the stack to the Done screen (`_STATE_DONE` / State 4) immediately.
   - On State 4, set the title `self._done_label` to `"Rolling back reorganization..."` and detail `self._done_detail` to `"Restoring files and updating Serato crates..."`. Hide `self._rollback_btn` and disable `self._done_back_btn`.
   - Start the `_RollbackWorker` using `self._rollback_log_path`.
3. In `_on_rollback_finished(self, restored, failed)`:
   - Re-enable `self._done_back_btn` so the user can navigate away.
   - Show the success status message as usual.
4. In `_on_rollback_error(self, message)`:
   - Re-enable `self._done_back_btn`.

---

### Task 4: Integrate Reorganizations in Dashboard Recent Activity Feed

**File**: [dashboard.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/dashboard.py)

Update the `_build_activity_section(self, serato_dir)` method to read recent reorganizations from the `_CrateSort` folder:
- Scan `_CrateSort/reorganization_log_*.json`.
- For each log file found:
  - Load the JSON and read `executed_at` and `moves` list.
  - Parse the ISO date and check if it occurred within the last 30 days.
  - If yes, append an item to `items` with:
    - `dot_color = self._TEAL` (action color)
    - `text = "Library Reorganized — [N] files moved"`
    - `_dt = dt` (the executed_at datetime object)
  - Check if `rolled_back_at` is present in the JSON log and occurred within the last 30 days.
  - If yes, append an item to `items` with:
    - `dot_color = self._ORANGE` (revert color)
    - `text = "Reorganization Rolled Back — [N] files restored"`
    - `_dt = dt_rollback` (the rolled_back_at datetime object)
- Let the existing list sorting (`items.sort(key=lambda x: x['_dt'], reverse=True)`) order these activity rows chronologically alongside the crate additions/deletions and track updates.

---

### Verification

Verify that all existing tests pass:
```bash
python3 cratesort/tests/run_organizer.py
```
