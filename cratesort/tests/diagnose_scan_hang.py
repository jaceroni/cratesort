#!/usr/bin/env python3
"""
Diagnose a stuck library scan.

Walks a directory tree the same way LibraryScanner does (same skip-dirs, same
sort order, same audio/video extensions) and reads tags with mutagen one file
at a time — but prints the full path of every file *before* it touches it and
times each tag read.  A per-file SIGALRM watchdog aborts any read that takes
longer than --timeout seconds so the script itself never hangs: it reports the
offending file and keeps going.

Usage:
    python cratesort/tests/diagnose_scan_hang.py "/Volumes/YOUR DRIVE"
    python cratesort/tests/diagnose_scan_hang.py "/Volumes/YOUR DRIVE" --timeout 20 --slow 1.5

Nothing is written or modified.  Ctrl-C to stop; it prints where it was.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

# Run from the repo without installing.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import mutagen  # noqa: E402

from cratesort.src.core.scanner import (  # noqa: E402
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    SKIP_DIRS,
    STEMS_EXTENSION,
)

# macOS: set on a file-provider placeholder whose contents are not on disk yet.
# Reading such a file can block for a long time (or forever, if offline) while
# the sync client tries to materialise it.
SF_DATALESS = 0x40000000

MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


class _ReadTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise _ReadTimeout()


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


def _is_dataless(st) -> bool:
    return bool(getattr(st, "st_flags", 0) & SF_DATALESS)


def iter_media_files(root: Path):
    """Yield media file paths in the same order LibraryScanner would hit them."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith("._")
        )
        for fname in sorted(filenames):
            lower = fname.lower()
            if lower.endswith(STEMS_EXTENSION) or fname.startswith("._"):
                continue
            if Path(fname).suffix.lower() in MEDIA_EXTENSIONS:
                yield Path(dirpath) / fname


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, help="Library root to scan (e.g. an external drive)")
    ap.add_argument("--timeout", type=float, default=15.0,
                    help="Abort any single tag read that exceeds this many seconds (default 15)")
    ap.add_argument("--slow", type=float, default=1.0,
                    help="Flag any read slower than this many seconds (default 1.0)")
    ap.add_argument("--start-at", type=int, default=0,
                    help="Skip the first N media files (resume a previous run)")
    args = ap.parse_args()

    root = args.root.expanduser()
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGALRM, _alarm)

    print(f"\n{'='*78}")
    print(f"  Scan-hang diagnostic")
    print(f"  Root      : {root}")
    print(f"  Timeout   : {args.timeout}s per file    Slow flag: {args.slow}s")
    print(f"{'='*78}\n", flush=True)

    total = 0
    slow: list[tuple[Path, float]] = []
    timed_out: list[Path] = []
    errors: list[tuple[Path, str]] = []
    big: list[tuple[Path, int]] = []
    dataless: list[Path] = []
    t_start = time.time()

    try:
        for idx, path in enumerate(iter_media_files(root)):
            if idx < args.start_at:
                continue
            total = idx + 1

            # stat first — this alone can block on a dead mount.
            signal.setitimer(signal.ITIMER_REAL, args.timeout)
            try:
                st = os.stat(path)
            except _ReadTimeout:
                signal.setitimer(signal.ITIMER_REAL, 0)
                print(f"[{idx:>6}] {path}\n         !! os.stat() TIMED OUT after {args.timeout}s "
                      f"— dead mount or unresponsive placeholder", flush=True)
                timed_out.append(path)
                continue
            except OSError as exc:
                signal.setitimer(signal.ITIMER_REAL, 0)
                print(f"[{idx:>6}] {path}\n         !! os.stat() failed: {exc}", flush=True)
                errors.append((path, f"stat: {exc}"))
                continue
            signal.setitimer(signal.ITIMER_REAL, 0)

            size = st.st_size
            flags = []
            if _is_dataless(st):
                flags.append("DATALESS/not-downloaded")
                dataless.append(path)
            if size >= 250 * 1024 * 1024:
                flags.append("HUGE")
                big.append((path, size))
            flag_str = ("   <-- " + ", ".join(flags)) if flags else ""

            print(f"[{idx:>6}] {path}  ({_fmt_size(size)}){flag_str}", flush=True)

            # the tag read — the thing that hangs the app
            signal.setitimer(signal.ITIMER_REAL, args.timeout)
            t0 = time.time()
            try:
                mutagen.File(path, easy=False)
            except _ReadTimeout:
                signal.setitimer(signal.ITIMER_REAL, 0)
                dt = time.time() - t0
                print(f"         !! mutagen TIMED OUT after {dt:.1f}s  <<<<< THIS IS THE STALL FILE",
                      flush=True)
                timed_out.append(path)
                continue
            except Exception as exc:
                signal.setitimer(signal.ITIMER_REAL, 0)
                dt = time.time() - t0
                print(f"         !! mutagen error ({dt:.2f}s): {exc!r}", flush=True)
                errors.append((path, repr(exc)))
                continue
            signal.setitimer(signal.ITIMER_REAL, 0)

            dt = time.time() - t0
            if dt >= args.slow:
                print(f"         .. slow read: {dt:.2f}s", flush=True)
                slow.append((path, dt))

    except KeyboardInterrupt:
        signal.setitimer(signal.ITIMER_REAL, 0)
        print(f"\n\ninterrupted at file #{total}", flush=True)

    elapsed = time.time() - t_start
    print(f"\n{'='*78}")
    print(f"  Done — {total} media files, {elapsed:.1f}s")
    print(f"{'='*78}")
    print(f"  Timed out (>{args.timeout}s) : {len(timed_out)}")
    for p in timed_out:
        print(f"      {p}")
    print(f"  Slow (>{args.slow}s)        : {len(slow)}")
    for p, dt in sorted(slow, key=lambda x: -x[1])[:20]:
        print(f"      {dt:6.2f}s  {p}")
    print(f"  Errors                  : {len(errors)}")
    for p, e in errors[:20]:
        print(f"      {p}\n         {e}")
    print(f"  Huge (>=250 MB)         : {len(big)}")
    for p, n in big:
        print(f"      {_fmt_size(n):>10}  {p}")
    print(f"  Dataless placeholders   : {len(dataless)}")
    for p in dataless[:20]:
        print(f"      {p}")
    print()


if __name__ == "__main__":
    main()
