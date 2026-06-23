from __future__ import annotations

import logging
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_FILENAME = 'database V2'


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class TrackDbEntry:
    """Parsed per-track data from Serato's database V2."""
    __slots__ = ('add_date', 'play_count')

    def __init__(self, add_date: Optional[datetime], play_count: Optional[int]):
        self.add_date   = add_date
        self.play_count = play_count


# Module-level cache: serato_dir path → {file_path: TrackDbEntry}
_CACHE: dict[str, dict[str, TrackDbEntry]] = {}


def read_track_metadata(serato_dir: str | Path) -> dict[str, TrackDbEntry]:
    """
    Parse Serato's `database V2` and return a mapping of track file path
    (from the `pfil` field) to a TrackDbEntry with add_date and play_count.

    Results are cached per serato_dir for the session lifetime.
    Returns an empty dict on any error; never raises.
    """
    serato_dir = Path(serato_dir)
    cache_key  = str(serato_dir)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    db_path = serato_dir / _DB_FILENAME
    if not db_path.exists():
        logger.warning('[DatabaseReader] database V2 not found at %s', db_path)
        _CACHE[cache_key] = {}
        return {}

    try:
        result = _parse_database_full(db_path)
    except Exception as exc:
        logger.warning('[DatabaseReader] Failed to parse %s: %s', db_path, exc)
        result = {}

    _CACHE[cache_key] = result
    logger.info('[DatabaseReader] Loaded %d track entries from %s', len(result), db_path)
    return result


def read_track_play_counts(serato_dir: str | Path) -> dict[str, int]:
    """
    Convenience wrapper: returns only the play_count mapping.
    Tracks with no play count entry are omitted.
    """
    return {
        path: entry.play_count
        for path, entry in read_track_metadata(serato_dir).items()
        if entry.play_count is not None
    }


def read_track_add_dates(serato_dir: str | Path) -> dict[str, datetime]:
    """
    Return a mapping of track file path → add date.
    Backed by read_track_metadata; results share the same cache.
    """
    return {
        path: entry.add_date
        for path, entry in read_track_metadata(serato_dir).items()
        if entry.add_date is not None
    }


def clear_cache() -> None:
    """Clear the in-memory parse cache (e.g. when a different library is loaded)."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Path normalization
# ---------------------------------------------------------------------------

# Common top-level media folders Serato organises tracks under.
# Used to extract the relative portion from absolute pfil paths.
_MEDIA_PREFIXES = (
    'MP3/', 'Music Videos/', 'Sound FX/', 'AAC/', 'AIFF/',
    'FLAC/', 'WAV/', 'OGG/', 'M4A/', 'MP4/',
)

_SERATO_COLON = ''   # U+F022 private-use char Serato uses instead of ' : '
_REAL_COLON   = ' : '


def _normalize_pfil_keys(raw_path: str) -> list[str]:
    """
    Return all candidate lookup keys for a raw pfil path value.

    Handles two known issues:
    1. Serato stores ` : ` in folder names as U+F022 () — replace back.
    2. Some entries are stored with absolute path prefixes; extract the
       media-relative portion so it matches what we derive from rec.path.
    """
    # Fix Serato's private-use character and normalise separators
    p = raw_path.replace(_SERATO_COLON, _REAL_COLON)
    p = p.replace('\\', '/').strip('\x00\xfe\xff')
    p = p.lstrip('/')

    keys: list[str] = []

    if any(p.startswith(prefix) for prefix in _MEDIA_PREFIXES):
        # Already relative — one key is enough
        keys.append(p)
    else:
        # Likely an absolute path — store the full normalised form AND
        # the media-relative portion (everything from the first media folder).
        keys.append(p)
        for prefix in _MEDIA_PREFIXES:
            idx = p.find('/' + prefix)
            if idx >= 0:
                keys.append(p[idx + 1:])   # drop the leading '/'
                break

    return [k for k in keys if k]


# ---------------------------------------------------------------------------
# Internal parser
# ---------------------------------------------------------------------------

def _parse_database_full(db_path: Path) -> dict[str, TrackDbEntry]:
    """
    Parse the TLV-format `database V2` file.

    Top-level structure:
        vrsn record  (version string)
        otrk record  (one per track, contains inner TLV fields)
        ...

    Inner fields read from each otrk:
        pfil  — UTF-16 BE string, the track's file path
        uadd  — uint32 BE, Unix timestamp of add date
        uply  — uint32 BE, play count
    """
    data   = db_path.read_bytes()
    result: dict[str, TrackDbEntry] = {}
    pos    = 0
    length = len(data)

    while pos + 8 <= length:
        tag = data[pos:pos + 4]
        try:
            tag_str = tag.decode('ascii')
        except (UnicodeDecodeError, ValueError):
            pos += 1
            continue

        if not all(32 <= b < 127 for b in tag):
            pos += 1
            continue

        try:
            record_len = struct.unpack('>I', data[pos + 4:pos + 8])[0]
        except struct.error:
            pos += 1
            continue

        if pos + 8 + record_len > length:
            pos += 1
            continue

        record_data = data[pos + 8: pos + 8 + record_len]
        pos += 8 + record_len

        if tag_str == 'otrk':
            parsed = _parse_otrk_full(record_data)
            if parsed:
                file_path, entry = parsed
                for key in _normalize_pfil_keys(file_path):
                    result.setdefault(key, entry)

    return result


def _parse_otrk_full(otrk_data: bytes) -> Optional[tuple[str, TrackDbEntry]]:
    """
    Parse inner TLV fields of one `otrk` record.
    Returns (file_path, TrackDbEntry) or None if pfil is missing.
    """
    file_path:  Optional[str]      = None
    add_date:   Optional[datetime] = None
    play_count: Optional[int]      = None
    pos  = 0
    dlen = len(otrk_data)

    while pos + 8 <= dlen:
        tag = otrk_data[pos:pos + 4]
        try:
            tag_str = tag.decode('ascii')
        except (UnicodeDecodeError, ValueError):
            pos += 1
            continue

        if not all(32 <= b < 127 for b in tag):
            pos += 1
            continue

        try:
            field_len = struct.unpack('>I', otrk_data[pos + 4:pos + 8])[0]
        except struct.error:
            pos += 1
            continue

        if pos + 8 + field_len > dlen:
            pos += 1
            continue

        value = otrk_data[pos + 8: pos + 8 + field_len]
        pos += 8 + field_len

        if tag_str == 'pfil':
            try:
                file_path = value.decode('utf-16-be', errors='replace')
            except Exception:
                pass

        elif tag_str == 'uadd' and field_len == 4:
            try:
                ts = struct.unpack('>I', value)[0]
                if ts > 0:
                    add_date = datetime.fromtimestamp(ts)
            except (struct.error, OSError, OverflowError):
                pass

        elif tag_str == 'uply' and field_len == 4:
            try:
                count = struct.unpack('>I', value)[0]
                play_count = count  # 0 is valid (track added but never played)
            except struct.error:
                pass

    if file_path:
        return file_path, TrackDbEntry(add_date=add_date, play_count=play_count)
    return None
