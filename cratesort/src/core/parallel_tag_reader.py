"""
ParallelTagReader — reads audio tags for many files across a small pool of
worker processes, with a parent-side per-file watchdog.

Why processes: a tag read can wedge in an uninterruptible kernel wait — a
failing drive, a flaky USB bridge, or (common on macOS 15/26) the FSKit exFAT
driver stalling. Nothing inside the calling process can interrupt that: not a
signal, not a QThread, not a timer, because the thread is stuck in the kernel
holding the GIL. The only thing that recovers is SIGKILL on a *separate*
process. So every real file read happens in a worker the parent can kill.

Behaviour:
  * ~N workers read in parallel; a healthy library scans faster than before.
  * If a worker doesn't return a file's result within ``per_file_timeout``,
    the parent kills it, marks that one file unreadable, spawns a replacement,
    and keeps going. One bad file costs one timeout, not a frozen app.
  * ``is_cancelled()`` is honoured promptly — all workers are killed.
  * If this platform can't spawn processes at all, it degrades to a
    thread-with-join-timeout fallback (a stuck read leaks a daemon thread but
    the scan still finishes) and finally to a plain sequential read.
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
import time
from collections import deque
from multiprocessing.connection import wait as mp_wait
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

OnResult = Callable[[str, str, dict], None]        # (path_str, ext, fields)
OnProgress = Callable[[int, int, str], None]       # (done, total, current_path)
IsCancelled = Callable[[], bool]

# How long the parent waits, per poll, for any worker to answer.
_POLL_INTERVAL = 1.0
# Grace period for a killed worker to actually die before we stop waiting on it.
_KILL_JOIN_TIMEOUT = 5.0


class _Worker:
    __slots__ = ("proc", "conn")

    def __init__(self, proc, conn):
        self.proc = proc
        self.conn = conn


class ParallelTagReader:
    def __init__(self, workers: int = 3, per_file_timeout: float = 15.0):
        self.workers = max(1, int(workers))
        self.per_file_timeout = float(per_file_timeout)

    # ------------------------------------------------------------------ public

    def read(
        self,
        tasks: list[tuple[str, str]],
        on_result: OnResult,
        on_progress: OnProgress | None = None,
        is_cancelled: IsCancelled | None = None,
    ) -> None:
        if not tasks:
            return
        is_cancelled = is_cancelled or (lambda: False)
        try:
            self._read_multiprocess(list(tasks), on_result, on_progress, is_cancelled)
        except Exception as exc:  # noqa: BLE001 - any spawn/pool failure -> fallback
            logger.warning(
                "Process pool unavailable (%s: %s) — falling back to in-thread reads",
                type(exc).__name__, exc,
            )
            self._read_threaded(list(tasks), on_result, on_progress, is_cancelled)

    # ---------------------------------------------------------- process pool

    def _read_multiprocess(
        self,
        tasks: list[tuple[str, str]],
        on_result: OnResult,
        on_progress: OnProgress | None,
        is_cancelled: IsCancelled,
    ) -> None:
        from cratesort.src.core.scan_worker_proc import worker_main

        ctx = mp.get_context("spawn")
        total = len(tasks)
        pending: deque[tuple[str, str]] = deque(tasks)
        done = 0

        n = min(self.workers, total)
        pool: list[_Worker] = [self._spawn(ctx, worker_main) for _ in range(n)]
        idle: list[_Worker] = list(pool)
        inflight: dict[object, tuple[_Worker, str, str, float]] = {}  # conn -> (w, path, ext, deadline)

        def _finish(path_str: str, ext: str, fields: dict) -> None:
            nonlocal done
            on_result(path_str, ext, fields)
            done += 1
            if on_progress:
                on_progress(done, total, path_str)

        def _replace(dead: _Worker) -> None:
            """Kill a wedged/broken worker and bring the pool back to strength.
            A worker stuck in uninterruptible I/O may not actually die — that's
            an OS-level leak we accept; it's daemonised and bounded by the
            number of distinct bad files."""
            self._kill(dead)
            if dead in pool:
                pool.remove(dead)
            try:
                fresh = self._spawn(ctx, worker_main)
                pool.append(fresh)
                idle.append(fresh)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not spawn replacement worker: %s", exc)

        try:
            while done < total:
                if is_cancelled():
                    return

                # Hand queued files to any idle workers.
                while idle and pending:
                    w = idle.pop()
                    path_str, ext = pending.popleft()
                    try:
                        w.conn.send((path_str, ext))
                    except (BrokenPipeError, OSError):
                        pending.appendleft((path_str, ext))
                        _replace(w)
                        break
                    inflight[w.conn] = (
                        w, path_str, ext, time.monotonic() + self.per_file_timeout,
                    )

                if not inflight:
                    if pending and not pool:
                        # Lost every worker and can't respawn — finish the
                        # remainder in-thread rather than spin forever.
                        logger.warning(
                            "No workers left — reading %d remaining file(s) in-thread",
                            len(pending),
                        )
                        self._read_threaded(
                            list(pending), on_result, on_progress, is_cancelled,
                            _done_offset=done, _total_override=total,
                        )
                    return

                ready = mp_wait(list(inflight.keys()), timeout=_POLL_INTERVAL)
                now = time.monotonic()

                for conn in ready:
                    entry = inflight.pop(conn, None)
                    if entry is None:
                        continue
                    w, path_str, ext, _deadline = entry
                    try:
                        _rp, fields = conn.recv()
                    except (EOFError, OSError):
                        _replace(w)
                        _finish(path_str, ext,
                                {"read_error": "worker process exited unexpectedly"})
                        continue
                    idle.append(w)
                    _finish(path_str, ext, fields)

                # Kill anything past its per-file deadline.
                for conn, (w, path_str, ext, deadline) in list(inflight.items()):
                    if now < deadline:
                        continue
                    inflight.pop(conn, None)
                    logger.warning(
                        "Tag read exceeded %.0fs — killing worker for: %s",
                        self.per_file_timeout, path_str,
                    )
                    _replace(w)
                    _finish(path_str, ext, {
                        "read_error":
                            f"Unreadable — drive did not respond within "
                            f"{int(self.per_file_timeout)}s",
                    })
        finally:
            for w in pool:
                self._shutdown(w)

    # ---------------------------------------------------------------- helpers

    def _spawn(self, ctx, target) -> _Worker:
        parent_conn, child_conn = ctx.Pipe(duplex=True)
        proc = ctx.Process(target=target, args=(child_conn,), daemon=True)
        proc.start()
        child_conn.close()  # only the worker keeps its end
        return _Worker(proc, parent_conn)

    def _kill(self, w: _Worker) -> None:
        try:
            w.proc.kill()
        except Exception:
            pass
        try:
            w.proc.join(timeout=_KILL_JOIN_TIMEOUT)
        except Exception:
            pass
        try:
            w.conn.close()
        except Exception:
            pass

    def _shutdown(self, w: _Worker) -> None:
        try:
            w.conn.send(None)
        except Exception:
            pass
        try:
            w.proc.join(timeout=2.0)
        except Exception:
            pass
        if w.proc.is_alive():
            self._kill(w)
        else:
            try:
                w.conn.close()
            except Exception:
                pass

    # -------------------------------------------------------------- fallback

    def _read_threaded(
        self,
        tasks: list[tuple[str, str]],
        on_result: OnResult,
        on_progress: OnProgress | None,
        is_cancelled: IsCancelled,
        _done_offset: int = 0,
        _total_override: int | None = None,
    ) -> None:
        """Best-effort isolation without processes: each read runs in a daemon
        thread joined with a timeout. A stuck read can't be killed, so the
        thread is abandoned (leaked) and the file marked unreadable — but the
        scan proceeds and the UI stays alive."""
        import threading

        from cratesort.src.core.scanner import read_one_file

        total = _total_override if _total_override is not None else len(tasks)
        done = _done_offset

        for path_str, ext in tasks:
            if is_cancelled():
                return

            box: dict = {}

            def _do(_p=path_str, _e=ext, _box=box) -> None:
                r: dict = {}
                try:
                    st = os.stat(_p)
                    r["_size"] = st.st_size
                    r["_mtime"] = st.st_mtime
                    r.update(read_one_file(Path(_p), _e))
                except Exception as exc:  # noqa: BLE001
                    r["read_error"] = f"{type(exc).__name__}: {exc}"
                _box.update(r)

            th = threading.Thread(target=_do, daemon=True)
            th.start()
            th.join(self.per_file_timeout)

            if th.is_alive():
                logger.warning(
                    "Tag read exceeded %.0fs (thread fallback) — abandoning: %s",
                    self.per_file_timeout, path_str,
                )
                on_result(path_str, ext, {
                    "read_error":
                        f"Unreadable — timed out after {int(self.per_file_timeout)}s",
                })
            else:
                on_result(path_str, ext, box)

            done += 1
            if on_progress:
                on_progress(done, total, path_str)
