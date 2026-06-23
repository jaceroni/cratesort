from __future__ import annotations

import base64
import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MARKERS2_DESC = 'Serato Markers2'
_MARKERS1_DESC = 'Serato Markers_'


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CuePoint:
    index:       int            # 0-7
    position_ms: int            # milliseconds from start
    color_rgb:   tuple[int, int, int]  # (R, G, B)
    name:        str            # empty string if unnamed

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CuePoint):
            return NotImplemented
        return self.index == other.index and self.position_ms == other.position_ms

    def __hash__(self) -> int:
        return hash((self.index, self.position_ms))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_cue_points(file_path: str | Path) -> list[CuePoint]:
    """
    Read hot cue points from a track's embedded Serato metadata.

    Tries Markers2 first (the current Serato format), falls back to
    Markers_ (legacy, first 5 cues only) if Markers2 is absent.

    Returns a list of CuePoint objects sorted by index.
    Never raises — returns [] on any error or unsupported format.
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    try:
        if ext in ('.mp3', '.aiff', '.aif'):
            return _read_id3_cues(file_path)
        # FLAC and MP4 cue-point support is future scope
        logger.debug('[MarkersReader] Unsupported format for cue read: %s', ext)
        return []
    except Exception as exc:
        logger.warning('[MarkersReader] Failed to read cues from %s: %s', file_path, exc)
        return []


# ---------------------------------------------------------------------------
# ID3 path (MP3 / AIFF)
# ---------------------------------------------------------------------------

def _read_id3_cues(file_path: Path) -> list[CuePoint]:
    import mutagen.id3 as id3_mod
    try:
        tags = id3_mod.ID3(str(file_path))
    except id3_mod.ID3NoHeaderError:
        return []

    # Try Markers2 first
    for key in tags:
        frame = tags[key]
        if getattr(frame, 'desc', None) == _MARKERS2_DESC:
            cues = _parse_markers2(frame.data)
            if cues is not None:
                return sorted(cues, key=lambda c: c.index)

    # Fall back to Markers_ (legacy, cues 0-4 only)
    for key in tags:
        frame = tags[key]
        if getattr(frame, 'desc', None) == _MARKERS1_DESC:
            cues = _parse_markers1(frame.data)
            if cues is not None:
                return sorted(cues, key=lambda c: c.index)

    return []


# ---------------------------------------------------------------------------
# Markers2 parser
# ---------------------------------------------------------------------------
#
# Binary layout after base64 decode (no padding, linefeeds every 72 chars):
#   Byte 0:   version major (0x01)
#   Byte 1:   version minor (0x01)
#   Then a sequence of entries:
#     - null-terminated ASCII type string (e.g. b"CUE\x00")
#     - uint32 big-endian: length of following data
#     - data bytes
#
# CUE entry data (always 13+ bytes):
#   [0]    0x00 padding
#   [1]    index: uint8 (0-7)
#   [2:6]  position: uint32 big-endian (milliseconds)
#   [6]    0x00 padding
#   [7:10] color: 3 bytes RGB
#   [10:12] 0x00 0x00 padding
#   [12:]  name: null-terminated UTF-8 (may be empty, i.e. just \x00)
#
# Source: Holzhaus/serato-tags reverse engineering reference.

def _parse_markers2(raw_data: bytes) -> Optional[list[CuePoint]]:
    try:
        # Strip any BOM or leading null bytes before the base64 content
        stripped = raw_data.lstrip(b'\x00\xfe\xff')
        b64_clean = stripped.replace(b'\n', b'').replace(b'\r', b'')
        # Add padding if needed
        pad = (4 - len(b64_clean) % 4) % 4
        decoded = base64.b64decode(b64_clean + b'=' * pad)
    except Exception as exc:
        logger.debug('[MarkersReader] Markers2 base64 decode failed: %s', exc)
        return None

    if len(decoded) < 2:
        return None

    # Skip 2-byte version header
    pos  = 2
    dlen = len(decoded)
    cues: list[CuePoint] = []

    while pos < dlen:
        # Read null-terminated type string
        null = decoded.find(b'\x00', pos)
        if null < 0:
            break
        entry_type = decoded[pos:null].decode('ascii', errors='replace')
        pos = null + 1

        if pos + 4 > dlen:
            break

        entry_len = struct.unpack('>I', decoded[pos:pos + 4])[0]
        pos += 4

        if pos + entry_len > dlen:
            break

        entry_data = decoded[pos: pos + entry_len]
        pos += entry_len

        if entry_type == 'CUE':
            cue = _parse_cue_entry(entry_data)
            if cue is not None:
                cues.append(cue)

    return cues


def _parse_cue_entry(data: bytes) -> Optional[CuePoint]:
    if len(data) < 13:
        return None
    try:
        index       = data[1]
        position_ms = struct.unpack('>I', data[2:6])[0]
        r, g, b     = data[7], data[8], data[9]
        # Name starts at byte 12, null-terminated
        name_bytes = data[12:]
        null = name_bytes.find(b'\x00')
        name = name_bytes[:null].decode('utf-8', errors='replace') if null >= 0 else ''
        return CuePoint(index=index, position_ms=position_ms, color_rgb=(r, g, b), name=name)
    except (IndexError, struct.error):
        return None


# ---------------------------------------------------------------------------
# Markers_ parser (legacy — cues 0-4 only)
# ---------------------------------------------------------------------------
#
# Binary layout (not base64):
#   Sequence of typed entries, each:
#     - null-terminated ASCII type: "CUE\x00", "LOOP\x00", "COLOR\x00"
#     - For CUE: 17 bytes
#         [0:4]  position: uint32 little-endian (ms)
#         [4]    0x7F padding
#         [5:8]  color RGB
#         [8]    0x00
#         [9:]   name UTF-8 null-terminated
#
# Source: Holzhaus/serato-tags reference.

def _parse_markers1(raw_data: bytes) -> Optional[list[CuePoint]]:
    try:
        stripped = raw_data.lstrip(b'\x00\xfe\xff')
        b64_clean = stripped.replace(b'\n', b'').replace(b'\r', b'')
        pad = (4 - len(b64_clean) % 4) % 4
        decoded = base64.b64decode(b64_clean + b'=' * pad)
    except Exception:
        # Markers_ is sometimes stored as raw bytes, not base64
        decoded = raw_data

    pos  = 0
    dlen = len(decoded)
    cues: list[CuePoint] = []
    index = 0  # Markers_ doesn't embed cue index — they're sequential

    while pos < dlen and index < 5:
        null = decoded.find(b'\x00', pos)
        if null < 0:
            break
        entry_type = decoded[pos:null].decode('ascii', errors='replace')
        pos = null + 1

        if entry_type == 'CUE':
            if pos + 9 > dlen:
                break
            try:
                position_ms = struct.unpack('<I', decoded[pos:pos + 4])[0]
                r, g, b     = decoded[pos + 5], decoded[pos + 6], decoded[pos + 7]
                pos += 9
                # Name follows, null-terminated
                null2 = decoded.find(b'\x00', pos)
                name = decoded[pos:null2].decode('utf-8', errors='replace') if null2 >= 0 else ''
                pos = null2 + 1 if null2 >= 0 else dlen
                cues.append(CuePoint(index=index, position_ms=position_ms,
                                     color_rgb=(r, g, b), name=name))
                index += 1
            except (IndexError, struct.error):
                break

        elif entry_type in ('LOOP', 'COLOR'):
            # Skip — we only care about CUE entries here
            # LOOP: 17+ bytes; COLOR: 8 bytes — advance past the block
            null2 = decoded.find(b'\x00', pos)
            if null2 >= 0:
                pos = null2 + 1
            else:
                break

    return cues if cues else None
