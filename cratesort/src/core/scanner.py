from __future__ import annotations

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import mutagen

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aif', '.aiff', '.m4a', '.ogg', '.wma'}
VIDEO_EXTENSIONS = {'.mp4', '.m4v', '.mov', '.avi'}
STEMS_EXTENSION = '.serato-stems'

# Directories to skip entirely during the walk — DJ app data, macOS internals
SKIP_DIRS = frozenset({
    '_Serato_', '_Rekordbox_', 'PIONEER',
    '_CrateSort',                               # CrateSort app data directory
    '.Spotlight-V100', '.Trashes', '.fseventsd',
    '.DocumentRevisions-V100', '.TemporaryItems',
    '__pycache__', '.git',
})

# Matches a Serato version suffix like ".1.2" or ".10.3" at the end of a filename
_STEMS_VERSION_RE = re.compile(r'(\.\d+)+$')


@dataclass
class TrackRecord:
    # Filesystem
    path: Path
    parent_dir: Path
    filename: str
    extension: str
    file_size: int  # bytes

    # Media type
    is_audio: bool
    is_video: bool

    # Tags
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[str] = None
    bpm: Optional[float] = None
    comment: Optional[str] = None

    # Audio properties
    duration: Optional[float] = None   # seconds
    bitrate: Optional[int] = None      # kbps
    sample_rate: Optional[int] = None  # Hz
    codec: Optional[str] = None

    # Artwork
    has_artwork: bool = False

    # Serato
    stems_path: Optional[Path] = None

    # Scan state
    read_error: Optional[str] = None

    @property
    def has_complete_metadata(self) -> bool:
        return all([self.title, self.artist, self.genre, self.year])

    @property
    def has_partial_metadata(self) -> bool:
        return (
            any([self.title, self.artist, self.genre, self.year])
            and not self.has_complete_metadata
        )

    @property
    def has_no_metadata(self) -> bool:
        return not any([self.title, self.artist, self.genre, self.year])


@dataclass
class ScanSummary:
    root_dirs: list[Path]
    total_files: int = 0
    by_format: dict[str, int] = field(default_factory=dict)
    complete_metadata: int = 0
    partial_metadata: int = 0
    no_metadata: int = 0
    with_stems: int = 0
    orphan_stems: list[Path] = field(default_factory=list)
    unique_artists: set[str] = field(default_factory=set)
    unique_genres: set[str] = field(default_factory=set)
    read_errors: list[tuple[Path, str]] = field(default_factory=list)


