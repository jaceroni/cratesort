# CrateSort — File Organizer Module

## Context

All Phase 1-3 modules are complete:
- Scanner, Classifier, Filename Cleaner, "The" Handler, Metadata Fixer, 
  Artist Consolidator, Duplicate Detector, Crate Reader, Crate Writer, 
  Path Rewriter

The stub file is ready: `src/core/file_organizer.py`

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

With a real `_Serato_/` folder containing 191 crates.

## What this module does

The File Organizer is the module that actually moves files on disk. It takes 
all the proposals from the Phase 2 engines (classifier results, filename 
proposals, "The" handler proposals, metadata fixes, consolidation candidates) 
and executes them — but ONLY after the user has reviewed and approved a 
complete reorganization plan.

This is the most dangerous module in the app. It moves files, renames files, 
and restructures directories. Everything it does must be previewable, 
approvable, and reversible.

## Critical design principles

1. **Preview → Approve → Execute → Verify.** Nothing happens without the 
   user seeing exactly what will change and saying yes.

2. **Non-destructive by default.** The organizer uses copy-verify-delete, not 
   move. Copy file to new location, verify the copy is complete and intact 
   (size + hash match), then delete the original. If verification fails, the 
   original stays and the copy is removed.

3. **Full rollback log.** Every file operation is logged with old path, new path, 
   timestamp, and hash. The rollback system can undo any reorganization by 
   reading this log.

4. **Serato crate paths updated automatically.** After files move, the Path 
   Rewriter updates all .crate files. This is part of the execution step, not 
   a separate user action.

5. **No file deletion.** The organizer moves files. It does not delete files. 
   The only exception is removing the original after a verified copy during 
   the move operation itself.

6. **Locked files are skipped.** If file locking is implemented, locked files 
   are never moved. For now, respect a skip list if provided.

7. **Protected folders are skipped.** The user can designate folders as 
   "don't touch" (purpose folders like _Drops, _Unsorted, _Tributes, etc.). 
   Files inside protected folders are scanned and inventoried but never moved 
   during reorganization.

## The reorganization plan

The organizer builds a complete `ReorganizationPlan` before touching anything. 
This plan shows every proposed change:

### What the plan contains

For each file that would move:
- `source_path`: Where it is now
- `destination_path`: Where it would go
- `reason`: Why (genre classification, artist consolidation, "The" handling, etc.)
- `filename_change`: Old filename → new filename (if the filename cleaner 
  proposed a rename)
- `metadata_changes`: What tag changes would be written (from the metadata fixer)
- `crates_affected`: Which Serato crates reference this file and would need 
  path updates

### Target hierarchy

The destination follows the CrateSort folder structure:
```
[designated root]/
  [Genre]/
    [Artist]/
      [Song Title].[ext]
```

Where:
- Genre comes from the classifier
- Artist folder uses the "The"-handled name if applicable 
  (`Doors, The/` not `The Doors/`)
- Artist folder uses the consolidation winner name if applicable
  (`Bob Seger/` with optional project subfolders)
- Filename uses the cleaned version from the filename cleaner
- The designated root is whatever directory the user pointed CrateSort at — 
  files stay within that root, never moved outside it

### What the plan also shows

- **Summary stats**: Total files moving, total staying put, total renamed, 
  total getting metadata fixes
- **New folders to create**: Genre and artist folders that don't exist yet
- **Empty folders after move**: Folders that would be empty after files move 
  out — propose deletion (with confirmation)
- **Protected folders**: Listed as skipped, with file counts
- **Conflicts**: Files that would collide at the destination (same name in 
  same target folder) — these need user resolution

## Execution engine

When the user approves the plan:

1. **Create destination folders** — Build any new genre/artist directories
2. **Move files** — For each file in the plan:
   a. Copy to destination
   b. Verify copy (file size match + SHA-256 hash match)
   c. If verified: delete original, log the move
   d. If verification fails: delete the failed copy, skip this file, log 
      the error, continue with remaining files
3. **Apply metadata changes** — Write approved tag changes (genre, style, 
   sort-artist) to moved files. NEVER touch Serato custom frames, comments, 
   or BPM.
4. **Update Serato crates** — Run the Path Rewriter with all old→new path 
   mappings. Backs up every modified .crate file before writing.
5. **Clean up empty folders** — Remove folders that are now empty (if user 
   approved this in the plan)
6. **Write rollback log** — Save the complete operation log as JSON in the 
   CrateSort data directory

## Rollback system

The rollback log (`reorganization_log_{timestamp}.json`) contains every 
operation performed. A `rollback()` method can:
- Read the log
- Move every file back to its original location
- Restore original filenames
- Restore original metadata (the log stores before/after values)
- Restore Serato crate files from backups
- Remove any folders that were created during the original reorganization

Rollback is a complete undo. After rollback, the library is in the exact 
state it was before the reorganization ran.

## What NOT to build

- No GUI — the organizer returns plans and accepts approve/reject, but the 
  visual presentation is the GUI's job later
- No duplicate consolidation execution — that's handled separately with its 
  own quarantine flow
- No intake workflow — that's a separate module
- No Serato database sync — just crate file path updates via the Path Rewriter

## Testing

Write a test runner (`tests/run_organizer.py`) that:

1. Runs the full pipeline: scanner → classifier → all Phase 2 modules
2. Builds a reorganization plan for the test library
3. Prints the complete plan:
   - Every file move (source → destination)
   - Every filename change
   - Every metadata change
   - Every crate that would be updated
   - Summary stats
   - Protected folder report (if any)
   - Conflict report (if any)
4. Does NOT execute the plan — preview only for this test
5. Also test the plan builder with a small subset (pick 3-5 files) and 
   actually execute a move into a temporary directory to verify:
   - Copy-verify-delete works
   - Rollback log is written correctly
   - Rollback restores everything to original state
   Clean up the temp directory after the test.

Run it against the test library and show me the actual output.

## Architecture notes

- `FileOrganizer` class — takes scan results, classifier results, and all 
  Phase 2 proposals
- `ReorganizationPlan` dataclass — the complete before/after picture
- `MoveOperation` dataclass — individual file move with source, dest, hash, 
  status
- `RollbackLog` class — reads/writes the JSON operation log
- The organizer coordinates the Scanner, Classifier, and all Phase 2 modules 
  but doesn't duplicate their logic — it consumes their output
- Use SHA-256 for copy verification — fast enough for files up to a few 
  hundred MB
- All paths via pathlib for cross-platform safety
- The execution engine should support progress callbacks so the GUI can 
  show a progress bar later
