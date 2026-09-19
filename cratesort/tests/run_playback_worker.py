#!/usr/bin/env python3
"""
Exercise PlaybackWorker end to end (out-of-process audio playback):

  1. Happy path   — play, seek, pause, resume, stop, shutdown against a real
                     short synthetic audio file.
  2. Watchdog     — inject a deliberately hanging "file" (a named pipe with
                     no writer, same technique as run_parallel_reader.py's
                     watchdog test) and confirm the parent detects the wedge,
                     kills the worker, and a subsequent play() on the
                     freshly-respawned worker plays a real file successfully.

This is a lower-confidence stand-in for the actual reported bug (a seek
wedging an *already-open* player mid-stream on a genuinely flaky drive) — that
shape isn't reproducible on demand without real failing hardware. The
authoritative check for that scenario is manual, on the real flaky external
drive (see the project plan/notes) — this script only proves the mechanism
(detection + kill + respawn + recovery) works at all.

Usage:
    python cratesort/tests/run_playback_worker.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.core.playback_worker import PlaybackWorker


def _find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    exe = shutil.which("ffmpeg")
    if not exe:
        print("ffmpeg not found (checked imageio_ffmpeg and PATH) — can't generate test audio")
        sys.exit(1)
    return exe


def _make_test_audio(path: Path, duration: float = 6.0) -> None:
    ffmpeg = _find_ffmpeg()
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
         "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
        check=True, capture_output=True,
    )


class _EventLog:
    def __init__(self) -> None:
        self.events: list[tuple[float, tuple]] = []

    def __call__(self, evt: tuple) -> None:
        self.events.append((time.monotonic(), evt))

    def last(self, kind: str):
        for t, e in reversed(self.events):
            if e[0] == kind:
                return t, e
        return None

    def count(self, kind: str) -> int:
        return sum(1 for _, e in self.events if e[0] == kind)


def _pump(worker: PlaybackWorker, seconds: float, interval: float = 0.05) -> None:
    """Stand-in for the GUI-thread QTimer that drives poll_events() in the
    real app — this script is plain Python (PlaybackWorker itself has no Qt
    dependency), so events are drained by hand on a sleep loop instead."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        worker.poll_events()
        time.sleep(interval)


def happy_path(audio_path: Path) -> None:
    print("\n--- happy path ---")
    log = _EventLog()
    worker = PlaybackWorker(log)
    worker.ensure_started()

    worker.play(str(audio_path))
    _pump(worker, 2.0)
    assert log.count("duration") > 0, "no duration event arrived"
    assert log.count("position") > 0, "no position event arrived"
    print(f"  duration event seen, {log.count('position')} position ticks in 2s")

    worker.seek(3000)
    _pump(worker, 1.0)
    last_pos = log.last("position")
    assert last_pos and last_pos[1][1] >= 2500, f"seek didn't take effect: {last_pos}"
    print(f"  after seek(3000ms): last position={last_pos[1][1]}ms")

    worker.pause()
    _pump(worker, 0.3)
    before = log.count("position")
    time.sleep(0.5)
    worker.poll_events()
    after = log.count("position")
    assert after - before <= 1, "position kept advancing after pause"
    print("  pause holds position steady")

    worker.play(str(audio_path), position_ms=last_pos[1][1])
    _pump(worker, 1.0)
    resumed = log.last("state")
    print(f"  resumed, last state event: {resumed[1] if resumed else None}")

    worker.stop()
    _pump(worker, 0.3)

    worker.shutdown()
    time.sleep(0.3)
    assert not worker.is_alive(), "worker handle should be cleared after shutdown"
    print("  shutdown OK")


def watchdog_open_hang(audio_path: Path) -> None:
    print("\n--- watchdog: open() hangs (FIFO, no writer) ---")
    tmp = Path(tempfile.mkdtemp())
    fifo = tmp / "wedged.mp3"
    os.mkfifo(fifo)

    try:
        log = _EventLog()
        worker = PlaybackWorker(log, liveness_timeout=3.0, stall_timeout=3.0)
        worker.ensure_started()

        t0 = time.monotonic()
        worker.play(str(fifo))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and log.count("wedged") == 0:
            worker.poll_events()
            time.sleep(0.1)
        dt = time.monotonic() - t0

        print(f"  wedge detected in {dt:.1f}s: {log.count('wedged') > 0}")
        assert log.count("wedged") > 0, "parent never detected the wedged worker"
        assert dt < 15, "took far too long — watchdog not working"

        # A subsequent real play() must succeed on the freshly-respawned worker
        # — this is the exact second-freeze scenario from the real bug report
        # (clicking a different track after one wedged also hung, because the
        # SAME player object was reused; here it must be a fresh process).
        before = log.count("duration")
        worker.play(str(audio_path))
        _pump(worker, 2.0)
        assert log.count("duration") > before, "recovery worker never played the real file"
        print("  recovered worker played a real file afterward")

        worker.shutdown()
    finally:
        fifo.unlink(missing_ok=True)
        tmp.rmdir()


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    audio_path = tmp / "test.mp3"
    print(f"generating test audio at {audio_path} ...")
    _make_test_audio(audio_path)
    try:
        happy_path(audio_path)
        watchdog_open_hang(audio_path)
        print("\nAll checks passed.\n")
    finally:
        audio_path.unlink(missing_ok=True)
        tmp.rmdir()


if __name__ == "__main__":
    main()
