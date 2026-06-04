#!/usr/bin/env python3
"""
File Organizer test runner.
Part 1: Preview full reorganization plan for the test library (no execution).
Part 2: Execute on 5 temp files, verify move + metadata, then rollback.
Usage:  python tests/run_organizer.py
"""
from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.scanner import LibraryScanner
from cratesort.src.core.classifier import GenreClassifier
from cratesort.src.core.filename_cleaner import FilenameCleaner
from cratesort.src.utils.the_handler import TheHandler
from cratesort.src.core.metadata_fixer import MetadataFixer
from cratesort.src.core.artist_consolidator import ArtistConsolidator
from cratesort.src.serato.crate_reader import CrateReader
from cratesort.src.core.file_organizer import FileOrganizer, _sha256

TEST_LIBRARY = Path('/Users/jacebrown/Desktop/cratesort-test-library')
SERATO_DIR   = TEST_LIBRARY / '_Serato_'

logging.basicConfig(level=logging.WARNING, format='%(levelname)s  %(message)s')

SEP = '─' * 72


def section(title: str) -> None:
    print(f'\n{SEP}')
    print(f'  {title}')
    print(SEP)


def build_inputs(library_root: Path, serato_dir: Path = None):
    """Run full pipeline and return all plan inputs as dicts keyed by Path."""
    inv, _ = LibraryScanner(library_root).scan()
    results = GenreClassifier().classify_all(inv)
    fname_props = FilenameCleaner().clean_all(inv)
    the_props = TheHandler().analyze_all({r.artist for r in inv if r.artist})
    meta_props = MetadataFixer().analyze_all(results)
    candidates = ArtistConsolidator().analyze(inv)

    crate_lib = None
    if serato_dir and serato_dir.exists():
        crate_lib = CrateReader(serato_dir).read()

    classifications = {rec.path: cls for rec, cls in results}
    filename_proposals = {rec.path: fp for rec, fp in zip(inv, fname_props)}
    the_by_artist = {p.original_name: p for p in the_props}
    meta_by_path = {mp.file_path: mp for mp in meta_props}
    cons_by_artist: dict = {}
    for c in candidates:
        for name in [c.primary_name] + c.variant_names:
            cons_by_artist[name] = c

    return inv, classifications, filename_proposals, the_by_artist, meta_by_path, cons_by_artist, crate_lib


