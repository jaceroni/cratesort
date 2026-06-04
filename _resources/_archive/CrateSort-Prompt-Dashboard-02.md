# CrateSort — Dashboard: Fix Change Detection (Prompt 30)

> **Run this at Sonnet high effort. Read `src/utils/checkpoint.py` and `src/gui/dashboard.py` completely before making any changes. Before writing any code, verify all imports.**

## Files to Read First

- `src/utils/checkpoint.py`
- `src/gui/dashboard.py`

---

## Bug 1 — Rename Detected as Delete + Create

When a crate is renamed in Serato, the checkpoint diff currently shows it as two changes: one removal (old name) and one addition (new name). This is wrong — it should be shown as a single rename event.

Fix `detect_changes()` in `checkpoint.py`:

After identifying removed crates and added crates, attempt to match them as renames:
- For each removed crate, check if any added crate has the same track count
- If yes, treat this as a rename: `{type: 'renamed', description: "Crate renamed: '[old]' → '[new]'", crate_path: new_path}`
- Remove both the addition and the removal from their respective lists
- If track counts don't match, keep them as separate add/remove events

This is a heuristic — it won't be perfect in all cases but will correctly handle the common rename scenario.

---

## Bug 2 — Track Additions to Existing Crates Not Detected

The checkpoint stores crate name → track count. When a track is added to an existing crate, the track count changes. This should appear as a change but isn't being detected.

Verify that `detect_changes()` correctly compares track counts for crates that exist in both current and previous snapshots. Add a third change type:

- For each crate that exists in both current and previous:
  - If `current_count > previous_count`: `{type: 'tracks_added', description: "[N] track(s) added to '[Crate Name]'", crate_path: crate_path}`
  - If `current_count < previous_count`: `{type: 'tracks_removed', description: "[N] track(s) removed from '[Crate Name]'", crate_path: crate_path}`

Where N = abs(current_count - previous_count).

---

## Bug 3 — Track Metadata Changes (Log Only, Do Not Fix Yet)

Changes to track metadata (artist name, title, BPM, etc.) within a crate are not detected because the checkpoint only tracks track counts, not metadata content. Detecting metadata changes would require storing a hash of each track's metadata — this is a future enhancement, not in scope for this prompt.

Add a comment in `checkpoint.py` noting this limitation:
`# TODO: metadata change detection (artist, title, BPM changes) requires per-track hashing — future enhancement`

---

## Display Fix — Change Row Descriptions

In `dashboard.py`, update the display of change rows to use clean human-readable descriptions without `.crate` file extension suffixes:

- "New crate: TEST CRATE 2.crate" → "New crate: TEST CRATE 2"
- "Crate removed: TEST CRATE - EDIT.crate" → "Crate removed: TEST CRATE - EDIT"

Strip `.crate` from any crate name displayed in the dashboard changes section.

---

## What NOT to Change

Do not change column indices, sort behavior, other dashboard sections, or any other functionality. Only fix the change detection logic and display formatting.
