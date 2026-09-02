"""
Worker-process entry point for ParallelTagReader.

Runs in a separate OS process so the parent can SIGKILL it if a tag read wedges
in an uninterruptible kernel wait (failing media, flaky USB bridge, the macOS
FSKit exFAT driver stalling). Keep the imports here minimal — under the
``spawn`` start method this module is re-imported fresh in every worker, and we
never want to drag PyQt or anything heavy into a worker.

Protocol over the duplex pipe:
    parent -> worker : (path_str, ext)      request a read
    parent -> worker : None                 shut down cleanly
    worker -> parent : (path_str, fields)   fields = CACHED_FIELDS dict, plus
                                            "_size" / "_mtime" from os.stat
"""
from __future__ import annotations

import os
from pathlib import Path


def worker_main(conn) -> None:
    # Imported here, not at module top, so an import failure is contained to the
    # worker and reported as a read error rather than crashing at spawn.
    try:
        from cratesort.src.core.scanner import read_one_file
    except Exception as exc:  # pragma: no cover - defensive
        _drain_reporting_error(conn, f"worker import failed: {exc}")
        return

    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return
        if msg is None:
            return

        path_str, ext = msg
        fields: dict = {}
        try:
            st = os.stat(path_str)          # can itself block on a dead mount
            fields["_size"] = st.st_size
            fields["_mtime"] = st.st_mtime
        except OSError as exc:
            fields["read_error"] = f"{type(exc).__name__}: {exc}"

        if "read_error" not in fields:
            try:
                fields.update(read_one_file(Path(path_str), ext))
            except Exception as exc:  # pragma: no cover - read_one_file is total
                fields["read_error"] = f"{type(exc).__name__}: {exc}"

        try:
            conn.send((path_str, fields))
        except (BrokenPipeError, OSError):
            return


def _drain_reporting_error(conn, message: str) -> None:
    """If we can't even import, still answer each request with the error so the
    parent doesn't have to wait out the full per-file timeout on every file."""
    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return
        if msg is None:
            return
        path_str = msg[0] if isinstance(msg, tuple) else str(msg)
        try:
            conn.send((path_str, {"read_error": message}))
        except (BrokenPipeError, OSError):
            return
