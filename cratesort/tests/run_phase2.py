#!/usr/bin/env python3
"""
Phase 2 test runner: Filename Cleaner, The Handler, Metadata Fixer.
Usage:  python tests/run_phase2.py
"""
from __future__ import annotations

import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.scanner import LibraryScanner
from cratesort.src.core.classifier import GenreClassifier
from cratesort.src.core.filename_cleaner import FilenameCleaner
from cratesort.src.core.metadata_fixer import MetadataFixer
from cratesort.src.utils.the_handler import TheHandler

TEST_LIBRARY = Path("/Users/jacebrown/Desktop/cratesort-test-library")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

SEP  = "─" * 72
SEP2 = "━" * 72


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def main() -> None:
    print(f"\n{'='*72}")
    print("  CrateSort Phase 2 — Proposal Engine Test")
    print(f"  Library: {TEST_LIBRARY}")
    print(f"{'='*72}\n")

    # ── 1. Scan ───────────────────────────────────────────────────────────
    print("Scanning...", flush=True)
    inventory, _ = LibraryScanner(TEST_LIBRARY).scan()
    print(f"  {len(inventory)} files\n")

    # ── 2. Classify ───────────────────────────────────────────────────────
    print("Classifying...", flush=True)
    classifier = GenreClassifier()
    classification_results = classifier.classify_all(inventory)
    print(f"  done\n")

    # ── 3. Filename cleaner ───────────────────────────────────────────────
    print("Running filename cleaner...", flush=True)
    cleaner = FilenameCleaner()
    filename_proposals = cleaner.clean_all(inventory)

    changed = [p for p in filename_proposals if p.has_changes]
    review  = [p for p in changed if p.needs_review]

    section(f"FILENAME CHANGES  ({len(changed)} files would be renamed)")
    for p in changed:
        flag = " ← REVIEW" if p.needs_review else ""
        print(f"\n  {p.original_filename}")
        print(f"  → {p.proposed_filename}{flag}")
        for c in p.changes_made:
            print(f"    • {c}")

    # ── 4. "The" handler ──────────────────────────────────────────────────
    print("\nRunning The handler...", flush=True)
    the_handler = TheHandler(handle_a_an=False)
    all_artists = {r.artist for r in inventory if r.artist}
    the_proposals = the_handler.analyze_all(all_artists)

    section(f"'THE' ARTIST HANDLING  ({len(the_proposals)} artists affected)")
    if the_proposals:
        print(f"  {'Original':<40}  {'Sort / Folder Form'}")
        print(f"  {'─'*38}  {'─'*30}")
        for p in the_proposals:
            print(f"  {p.original_name:<40}  {p.sort_name}")
    else:
        print("  (none)")

    # ── 5. Metadata fixer ─────────────────────────────────────────────────
    print("\nRunning metadata fixer...", flush=True)
    fixer = MetadataFixer()
    meta_proposals = fixer.analyze_all(classification_results)

    # Group changes by field type
    by_field: dict[str, list] = defaultdict(list)
    for prop in meta_proposals:
        for change in prop.changes:
            by_field[change.field].append((prop, change))

    total_changes = sum(len(p.changes) for p in meta_proposals)
    total_review  = sum(p.review_count for p in meta_proposals)

    section(f"METADATA FIXES  ({total_changes} changes across {len(meta_proposals)} files)")

    # Genre changes
    genre_changes = by_field.get('genre', [])
    if genre_changes:
        print(f"\n  Genre corrections ({len(genre_changes)}):")
        print(f"  {'File':<55}  {'From':<20}  →  {'To'}")
        print(f"  {'─'*53}  {'─'*18}  {'─'*18}")
        for prop, change in sorted(genre_changes, key=lambda x: x[1].current_value or ''):
            from_val = change.current_value or '(none)'
            flag = " ← REVIEW" if change.needs_review else ""
            print(f"  {Path(prop.file_path).name:<55}  {from_val:<20}  →  {change.proposed_value}{flag}")

    # Sort-artist changes
    sort_changes = by_field.get('sort_artist', [])
    if sort_changes:
        print(f"\n  Sort-artist (TSOP) writes ({len(sort_changes)}):")
        print(f"  {'File':<55}  Sort Artist")
        print(f"  {'─'*53}  {'─'*30}")
        for prop, change in sort_changes:
            print(f"  {Path(prop.file_path).name:<55}  {change.proposed_value}")

    # Year flags
    year_flags = by_field.get('year', [])
    if year_flags:
        print(f"\n  Year flags — needs review ({len(year_flags)}):")
        for prop, change in year_flags:
            print(f"\n  {Path(prop.file_path).name}")
            print(f"    year    : {change.current_value}")
            print(f"    reason  : {change.reason}")

    # ── 6. Summary ────────────────────────────────────────────────────────
    section("SUMMARY")
    print(f"  Files scanned            : {len(inventory)}")
    print(f"  Filenames to rename      : {len(changed)}  ({len(review)} flagged for review)")
    print(f"  Artists with 'The' sort  : {len(the_proposals)}")
    print(f"  Metadata changes total   : {total_changes}")
    print(f"    Genre corrections      : {len(genre_changes)}")
    print(f"    Sort-artist writes     : {len(sort_changes)}")
    print(f"    Year flags (review)    : {len(year_flags)}")
    print(f"  Total items needing review : {len(review) + total_review}")
    print(f"\n{'='*72}\n")


if __name__ == "__main__":
    main()
