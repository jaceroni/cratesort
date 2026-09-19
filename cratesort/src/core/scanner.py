from __future__ import annotations

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import mutagen

from cratesort.src.core import scan_cache

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.aif', '.aiff', '.m4a', '.ogg', '.wma'}
VIDEO_EXTENSIONS = {'.mp4', '.m4v', '.mov', '.avi'}
STEMS_EXTENSION = '.serato-stems'

# Parallel tag-read defaults. 3 worker processes is a safe middle ground:
# real throughput gain on a healthy drive, and one wedged worker never stalls
# the others. Higher counts hammer a struggling USB bus harder for little gain.
_DEFAULT_WORKERS = 3
# Per-file wall-clock budget in a worker. Tag data lives at the head/tail of a
# file, so a healthy read is well under a second even over USB2; anything past
# this is a stalled read and the worker gets killed, the file marked unreadable.
_DEFAULT_PER_FILE_TIMEOUT = 15.0

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

    def __init__(
        self,
        *root_dirs: str | Path,
        progress_callback=None,
        is_cancelled=None,
        workers: int | None = None,
        per_file_timeout: float | None = None,
    ):
        self.root_dirs = [Path(d) for d in root_dirs]
        self._progress_callback = progress_callback  # callable(files_found: int, label: str)
        # callable() -> bool; polled between files so a cancelled scan stops
        # promptly instead of grinding through the whole tree first.
        self._is_cancelled = is_cancelled or (lambda: False)
        # Tag reads run in a small pool of separate processes the parent can
        # kill — the only way to survive a read that wedges in an
        # uninterruptible kernel wait (failing media, flaky USB bridge, or the
        # macOS FSKit exFAT driver stalling). Overridable mostly for tests.
        self._workers = workers if workers is not None else _DEFAULT_WORKERS
        self._per_file_timeout = (
            per_file_timeout if per_file_timeout is not None else _DEFAULT_PER_FILE_TIMEOUT
        )

    def scan(self) -> tuple[list[TrackRecord], ScanSummary]:
        inventory: list[TrackRecord] = []
        summary = ScanSummary(root_dirs=self.root_dirs)
        root = self.root_dirs[0] if self.root_dirs else None
        _configure_scan_logging(root)

        # Per-file cache (path -> {size, mtime, <tag fields>}) keyed off the
        # first root dir, which is always the library root in practice —
        # lets unchanged files skip the expensive mutagen tag-read below.
        # Corrupt/missing cache -> empty dict -> identical to a full scan.
        self._cache = scan_cache.load_cache(root) if root else {}
        self._new_cache: dict[str, dict] = {}

        # dir -> {lowercased_base_name -> stems_path}
        stems_map: dict[Path, dict[str, Path]] = {}

        # ---- Phase 1: walk the tree and collect media file paths. Directory
        # traversal is cheap and rarely the thing that stalls, so it stays
        # in-process; nothing here opens a file.
        media_files: list[tuple[Path, str]] = []
        for root_dir in self.root_dirs:
            if not root_dir.exists():
                logger.warning("Root directory does not exist: %s", root_dir)
                continue
            logger.info("Scanning: %s", root_dir)
            self._walk(root_dir, media_files, stems_map)

        if self._is_cancelled():
            return inventory, summary

        # ---- Phase 2: split into cache hits (assembled here, no file opened)
        # and the files that actually need a tag read.
        to_read: list[tuple[str, str]] = []  # (path_str, ext)
        for path, ext in media_files:
            if self._is_cancelled():
                return inventory, summary
            path_str = str(path)
            try:
                st = path.stat()
            except OSError as exc:
                # stat itself failed — treat as an unreadable file and carry
                # on. Not cached, so it's retried on the next scan.
                logger.warning("stat failed — %s: %s", path.name, exc)
                inventory.append(self._blank_record(
                    path, ext, 0, read_error=f"{type(exc).__name__}: {exc}"))
                continue

            cached = self._cache.get(path_str)
            if (
                cached is not None
                and not cached.get("read_error")
                and cached.get("size") == st.st_size
                and cached.get("mtime") == st.st_mtime
            ):
                rec = self._blank_record(path, ext, st.st_size)
                for k in scan_cache.CACHED_FIELDS:
                    if k != "read_error":
                        setattr(rec, k, cached.get(k))
                inventory.append(rec)
                self._new_cache[path_str] = {
                    "size": st.st_size, "mtime": st.st_mtime,
                    **{k: getattr(rec, k) for k in scan_cache.CACHED_FIELDS},
                }
            else:
                to_read.append((path_str, ext))

        # From here on progress has a real denominator: every media file found,
        # cache hits included. `done` is how many records exist so far.
        total_files = len(inventory) + len(to_read)
        if self._progress_callback:
            self._progress_callback(
                len(inventory), total_files,
                "Reading tags…" if to_read else "Finishing up…",
            )

        # ---- Phase 3: read the rest in killable worker processes. A read that
        # wedges in an uninterruptible kernel wait (failing media, flaky USB
        # bridge, macOS FSKit exFAT stall) costs one file and a kill, not a
        # frozen app.
        if to_read and not self._is_cancelled():
            from cratesort.src.core.parallel_tag_reader import ParallelTagReader

            def _on_result(path_str: str, ext: str, fields: dict) -> None:
                p = Path(path_str)
                rec = self._blank_record(
                    p, ext, fields.get("_size") or 0,
                    read_error=fields.get("read_error"),
                )
                for k in scan_cache.CACHED_FIELDS:
                    if k != "read_error":
                        setattr(rec, k, fields.get(k))
                inventory.append(rec)
                if rec.read_error:
                    logger.warning("Tag read error — %s: %s", p.name, rec.read_error)
                else:
                    self._new_cache[path_str] = {
                        "size": fields.get("_size") or 0,
                        "mtime": fields.get("_mtime") or 0,
                        **{k: getattr(rec, k) for k in scan_cache.CACHED_FIELDS},
                    }

            def _on_progress(done: int, _total: int, current: str) -> None:
                # Report against the true file total, not just this phase's
                # slice, and count every record built so far (cache hits too).
                if self._progress_callback:
                    self._progress_callback(
                        len(inventory), total_files, Path(current).name)

            reader = ParallelTagReader(
                workers=self._workers,
                per_file_timeout=self._per_file_timeout,
            )
            reader.read(to_read, _on_result, _on_progress, self._is_cancelled)

        self._attach_stems(inventory, stems_map, summary)
        self._build_summary(inventory, summary)

        if root:
            scan_cache.save_cache(root, self._new_cache)
            _write_unreadable_report(root, summary.read_errors)

        logger.info(
            "Scan complete: %d files (%d unreadable)",
            summary.total_files, len(summary.read_errors),
        )
        return inventory, summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _blank_record(
        self, path: Path, ext: str, size: int, *, read_error: Optional[str] = None,
    ) -> TrackRecord:
        return TrackRecord(
            path=path,
            parent_dir=path.parent,
            filename=path.name,
            extension=ext,
            file_size=size,
            is_audio=(ext in AUDIO_EXTENSIONS),
            is_video=(ext in VIDEO_EXTENSIONS),
            codec=ext.lstrip(".").upper(),
            read_error=read_error,
        )

    def _walk(
        self,
        root_dir: Path,
        media_files: list[tuple[Path, str]],
        stems_map: dict[Path, dict[str, Path]],
    ) -> None:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            if self._is_cancelled():
                return
            # Prune directories in-place so os.walk won't descend into them
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith('._')
            )
            filenames.sort()
            dir_path = Path(dirpath)

            dir_stems: dict[str, Path] = {}
            found_here = 0

            for fname in filenames:
                lower = fname.lower()
                if lower.endswith(STEMS_EXTENSION):
                    base = self._stems_base(fname)
                    dir_stems[base.lower()] = dir_path / fname
                elif not fname.startswith('._'):
                    ext = Path(fname).suffix.lower()
                    if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
                        media_files.append((dir_path / fname, ext))
                        found_here += 1

            if dir_stems:
                stems_map[dir_path] = dir_stems

            if found_here:
                logger.info("  %s — %d file(s)", dir_path.name, found_here)
                # Discovery has no meaningful denominator yet, so report a
                # count of 0 (the numeric progress card stays put) and let the
                # label carry the news that we're still finding files.
                if self._progress_callback:
                    self._progress_callback(
                        0, -1, f"Finding files — {dir_path.name}")

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


