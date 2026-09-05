"""
PlaybackWorker — runs audio decode/output in a separate, killable OS process.

Why processes: exactly the same reasoning as ParallelTagReader (see that
module's docstring) — a QMediaPlayer seek/decode can wedge in an
uninterruptible kernel wait against a stalling drive, and nothing inside the
calling process can interrupt that. Only SIGKILL on a *separate* process
recovers. This was fixed for library scanning; this module extends the same
principle to audio playback, whose lack of it was confirmed as the cause of a
real freeze (scrubbing a track's position slider mid-playback wedged the
QMediaPlayer object itself, and a subsequent click on a different track hung
too, since the same wedged player object was still being reused).

Shape differs from ParallelTagReader in one deliberate way: that class pools
N *short-lived, one-shot-per-file* workers for a bounded batch job (a scan).
This class owns exactly *one long-lived, stateful, bidirectional* worker for
the life of an app session — spawned lazily on first play() and kept alive
across track changes (not respawned per track, which would add a spawn-
latency hit to every single click). It's only killed+respawned on an explicit
shutdown() or a detected wedge (see poll_events()). Playback also needs a
liveness signal even while completely idle (paused, nothing loaded) — a
one-shot worker never needed this since it's always either answering a
request or already dead — which is why playback_worker_proc.py's child sends
a heartbeat every 2s regardless of what's playing.

Threading invariant: every public method here must only ever be called from
the GUI thread. poll_events() is meant to be driven by a GUI-thread QTimer
(~100ms) — draining the pipe with non-blocking poll(0)/recv() is safe there
since it only ever touches an OS pipe between two live processes, never disk
(unlike the actual playback work happening inside the worker, which is
exactly the thing this class exists to isolate). A wedge is *detected* here
with cheap timestamp comparisons, but its *teardown* (proc.kill() +
proc.join()) is dispatched to a daemon thread so a stall being detected can
never itself block the GUI thread — the one moment freeze-safety matters most.
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

OnEvent = Callable[[tuple], None]

# How long with zero messages at all (including heartbeats) before a worker
# is declared dead outright. Matches the existing pre-flight open-probe's 8s
# convention (playback_controller.py) for consistency. This is a pure safety
# net — see _STALL_TIMEOUT below for the watchdog condition that actually
# catches the failures this module exists for.
_LIVENESS_TIMEOUT = 8.0
# How long after a play()/seek() with no real position progress before a
# worker is declared stalled. Deliberately NOT based on the worker's
# self-reported PlaybackState — empirically (see cratesort/tests/
# run_playback_worker.py's watchdog test), Qt Multimedia's FFmpeg backend
# does its actual file I/O (open, demux, seek) on its OWN internal thread,
# not the thread running the child's Qt event loop. A wedge there can leave
# the child's event loop — and therefore its heartbeat timer — completely
# healthy while the media never loads and never reaches PlayingState at all
# (confirmed: a FIFO with no writer gets stuck at MediaStatus.LoadingMedia
# forever with zero further events, heartbeats included). So "no heartbeat"
# is NOT a reliable wedge signal on its own; what's actually reliable is
# "we asked for progress and didn't get any real position tick back in a
# reasonable time" — see _expecting_progress. Measured on this Qt6/
# AVFoundation build: positionChanged fires roughly every 50ms once
# something is genuinely playing, so 6s tolerates well over a hundred missed
# ticks before firing — generous margin against false positives (e.g. a
# slow external-drive spin-up), still fast enough to recover quickly from a
# real stall.
_STALL_TIMEOUT = 6.0
# Grace period for a killed worker to actually die before giving up on it —
# reused verbatim from parallel_tag_reader.py's _KILL_JOIN_TIMEOUT (same
# tradeoff: a worker stuck in uninterruptible I/O may not actually die, and
# that's an accepted, bounded, daemonised leak). Safe to keep generous here
# since it now always runs off the GUI thread.
_KILL_JOIN_TIMEOUT = 5.0
_SHUTDOWN_JOIN_TIMEOUT = 2.0


class PlaybackWorker:
    def __init__(
        self,
        on_event: OnEvent,
        *,
        liveness_timeout: float = _LIVENESS_TIMEOUT,
        stall_timeout: float = _STALL_TIMEOUT,
    ):
        self._on_event = on_event
        self._liveness_timeout = liveness_timeout
        self._stall_timeout = stall_timeout

        self._proc = None
        self._conn = None
        self._last_msg_time: Optional[float] = None
        self._last_position_time: Optional[float] = None
        # True whenever we've asked the worker to be making progress
        # (play()/seek()) and haven't yet gotten proof it actually is (a real
        # position tick) — see _STALL_TIMEOUT's docstring for why this, not
        # the worker's self-reported PlaybackState, is the thing to watch.
        # Cleared by pause()/stop() (explicit "don't expect progress" intent)
        # and by any position event actually arriving.
        self._expecting_progress = False

    # ------------------------------------------------------------- lifecycle

    def ensure_started(self) -> None:
        if self._proc is not None:
            return
        try:
            ctx = mp.get_context("spawn")
            from cratesort.src.core.playback_worker_proc import worker_main
            parent_conn, child_conn = ctx.Pipe(duplex=True)
            proc = ctx.Process(target=worker_main, args=(child_conn,), daemon=True)
            proc.start()
            child_conn.close()  # only the worker keeps its end
        except Exception as exc:  # noqa: BLE001 - any spawn failure surfaces as an error
            logger.warning("Could not start playback worker: %s", exc)
            self._on_event(("error", f"Could not start playback: {exc}"))
            return

        self._proc = proc
        self._conn = parent_conn
        # Seed both clocks now, not None — gives the freshly-spawned child its
        # full liveness grace period to import PyQt6, build a QCoreApplication,
        # and send its first heartbeat before any watchdog check can fire.
        now = time.monotonic()
        self._last_msg_time = now
        self._last_position_time = now
        self._expecting_progress = False

    def is_alive(self) -> bool:
        return self._proc is not None

    # ---------------------------------------------------------------- commands

    def play(self, path: str, position_ms: int = 0) -> None:
        # Self-healing: play() is the one call a caller will always make to
        # start a track, including right after a wedge was just recovered
        # from — so it's the natural place to lazily respawn rather than
        # relying on every call site to remember ensure_started() first.
        # ensure_started() itself is a no-op if a worker is already alive.
        self.ensure_started()
        self._begin_expecting_progress()
        self._send(("play", path, position_ms))

    def resume(self) -> None:
        """Resume the already-loaded source (post-pause) without re-opening
        the file — see playback_worker_proc.py's protocol docstring for why
        this is a distinct command from play()."""
        self.ensure_started()
        self._begin_expecting_progress()
        self._send(("resume",))

    def seek(self, position_ms: int) -> None:
        self._begin_expecting_progress()
        self._send(("seek", position_ms))

    def pause(self) -> None:
        self._expecting_progress = False
        self._send(("pause",))

    def stop(self) -> None:
        self._expecting_progress = False
        self._send(("stop",))

    def _begin_expecting_progress(self) -> None:
        self._expecting_progress = True
        # Reset the clock to now, not whenever the last real tick happened —
        # e.g. after a long pause, _last_position_time could be arbitrarily
        # old, which would otherwise make the very next play() look
        # instantly stalled.
        self._last_position_time = time.monotonic()

    def set_volume(self, value: float) -> None:
        self._send(("set_volume", value))

    def set_muted(self, muted: bool) -> None:
        self._send(("set_muted", muted))

    def _send(self, msg) -> None:
        if self._conn is None:
            return
        try:
            self._conn.send(msg)
        except (BrokenPipeError, OSError):
            self._handle_wedge("pipe closed while sending a command")

    # ------------------------------------------------------------------ polling

    def poll_events(self) -> None:
        """Call every GUI-thread timer tick. Drains available events, then
        runs the watchdog checks. No-op if no worker is currently alive."""
        if self._conn is None:
            return

        try:
            while self._conn.poll(0):
                msg = self._conn.recv()
                self._on_message(msg)
        except (EOFError, OSError):
            self._handle_wedge("worker connection closed unexpectedly")
            return

        if self._conn is None:  # a handler above may have already torn down
            return

        now = time.monotonic()
        if now - self._last_msg_time > self._liveness_timeout:
            self._handle_wedge(
                f"no response from playback worker for over {int(self._liveness_timeout)}s"
            )
        elif self._expecting_progress and now - self._last_position_time > self._stall_timeout:
            self._handle_wedge(
                f"playback stalled — no progress for over {int(self._stall_timeout)}s"
            )

    def _on_message(self, msg) -> None:
        now = time.monotonic()
        self._last_msg_time = now
        kind = msg[0]
        if kind == "position":
            self._last_position_time = now
            self._on_event(("position", msg[1]))
        elif kind == "duration":
            self._on_event(("duration", msg[1]))
        elif kind == "state":
            self._on_event(("state", msg[1]))
        elif kind == "error":
            self._on_event(("error", msg[1]))
        elif kind == "heartbeat":
            pass  # updating _last_msg_time above is the whole point of it

    # ------------------------------------------------------------------ wedge

    def _handle_wedge(self, reason: str) -> None:
        if self._proc is None:
            return
        dead_proc, dead_conn = self._proc, self._conn
        self._proc = None
        self._conn = None
        self._expecting_progress = False
        logger.warning("Playback worker wedged (%s) — recovering", reason)
        self._on_event(("wedged", reason))
        threading.Thread(target=_kill, args=(dead_proc, dead_conn), daemon=True).start()

    # --------------------------------------------------------------- shutdown

    def shutdown(self) -> None:
        """App-quit path only — allowed to block briefly (same tradeoff
        MainWindow.closeEvent() already makes for its other worker cleanup)."""
        if self._proc is None:
            return
        proc, conn = self._proc, self._conn
        self._proc = None
        self._conn = None
        try:
            conn.send(None)
        except Exception:
            pass
        try:
            proc.join(timeout=_SHUTDOWN_JOIN_TIMEOUT)
        except Exception:
            pass
        if proc.is_alive():
            _kill(proc, conn)
        else:
            try:
                conn.close()
            except Exception:
                pass


def _kill(proc, conn) -> None:
    """A worker stuck in uninterruptible I/O may not actually die — that's an
    OS-level leak we accept, same tradeoff as the scan path's worker pool;
    it's daemonised and bounded to at most one leaked process per wedge."""
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.join(timeout=_KILL_JOIN_TIMEOUT)
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass
