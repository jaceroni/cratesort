# CrateSort — Serato File Format Research (Prompt 22)

> **This is a research and reporting task only. Do not change any code. Do not write any new code. Read and report only.**

## Files to Read First

- `src/serato/crate_reader.py` — to understand what fields are currently being parsed
- `src/serato/crate_writer.py` — to understand what is currently being written

---

## Research Task 1 — How Does Serato Store Crate Display Order?

Serato DJ Pro allows the user to drag and reorder crates in its UI. That order is persisted somewhere so it survives app restarts. We need to know exactly where and how.

Inspect the following locations in the user's Serato library at `/Users/jacebrown/Desktop/cratesort-test-library/_Serato_/` (or the live library if accessible):

1. Look at the `database V2` file — open it and report what fields relate to crate ordering. Is there an index, a position field, or a sequence number per crate entry?
2. Look at the `Crates/` directory — are the `.crate` filenames prefixed with numbers or any ordering indicator?
3. Look for any other files in `_Serato_/` that might store crate order — `ordering`, `smartcrates`, or similar
4. Check if the `.crate` files themselves contain any internal ordering field beyond the track list

Report:
- Exactly where crate order is stored
- What format it uses (integer index, filename prefix, database field, etc.)
- Whether CrateSort can write to it safely without corrupting Serato's database
- What would need to change in `crate_writer.py` to write the correct order so Serato respects it on next launch

---

## Research Task 2 — Do Serato .crate Files Store Per-Track Timestamps?

We need to know if Serato stores the date a track was added to a crate anywhere in the `.crate` file format.

Inspect several real `.crate` files from the test library in raw binary/hex:

1. Open 2-3 `.crate` files and list every field/block present in each track entry — not just `ptrk`. Report every 4-character tag found and what data it contains.
2. Is there any timestamp, date, or time field stored per track entry? If yes: what is the tag, what format is the value (Unix timestamp, date string, etc.), and what does it represent?
3. Does the `serato-crate` library expose this field, or is it being silently dropped during parsing?
4. If no per-track timestamp exists in the `.crate` file, is there any other location in the Serato library where track add dates are stored?

Report your findings completely and clearly. This determines whether the Date Added column can be populated from Serato data or whether CrateSort needs to manage its own timestamps.

---

## Deliverable

A clear written report answering both research questions. No code changes. No implementation. Just facts about what's in the files.
