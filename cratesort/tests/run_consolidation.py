#!/usr/bin/env python3
"""
Consolidation test runner: Artist Consolidator + Duplicate Detector.
Usage:  python tests/run_consolidation.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.scanner import LibraryScanner
from cratesort.src.core.classifier import GenreClassifier
from cratesort.src.core.artist_consolidator import ArtistConsolidator
from cratesort.src.core.duplicate_detector import DuplicateDetector

TEST_LIBRARY = Path("/Users/jacebrown/Desktop/cratesort-test-library")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

SEP = "─" * 72


def fmt_mb(b: int) -> str:
    return f"{b / 1_048_576:.1f} MB"


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def main() -> None:
    print(f"\n{'='*72}")
    print("  CrateSort Consolidation — Test Run")
    print(f"  Library: {TEST_LIBRARY}")
    print(f"{'='*72}\n")

    # ── Scan + Classify ───────────────────────────────────────────────────
    print("Scanning...", flush=True)
    inventory, _ = LibraryScanner(TEST_LIBRARY).scan()
    print(f"  {len(inventory)} files\n")

    print("Classifying...", flush=True)
    results = GenreClassifier().classify_all(inventory)
    print(f"  done\n")

    # ── Artist Consolidation ──────────────────────────────────────────────
    print("Running artist consolidator...", flush=True)
    candidates = ArtistConsolidator().analyze(inventory)

    section(f"CONSOLIDATION CANDIDATES  ({len(candidates)} groups)")

    if not candidates:
        print("  None found.")
    else:
        for i, c in enumerate(candidates, 1):
            conf_sym = {'HIGH': '●', 'MEDIUM': '◐', 'LOW': '○'}.get(c.confidence, '?')
            print(f"\n  [{i}] {conf_sym} {c.confidence}  —  method: {c.match_method}")
            print(f"      Primary   : {c.primary_name}  ({c.track_counts.get(c.primary_name, 0)} tracks)")
            for v in c.variant_names:
                print(f"      Variant   : {v}  ({c.track_counts.get(v, 0)} tracks)")
            if c.genres:
                print(f"      Genres    : {', '.join(sorted(c.genres))}")

            print(f"      Sample tracks:")
            for name, titles in c.sample_tracks.items():
                for title in titles:
                    print(f"        {name} — {title}")

            mp = c.merge_proposal
            subfolder_note = "with project subfolders" if mp.use_subfolders else "merge into one folder"
            print(f"      Proposal  : keep '{mp.winning_name}' ({subfolder_note})")

            if len(set(c.genres)) > 1:
                print(f"      ⚠ GENRE MISMATCH — variants span multiple genres. "
                      f"Verify this isn't a false positive.")

    # ── Duplicate Detection ───────────────────────────────────────────────
    print("\nRunning duplicate detector...", flush=True)
    detector = DuplicateDetector()
    dup_groups, dup_summary = detector.detect(inventory)

    section(f"DUPLICATE GROUPS  ({dup_summary.total_groups} found)")

    if not dup_groups:
        print("  No duplicates detected in this library.")
    else:
        for i, grp in enumerate(dup_groups, 1):
            print(f"\n  [{i}] \"{grp.canonical_title}\" — {grp.canonical_artist}")
            print(f"       Copies: {len(grp.copies)}  |  "
                  f"Space savings: {fmt_mb(grp.space_savings)}  |  "
                  f"Conflicts: {len(grp.metadata_conflicts)}")

            for j, copy in enumerate(grp.copies):
                winner_mark = " ← KEEP" if copy is grp.recommended_winner else ""
                print(f"\n       Copy {j+1}{winner_mark}")
                print(f"         File    : {copy.file_path.name}")
                print(f"         Folder  : {copy.folder_context}")
                print(f"         Format  : {copy.format}  |  "
                      f"{copy.bitrate or '?'} kbps  |  "
                      f"{copy.file_size / 1_048_576:.1f} MB")
                print(f"         Genre   : {copy.genre_tag or '—'}")
                print(f"         Year    : {copy.year_tag or '—'}")
                print(f"         BPM     : {copy.bpm or '—'}")
                print(f"         Comment : {copy.comment or '—'}")
                print(f"         Stems   : {'yes' if copy.has_stems else 'no'}")

            if grp.metadata_conflicts:
                print(f"\n       Metadata conflicts:")
                for conflict in grp.metadata_conflicts:
                    print(f"         {conflict.field}:")
                    for path_str, val in conflict.values.items():
                        print(f"           {Path(path_str).name}: {val or '(none)'}")

    # ── Summary ───────────────────────────────────────────────────────────
    section("SUMMARY")
    print(f"  Files scanned              : {len(inventory)}")
    print(f"  Consolidation candidates   : {len(candidates)}")
    conf_counts = {}
    for c in candidates:
        conf_counts[c.confidence] = conf_counts.get(c.confidence, 0) + 1
    for level in ('HIGH', 'MEDIUM', 'LOW'):
        if level in conf_counts:
            print(f"    {level:<8} : {conf_counts[level]}")
    print()
    print(f"  Duplicate groups           : {dup_summary.total_groups}")
    print(f"  Duplicate files            : {dup_summary.total_duplicate_files}")
    print(f"  Space recoverable          : {fmt_mb(dup_summary.space_recoverable)}")
    print(f"  Groups with conflicts      : {dup_summary.groups_with_conflicts}")
    print(f"  Groups auto-approvable     : {dup_summary.groups_auto_approvable}")
    print(f"\n{'='*72}\n")


if __name__ == "__main__":
    main()