class LibraryScanner:
    """
    Walks one or more root directories and catalogs every supported audio/video
    file, reading ID3/MP4/Vorbis tags via mutagen.  Results are returned as a
    list of TrackRecord dataclasses plus a ScanSummary.
    """

    def __init__(self, *root_dirs: str | Path, progress_callback=None):
        self.root_dirs = [Path(d) for d in root_dirs]
        self._progress_callback = progress_callback  # callable(files_found: int, dir_name: str)

    def scan(self) -> tuple[list[TrackRecord], ScanSummary]:
        inventory: list[TrackRecord] = []
        summary = ScanSummary(root_dirs=self.root_dirs)

        # dir -> {lowercased_base_name -> stems_path}
        stems_map: dict[Path, dict[str, Path]] = {}

        for root_dir in self.root_dirs:
            if not root_dir.exists():
                logger.warning("Root directory does not exist: %s", root_dir)
                continue
            logger.info("Scanning: %s", root_dir)
            self._walk(root_dir, inventory, stems_map)

        self._attach_stems(inventory, stems_map, summary)
        self._build_summary(inventory, summary)

        logger.info("Scan complete: %d files", summary.total_files)
        return inventory, summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _walk(
        self,
        root_dir: Path,
        inventory: list[TrackRecord],
        stems_map: dict[Path, dict[str, Path]],
    ) -> None:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Prune directories in-place so os.walk won't descend into them
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith('._')
            )
            filenames.sort()
            dir_path = Path(dirpath)

            dir_stems: dict[str, Path] = {}
            audio_video_files: list[tuple[str, str]] = []  # (filename, ext)

            for fname in filenames:
                lower = fname.lower()
                if lower.endswith(STEMS_EXTENSION):
                    base = self._stems_base(fname)
                    dir_stems[base.lower()] = dir_path / fname
                else:
                    ext = Path(fname).suffix.lower()
                    if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
                        audio_video_files.append((fname, ext))

            if dir_stems:
                stems_map[dir_path] = dir_stems

            if audio_video_files:
                logger.info("  %s — %d file(s)", dir_path.name, len(audio_video_files))
                for fname, ext in audio_video_files:
                    record = self._scan_file(dir_path / fname, ext)
                    inventory.append(record)
                    logger.debug("    %s", fname)
                if self._progress_callback:
                    self._progress_callback(len(inventory), dir_path.name)

    def _attach_stems(
        self,
        inventory: list[TrackRecord],
        stems_map: dict[Path, dict[str, Path]],
        summary: ScanSummary,
    ) -> None:
        matched_stems: set[Path] = set()

        for record in inventory:
            dir_stems = stems_map.get(record.parent_dir)
            if dir_stems:
                base_lower = record.path.stem.lower()
                stems_path = dir_stems.get(base_lower)
                if stems_path:
                    record.stems_path = stems_path
                    matched_stems.add(stems_path)

        for dir_stems in stems_map.values():
            for stems_path in dir_stems.values():
                if stems_path not in matched_stems:
                    summary.orphan_stems.append(stems_path)
                    logger.warning("Orphan stems (no matching audio): %s", stems_path)

    def _build_summary(self, inventory: list[TrackRecord], summary: ScanSummary) -> None:
        summary.total_files = len(inventory)

        for record in inventory:
            summary.by_format[record.extension] = (
                summary.by_format.get(record.extension, 0) + 1
            )

            if record.read_error:
                summary.read_errors.append((record.path, record.read_error))
            elif record.has_complete_metadata:
                summary.complete_metadata += 1
            elif record.has_partial_metadata:
                summary.partial_metadata += 1
            else:
                summary.no_metadata += 1

            if record.stems_path:
                summary.with_stems += 1

            if record.artist:
                summary.unique_artists.add(record.artist)
            if record.genre:
                summary.unique_genres.add(record.genre)

    def _stems_base(self, stems_filename: str) -> str:
        """Strip .serato-stems and any trailing Serato version suffix (e.g. .1.2)."""
        name = stems_filename[: -len(STEMS_EXTENSION)]
        return _STEMS_VERSION_RE.sub("", name)

    def _scan_file(self, path: Path, ext: str) -> TrackRecord:
        record = TrackRecord(
            path=path,
            parent_dir=path.parent,
            filename=path.name,
            extension=ext,
            file_size=path.stat().st_size,
            is_audio=(ext in AUDIO_EXTENSIONS),
            is_video=(ext in VIDEO_EXTENSIONS),
            codec=ext.lstrip(".").upper(),
        )
        try:
            self._read_tags(record, path, ext)
        except Exception as exc:
            record.read_error = str(exc)
            logger.warning("Tag read error — %s: %s", path.name, exc)
        return record

    def _read_tags(self, record: TrackRecord, path: Path, ext: str) -> None:
        audio = mutagen.File(path, easy=False)
        if audio is None:
            return

        info = getattr(audio, "info", None)
        if info:
            if hasattr(info, "length"):
                record.duration = round(info.length, 2)
            if hasattr(info, "bitrate"):
                # mutagen returns bitrate in bps; store as kbps
                record.bitrate = info.bitrate // 1000
            if hasattr(info, "sample_rate"):
                record.sample_rate = info.sample_rate

        if ext in {".mp3", ".wav", ".aif", ".aiff"}:
            self._read_id3(record, audio)
        elif ext in {".m4a", ".mp4", ".m4v", ".mov"}:
            self._read_mp4(record, audio)
        elif ext == ".flac":
            self._read_vorbis(record, audio)
        elif ext == ".ogg":
            self._read_vorbis(record, audio)
        elif ext == ".wma":
            self._read_asf(record, audio)

    # --- Format-specific readers ---

    def _read_id3(self, record: TrackRecord, audio) -> None:
        tags = getattr(audio, "tags", None)
        if tags is None:
            return
        record.title = self._id3_text(tags, "TIT2")
        record.artist = self._id3_text(tags, "TPE1")
        record.album = self._id3_text(tags, "TALB")
        record.genre = self._id3_text(tags, "TCON")
        record.year = self._id3_text(tags, "TDRC")
        record.bpm = self._id3_float(tags, "TBPM")
        record.comment = self._id3_comment(tags)
        record.has_artwork = any(k.startswith("APIC") for k in tags)

    def _read_mp4(self, record: TrackRecord, audio) -> None:
        tags = getattr(audio, "tags", None)
        if tags is None:
            return
        record.title = self._mp4_text(tags, "©nam")
        record.artist = self._mp4_text(tags, "©ART")
        record.album = self._mp4_text(tags, "©alb")
        record.genre = self._mp4_text(tags, "©gen")
        record.year = self._mp4_text(tags, "©day")
        record.comment = self._mp4_text(tags, "©cmt")
        if "tmpo" in tags:
            try:
                record.bpm = float(tags["tmpo"][0])
            except (IndexError, TypeError, ValueError):
                pass
        record.has_artwork = "covr" in tags

    def _read_vorbis(self, record: TrackRecord, audio) -> None:
        tags = getattr(audio, "tags", None)
        if tags is None:
            return
        record.title = self._vorbis_text(tags, "title")
        record.artist = self._vorbis_text(tags, "artist")
        record.album = self._vorbis_text(tags, "album")
        record.genre = self._vorbis_text(tags, "genre")
        record.year = self._vorbis_text(tags, "date")
        record.comment = self._vorbis_text(tags, "comment")
        bpm_str = self._vorbis_text(tags, "bpm")
        if bpm_str:
            try:
                record.bpm = float(bpm_str)
            except ValueError:
                pass
        record.has_artwork = bool(getattr(audio, "pictures", None))

    def _read_asf(self, record: TrackRecord, audio) -> None:
        tags = getattr(audio, "tags", None)
        if tags is None:
            return
        record.title = self._asf_text(tags, "Title")
        record.artist = self._asf_text(tags, "Author")
        record.album = self._asf_text(tags, "WM/AlbumTitle")
        record.genre = self._asf_text(tags, "WM/Genre")
        record.year = self._asf_text(tags, "WM/Year")
        record.comment = self._asf_text(tags, "Description")

    # --- Tag value coercers ---

    def _id3_text(self, tags, key: str) -> Optional[str]:
        frame = tags.get(key)
        if frame is None:
            return None
        val = str(frame).strip()
        return val or None

    def _id3_float(self, tags, key: str) -> Optional[float]:
        frame = tags.get(key)
        if frame is None:
            return None
        try:
            return float(str(frame).strip())
        except ValueError:
            return None

    def _id3_comment(self, tags) -> Optional[str]:
        for key in tags:
            if key.startswith("COMM"):
                frame = tags[key]
                text = frame.text[0].strip() if frame.text else ""
                if text:
                    return text
        return None

    def _mp4_text(self, tags, key: str) -> Optional[str]:
        val = tags.get(key)
        if val is None:
            return None
        try:
            text = str(val[0] if isinstance(val, list) else val).strip()
            return text or None
        except (IndexError, TypeError):
            return None

    def _vorbis_text(self, tags, key: str) -> Optional[str]:
        val = tags.get(key)
        if val is None:
            return None
        try:
            text = (val[0] if isinstance(val, list) else str(val)).strip()
            return text or None
        except (IndexError, TypeError):
            return None

    def _asf_text(self, tags, key: str) -> Optional[str]:
        val = tags.get(key)
        if val is None:
            return None
        try:
            text = str(val[0] if isinstance(val, list) else val).strip()
            return text or None
        except (IndexError, TypeError):
            return None
