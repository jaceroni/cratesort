"""Copy tag metadata (including embedded artwork) from a source media file onto
a freshly-converted output file, so descriptive tags survive format conversion."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_SERATO_GEOB_PREFIX = 'Serato '

_MP4_TAG_EXTS = {'.mov', '.mp4', '.m4v'}

# M4A/MP4 audio atoms are plain values (str/int/MP4Cover), not ID3 Frame
# objects — map the common ones onto their ID3 equivalents so title/artist/
# album/artwork still survive an M4A -> MP3 conversion.
_MP4_ATOM_TO_ID3_TEXT = {
    '\xa9nam': 'TIT2', '\xa9ART': 'TPE1', '\xa9alb': 'TALB',
    '\xa9gen': 'TCON', '\xa9day': 'TDRC', '\xa9wrt': 'TCOM', '\xa9grp': 'TIT1',
}


def _copy_id3_tags(src_file, dst_id3) -> None:
    for frame in src_file.tags.values():
        if frame.FrameID == 'GEOB' and str(getattr(frame, 'desc', '')).startswith(_SERATO_GEOB_PREFIX):
            continue
        try:
            dst_id3.add(frame)
        except Exception:
            pass


def _copy_mp4_tags_as_id3(src_file, dst_id3) -> None:
    from mutagen.id3 import APIC, Frames

    for atom, frame_id in _MP4_ATOM_TO_ID3_TEXT.items():
        values = src_file.tags.get(atom)
        if not values:
            continue
        text = '; '.join(str(v) for v in values)
        try:
            dst_id3.add(Frames[frame_id](encoding=3, text=text))
        except Exception:
            pass

    for cover in src_file.tags.get('covr', []):
        mime = 'image/png' if cover.imageformat == cover.FORMAT_PNG else 'image/jpeg'
        try:
            dst_id3.add(APIC(encoding=3, mime=mime, type=3, desc='cover', data=bytes(cover)))
        except Exception:
            pass


def copy_audio_tags(src: Path, dst: Path) -> None:
    """
    Copy tags (title, artist, album, genre, year, comments, artwork, custom
    tags, etc.) from a WAV/AIFF/MP3/M4A source onto a newly-converted MP3.

    WAV/AIFF/MP3 sources carry native ID3 frames, copied as-is. M4A sources
    carry MP4 atoms instead, which are mapped onto their ID3 equivalents.

    Serato's own analysis caches (GEOB frames named e.g. "Serato Analysis",
    "Serato Markers2", "Serato BeatGrid") are skipped deliberately — they encode
    exact sample positions in the *original* audio, which shift once re-encoded,
    so carrying them over verbatim would show Serato stale/incorrect cue points
    and beatgrid until it re-analyzes the file anyway.
    """
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, ID3NoHeaderError
    from mutagen.mp4 import MP4Tags

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

    if isinstance(src_file.tags, MP4Tags):
        _copy_mp4_tags_as_id3(src_file, dst_id3)
    else:
        _copy_id3_tags(src_file, dst_id3)

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
