# CrateSort — Write Crate Order to Serato neworder.pref (Prompt 23)

> **Run this at Sonnet high effort. Read every referenced file completely before writing any code. Before writing any code, verify that every class, method, and module you reference is already imported in the target file. Add any missing imports before using them.**

## Files to Read First

- `src/serato/crate_writer.py` — add new method here
- `src/serato/crate_reader.py` — understand how Serato library path is resolved
- `src/gui/crate_manager.py` — find every place crate order is saved to crate_order.json and replace with the new method

---

## Background

Serato DJ Pro stores the user-defined crate display order in `_Serato_/neworder.pref`. This is a UTF-16 Big Endian text file with this exact format:

```
[begin record]
[crate]CrateName
[crate]CrateName%%SubcrateName
[crate]CrateName%%SubcrateName%%GrandchildName
[end record]
```

The `%%` separator matches the `.crate` filename convention. Every crate and subcrate appears in this file in the exact order Serato displays them top to bottom in its sidebar. The file is the canonical display order — Serato reads it on launch and renders crates in that order.

CrateSort currently saves crate order to `_CrateSort/crate_order.json` which only affects CrateSort's own display. This must be replaced with writes to `neworder.pref` so Serato respects the user's order on next launch.

---

## Change 1 — Add write_crate_order() to crate_writer.py

Add a new method to `CrateWriter` (or the appropriate class in `crate_writer.py`):

`write_crate_order(serato_dir: str, ordered_crate_paths: list[str]) -> bool`

Where:
- `serato_dir` is the path to the `_Serato_/` directory
- `ordered_crate_paths` is a flat ordered list of crate paths in CrateSort's internal format (e.g. `["Blues", "Blues/Jump Blues", "Country Western", "Funk", "Funk/2-Step Grooves", ...]`)

The method must:

1. Convert each CrateSort crate path to Serato's `%%`-separated format:
   - `"Blues"` → `"Blues"`
   - `"Blues/Jump Blues"` → `"Blues%%Jump Blues"`
   - `"Funk/Sub/SubSub"` → `"Funk%%Sub%%SubSub"`

2. Build the file content:
   - First line: `[begin record]`
   - One line per crate: `[crate]CrateName` (using the converted `%%` format)
   - Last line: `[end record]`

3. Write to `_Serato_/neworder.pref` as UTF-16 Big Endian encoding with BOM

4. Return `True` on success, `False` on failure. Log any errors but do not raise exceptions.

Also read the existing `neworder.pref` before writing to preserve any virtual parent entries (crates listed in neworder.pref that have no corresponding `.crate` file). These virtual parents must be included in the correct position in the output.

---

## Change 2 — Replace crate_order.json with neworder.pref in crate_manager.py

In `src/gui/crate_manager.py`, find every place that reads from or writes to `_CrateSort/crate_order.json`. Replace each write with a call to `write_crate_order()`.

The ordered list passed to `write_crate_order()` must be the complete flat ordered list of ALL crates in the tree — not just the ones that were reordered. Walk the entire crate tree in display order (top to bottom, depth-first) and collect every crate path.

Keep `crate_order.json` as a fallback for CrateSort's own display order if needed, but every user-initiated reorder must also write to `neworder.pref`.

After writing to `neworder.pref`, show teal footer text: "Crate order saved — Serato will reflect this order on next launch."

---

## Change 3 — Read neworder.pref on Startup

In `src/serato/crate_reader.py`, add a method:

`read_crate_order(serato_dir: str) -> list[str]`

That reads `neworder.pref` and returns the ordered list of crate paths in CrateSort's internal format (converting `%%` back to `/`).

In `src/gui/crate_manager.py`, when building the crate tree on startup, use `read_crate_order()` to determine the display order of crates rather than `crate_order.json`. This ensures CrateSort always starts in sync with whatever order Serato last had.

---

## General Requirements

- UTF-16 Big Endian encoding with BOM for all reads and writes of neworder.pref
- Never corrupt neworder.pref — always write atomically (write to a temp file, then rename)
- Serato custom ID3 frames are never modified
- Do not break any existing crate manager functionality
- The crate_order.json file can remain as a legacy fallback but neworder.pref is the source of truth going forward
