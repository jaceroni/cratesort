"""Copy tag metadata (including embedded artwork) from a source media file onto
a freshly-converted output file, so descriptive tags survive format conversion."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SERATO_GEOB_PREFIX = 'Serato '

_MP4_TAG_EXTS = {'.mov', '.mp4', '.m4v'}


def copy_audio_tags(src: Path, dst: Path) -> None:
    """
    Copy every ID3 frame (title, artist, album, genre, year, comments, artwork,
    custom tags, etc.) from a WAV/AIFF/MP3 source onto a newly-converted MP3.

    Serato's own analysis caches (GEOB frames named e.g. "Serato Analysis",
    "Serato Markers2", "Serato BeatGrid") are skipped deliberately — they encode
    exact sample positions in the *original* audio, which shift once re-encoded,
    so carrying them over verbatim would show Serato stale/incorrect cue points
    and beatgrid until it re-analyzes the file anyway.
    """
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, ID3NoHeaderError

    try:
        src_file = MutagenFile(str(src))
    except Exception:
        logger.warning('Could not read tags from %s', src)
        return
    if not src_file or not getattr(src_file, 'tags', None):
        return

    try:
        dst_id3 = ID3(str(dst))
    except ID3NoHeaderError:
        dst_id3 = ID3()
    except Exception:
        logger.warning('Could not open %s for tagging', dst)
        return

    for frame in src_file.tags.values():
        if frame.FrameID == 'GEOB' and str(getattr(frame, 'desc', '')).startswith(_SERATO_GEOB_PREFIX):
            continue
        try:
            dst_id3.add(frame)
        except Exception:
            pass

    try:
        dst_id3.save(str(dst), v2_version=3)
    except Exception:
        logger.warning('Could not save tags to %s', dst)


def copy_video_tags(src: Path, dst: Path) -> None:
    """
    Best-effort copy of MP4/QuickTime atoms (title, artist, cover art, etc.)
    from a MOV/MP4/M4V source onto a newly-converted MP4.

    Only the MP4 atom family is supported here — mutagen has no tag reader for
    MKV/AVI/WMV/WEBM/FLV/MPG, so for those source formats whatever global
    metadata ffmpeg itself carried over (via -map_metadata) is all that survives.
    """
    if src.suffix.lower() not in _MP4_TAG_EXTS:
        return

    from mutagen.mp4 import MP4

    try:
        src_mp4 = MP4(str(src))
    except Exception:
        return
    if not src_mp4.tags:
        return

    try:
        dst_mp4 = MP4(str(dst))
    except Exception:
        logger.warning('Could not open %s for tagging', dst)
        return
    if dst_mp4.tags is None:
        dst_mp4.add_tags()

    for key, value in src_mp4.tags.items():
        dst_mp4.tags[key] = value

    try:
        dst_mp4.save()
    except Exception:
        logger.warning('Could not save tags to %s', dst)


def _detect_image_format(data: bytes) -> str:
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    return 'jpeg'


def embed_artwork(dst: Path, fmt: str, artwork_path: Path) -> None:
    """Embed a user-chosen image as cover art on a media file — 'mp3' writes an
    ID3 APIC frame, anything else writes an MP4 'covr' atom. Used where there's
    no source file to inherit artwork from (e.g. YouTube imports)."""
    data = artwork_path.read_bytes()
    img_fmt = _detect_image_format(data)

    if fmt == 'mp3':
        from mutagen.id3 import ID3, ID3NoHeaderError, APIC
        try:
            tags = ID3(str(dst))
        except ID3NoHeaderError:
            tags = ID3()
        except Exception:
            logger.warning('Could not open %s for artwork', dst)
            return
        tags.delall('APIC')
        mime = 'image/png' if img_fmt == 'png' else 'image/jpeg'
        tags.add(APIC(encoding=3, mime=mime, type=3, desc='cover', data=data))
        try:
            tags.save(str(dst), v2_version=3)
        except Exception:
            logger.warning('Could not save artwork to %s', dst)
    else:
        from mutagen.mp4 import MP4, MP4Cover
        try:
            video = MP4(str(dst))
        except Exception:
            logger.warning('Could not open %s for artwork', dst)
            return
        if video.tags is None:
            video.add_tags()
        cover_format = MP4Cover.FORMAT_PNG if img_fmt == 'png' else MP4Cover.FORMAT_JPEG
        video.tags['covr'] = [MP4Cover(data, imageformat=cover_format)]
        try:
            video.save()
        except Exception:
            logger.warning('Could not save artwork to %s', dst)
