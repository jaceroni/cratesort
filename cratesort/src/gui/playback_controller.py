from __future__ import annotations

import threading

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from cratesort.src.core.playback_worker import PlaybackWorker

# A stalled macOS FSKit exFAT mount can block a plain file read indefinitely
# in an uninterruptible kernel wait — the same failure class the scan path
# was hardened against (see parallel_tag_reader.py). QMediaPlayer.setSource()
# hits that same read synchronously on the GUI thread with no timeout, so a
# bad external drive freezes the whole app on a single track click. play()
# below probes the file on a daemon thread first and only touches a real
# player once the probe confirms the file is actually readable. Shorter than
# the scan path's 15s per-file timeout since this blocks one interactive
# click rather than ambient background work.
_PROBE_TIMEOUT_MS = 8000
_PROBE_READ_BYTES = 65536

# How often the GUI thread drains the audio worker's pipe. Fast enough that
# scrub/seek/play-pause feel instant, cheap enough to be negligible CPU — see
# PlaybackWorker's own docstring for why this is a plain QTimer poll rather
# than a QThread (unlike the scan path's pattern, there's no long blocking
# call here to isolate; the only ongoing work is a non-blocking pipe check).
_AUDIO_POLL_INTERVAL_MS = 100


class PlaybackController(QObject):
    """Owns playback for the whole app — audio and video.

    Video stays fully in-process (a single QMediaPlayer/QAudioOutput pair,
    self._player/self._audio_output below) — QMediaPlayer.setVideoOutput()
    hands a live, GUI-process-resident Qt widget straight to the player, and
    there's no serializable frame boundary that would let video move to a
    subprocess without inventing cross-process video-frame IPC (a separate,
    much larger project). This is an explicit, accepted scope limit: video
    playback from a stalling drive is NOT protected by the audio fix below.

    Audio-only tracks run in a separate, killable OS process instead
    (self._audio_worker, a PlaybackWorker) — a QMediaPlayer seek/decode can
    wedge in an uninterruptible kernel wait against a stalling drive, and
    nothing in-process can recover from that (confirmed: a real freeze while
    scrubbing a track's position slider, and reusing the same wedged player
    for a different track afterward hung too). Only SIGKILL on a separate
    process reliably recovers — the same principle already applied to
    library scanning (parallel_tag_reader.py/scan_worker_proc.py).

    PlaybackBar, FloatingVideoWindow, MainWindow, LibraryBrowserView, and
    CrateManagerView all subscribe to this exact same public API regardless
    of which backend is actually playing — every method/signal here has the
    identical name and signature it had before this split, and every
    consumer is purely signal-driven (never polls a getter mid-playback
    except is_muted()/current_track, both answered from GUI-thread-local
    state instantly either way). Knows nothing about "next/previous" —
    that's tree traversal and stays in LibraryBrowserView/MainWindow.
    """

    position_changed      = pyqtSignal(int)     # ms
    duration_changed       = pyqtSignal(int)     # ms
    playback_state_changed = pyqtSignal(object)  # QMediaPlayer.PlaybackState
    media_error             = pyqtSignal(str)
    now_playing_changed     = pyqtSignal(object)  # TrackRecord

    _probe_finished = pyqtSignal(object, object, bool, str)  # token, rec, ok, error

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._current_track = None
        self._probe_token = None
        self._probe_timer = None

        # None while nothing is loaded; "video" or "audio" once play()
        # actually hands a track to one backend or the other.
        self._active_path = None

        # Cross-cutting — authoritative in the controller itself rather than
        # read back from whichever backend happens to be active, since once
        # there are two possible backends a getter has to answer correctly
        # regardless of which one is currently in use (and apply correctly
        # to whichever one becomes active next).
        self._volume = 80
        self._muted = False

        # Audio path: state mirrored here from worker events so getters
        # answer instantly from GUI-thread-local state, same as the video
        # path's direct (but synchronous, in-process) player reads.
        self._audio_worker = PlaybackWorker(on_event=self._on_worker_event)
        self._audio_position = 0
        self._audio_duration = 0
        self._audio_playback_state = QMediaPlayer.PlaybackState.StoppedState
        self._audio_poll_timer = QTimer(self)
        self._audio_poll_timer.setInterval(_AUDIO_POLL_INTERVAL_MS)
        self._audio_poll_timer.timeout.connect(self._audio_worker.poll_events)

        # positionChanged/durationChanged emit qint64 — proxy through a plain
        # callable rather than signal-to-signal connect, which requires an
        # exact qint64/int signature match and fails otherwise.
        self._player.positionChanged.connect(lambda ms: self._on_video_position(int(ms)))
        self._player.durationChanged.connect(lambda ms: self._on_video_duration(int(ms)))
        self._player.playbackStateChanged.connect(lambda state: self._on_video_state(state))
        self._player.errorOccurred.connect(self._on_error)
        self._probe_finished.connect(self._on_probe_finished)

    # ── Video-path signal relays (only forwarded while video is active, so a
    # background video player left loaded doesn't fight the audio path's own
    # position/state reporting) ─────────────────────────────────────────────

    def _on_video_position(self, ms: int) -> None:
        if self._active_path == "video":
            self.position_changed.emit(ms)

    def _on_video_duration(self, ms: int) -> None:
        if self._active_path == "video":
            self.duration_changed.emit(ms)

    def _on_video_state(self, state) -> None:
        if self._active_path == "video":
            self.playback_state_changed.emit(state)

    def _on_error(self, _error, error_string: str) -> None:
        if error_string:
            self.media_error.emit(error_string)

    @property
    def current_track(self):
        return self._current_track

    # ── Opening a track ──────────────────────────────────────────────────

    def play(self, rec) -> None:
        self._current_track = rec
        token = object()
        self._probe_token = token

        if self._probe_timer is not None:
            self._probe_timer.stop()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._on_probe_timeout(token, rec))
        timer.start(_PROBE_TIMEOUT_MS)
        self._probe_timer = timer

        path = str(rec.path)

        def _probe() -> None:
            try:
                with open(path, 'rb') as f:
                    f.read(_PROBE_READ_BYTES)
                self._probe_finished.emit(token, rec, True, '')
            except OSError as exc:
                self._probe_finished.emit(token, rec, False, str(exc))

        # Daemon thread: if the read wedges in an uninterruptible kernel
        # wait, nothing in-process can kill it. Leaving it as a leaked
        # daemon thread (never joined) keeps the GUI thread free and lets
        # the process still exit cleanly later — same tradeoff the scan
        # path's thread-isolation fallback already accepts.
        threading.Thread(target=_probe, daemon=True).start()

    def _on_probe_timeout(self, token, rec) -> None:
        if token is not self._probe_token:
            return
        self._probe_token = None
        self.media_error.emit(
            f"“{rec.path.name}” didn’t respond — its drive may be disconnected or slow to wake up."
        )

    def _on_probe_finished(self, token, rec, ok: bool, error: str) -> None:
        if token is not self._probe_token:
            return  # superseded by a later click, or already timed out
        self._probe_token = None
        if self._probe_timer is not None:
            self._probe_timer.stop()
        if not ok:
            self.media_error.emit(error or f"Couldn't read “{rec.path.name}”.")
            return

        if getattr(rec, 'is_video', False):
            if self._active_path == "audio":
                self._audio_worker.stop()
                self._audio_poll_timer.stop()
            self._active_path = "video"
            self._player.setSource(QUrl.fromLocalFile(str(rec.path)))
            self._player.play()
        else:
            if self._active_path == "video":
                self._player.stop()
            self._active_path = "audio"
            # ensure_started() first (idempotent no-op if already running) —
            # set_volume/set_muted are silently dropped if sent before the
            # worker exists, since there's no pipe to send them over yet.
            self._audio_worker.ensure_started()
            self._audio_worker.set_volume(self._volume / 100)
            self._audio_worker.set_muted(self._muted)
            self._audio_worker.play(str(rec.path))
            if not self._audio_poll_timer.isActive():
                self._audio_poll_timer.start()

        self.now_playing_changed.emit(rec)

    # ── Audio-worker event handling ──────────────────────────────────────

    def _on_worker_event(self, evt: tuple) -> None:
        kind = evt[0]
        if kind == "position":
            self._audio_position = evt[1]
            if self._active_path == "audio":
                self.position_changed.emit(evt[1])
        elif kind == "duration":
            self._audio_duration = evt[1]
            if self._active_path == "audio":
                self.duration_changed.emit(evt[1])
        elif kind == "state":
            self._audio_playback_state = QMediaPlayer.PlaybackState(evt[1])
            if self._active_path == "audio":
                self.playback_state_changed.emit(self._audio_playback_state)
        elif kind == "error":
            self.media_error.emit(evt[1])
        elif kind == "wedged":
            self._audio_poll_timer.stop()
            self._audio_playback_state = QMediaPlayer.PlaybackState.StoppedState
            self._audio_position = 0
            if self._active_path == "audio":
                # Row icons revert to "not playing" — both LibraryBrowserView
                # and CrateManagerView are purely signal-driven off this,
                # confirmed, no changes needed there.
                self.playback_state_changed.emit(self._audio_playback_state)
            name = self._current_track.path.name if self._current_track else 'Playback'
            self.media_error.emit(
                f"“{name}” stopped responding — its drive may be disconnected or too slow to keep up."
            )
            self._active_path = None

    # ── Transport controls ───────────────────────────────────────────────

    def play_or_toggle(self, rec) -> None:
        """Row-icon click behaviour: if this track is already the loaded one,
        toggle play/pause; otherwise load and play it. So a second click on
        the same row pauses, a third resumes — never a restart."""
        cur = self._current_track
        if cur is not None and str(getattr(cur, 'path', '')) == str(getattr(rec, 'path', '')):
            self.toggle_play_pause()
        else:
            self.play(rec)

    def toggle_play_pause(self) -> None:
        if self._active_path == "audio":
            if self._audio_playback_state == QMediaPlayer.PlaybackState.PlayingState:
                self._audio_worker.pause()
            else:
                self._audio_worker.resume()
        else:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.pause()
            else:
                self._player.play()

    def pause(self) -> None:
        if self._active_path == "audio":
            self._audio_worker.pause()
        else:
            self._player.pause()

    def stop(self) -> None:
        # Invalidate any in-flight probe so a late result from a click the
        # user already backed out of doesn't start playback after the fact.
        self._probe_token = None
        if self._probe_timer is not None:
            self._probe_timer.stop()
        if self._active_path == "audio":
            self._audio_worker.stop()
            self._audio_poll_timer.stop()
            self._audio_position = 0
            self._audio_playback_state = QMediaPlayer.PlaybackState.StoppedState
        else:
            self._player.stop()
        self._active_path = None

    def is_playing(self) -> bool:
        if self._active_path == "audio":
            return self._audio_playback_state == QMediaPlayer.PlaybackState.PlayingState
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def seek(self, position_ms: int) -> None:
        if self._active_path == "audio":
            self._audio_worker.seek(position_ms)
        else:
            self._player.setPosition(position_ms)

    def position(self) -> int:
        if self._active_path == "audio":
            return self._audio_position
        return self._player.position()

    def duration(self) -> int:
        if self._active_path == "audio":
            return self._audio_duration
        return self._player.duration()

    def set_volume(self, value: int) -> None:
        """value: 0-100"""
        self._volume = max(0, min(100, value))
        self._audio_output.setVolume(self._volume / 100)
        self._audio_worker.set_volume(self._volume / 100)

    def volume(self) -> int:
        return self._volume

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        self._audio_output.setMuted(muted)
        self._audio_worker.set_muted(muted)

    def is_muted(self) -> bool:
        return self._muted

    def set_video_output(self, video_widget) -> None:
        self._player.setVideoOutput(video_widget)

    # ── App shutdown ─────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Call once, from MainWindow.closeEvent(), so the audio worker
        process never lingers as a zombie after the app quits. Allowed to
        block briefly — a one-time app-quit action, same tradeoff already
        made for the dashboard's other worker cleanup."""
        self._audio_poll_timer.stop()
        self._audio_worker.shutdown()
