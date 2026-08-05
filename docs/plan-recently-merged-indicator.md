# Track-level "recently merged" indicator (Library tab)

**Status: SHIPPED 2026-08-05.** Implemented as planned below — see `CLAUDE-CS.md` → "Locked decision — August 2026 (track-level 'recently merged' indicator)" for the final as-built writeup (color/glyph choice, verification results). This doc is kept as the original design rationale, not an open TODO.

## Context

CrateSort's duplicate consolidation ("Rinse Your Library") already writes a durable, detailed record of every merge — `_CrateSort/duplicate_consolidation_<timestamp>.json`, one per consolidation run, listing every loser file absorbed into every winner file. But nothing anywhere in the app ever reads these files back. The only user-visible trace of a consolidation event is the one-time celebration screen ("N duplicates cleaned up · Y GB freed") — the instant that's dismissed, the Library tab shows no indication that any specific track was just merged. A user who runs Rinse, then checks Library, sees the duplicate rows are simply gone — indistinguishable from any other reason a track count might have changed.

This was found and confirmed via full code trace (not guessed) while investigating why the just-shipped persistent classification Status column (`_derive_persistent_status` in `library_browser.py`, see `CLAUDE-CS.md` → "Locked decision — August 2026 (persistent classification Status column)") didn't reflect anything about a merge that had just happened. It doesn't, on purpose in hindsight — **consolidation and classification are different scopes**: classification Status is an artist-level judgment (does this whole artist have a trustworthy genre), while consolidation happens per individual audio file (this specific track absorbed N duplicate copies). The fix is a separate, track-level indicator, not an extension of the artist-level Status column.

**Confirmed with Jace:** the indicator should be time-windowed — 30 days — rather than a permanent forever-visible flag, since its value is "confirm my recent Rinse run actually did something," not a permanent historical record. The underlying log files themselves are never deleted; only the visible indicator's date filter expires.

## Design

### 1. Read the existing rollback logs (new, small, additive — no changes to how they're written)

`RollbackLog` (`cratesort/src/core/file_organizer.py:113-190`) is the class that already writes these files; `DuplicateConsolidator.consolidate()` (`cratesort/src/core/duplicate_consolidator.py`) calls `rlog.log_move(op, duplicate=True)` per loser (line ~163), and names the file `duplicate_consolidation_{datetime.now():%Y%m%d_%H%M%S}.json` (line ~74-78).

**Confirmed exact schema** (verified against a real sample file on disk), per `moves` entry with `duplicate: true`:
```json
{
  "source": "<loser file path>",
  "destination": "<winner file path>",
  "sha256": "<hash or ''>",
  "executed_at": "<ISO datetime>",
  "status": "completed" | "failed" | "skipped" | "destination_written",
  "duplicate": true
}
```
Top-level: `version`, `library_root`, `serato_dir`, `executed_at`, `moves` (list, as above), `metadata_changes`, `crate_backup_paths`.

