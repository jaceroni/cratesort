#!/usr/bin/env python3
"""
Exercise ParallelTagReader end to end:

  1. Happy path — read a real folder of audio files across worker processes.
  2. Watchdog  — inject a deliberately hanging read and confirm the pool kills
                 the worker, marks that one file unreadable, and finishes the
                 rest instead of hanging.

Usage:
    python cratesort/tests/run_parallel_reader.py "/some/folder/with/audio"
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.scanner import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from cratesort.src.core.parallel_tag_reader import ParallelTagReader

MEDIA = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def collect(root: Path, limit: int = 40) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in MEDIA and p.is_file():
            out.append((str(p), p.suffix.lower()))
        if len(out) >= limit:
            break
    return out


def happy_path(tasks: list[tuple[str, str]]) -> None:
    print(f"\n--- happy path: {len(tasks)} files, 3 workers ---")
    results: dict[str, dict] = {}
    t0 = time.time()
    ParallelTagReader(workers=3, per_file_timeout=15).read(
        tasks,
        on_result=lambda p, e, f: results.__setitem__(p, f),
        on_progress=lambda d, t, c: None,
    )
    dt = time.time() - t0
    ok = sum(1 for f in results.values() if not f.get("read_error"))
    bad = len(results) - ok
    print(f"  {len(results)}/{len(tasks)} returned in {dt:.2f}s  ({ok} ok, {bad} errored)")
    assert len(results) == len(tasks), "not every file came back"
    sample = next(iter(results.values()))
    print(f"  sample fields: title={sample.get('title')!r} artist={sample.get('artist')!r} "
          f"dur={sample.get('duration')!r} size={sample.get('_size')!r}")


def watchdog_path(tasks: list[tuple[str, str]]) -> None:
    """Inject a real hanging read: a named pipe (FIFO) with no writer. The
    worker's os.stat() succeeds, then mutagen's open() blocks forever — the
    same shape as a wedged drive read. The parent must kill the worker, mark
    that file unreadable, and finish everything else.

    (A FIFO is used rather than monkeypatching read_one_file because 'spawn'
    workers re-import the module fresh and never see the parent's patch.)"""
    print("\n--- watchdog: one file hangs (FIFO, no writer), timeout=4s ---")
    tmp = Path(tempfile.mkdtemp())
    fifo = tmp / "wedged.mp3"
    os.mkfifo(fifo)

    mid = len(tasks) // 2
    poisoned = tasks[:mid] + [(str(fifo), ".mp3")] + tasks[mid:]

    try:
        results: dict[str, dict] = {}
        t0 = time.time()
        ParallelTagReader(workers=3, per_file_timeout=4).read(
            poisoned,
            on_result=lambda p, e, f: results.__setitem__(p, f),
            on_progress=lambda d, t, c: None,
        )
        dt = time.time() - t0
    finally:
        fifo.unlink(missing_ok=True)
        tmp.rmdir()

    print(f"  finished in {dt:.1f}s (would be forever without the watchdog)")
    assert len(results) == len(poisoned), f"expected {len(poisoned)} results, got {len(results)}"
    assert results[str(fifo)].get("read_error"), "hanging file should be marked unreadable"
    print(f"  hanging file -> {results[str(fifo)]['read_error']!r}")
    others_ok = sum(
        1 for p, f in results.items() if p != str(fifo) and not f.get("read_error")
    )
    print(f"  {others_ok}/{len(poisoned) - 1} other files read fine despite the stall")
    assert dt < 60, "took far too long — watchdog not working"


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    root = Path(sys.argv[1]).expanduser()
    tasks = collect(root)
    if len(tasks) < 4:
        print(f"need at least 4 media files under {root}, found {len(tasks)}")
        sys.exit(1)
    happy_path(tasks)
    watchdog_path(tasks)
    print("\nAll checks passed.\n")


if __name__ == "__main__":
    main()
