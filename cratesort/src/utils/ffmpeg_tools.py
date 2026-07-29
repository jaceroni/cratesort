"""Locate the ffmpeg binary and probe media duration, without a system ffmpeg install."""
from __future__ import annotations

import logging
import re
import subprocess

logger = logging.getLogger(__name__)

_DURATION_RE = re.compile(r'Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)')

_cached_ffmpeg_path: str | None = None


def get_ffmpeg_path() -> str:
    """
    Return a path to a working ffmpeg binary.

    Prefers the binary bundled by the `imageio-ffmpeg` package (no system install
    or network fetch required, and PyInstaller-friendly). Falls back to the bare
    'ffmpeg' command (resolved via $PATH) if that package is unavailable.
    """
    global _cached_ffmpeg_path
    if _cached_ffmpeg_path is not None:
        return _cached_ffmpeg_path

    try:
        import imageio_ffmpeg
        _cached_ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        logger.warning('imageio_ffmpeg unavailable — falling back to system ffmpeg on PATH')
        _cached_ffmpeg_path = 'ffmpeg'

    return _cached_ffmpeg_path


def parse_duration_from_text(text: str) -> float:
    """Parse a 'Duration: HH:MM:SS.ss' fragment out of ffmpeg output text, or 0.0 if absent."""
    match = _DURATION_RE.search(text)
    if not match:
        return 0.0
    hours, minutes, seconds, hundredths = match.groups()
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(hundredths) / (10 ** len(hundredths))
    )


_FRIENDLY_ERRORS = (
    ('already exists', 'A file with that name already exists in the destination folder.'),
    ('permission denied', "CrateSort doesn't have permission to save files in that folder."),
    ('no such file or directory', 'The destination folder could not be found — it may have been moved, renamed, or deleted.'),
    ('no space left on device', 'Not enough free disk space to save the converted file.'),
    ('read-only file system', 'That folder is read-only — CrateSort can\'t save files there.'),
)


def friendly_ffmpeg_error(detail: str) -> str:
    """
    Translate a raw ffmpeg error fragment into plain language a non-technical
    user can act on. Falls back to the raw detail (still shown, just unexplained)
    if none of the known patterns match.
    """
    lowered = detail.lower()
    for needle, friendly in _FRIENDLY_ERRORS:
        if needle in lowered:
            return friendly
    return detail


def get_media_duration(path: str) -> float:
    """
    Return the duration of a media file in seconds, or 0.0 if it can't be determined.

    Uses ffmpeg's own stderr banner (`Duration: HH:MM:SS.ss`) rather than ffprobe,
    since imageio-ffmpeg bundles only the ffmpeg binary.
    """
    try:
        r = subprocess.run(
            [get_ffmpeg_path(), '-i', path],
            capture_output=True, text=True, timeout=30,
        )
        return parse_duration_from_text(r.stderr)
    except Exception:
        return 0.0
