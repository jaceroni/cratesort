# Rinse (Duplicate Detection) — Manual Test Findings — 2026-08-27

> **Resolution status (2026-08-27):** #1, #2, #3 all fixed. #4 deferred as instructed.
> - **#1** — `normalize_title()` now strips *any* trailing `(...)`/`[...]` group instead of
>   matching a fixed allow-list, so a user-added suffix like `(Bootleg)` no longer moves the
>   file into a different detection bucket. Root cause was bucket-key string inequality, not a
>   stale cache — detection groups a pair only when normalized `artist + title` match exactly,
>   and audio signals (duration/bitrate/size) only pick the *tier* of an already-formed group.
>   `cratesort/src/utils/normalize.py`; test `cratesort/tests/test_normalize.py`.
> - **#2** — new `_dedupe_track_refs()` in `path_rewriter.py` collapses `otrk` rows that resolve
>   to the same path after a rewrite, keeping the first occurrence's position. Scoped to crates
>   the pass already modifies (not a global every-write invariant) — sufficient to prevent the
>   defect, avoids expanding the pass's backup/rollback footprint. Test `test_path_rewriter.py`.
> - **#3** — the Library tree and Crates table had drifted apart on row height *and* inline-edit
>   treatment; they now share both. `TRACK_ROW_HEIGHT = 36` lives in `theme.py`; the Library
>   tree pins every row to it via a per-item size hint (`_make_artist_item` / `_make_track_child`)
>   — the Crates table already locked its `verticalHeader` sections to 36. The double-click
>   editor is now one shared widget: `gui/inline_edit.py::make_inline_editor()` builds an
>   identically-styled `QLineEdit` (36px tall, 4px QSS `margin` → a centred inset pill) for both
>   screens. The Library tree's `QTreeWidget::item` rule dropped its vertical padding so
>   `setItemWidget` places the editor flush at the row top like `setCellWidget` does, letting
>   both use the exact same helper. Tests `test_track_row_height.py`.
>
> pytest is not installed in the dev environment used for these fixes; each test was verified
> by direct execution and the files placed under the configured `testpaths` for later runs.

Context: Jace ran a manual test of the duplicate detection/consolidation flow before
scanning his full library — created a test crate with two intentional duplicates
(Do or Die "Pimpology" and The Gap Band "Early in the Morning"), each also referenced
from separate crates (Funk, Hip-Hop), then walked the full Rinse flow end to end.

Three issues found, plus one item explicitly deferred. Priority order below reflects
severity, not order found.

---

## 1. Editing metadata on a flagged duplicate causes it to stop being detected (HIGHEST PRIORITY)

**This undermines the core purpose of Rinse** — the feature exists specifically to catch
files that are the same audio despite messy/missing/inconsistent metadata. If cleaning up
a file's tags removes it from detection, the feature fails the exact case it's meant to solve.

### Repro steps
1. Confirm two files are correctly flagged as duplicates by the dashboard (same audio,
   different metadata completeness).
2. Without consolidating, go to Library and edit the sparser file's metadata: set track
   title to include a distinguishing suffix (tested: appending "(Bootleg)"), and assign
   the artist field.
3. Do not save classification — a "classifications not saved" prompt appears; select
   "Leave anyway."
4. Return to Dashboard.

### Observed
- The pair no longer appears in the duplicate count/banner.
- Confirmed NOT a display cache issue — verified via:
  - Full app relaunch (twice)
  - Full library rescan triggered by the Serato "changes detected" flow
  - Manually adding both files to the same crate (Hip-Hop) and rechecking — still not
    flagged, and no "Serato crates changed" banner triggers on next launch either
- Both files remain fully intact and playable on disk throughout — this is a detection
  failure, not a data-loss issue.

### What Cody needs to do
**Do not fix blind.** First read `DuplicateDetector.detect()` in `duplicate_detector.py`
end to end and report back exactly which fields/signals are used to group a pair as
`true_duplicate` or `variant` — specifically whether title/artist metadata equality or
similarity is part of the matching logic at all, versus purely audio-derived signals
(duration, bitrate, variant keyword scan per the existing tiering rule).

Two known variables changed in the test and both need to be ruled in or out separately:
- Title changed (added "(Bootleg)" — note this is also a word that may hit the existing
  variant-keyword list, which would reclassify the pair from `true_duplicate` to `variant`
  rather than removing it from detection entirely — check whether the dashboard duplicate
  count only reflects `true_duplicate` tier)
- Artist field was set on a previously-unassigned file

Report findings before proposing a fix. This is a matching-logic investigation, not a
one-line patch.

---

## 2. Consolidation can leave a duplicate reference to the same file inside one crate

### Repro steps
1. Have two duplicate copies of a track both referenced inside the *same* crate (not two
   different crates — the same one), in addition to other crates each holding only one copy.
2. Run Rinse → select winners → Consolidate Checked → confirm deletion.

### Observed
- Crates that held only one of the two copies correctly resolve to the winner file — no issue.
- The crate that held *both* copies ends up with two rows, both now pointing at the winner
  file — effectively a visible duplicate of itself inside that crate.
- No files on disk were duplicated or affected — this is a crate-reference-list bug, not
  a file-system bug.

### Root cause (understood — no investigation needed)
In `duplicate_consolidator.py`, `PathRewriter.rewrite()` rewrites each crate reference's
path independently. When a single crate contains references to both the winner and the
loser, both get rewritten to the winner's path, but nothing deduplicates the resulting
reference list before the `.crate` file is written back to disk.

### Requested fix
In `PathRewriter.rewrite()`, after rewriting paths for a given crate and before writing
that `.crate` file back out, deduplicate the track reference list by resolved path.
Preserve the position of the first occurrence — do not otherwise reorder the crate.

Open question for Cody to weigh in on: should this dedupe be scoped narrowly to only the
crates touched by the current consolidation pass, or implemented as a general invariant
enforced on every `.crate` write (i.e., a crate should never legally contain the same
resolved file path twice, full stop)? Recommend the general invariant if it doesn't
meaningfully expand the diff, since the narrower fix only prevents recurrence of this
exact path and wouldn't guard against the same defect being introduced elsewhere later.

---

## 3. Inline metadata editor in Library view clips text descenders

### Observed
Double-clicking a row in the **Library** screen to edit metadata (track name, album, etc.)
opens an inline editor that is too short vertically — descenders on letters like g, p, y
are cut off, making edited text hard to read while typing.

### Reference standard — use this, don't invent new sizing
The **Crates screen's track table** (right-hand pane, not the crate tree) has the correct
row height and inline editor sizing already — double-clicking to edit there gives descenders
full clearance. Match the Library screen's inline editor to whatever the Crates screen's
track table is already doing. Do not design new sizing from scratch.

### Fix approach
Per the existing small-visual-change rule: read the exact lines governing row height /
editor widget sizing in both the Library view and the Crates screen's track table, diff
the two, and bring Library in line with Crates. Do not touch unrelated layout.

---

## 4. Deferred — not in scope for this pass

Duplicate consolidation is not currently covered by the sidebar Undo/Redo stack
(`undo_manager.py`'s Command pattern) — it's only recoverable via the Organize tab's
Rollback history, which is the wrong place for it since Rinse runs at first-scan, before
the user has any relationship to the Organize flow. This is a real gap but is explicitly
deferred — do not implement in this pass. Noted here so it isn't lost.

---

## Priority for this work session

1. Fix #1 (investigate first, then fix) — highest severity, undermines Rinse's core value
2. Fix #2 — root cause known, straightforward fix
3. Fix #3 — smaller UI fix, match existing reference component

Do not attempt #4.
