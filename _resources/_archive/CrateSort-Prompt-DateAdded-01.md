# CrateSort — Date Added Column via Serato Database V2 Parser (Prompt 24)

> **Run this at Sonnet high effort. Read every referenced file completely before writing any code. Before writing any code, verify that every class, method, and module you reference is already imported in the target file. Add any missing imports before using them.**

## Files to Read First

- `src/serato/crate_reader.py` — understand current Serato reading architecture
- `src/serato/crate_writer.py` — understand existing Serato module patterns
- `src/gui/crate_manager.py` — understand how track panel columns are populated, specifically TC_DATE (column index 8)

---

## Background

Serato stores the date a track was added to the library in its `database V2` file, not in `.crate` files. The relevant fields per track record (`otrk`) are:

- `uadd` — 4-byte big-endian unsigned integer, Unix timestamp of when the track was added to the Serato library
- `tadd` — UTF-16 string version of the same timestamp
- `pfil` — UTF-16 string, the track's file path (used as the lookup key)

The `database V2` file uses TLV (Tag-4-byte + Length-4-byte + Value) format with UTF-16 BE strings.

---

## Change 1 — New Module: src/serato/database_reader.py

Create a new module `src/serato/database_reader.py` with one primary function:

`read_track_add_dates(serato_dir: str) -> dict[str, datetime]`

Where:
- `serato_dir` is the path to the `_Serato_/` directory
- Returns a dict mapping file path (from `pfil`) → `datetime` object (from `uadd`)
- Returns empty dict on any error — never raises exceptions

Implementation:
- Open `_Serato_/database V2` in binary mode
- Parse TLV records to find all `otrk` blocks
- Within each `otrk`, extract `pfil` (file path) and `uadd` (Unix timestamp)
- Convert `uadd` (4-byte big-endian int) to a `datetime` using `datetime.fromtimestamp()`
- Store in the dict keyed by the `pfil` path value
- Cache the result in memory — only parse the file once per CrateSort session
- Log a warning if `database V2` is not found but do not crash

---

## Change 2 — Wire Date Added into the Track Panel

In `src/gui/crate_manager.py`:

### On startup / library load:
Call `read_track_add_dates(serato_dir)` once and store the result as `self._add_dates: dict[str, datetime]` on the `CrateManagerView`.

### In `_populate_resolved_row()`:
Find where `TC_DATE` (column index 8) is currently set. Replace the placeholder `—` with the actual date from `self._add_dates`.

Look up the track's file path in `self._add_dates`. If found, format the datetime as `YYYY-MM-DD` and display it. If not found, display `—`.

### Sorting:
The Date Added column must sort correctly as a date — not as a string. Store the Unix timestamp integer in `Qt.ItemDataRole.UserRole` on the Date Added cell so Qt sorts numerically. The display text is the formatted date string.

---

## Change 3 — Serato Directory Resolution

`database_reader.py` needs the path to `_Serato_/`. This is the same directory CrateSort already uses for reading `.crate` files. Pass the existing `serato_dir` value from wherever it is currently stored in `crate_manager.py` or `crate_reader.py`.

Do not hardcode any paths. Use whatever mechanism already exists in the codebase to resolve the Serato directory.

---

## General Requirements

- Never modify `database V2` — read only
- If `database V2` is missing or malformed, the Date Added column shows `—` for all tracks — never crashes
- The parser must be fast enough to not block the UI on launch — if the file is large, consider parsing in a background thread
- Serato custom ID3 frames are never modified
- Do not change any column indices — TC_DATE is already at index 8
- Do not change any existing column behavior
