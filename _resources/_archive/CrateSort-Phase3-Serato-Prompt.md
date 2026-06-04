# CrateSort — Phase 3: Serato Integration

## Context

All Phase 1-2 engine modules are complete and audited:
- Scanner, Classifier, Filename Cleaner, "The" Handler, Metadata Fixer, 
  Artist Consolidator, Duplicate Detector

Three stub files are ready for implementation:
- `src/serato/crate_reader.py`
- `src/serato/crate_writer.py`
- `src/serato/path_rewriter.py`

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

There is now a real `_Serato_/` folder inside the test library, copied from a 
live DJ setup. It contains dozens of real crate files with real track references. 
These crate files reference paths on the original external drive — the paths will 
NOT match the test library's audio files. That's expected and fine.

The Serato file format research doc from Session 1 is in `docs/serato-file-format.md`. 
Read that first — it covers the .crate binary TLV format, tag types, path encoding, 
and nested record structure.

The `serato-crate` library is already in `requirements.txt` for .crate read/write.

## Critical rule: Serato's edits always win

This is the project's golden rule. CrateSort NEVER overwrites Serato's data 
without explicit user intent. The crate reader reads. The crate writer only 
writes when the user triggers an action. The path rewriter only updates file 
paths inside crates after the user approves a file move.

## Important: Read-only first

The crate reader is the priority in this session. The crate writer and path 
rewriter should be implemented but they are lower priority — get the reader 
rock solid first since everything depends on being able to accurately read 
what Serato has.

---

## Module 1: Crate Reader (`src/serato/crate_reader.py`)

### What it does

Reads all `.crate` files from a `_Serato_/` directory and builds a complete 
picture of the user's crate structure.

### What to read

1. **Crate inventory** — Find every `.crate` file in `_Serato_/Subcrates/`. 
   Map out the full crate tree including nested crates (subcrates are encoded 
   in the filename with `%%` separators per the format doc).

2. **Crate membership** — For each crate, read all track paths it contains. 
   These are the file references inside the .crate binary format.

3. **Crate hierarchy** — Build the parent/child tree. A crate named 
   `Funk%%Classic Funk.crate` is a subcrate of `Funk.crate`. Map this 
   hierarchy so the GUI can display it as a tree later.

4. **Smart crates** — Detect and catalog smart crate definitions if they 
   exist in the Serato data. Read their rules but don't execute them — 
   just catalog what's there.

### Path handling

The track paths inside .crate files are absolute paths from the original 
drive. The reader should:
- Read and store paths exactly as they appear in the crate file
- Also store a normalized/relative version for matching against the scanner's 
  inventory later
- Flag paths that don't resolve to any file in the scanned library (expected 
  for the test setup since the crate files reference the external drive)
- Count resolved vs unresolved paths per crate

### Output

A `CrateLibrary` object containing:
- `crates`: List of `Crate` objects, each with:
  - `name`: The crate's display name
  - `filename`: The actual .crate filename
  - `tracks`: List of track paths (as stored in the crate file)
  - `parent`: Parent crate name (or None for top-level)
  - `children`: List of child crate names
  - `track_count`: Number of tracks in this crate
  - `resolved_count`: How many tracks match files in the scanned library
  - `unresolved_count`: How many tracks point to files not found
- `tree`: The full hierarchy as a nested structure
- `total_crates`: Count
- `total_tracks_referenced`: Count (across all crates, with duplicates)
- `unique_tracks_referenced`: Count (deduplicated across all crates)
- `orphan_tracks`: Tracks in crates that don't exist in the scanned library

### Error handling

- Malformed .crate files should be logged and skipped, not crash the reader
- Empty crates are valid — catalog them
- Handle encoding issues in crate names and track paths gracefully

---

## Module 2: Crate Writer (`src/serato/crate_writer.py`)

### What it does

Writes `.crate` files in Serato's native format. This is how CrateSort 
creates new crates, adds tracks to crates, removes tracks from crates, 
renames crates, and duplicates crates.

### Operations to support

1. **Create crate** — Write a new .crate file with a given name and track list
2. **Add tracks** — Append track paths to an existing crate
3. **Remove tracks** — Remove specific track paths from a crate
4. **Rename crate** — Create new .crate file with new name, copy contents, 
   delete old file
5. **Duplicate crate** — Copy a crate's contents to a new name
6. **Delete crate** — Remove the .crate file (with confirmation — the writer 
   just executes, confirmation is the GUI's job)
7. **Create subcrate** — Write a crate with the `%%` naming convention for 
   nesting

### Safety rules

- NEVER modify a crate without explicit instruction
- NEVER delete tracks from disk — only from crate membership
- Always write valid .crate format that Serato can read
- Write operations should be atomic where possible — write to temp file, 
  then rename, so a crash mid-write doesn't corrupt the crate
- Keep a log of every write operation for the checkpoint/rollback system later

### Output

Each operation returns a `CrateWriteResult`:
- `success`: Boolean
- `operation`: What was done
- `crate_name`: Which crate
- `tracks_affected`: How many tracks were added/removed
- `backup_path`: Path to the pre-modification backup (if applicable)

---

## Module 3: Path Rewriter (`src/serato/path_rewriter.py`)

### What it does

After CrateSort moves files during reorganization, the path rewriter updates 
all `.crate` files to point to the new file locations. This is what keeps 
Serato crates intact after a library reorganization.

### How it works

1. Takes a list of `PathChange` objects: `{old_path, new_path}`
2. Reads every .crate file in the _Serato_ directory
3. For each crate, replaces any matching old paths with new paths
4. Writes the updated crate files back

### Safety rules

- Only rewrites paths that are in the provided change list — never guesses
- Creates a backup of every crate file before modification
- Logs every path change made in every crate (for rollback)
- If a path in a crate doesn't match any change in the list, leave it alone
- Dry-run mode: can report what WOULD change without writing anything

### Output

A `RewriteResult`:
- `crates_modified`: How many crate files were updated
- `paths_rewritten`: Total path changes across all crates
- `crates_unchanged`: Crates that had no matching paths
- `changes_log`: Detailed list of every change in every crate
- `backup_paths`: Where the pre-modification backups are stored

---

## Testing

Write a test runner (`tests/run_serato.py`) that:

1. Points the crate reader at the `_Serato_/` folder in the test library
2. Reads all crate files and prints:
   - Total crates found
   - The full crate hierarchy (indented tree view)
   - A few sample crates with their track counts and sample track paths
   - Resolved vs unresolved path counts (most will be unresolved since the 
     crate files reference the external drive, not the test library)
3. Tests the crate writer by:
   - Creating a new test crate with a few track paths from the test library
   - Reading it back to verify it's valid
   - Adding a track to it
   - Removing a track from it
   - Deleting it (cleanup)
4. Tests the path rewriter in dry-run mode:
   - Creates a fake path change list
   - Runs against a test crate
   - Shows what would change without writing

Run it against the test library and show me the actual output.

## Architecture notes

- `CrateReader` class — takes a path to a `_Serato_/` directory
- `CrateWriter` class — takes a path to a `_Serato_/` directory
- `PathRewriter` class — takes a path to a `_Serato_/` directory
- Use the `serato-crate` library for the binary .crate format read/write
- If `serato-crate` doesn't support something we need, fall back to the 
  custom parser using the format doc in `docs/serato-file-format.md`
- All write operations create backups before modifying
- The reader must handle the real-world messiness of dozens of actual crate 
  files — encoding issues, deep nesting, empty crates, large track lists