# ----------------------------------------------------------------------------
# Module-level helpers — shared by the in-process path and the worker process
# ----------------------------------------------------------------------------

# One throwaway LibraryScanner just to reach the stateless _read_tags/_read_*
# coercer methods. They never touch instance state, so a single shared instance
# is safe both in the app and inside a worker process.
_TAG_READER = LibraryScanner()


def read_one_file(path: Path, ext: str) -> dict:
    """Read tag/audio fields for a single file into a plain dict keyed by
    scan_cache.CACHED_FIELDS. Any failure is captured as ``read_error`` rather
    than raised, so the caller (in-process or across a pipe) always gets a
    result. This is the single tag-read code path."""
    record = TrackRecord(
        path=path,
        parent_dir=path.parent,
        filename=path.name,
        extension=ext,
        file_size=0,
        is_audio=(ext in AUDIO_EXTENSIONS),
        is_video=(ext in VIDEO_EXTENSIONS),
        codec=ext.lstrip(".").upper(),
    )
    try:
        _TAG_READER._read_tags(record, path, ext)
    except Exception as exc:  # noqa: BLE001 — deliberately catch-all; see docstring
        record.read_error = f"{type(exc).__name__}: {exc}"
    return {k: getattr(record, k) for k in scan_cache.CACHED_FIELDS}


