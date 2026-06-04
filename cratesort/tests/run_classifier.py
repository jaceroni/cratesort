#!/usr/bin/env python3
"""
Run the GenreClassifier against the test library and print results.
Usage:  python tests/run_classifier.py
"""
from __future__ import annotations

import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.scanner import LibraryScanner
from cratesort.src.core.classifier import GenreClassifier, Confidence

TEST_LIBRARY = Path("/Users/jacebrown/Desktop/cratesort-test-library")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")

SEP = "─" * 72


def main() -> None:
    print(f"\n{'='*72}")
    print("  CrateSort Classifier — Test Run")
    print(f"  Library: {TEST_LIBRARY}")
    print(f"{'='*72}\n")

    print("Scanning...", flush=True)
    inventory, _ = LibraryScanner(TEST_LIBRARY).scan()

    print(f"Classifying {len(inventory)} files...\n", flush=True)
    classifier = GenreClassifier()
    results = classifier.classify_all(inventory)

    # ── Build summary buckets ─────────────────────────────────────────────
    by_genre: dict[str, list] = defaultdict(list)
    by_confidence: dict[str, int] = defaultdict(int)
    unclassified = []
    needs_review = []

    for rec, result in results:
        by_confidence[result.confidence.value] += 1
        if result.genre is None:
            unclassified.append((rec, result))
        else:
            by_genre[result.genre].append((rec, result))
        if result.needs_review:
            needs_review.append((rec, result))

    # ── Confidence summary ────────────────────────────────────────────────
    print(SEP)
    print("  CLASSIFICATION SUMMARY")
    print(SEP)
    total = len(results)
    classified = total - len(unclassified)
    print(f"  Total files      : {total}")
    print(f"  Classified       : {classified}  ({100*classified//total}%)")
    print(f"  Unclassified     : {len(unclassified)}")
    print(f"  Flagged review   : {len(needs_review)}")
    print()
    print("  Confidence breakdown:")
    for level in ("HIGH", "MEDIUM", "LOW", "NONE"):
        count = by_confidence.get(level, 0)
        bar = "█" * (count // 1)
        print(f"    {level:<8}  {count:>3}  {bar}")

    # ── Results by genre ──────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  CLASSIFIED FILES BY GENRE")
    print(SEP)
    for genre in sorted(by_genre):
        entries = by_genre[genre]
        print(f"\n  ── {genre} ({len(entries)}) {'─'*(50-len(genre))}")
        for rec, result in sorted(entries, key=lambda x: x[0].filename):
            conf_char = {"HIGH": "✓", "MEDIUM": "~", "LOW": "?"}.get(
                result.confidence.value, "?"
            )
            orig = f"  [{result.original_genre_tag}]" if result.original_genre_tag != genre else ""
            review = " ← REVIEW" if result.needs_review else ""
            print(f"    {conf_char} {rec.filename}{orig}{review}")
            if result.confidence != Confidence.HIGH:
                print(f"      reason: {result.reason}")

    # ── Unclassified ──────────────────────────────────────────────────────
    if unclassified:
        print(f"\n{SEP}")
        print("  UNCLASSIFIED — NEEDS MANUAL REVIEW")
        print(SEP)
        for rec, result in unclassified:
            print(f"  {rec.filename}")
            print(f"    genre tag : {result.original_genre_tag or '(none)'}")
            print(f"    artist    : {rec.artist or '—'}")
            print(f"    comment   : {rec.comment or '—'}")
            print(f"    reason    : {result.reason}")

    # ── Reclassified (original tag differed from result) ──────────────────
    reclassified = [
        (rec, r) for rec, r in results
        if r.genre and r.original_genre_tag and r.original_genre_tag != r.genre
        and r.original_genre_tag not in (None, "")
    ]
    if reclassified:
        print(f"\n{SEP}")
        print("  RECLASSIFIED  (original tag → assigned genre)")
        print(SEP)
        for rec, result in sorted(reclassified, key=lambda x: x[0].filename):
            print(
                f"  {rec.filename}\n"
                f"    {result.original_genre_tag}  →  {result.genre}"
                f"  [{result.confidence.value}]  {result.reason}"
            )

    print(f"\n{'='*72}\n")


if __name__ == "__main__":
    main()
