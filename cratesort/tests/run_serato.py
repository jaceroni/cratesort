#!/usr/bin/env python3
"""
Phase 3 Serato integration test runner.
Tests CrateReader, CrateWriter, and PathRewriter.
Usage:  python tests/run_serato.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.serato.crate_reader import CrateReader
from cratesort.src.serato.crate_writer import CrateWriter
from cratesort.src.serato.path_rewriter import PathRewriter, PathChange

TEST_LIBRARY = Path('/Users/jacebrown/Desktop/cratesort-test-library')
SERATO_DIR   = TEST_LIBRARY / '_Serato_'

logging.basicConfig(level=logging.WARNING, format='%(levelname)s  %(message)s')

SEP = '─' * 72


def section(title: str) -> None:
    print(f'\n{SEP}')
    print(f'  {title}')
    print(SEP)


def main() -> None:
    print(f'\n{"="*72}')
    print('  CrateSort Phase 3 — Serato Integration Test')
    print(f'  _Serato_ dir: {SERATO_DIR}')
    print(f'{"="*72}')

    # ── 1. CrateReader ────────────────────────────────────────────────────
    section('CRATE READER')

    reader = CrateReader(SERATO_DIR)
    lib = reader.read()

    print(f'\n  Total crates            : {lib.total_crates}')
    print(f'  Total track references  : {lib.total_tracks_referenced}')
    print(f'  Unique tracks referenced: {lib.unique_tracks_referenced}')
    print(f'  Resolved paths          : {lib.unique_tracks_referenced - len(lib.orphan_tracks)}')
    print(f'  Unresolved (orphan) paths: {len(lib.orphan_tracks)}')

    section('CRATE HIERARCHY (full tree)')
    print(reader.format_tree(lib))

    section('SAMPLE CRATES WITH TRACKS (first 5 non-empty)')
    shown = 0
    for crate in lib.crates.values():
        if crate.track_count == 0 or crate.read_error:
            continue
        print(f'\n  {crate.full_path}  ({crate.track_count} tracks)')
        for track in crate.tracks[:4]:
            print(f'    {track}')
        if crate.track_count > 4:
            print(f'    ... +{crate.track_count - 4} more')
        shown += 1
        if shown >= 5:
            break

    section('READ ERRORS')
    errors = [(fp, c) for fp, c in lib.crates.items() if c.read_error]
    if errors:
        for fp, crate in errors:
            print(f'  {fp}: {crate.read_error}')
    else:
        print('  None.')

    # ── 2. CrateWriter ────────────────────────────────────────────────────
    section('CRATE WRITER — round-trip test')

    writer = CrateWriter(SERATO_DIR)

    # Use real paths from the test library (relative to drive root)
    # These are posix paths from the root, matching how Serato stores them
    test_tracks = [
        'Users/jacebrown/Desktop/cratesort-test-library/MP3/Blues/Albert King/Cold Feet.mp3',
        'Users/jacebrown/Desktop/cratesort-test-library/MP3/Blues/Little Walter/Shake Dancer.mp3',
        'Users/jacebrown/Desktop/cratesort-test-library/MP3/Funk : Classic/Isaac Hayes/Joy - Pt. 1.mp3',
    ]
    test_crate_name = '_CrateSort_Test'

    # Create
    r = writer.create_crate(test_crate_name, test_tracks)
    print(f'\n  create_crate("{test_crate_name}"):  success={r.success}  '
          f'tracks={r.tracks_affected}  error={r.error}')

    # Read back to verify
    lib2 = reader.read()
    created = lib2.crates.get(test_crate_name)
    if created:
        print(f'  Read back:  {created.track_count} tracks  ✓')
        for t in created.tracks:
            print(f'    {t}')
    else:
        print('  Read back:  crate not found  ✗')

    # Add a track
    extra_track = 'Users/jacebrown/Desktop/cratesort-test-library/MP3/Hip-Hop : Rap/Big L/Danger Zone.mp3'
    r = writer.add_tracks(test_crate_name, [extra_track])
    print(f'\n  add_tracks:    success={r.success}  added={r.tracks_affected}  '
          f'backup={r.backup_path.name if r.backup_path else None}')

    # Remove a track
    r = writer.remove_tracks(test_crate_name, [test_tracks[1]])
    print(f'  remove_tracks: success={r.success}  removed={r.tracks_affected}')

    # Verify final state
    lib3 = reader.read()
    final = lib3.crates.get(test_crate_name)
    if final:
        print(f'  Final state:  {final.track_count} tracks  (expected 3)')
        for t in final.tracks:
            print(f'    {t}')

    # Duplicate
    dup_name = '_CrateSort_Test_Copy'
    r = writer.duplicate_crate(test_crate_name, dup_name)
    print(f'\n  duplicate_crate: success={r.success}  tracks={r.tracks_affected}')

    # Rename duplicate
    r = writer.rename_crate(dup_name, '_CrateSort_Test_Renamed')
    print(f'  rename_crate:    success={r.success}')

    # Delete both test crates (cleanup)
    for name in [test_crate_name, '_CrateSort_Test_Renamed']:
        r = writer.delete_crate(name)
        print(f'  delete_crate("{name}"): success={r.success}  backup={r.backup_path.name if r.backup_path else None}')

    # Confirm cleanup
    lib4 = reader.read()
    leftovers = [fp for fp in lib4.crates if '_CrateSort_Test' in fp]
    print(f'  Cleanup verified: {"✓ no leftovers" if not leftovers else "✗ " + str(leftovers)}')

    # ── 3. PathRewriter — dry-run ─────────────────────────────────────────
    section('PATH REWRITER — dry-run mode')

    # Find a crate with real tracks to use as target
    target_crate = None
    for crate in lib.crates.values():
        if crate.track_count >= 2 and not crate.read_error:
            target_crate = crate
            break

    if target_crate:
        print(f'\n  Target crate: {target_crate.full_path}  ({target_crate.track_count} tracks)')

        # Build fake path changes using the first two real track paths from that crate
        old1 = target_crate.tracks[0]
        old2 = target_crate.tracks[1]
        fake_changes = [
            PathChange(old1, old1.replace('MP3/', 'MP3_REORGANIZED/')),
            PathChange(old2, old2.replace('MP3/', 'MP3_REORGANIZED/')),
            PathChange('nonexistent/path.mp3', 'somewhere/else.mp3'),  # should not match
        ]

        print(f'  Changes to apply (dry run):')
        for c in fake_changes:
            print(f'    {c.old_path[:60]}')
            print(f'    → {c.new_path[:60]}')

        rewriter = PathRewriter(SERATO_DIR)
        result = rewriter.rewrite(fake_changes, dry_run=True)

        print(f'\n  DRY RUN results:')
        print(f'    Crates that would be modified : {result.crates_modified}')
        print(f'    Paths that would be rewritten : {result.paths_rewritten}')
        print(f'    Crates unchanged              : {result.crates_unchanged}')
        print(f'    Backups created               : {len(result.backup_paths)} (0 in dry run)')
        print(f'    Errors                        : {len(result.errors)}')

        if result.changes_log:
            print(f'\n  Sample changes from log (first 5):')
            for rec in result.changes_log[:5]:
                print(f'    [{rec.crate_full_path}]')
                print(f'      {rec.old_track_path}')
                print(f'      → {rec.new_track_path}')
    else:
        print('  No crate with tracks found for path rewriter test.')

    print(f'\n{"="*72}\n')


if __name__ == '__main__':
    main()
