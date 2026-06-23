from __future__ import annotations

import base64
import logging
import struct
from pathlib import Path

from cratesort.src.serato.markers_reader import CuePoint, _MARKERS2_DESC

logger = logging.getLogger(__name__)


def write_cue_points(file_path: str | Path, cue_points: list[CuePoint]) -> bool:
    """
    Write `cue_points` into the `GEOB:Serato Markers2` frame of an MP3/AIFF file.

    Reads the existing Markers2 frame, replaces only the CUE entries with the
    provided list, and preserves all other entry types (LOOP, COLOR, BPMLOCK).

    Returns True on success, False on any error. Never raises.
    """
    file_path = Path(file_path)
    ext = file_path.suffix.lower()

    if ext not in ('.mp3', '.aiff', '.aif'):
        logger.debug('[MarkersWriter] Unsupported format for cue write: %s', ext)
        return False

    try:
        return _write_id3_cues(file_path, cue_points)
    except Exception as exc:
        logger.warning('[MarkersWriter] Failed to write cues to %s: %s', file_path, exc)
        return False


# ---------------------------------------------------------------------------
# ID3 path (MP3 / AIFF)
# ---------------------------------------------------------------------------

def _write_id3_cues(file_path: Path, new_cues: list[CuePoint]) -> bool:
    import mutagen.id3 as id3_mod

    try:
        tags = id3_mod.ID3(str(file_path))
    except id3_mod.ID3NoHeaderError:
        tags = id3_mod.ID3()

    # Find and decode the existing Markers2 frame
    existing_frame = None
    existing_key   = None
    for key in tags:
        frame = tags[key]
        if getattr(frame, 'desc', None) == _MARKERS2_DESC:
            existing_frame = frame
            existing_key   = key
            break

    # Decode existing non-CUE entries to preserve them (LOOP, COLOR, BPMLOCK, etc.)
    preserved_entries: list[tuple[str, bytes]] = []
    version_header = b'\x01\x01'

    if existing_frame is not None:
        parsed = _decode_markers2_entries(existing_frame.data)
        if parsed is not None:
            version_header, entries = parsed
            preserved_entries = [(t, d) for t, d in entries if t != 'CUE']

    # Build new CUE entries for the provided cue points
    cue_entries = [_encode_cue_entry(c) for c in sorted(new_cues, key=lambda c: c.index)]

    # Serialize all entries: preserved non-CUE + new CUE entries
    body = bytearray(version_header)
    for entry_type, entry_data in preserved_entries:
        body += _encode_entry(entry_type, entry_data)
    for cue_data in cue_entries:
        body += _encode_entry('CUE', cue_data)

    # Base64-encode with linefeeds every 72 chars (Serato's encoding style)
    b64 = base64.b64encode(bytes(body))
    wrapped = b'\n'.join(b64[i:i + 72] for i in range(0, len(b64), 72))

    # Write back as a GEOB frame
    new_frame = id3_mod.GEOB(
        encoding=0,
        mime='application/octet-stream',
        filename='',
        desc=_MARKERS2_DESC,
        data=wrapped,
    )

    if existing_key:
        tags[existing_key] = new_frame
    else:
        tags.add(new_frame)

    tags.save(str(file_path), v2_version=3)
    return True


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _encode_entry(entry_type: str, data: bytes) -> bytes:
    """Serialize one Markers2 entry: null-terminated type + uint32 BE length + data."""
    out = bytearray()
    out += entry_type.encode('ascii') + b'\x00'
    out += struct.pack('>I', len(data))
    out += data
    return bytes(out)


def _encode_cue_entry(cue: CuePoint) -> bytes:
    """
    Serialize a CUE entry data block (13+ bytes):
      [0]    0x00 padding
      [1]    index uint8
      [2:6]  position uint32 BE (ms)
      [6]    0x00 padding
      [7:10] color RGB
      [10:12] 0x00 0x00 padding
      [12:]  name null-terminated UTF-8
    """
    r, g, b = cue.color_rgb
    name_bytes = cue.name.encode('utf-8') + b'\x00'
    data = bytearray(12 + len(name_bytes))
    data[0]  = 0x00
    data[1]  = cue.index & 0xFF
    struct.pack_into('>I', data, 2, cue.position_ms)
    data[6]  = 0x00
    data[7]  = r
    data[8]  = g
    data[9]  = b
    data[10] = 0x00
    data[11] = 0x00
    data[12:] = name_bytes
    return bytes(data)


def _decode_markers2_entries(
    raw_data: bytes,
) -> tuple[bytes, list[tuple[str, bytes]]] | None:
    """
    Decode a Markers2 GEOB frame's raw bytes into (version_header, [(type, data)]).
    Returns None on decode failure.
    """
    try:
        stripped  = raw_data.lstrip(b'\x00\xfe\xff')
        b64_clean = stripped.replace(b'\n', b'').replace(b'\r', b'')
        pad       = (4 - len(b64_clean) % 4) % 4
        decoded   = base64.b64decode(b64_clean + b'=' * pad)
    except Exception:
        return None

    if len(decoded) < 2:
        return None

    version_header = decoded[:2]
    pos    = 2
    dlen   = len(decoded)
    entries: list[tuple[str, bytes]] = []

    while pos < dlen:
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

        entries.append((entry_type, decoded[pos: pos + entry_len]))
        pos += entry_len

    return version_header, entries
