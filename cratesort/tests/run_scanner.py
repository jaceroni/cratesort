#!/usr/bin/env python3
"""
Run the LibraryScanner against the test library and print results.
Usage:  python tests/run_scanner.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running from the cratesort/ project root without installing
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.scanner import LibraryScanner

TEST_LIBRARY = Path("/Users/jacebrown/Desktop/cratesort-test-library")

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)


def fmt_seconds(s: float | None) -> str:
    if s is None:
        return "—"
    m, sec = divmod(int(s), 60)
    return f"{m}:{sec:02d}"


def fmt_bytes(b: int) -> str:
    return f"{b / 1_048_576:.1f} MB" if b >= 1_048_576 else f"{b / 1024:.0f} KB"


def main() -> None:
    print(f"\n{'='*70}")
    print(f"  CrateSort Scanner — Test Run")
    print(f"  Library: {TEST_LIBRARY}")
    print(f"{'='*70}\n")

    scanner = LibraryScanner(TEST_LIBRARY)
    inventory, summary = scanner.scan()

    # ------------------------------------------------------------------ Summary
    print(f"\n{'─'*70}")
    print("  SCAN SUMMARY")
    print(f"{'─'*70}")
    print(f"  Total files cataloged : {summary.total_files}")
    print()
    print("  By format:")
    for ext, count in sorted(summary.by_format.items()):
        print(f"    {ext:<10} {count}")
    print()
    print(f"  Metadata quality:")
    print(f"    Complete (title+artist+genre+year) : {summary.complete_metadata}")
    print(f"    Partial                            : {summary.partial_metadata}")
    print(f"    None                               : {summary.no_metadata}")
    print()
    print(f"  Stems attachments  : {summary.with_stems}")
    print(f"  Orphan stems files : {len(summary.orphan_stems)}")
    if summary.orphan_stems:
        for p in summary.orphan_stems:
            print(f"    • {p.name}")
    print()
    print(f"  Unique artists : {len(summary.unique_artists)}")
    for a in sorted(summary.unique_artists):
        print(f"    {a}")
    print()
    print(f"  Unique genres (as tagged) : {len(summary.unique_genres)}")
    for g in sorted(summary.unique_genres):
        print(f"    {g}")

    # ------------------------------------------------------------------ Sample records
    print(f"\n{'─'*70}")
    print("  SAMPLE RECORDS  (first 10 with complete metadata)")
    print(f"{'─'*70}")
    shown = 0
    for rec in inventory:
        if rec.has_complete_metadata and not rec.read_error:
            print(f"\n  File     : {rec.filename}")
            print(f"  Path     : {rec.path}")
            print(f"  Format   : {rec.codec}  |  {fmt_bytes(rec.file_size)}")
            print(f"  Duration : {fmt_seconds(rec.duration)}  |  {rec.bitrate} kbps  |  {rec.sample_rate} Hz")
            print(f"  Title    : {rec.title}")
            print(f"  Artist   : {rec.artist}")
            print(f"  Album    : {rec.album}")
            print(f"  Genre    : {rec.genre}")
            print(f"  Year     : {rec.year}")
            print(f"  BPM      : {rec.bpm or '—'}")
            print(f"  Comment  : {rec.comment or '—'}")
            if rec.stems_path:
                print(f"  Stems    : {rec.stems_path.name}")
            shown += 1
            if shown >= 10:
                break

    # ------------------------------------------------------------------ Partial / no metadata
    print(f"\n{'─'*70}")
    print("  FILES WITH MISSING OR PARTIAL METADATA")
    print(f"{'─'*70}")
    for rec in inventory:
        if rec.read_error or rec.has_no_metadata or rec.has_partial_metadata:
            status = "ERROR" if rec.read_error else ("NONE" if rec.has_no_metadata else "PARTIAL")
            missing = []
            if not rec.title:
                missing.append("title")
            if not rec.artist:
                missing.append("artist")
            if not rec.genre:
                missing.append("genre")
            if not rec.year:
                missing.append("year")
            detail = rec.read_error if rec.read_error else f"missing: {', '.join(missing)}"
            print(f"  [{status:<7}]  {rec.filename}")
            print(f"             {detail}")

    # ------------------------------------------------------------------ Read errors
    if summary.read_errors:
        print(f"\n{'─'*70}")
        print("  READ ERRORS")
        print(f"{'─'*70}")
        for path, err in summary.read_errors:
            print(f"  {path.name}")
            print(f"    {err}")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