def main() -> None:
    print(f'\n{"="*72}')
    print('  CrateSort File Organizer — Test Run')
    print(f'  Library: {TEST_LIBRARY}')
    print(f'{"="*72}')

    # ═══════════════════════════════════════════════════════════════════════
    # PART 1: Full library preview (no execution)
    # ═══════════════════════════════════════════════════════════════════════
    section('PART 1 — REORGANIZATION PLAN PREVIEW (no execution)')

    print('\nRunning full pipeline...', flush=True)
    inv, classifications, filename_proposals, the_by_artist, meta_by_path, \
        cons_by_artist, crate_lib = build_inputs(TEST_LIBRARY, SERATO_DIR)

    organizer = FileOrganizer(
        library_root=TEST_LIBRARY,
        serato_dir=SERATO_DIR,
    )
    plan = organizer.build_plan(
        inventory=inv,
        classifications=classifications,
        filename_proposals=filename_proposals,
        the_proposals=the_by_artist,
        meta_proposals=meta_by_path,
        consolidation=cons_by_artist,
        crate_library=crate_lib,
    )

    s = plan.summary
    section('PLAN SUMMARY')
    print(f'  Files scanned           : {s.total_scanned}')
    print(f'  Would move              : {s.files_to_move}')
    print(f'  Already in place        : {s.files_staying}')
    print(f'  Would rename            : {s.files_renamed}')
    print(f'  Would fix metadata      : {s.files_with_metadata}')
    print(f'  Crate files to update   : {s.crates_to_update}')
    print(f'  New folders to create   : {s.new_folders}')
    print(f'  Folders empty after     : {s.empty_folders_after}')
    print(f'  Protected skipped       : {s.protected_skipped}')
    print(f'  Destination conflicts   : {s.conflict_count}')

    section(f'ALL FILE MOVES ({s.files_to_move} total)')
    for op in plan.operations:
        src_rel = op.source_path.relative_to(TEST_LIBRARY)
        dest_rel = op.destination_path.relative_to(TEST_LIBRARY)
        print(f'\n  {src_rel}')
        print(f'  → {dest_rel}')
        if op.filename_change:
            print(f'     rename: {op.filename_change[0]} → {op.filename_change[1]}')
        if op.metadata_changes:
            for mc in op.metadata_changes:
                if not mc.needs_review:
                    print(f'     tag: {mc.field}: {mc.current_value!r} → {mc.proposed_value!r}')
        if op.crates_affected:
            print(f'     crates: {", ".join(op.crates_affected[:3])}{"..." if len(op.crates_affected) > 3 else ""}')

    section('FILES STAYING PUT')
    for p in sorted(plan.stays_put):
        print(f'  {p.relative_to(TEST_LIBRARY)}')

    section('PROTECTED FOLDERS — SKIPPED')
    if plan.protected_skipped:
        for path, reason in sorted(plan.protected_skipped):
            print(f'  {path.relative_to(TEST_LIBRARY)}  ({reason})')
    else:
        print('  None.')

    section('CONFLICTS')
    if plan.conflicts:
        for c in plan.conflicts:
            print(f'  Destination: {c.destination_path}')
            for src in c.sources:
                print(f'    source: {src}')
    else:
        print('  None — no destination collisions.')

    section('NEW FOLDERS TO CREATE')
    for folder in sorted(plan.new_folders)[:15]:
        print(f'  {folder.relative_to(TEST_LIBRARY)}')
    if len(plan.new_folders) > 15:
        print(f'  ... +{len(plan.new_folders) - 15} more')

    # ═══════════════════════════════════════════════════════════════════════
    # PART 2: Execute on 5 temp files + verify + rollback
    # ═══════════════════════════════════════════════════════════════════════
    section('PART 2 — EXECUTE ON 5 TEMP FILES + ROLLBACK TEST')

    # Pick 5 specific files from the test library that are in different genres
    test_files = [
        TEST_LIBRARY / 'MP3' / 'Blues' / 'Albert King' / 'Cold Feet.mp3',
        TEST_LIBRARY / 'MP3' / 'Blues' / 'Little Walter' / 'Shake Dancer.mp3',
        TEST_LIBRARY / 'MP3' / 'Hip-Hop : Rap' / 'Big L' / 'Danger Zone.mp3',
        TEST_LIBRARY / 'MP3' / 'Funk : Classic' / 'Isaac Hayes' / 'Joy - Pt. 1.mp3',
        TEST_LIBRARY / 'MP3' / 'Hip-Hop : Rap' / 'Seasonal' / 'Halloween' / 'ACDC' / 'Hells Bells.mp3',
    ]
    test_files = [f for f in test_files if f.exists()]

    if not test_files:
        print('\n  No test files found — skipping execution test.')
        print(f'\n{"="*72}\n')
        return

    tmpdir = Path(tempfile.mkdtemp(prefix='cratesort_test_'))
    print(f'\n  Temp directory: {tmpdir}')
    print(f'  Test files: {len(test_files)}')

    try:
        # Copy test files into temp dir (flat structure — no genre/artist folders)
        for src in test_files:
            dst = tmpdir / src.name
            shutil.copy2(str(src), str(dst))
            print(f'    Copied: {src.name}')

        # Run pipeline on temp dir
        print('\n  Building plan for temp files...')
        tmp_inv, tmp_cls, tmp_fp, tmp_the, tmp_meta, tmp_cons, _ = build_inputs(tmpdir)

        tmp_organizer = FileOrganizer(
            library_root=tmpdir,
            serato_dir=None,
            data_dir=tmpdir / '_CrateSort',
        )
        tmp_plan = tmp_organizer.build_plan(
            inventory=tmp_inv,
            classifications=tmp_cls,
            filename_proposals=tmp_fp,
            the_proposals=tmp_the,
            meta_proposals=tmp_meta,
            consolidation=tmp_cons,
        )

        print(f'  Plan: {tmp_plan.summary.files_to_move} files would move, '
              f'{tmp_plan.summary.files_staying} staying')
        for op in tmp_plan.operations:
            src_name = op.source_path.relative_to(tmpdir)
            dst_name = op.destination_path.relative_to(tmpdir)
            print(f'    {src_name}  →  {dst_name}')

        # --- Execute ---
        print('\n  Executing plan...')
        result = tmp_organizer.execute(tmp_plan)

        print(f'  Result: {len(result.completed)} completed, '
              f'{len(result.failed)} failed, {len(result.skipped)} skipped')
        print(f'  Duration: {result.duration_seconds:.2f}s')
        print(f'  Rollback log: {result.rollback_log_path.name if result.rollback_log_path else "none"}')

        # Verify files are at new locations
        # Note: if metadata was written after the move, the file hash will differ
        # from sha256_source (expected). We verify the copy was clean via sha256_copy,
        # and just check existence/src-gone for files with metadata changes.
        print('\n  Verifying moved files...')
        all_verified = True
        for op in result.completed:
            src_gone = not op.source_path.exists()
            dst_exists = op.destination_path.exists()
            # sha256_copy is the hash right after copy (before metadata write)
            copy_ok = (op.sha256_source == op.sha256_copy) if op.sha256_copy else True
            ok = src_gone and dst_exists and copy_ok
            status = '✓' if ok else '✗'
            if not ok:
                all_verified = False
            meta_note = ' [metadata written]' if op.metadata_changes else ''
            print(f'  {status} {op.destination_path.relative_to(tmpdir)}{meta_note}')
            print(f'      src gone={src_gone}  dst_exists={dst_exists}  copy_verified={copy_ok}')

        # --- Rollback ---
        if result.rollback_log_path:
            print('\n  Rolling back...')
            rb_result = tmp_organizer.rollback(result.rollback_log_path)
            print(f'  Rollback: {rb_result["restored"]} restored, '
                  f'{rb_result["failed"]} failed, '
                  f'{rb_result["skipped"]} skipped')
            if rb_result['errors']:
                for e in rb_result['errors']:
                    print(f'    ERROR: {e}')

            # Verify original files are back
            print('\n  Verifying rollback...')
            all_restored = True
            for src in test_files:
                restored = (tmpdir / src.name).exists()
                status = '✓' if restored else '✗'
                if not restored:
                    all_restored = False
                print(f'  {status} {src.name}')

            print(f'\n  Overall:  '
                  f'execute={"PASS" if all_verified else "FAIL"}  '
                  f'rollback={"PASS" if all_restored else "FAIL"}')

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f'\n  Cleaned up temp directory: {tmpdir.name}')

    print(f'\n{"="*72}\n')


if __name__ == '__main__':
    main()
