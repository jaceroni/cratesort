from __future__ import annotations

import logging
import shutil
import struct
from pathlib import Path
from typing import Optional

from cratesort.src.serato.database_reader import _normalize_pfil_keys

logger = logging.getLogger(__name__)

_DB_FILENAME = 'database V2'


def update_play_count(
    serato_dir: str | Path,
    file_path_posix: str,
    new_play_count: int,
) -> bool:
    """
    Update (or insert) the `uply` field for one track in Serato's `database V2`.

    Writes atomically: patches a temp file, then renames it over the original.
    Creates a .bak backup before writing.

    Returns True on success, False if the track was not found or on any error.
    Never raises.
    """
    serato_dir = Path(serato_dir)
    db_path    = serato_dir / _DB_FILENAME

    if not db_path.exists():
        logger.warning('[DatabaseWriter] database V2 not found at %s', db_path)
        return False

    try:
        data = db_path.read_bytes()
    except OSError as exc:
        logger.warning('[DatabaseWriter] Cannot read %s: %s', db_path, exc)
        return False

    # Build lookup keys for this file path (same normalization as reader)
    target_keys = set(_normalize_pfil_keys(file_path_posix))

    patched, new_data = _patch_uply(data, target_keys, new_play_count)
    if not patched:
        logger.warning(
            '[DatabaseWriter] Track not found in database V2: %s', file_path_posix
        )
        return False

    try:
        bak_path = db_path.with_suffix('.bak')
        shutil.copy2(db_path, bak_path)

        tmp_path = db_path.with_suffix('.tmp')
        tmp_path.write_bytes(new_data)
        tmp_path.rename(db_path)

        logger.info(
            '[DatabaseWriter] Updated play_count=%d for %s', new_play_count, file_path_posix
        )
        return True
    except OSError as exc:
        logger.warning('[DatabaseWriter] Write failed for %s: %s', db_path, exc)
        return False


# ---------------------------------------------------------------------------
# Binary patcher
# ---------------------------------------------------------------------------

def _patch_uply(
    data: bytes,
    target_keys: set[str],
    new_play_count: int,
) -> tuple[bool, bytes]:
    """
    Scan `data` for the `otrk` record matching any key in `target_keys`.
    Within that record, update or insert a `uply` field with `new_play_count`.
    Returns (patched: bool, new_data: bytes).
    """
    out   = bytearray()
    pos   = 0
    length = len(data)
    found  = False

    while pos + 8 <= length:
        tag = data[pos:pos + 4]
        try:
            tag_str = tag.decode('ascii')
        except (UnicodeDecodeError, ValueError):
            out.append(data[pos])
            pos += 1
            continue

        if not all(32 <= b < 127 for b in tag):
            out.append(data[pos])
            pos += 1
            continue

        try:
            record_len = struct.unpack('>I', data[pos + 4:pos + 8])[0]
        except struct.error:
            out.append(data[pos])
            pos += 1
            continue

        if pos + 8 + record_len > length:
            out.append(data[pos])
            pos += 1
            continue

        record_data = data[pos + 8: pos + 8 + record_len]

        if tag_str == 'otrk' and not found:
            file_path = _extract_pfil(record_data)
            if file_path and _matches(file_path, target_keys):
                patched_record = _patch_otrk_uply(record_data, new_play_count)
                out += tag
                out += struct.pack('>I', len(patched_record))
                out += patched_record
                pos += 8 + record_len
                found = True
                continue

        out += data[pos: pos + 8 + record_len]
        pos += 8 + record_len

    # Append any trailing bytes that didn't form a full record
    out += data[pos:]

    return found, bytes(out)


def _extract_pfil(otrk_data: bytes) -> Optional[str]:
    """Extract the pfil (file path) string from an otrk record's TLV fields."""
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
                return value.decode('utf-16-be', errors='replace')
            except Exception:
                return None

    return None


def _matches(file_path: str, target_keys: set[str]) -> bool:
    from cratesort.src.serato.database_reader import _normalize_pfil_keys
    for key in _normalize_pfil_keys(file_path):
        if key in target_keys:
            return True
    return False


def _patch_otrk_uply(otrk_data: bytes, new_play_count: int) -> bytes:
    """
    Return a new otrk record body with the `uply` field set to `new_play_count`.
    If `uply` already exists, it is updated in place.
    If it doesn't exist, it is appended at the end of the record.
    All other fields are preserved unchanged.
    """
    out          = bytearray()
    pos          = 0
    dlen         = len(otrk_data)
    uply_written = False

    while pos + 8 <= dlen:
        tag = otrk_data[pos:pos + 4]
        try:
            tag_str = tag.decode('ascii')
        except (UnicodeDecodeError, ValueError):
            out.append(otrk_data[pos])
            pos += 1
            continue

        if not all(32 <= b < 127 for b in tag):
            out.append(otrk_data[pos])
            pos += 1
            continue

        try:
            field_len = struct.unpack('>I', otrk_data[pos + 4:pos + 8])[0]
        except struct.error:
            out.append(otrk_data[pos])
            pos += 1
            continue

        if pos + 8 + field_len > dlen:
            out.append(otrk_data[pos])
            pos += 1
            continue

        if tag_str == 'uply':
            # Replace existing uply with new value
            out += b'uply'
            out += struct.pack('>I', 4)
            out += struct.pack('>I', new_play_count)
            uply_written = True
        else:
            out += otrk_data[pos: pos + 8 + field_len]

        pos += 8 + field_len

    # Append any partial trailing bytes
    out += otrk_data[pos:]

    if not uply_written:
        # Insert uply at the end of the record
        out += b'uply'
        out += struct.pack('>I', 4)
        out += struct.pack('>I', new_play_count)

    return bytes(out)