New function — e.g. `read_recent_merges(library_path: Path, within_days: int = 30) -> dict[str, dict]` in `cratesort/src/core/duplicate_consolidator.py` (natural home, same module that writes these logs):
- Mirror the exact existing precedent for the analogous `reorganization_log_*.json` pattern — `organize_view.py:648-687` (`_refresh_gate_screen`): `library_path.joinpath('_CrateSort').glob('duplicate_consolidation_*.json')`, open each in a `try/except Exception: continue` (skip corrupt/partial files), read `moves`. Unlike Organize's UI-display cap of the 3 most recent logs, read **all** matching files — this is a data lookup, not a history list.
- Keep only entries where `duplicate is True` and `status == 'completed'`.
- Parse `executed_at` (ISO format, `datetime.fromisoformat`), keep only entries within the last `within_days` days of "now."
- Normalize `destination` with `unicodedata.normalize('NFC', str(p))` before using it as a dict key — mirror the exact existing precedent in `file_organizer.py:1162-1171` (`_sync_metadata_files`'s `_nfc_path`) and `path_rewriter.py:27`. Do not invent a new normalization scheme.
- Return `{normalized_destination_path: {'count': int, 'most_recent': iso_date_str}}`, aggregating across however many log files/events reference the same winner (a track can in principle be a merge winner more than once across separate Rinse runs over time).

### 2. Wire into `library_browser.py` — track-level rows only

- **`load()`** (`library_browser.py:~605-663`): alongside the existing session/edits loading block, call `read_recent_merges(library_path)` once per load, store as `self._recent_merges: dict[str, dict] = {}` (declared/reset the same way `self._session_genre`/`self._edits` already are).
- **`_make_track_child`** (`library_browser.py:1256-1317`, confirmed this is where every track-level row's columns/colors/tooltip get set, and confirmed it is the *only* place — track rows are lazy-built on artist-row expand via `_on_item_expanded`, `library_browser.py:1347-1357`, so `self._recent_merges` must already be populated by `load()` before any expand can fire, which it will be): look up `unicodedata.normalize('NFC', str(rec.path))` in `self._recent_merges`. If present, this row gets the "recently merged" treatment — mirror the **existing, already-working `is_new` pattern** in this same function (a glyph prefix on the title text, a distinct whole-row color via `for col in range(len(HEADERS)): child.setForeground(col, brush)`, and a tooltip on `LC_ARTIST`) rather than inventing a new column-based mechanism. Do **not** repurpose `LC_CLS_PROPOSED`/`LC_CLS_CONF`/`LC_CLS_STATUS` — those have an existing classify-mode-only, artist-row-only contract (confirmed: `_make_track_child` never touches them today), and retrofitting a persistent track-level meaning onto them would conflict with that contract rather than cleanly extend it.
- **Precedence when states collide** (a track can currently be: unclassified-red, unclassified-but-tagged-amber, newly-added-teal, or normal-muted — this adds a 5th, "recently merged"): recommend merged takes precedence over "new" (rarer, more specific information) but classification-incompleteness (red/amber) still wins over both, since an unclassified track needs action, whereas "recently merged" is an FYI. This ordering is a small, cheap-to-change `if/elif` — flag it for a quick gut check with Jace during implementation rather than treating it as locked.
- Tooltip text, e.g.: `f'Absorbed {count} duplicate cop{"y" if count == 1 else "ies"} on {most_recent_date}'`.

### 3. Explicitly NOT in scope for this pass

- No artist-level rollup/badge ("this artist has a recently-merged track somewhere inside it") — keep this pass scoped to the track row itself, matching consolidation's actual per-file granularity. Don't reopen the artist-level Status column's logic to fold this in.
- No settings UI for the 30-day window — hardcoded default, not user-configurable in v1.
- No changes to `duplicate_consolidator.py`'s write path, `RollbackLog`, or the celebration screen — this is purely additive read-side plumbing on data that already exists.

## Open items to resolve during implementation (need a quick visual/product gut-check, not guessable from code alone)

- **Exact glyph and color.** `is_new` already uses `#5c9d94` (teal-ish); unclassified uses `#C75B5B` (red) and `#c9a87a` (amber). Whatever's chosen for "merged" needs to be visually distinct from all three and should come from CrateSort's locked palette (`CLAUDE-CS.md`) rather than an invented hex — check with Brandy/Dez before finalizing, this is a brand decision, not a code one.
- **Precedence when a track is both new and recently-merged** (rare, but possible) — minor call, noted above.

## Files touched

- `cratesort/src/core/duplicate_consolidator.py` — add `read_recent_merges()`.
- `cratesort/src/gui/library_browser.py` — `load()` populates `self._recent_merges`; `_make_track_child` renders the indicator.

## Verification

- Headless (same pattern used for every other feature this session — real widgets, no screenshots, run via `QT_QPA_PLATFORM=offscreen`): write a synthetic `duplicate_consolidation_<timestamp>.json` into a test library's `_CrateSort/` folder with a known winner path and an `executed_at` within 30 days; load the library, expand that artist's row (triggers `_on_item_expanded` → `_make_track_child`), confirm the winner track shows the indicator + correct tooltip text/count.
- 30-day boundary: a log with `executed_at` older than 30 days should **not** produce a visible indicator for that track.
- Path normalization: a log entry's `destination` written with different Unicode normalization (NFD) than the freshly-scanned `rec.path`'s NFC form should still match (mirrors the exact risk `_sync_metadata_files`/`path_rewriter.py` already guard against elsewhere).
- Aggregation: a winner path appearing as `destination` across two separate log files (merged more than once over time) should produce a combined/most-recent count, not silently show only one event or crash on the second.
- Confirm `duplicate_consolidation_*.json` files are never deleted, moved, or mutated by this feature — read-only consumer.
