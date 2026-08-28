from __future__ import annotations

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer


class PlaybackController(QObject):
    """Owns the single QMediaPlayer/QAudioOutput pair for the whole app.

    PlaybackBar and FloatingVideoWindow both subscribe to this instead of
    touching QMediaPlayer directly, so playback state is never duplicated
    between the two. Knows nothing about "next/previous" — that's tree
    traversal and stays in LibraryBrowserView/MainWindow.
    """

    position_changed      = pyqtSignal(int)     # ms
    duration_changed       = pyqtSignal(int)     # ms
    playback_state_changed = pyqtSignal(object)  # QMediaPlayer.PlaybackState
    media_error             = pyqtSignal(str)
    now_playing_changed     = pyqtSignal(object)  # TrackRecord

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._current_track = None

        # positionChanged/durationChanged emit qint64 — proxy through a plain
        # callable rather than signal-to-signal connect, which requires an
        # exact qint64/int signature match and fails otherwise.
        self._player.positionChanged.connect(lambda ms: self.position_changed.emit(int(ms)))
        self._player.durationChanged.connect(lambda ms: self.duration_changed.emit(int(ms)))
        self._player.playbackStateChanged.connect(lambda state: self.playback_state_changed.emit(state))
        self._player.errorOccurred.connect(self._on_error)

    def _on_error(self, _error, error_string: str) -> None:
        if error_string:
            self.media_error.emit(error_string)

    @property
    def current_track(self):
        return self._current_track

    def play(self, rec) -> None:
        self._current_track = rec
        self._player.setSource(QUrl.fromLocalFile(str(rec.path)))
        self._player.play()
        self.now_playing_changed.emit(rec)

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
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def seek(self, position_ms: int) -> None:
        self._player.setPosition(position_ms)

    def position(self) -> int:
        return self._player.position()

    def duration(self) -> int:
        return self._player.duration()

    def set_volume(self, value: int) -> None:
        """value: 0-100"""
        self._audio_output.setVolume(max(0.0, min(1.0, value / 100)))

    def volume(self) -> int:
        return round(self._audio_output.volume() * 100)

    def set_muted(self, muted: bool) -> None:
        self._audio_output.setMuted(muted)

    def is_muted(self) -> bool:
        return self._audio_output.isMuted()

    def set_video_output(self, video_widget) -> None:
        self._player.setVideoOutput(video_widget)