def _write_unreadable_report(
    library_root: Path, read_errors: list[tuple[Path, str]],
) -> None:
    """Drop a plain-text list of the files the scan couldn't read at
    <root>/_CrateSort/logs/unreadable-files.txt so the user can see exactly
    which tracks were skipped (and why) without digging through the log.
    Removed when a later scan reads everything cleanly."""
    report = Path(library_root) / "_CrateSort" / "logs" / "unreadable-files.txt"
    try:
        if not read_errors:
            report.unlink(missing_ok=True)
            return
        report.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"{len(read_errors)} file(s) could not be read during the last scan.",
            "This usually means the drive, its cable, or the OS filesystem "
            "driver stalled on these files — not that CrateSort is broken.",
            "",
        ]
        for path, err in read_errors:
            lines.append(f"{path}")
            lines.append(f"    -> {err}")
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:  # never let reporting break a finished scan
        logger.warning("Could not write unreadable-files.txt: %s", exc)


_SCAN_LOG_CONFIGURED = False


def _configure_scan_logging(library_root: Optional[Path]) -> None:
    """Attach a rotating file handler under <root>/_CrateSort/logs/scan.log the
    first time a scan runs, so a stall is always diagnosable after the fact —
    the last line names the file it died on. No-op if there's no root or it's
    already wired."""
    global _SCAN_LOG_CONFIGURED
    if _SCAN_LOG_CONFIGURED or library_root is None:
        return
    try:
        from logging.handlers import RotatingFileHandler

        logs_dir = Path(library_root) / "_CrateSort" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            logs_dir / "scan.log", maxBytes=2_000_000, backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s"))
        pkg_logger = logging.getLogger("cratesort")
        pkg_logger.addHandler(handler)
        if pkg_logger.level == logging.NOTSET or pkg_logger.level > logging.INFO:
            pkg_logger.setLevel(logging.INFO)
        _SCAN_LOG_CONFIGURED = True
    except Exception as exc:  # logging must never take the app down
        logger.warning("Could not set up scan.log: %s", exc)
