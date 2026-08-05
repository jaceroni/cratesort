from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_FILENAME = 'scan_cache.json'

# Fields cached per file, beyond the size/mtime invalidation key. Mirrors
# TrackRecord's tag/audio-property surface (scanner.py) — filesystem-derived
# fields (path, parent_dir, filename, extension, is_audio, is_video, codec)
# are cheap to re-derive from the path itself and aren't stored here.
CACHED_FIELDS = (
    'title', 'artist', 'album', 'genre', 'year', 'bpm', 'comment',
    'duration', 'bitrate', 'sample_rate', 'has_artwork', 'read_error',
)


def _cache_path(library_path: Path) -> Path:
    return library_path / '_CrateSort' / _CACHE_FILENAME


def load_cache(library_path: Path) -> dict[str, dict[str, Any]]:
    """
    Per-file scan cache: path string -> {size, mtime, <tag/audio fields>}.
    Used by LibraryScanner to skip re-reading tags for files whose size and
    mtime haven't changed since the last scan.

    Returns an empty dict on any error or if no cache exists yet — a safe
    fallback equivalent to "do a full scan," never a crash.
    """
    path = _cache_path(library_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        entries = data.get('entries', {})
        return entries if isinstance(entries, dict) else {}
    except Exception as exc:
        logger.warning('[ScanCache] Failed to read %s: %s', path, exc)
        return {}


def save_cache(library_path: Path, entries: dict[str, dict[str, Any]]) -> None:
    path = _cache_path(library_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({'entries': entries}, indent=2),
        encoding='utf-8',
    )


def clear_cache(library_path: Path) -> None:
    """Delete the scan cache — forces a full rescan on next launch."""
    path = _cache_path(library_path)
    if path.exists():
        path.unlink()
