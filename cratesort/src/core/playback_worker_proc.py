"""
Worker-process entry point for PlaybackWorker (out-of-process audio playback).

Runs in a separate OS process so the parent can SIGKILL it if a QMediaPlayer
seek/decode wedges in an uninterruptible kernel wait (failing media, flaky USB
bridge, the macOS FSKit exFAT driver stalling) — the same failure class already
fixed for library scanning (see scan_worker_proc.py / parallel_tag_reader.py),
just never previously extended to playback. Keep the imports here minimal —
under the ``spawn`` start method this module is re-imported fresh in every
worker, and we never want to drag PyQt or anything heavy into a worker.

Unlike scan_worker_proc.py's one-shot request/response shape, this worker is
long-lived and bidirectional: a single Qt event loop must service both
incoming commands (via a QSocketNotifier on the pipe's fd — the duplex
multiprocessing.Pipe is backed by a real socket on POSIX) and QMediaPlayer's
own signals (position/duration/state/error), for the life of one playback
session. It also emits a heartbeat every 2s purely so the parent always has a
liveness signal to check against even while idle (paused/stopped, no other
traffic) — a one-shot worker never needed this since it's either answering a
request or dead.

Protocol over the duplex pipe:
    parent -> worker : ("play", path_str, position_ms)   load + play
    parent -> worker : ("resume",)                        play() on the
                                                           already-loaded
                                                           source — NOT the
                                                           same as "play":
                                                           avoids re-opening
                                                           the file (extra
                                                           drive I/O) just to
                                                           resume from pause
    parent -> worker : ("seek", position_ms)
    parent -> worker : ("pause",)
    parent -> worker : ("stop",)
    parent -> worker : ("set_volume", value)              0.0-1.0
    parent -> worker : ("set_muted", muted)                bool
    parent -> worker : None                                shut down cleanly

    worker -> parent : ("position", ms)
    worker -> parent : ("duration", ms)
    worker -> parent : ("state", value)        QMediaPlayer.PlaybackState.value,
                                                sent as a plain int — never pickle
                                                the raw Qt enum across two
                                                independently-loaded PyQt6
                                                instances
    worker -> parent : ("error", message)
    worker -> parent : ("source_ready",)       ack that setSource()+play() fired
    worker -> parent : ("heartbeat",)
"""
from __future__ import annotations


def worker_main(conn) -> None:
    # Imported here, not at module top, so an import failure is contained to
    # the worker and reported as an error rather than crashing at spawn.
    try:
        from PyQt6.QtCore import QCoreApplication, QSocketNotifier, QTimer, QUrl
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
    except Exception as exc:  # pragma: no cover - defensive
        _report_import_failure(conn, f"playback worker import failed: {exc}")
        return

    app = QCoreApplication([])
    player = QMediaPlayer()
    audio_output = QAudioOutput()
    player.setAudioOutput(audio_output)

    def send(msg) -> None:
        try:
            conn.send(msg)
        except (BrokenPipeError, OSError):
            app.quit()

    player.positionChanged.connect(lambda ms: send(("position", int(ms))))
    player.durationChanged.connect(lambda ms: send(("duration", int(ms))))
    player.playbackStateChanged.connect(lambda state: send(("state", int(state.value))))
    player.errorOccurred.connect(
        lambda _err, message: send(("error", message)) if message else None
    )

    heartbeat = QTimer()
    heartbeat.setInterval(2000)
    heartbeat.timeout.connect(lambda: send(("heartbeat",)))
    heartbeat.start()

    def handle(msg) -> bool:
        """Returns False when the worker should shut down."""
        if msg is None:
            return False
        kind = msg[0]
        if kind == "play":
            _, path_str, position_ms = msg
            player.setSource(QUrl.fromLocalFile(path_str))
            if position_ms:
                player.setPosition(position_ms)
            player.play()
            send(("source_ready",))
        elif kind == "resume":
            player.play()
        elif kind == "seek":
            player.setPosition(msg[1])
        elif kind == "pause":
            player.pause()
        elif kind == "stop":
            player.stop()
        elif kind == "set_volume":
            audio_output.setVolume(msg[1])
        elif kind == "set_muted":
            audio_output.setMuted(msg[1])
        return True

    def drain(_fd=None) -> None:
        # Disabled while draining to avoid re-entrant activation mid-recv();
        # conn.poll(0) guards every recv() so it can never block even if the
        # notifier fires spuriously or on a partial message.
        notifier.setEnabled(False)
        try:
            while conn.poll(0):
                try:
                    msg = conn.recv()
                except (EOFError, OSError):
                    app.quit()
                    return
                if not handle(msg):
                    app.quit()
                    return
        finally:
            notifier.setEnabled(True)

    notifier = QSocketNotifier(conn.fileno(), QSocketNotifier.Type.Read)
    notifier.activated.connect(drain)

    app.exec()


def _report_import_failure(conn, message: str) -> None:
    """If we can't even import Qt/multimedia, still answer with an error
    immediately so the parent's liveness watchdog doesn't have to wait out the
    full timeout before finding out something's wrong."""
    try:
        conn.send(("error", message))
    except (BrokenPipeError, OSError):
        return
