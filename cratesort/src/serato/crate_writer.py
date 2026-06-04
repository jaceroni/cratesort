from __future__ import annotations

import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, '/opt/homebrew/lib/python3.14/site-packages')
from serato_crate import SeratoCrate
from serato_crate.crate_file import read_crate_file, write_crate_file

logger = logging.getLogger(__name__)

SUBCRATES_DIR = 'Subcrates'
BACKUP_DIR = '_CrateSort_Backups'
CRATE_VERSION = '1.0/Serato ScratchLive Crate'


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CrateWriteResult:
    success: bool
    operation: str
    crate_name: str
    tracks_affected: int = 0
    backup_path: Optional[Path] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class CrateWriter:
    """
    Writes and modifies Serato .crate files.

    Safety guarantees:
    - Writes are atomic: temp file → rename, so a crash mid-write never
      corrupts an existing crate.
    - Every write to an existing file creates a timestamped backup first.
    - Column display settings (osrt/ovct records) are preserved when modifying
      existing crates via the raw format functions.
    - NEVER deletes audio files — only crate membership.
    """

    def __init__(self, serato_dir: str | Path):
        self._serato_dir = Path(serato_dir)
        self._subcrates_dir = self._serato_dir / SUBCRATES_DIR
        self._backup_dir = self._serato_dir / BACKUP_DIR

    # ── Public API ────────────────────────────────────────────────────────────

    def create_crate(
        self,
        crate_path: str,
        tracks: Optional[list[str]] = None,
    ) -> CrateWriteResult:
        """Create a new .crate file.  Fails if it already exists."""
        file_path = self._to_filepath(crate_path)
        if file_path.exists():
            return CrateWriteResult(
                success=False,
                operation='create',
                crate_name=crate_path,
                error=f'Crate already exists: {file_path.name}',
            )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        track_list = tracks or []
        crate = SeratoCrate()
        crate.tracks = [Path(t) for t in track_list]
        self._write_atomic(file_path, crate.crate_data)

        logger.info("Created crate: %s (%d tracks)", crate_path, len(track_list))
        return CrateWriteResult(
            success=True,
            operation='create',
            crate_name=crate_path,
            tracks_affected=len(track_list),
        )

    def add_tracks(
        self, crate_path: str, tracks: list[str]
    ) -> CrateWriteResult:
        """Append tracks to an existing crate (deduplicates)."""
        file_path = self._to_filepath(crate_path)
        if not file_path.exists():
            return self._not_found(crate_path, 'add_tracks')

        backup = self._backup(file_path)
        raw_data = read_crate_file(file_path)
        existing = self._extract_tracks(raw_data)
        existing_set = set(existing)
        new_tracks = [t for t in tracks if t not in existing_set]

        if not new_tracks:
            return CrateWriteResult(
                success=True,
                operation='add_tracks',
                crate_name=crate_path,
                tracks_affected=0,
                backup_path=backup,
            )

        updated = existing + new_tracks
        self._write_atomic(file_path, self._rebuild_data(raw_data, updated))

        logger.info("Added %d tracks to crate: %s", len(new_tracks), crate_path)
        return CrateWriteResult(
            success=True,
            operation='add_tracks',
            crate_name=crate_path,
            tracks_affected=len(new_tracks),
            backup_path=backup,
        )

    def remove_tracks(
        self, crate_path: str, tracks: list[str]
    ) -> CrateWriteResult:
        """Remove specific tracks from an existing crate."""
        file_path = self._to_filepath(crate_path)
        if not file_path.exists():
            return self._not_found(crate_path, 'remove_tracks')

        backup = self._backup(file_path)
        raw_data = read_crate_file(file_path)
        existing = self._extract_tracks(raw_data)
        remove_set = set(tracks)
        updated = [t for t in existing if t not in remove_set]
        removed_count = len(existing) - len(updated)

        self._write_atomic(file_path, self._rebuild_data(raw_data, updated))

        logger.info("Removed %d tracks from crate: %s", removed_count, crate_path)
        return CrateWriteResult(
            success=True,
            operation='remove_tracks',
            crate_name=crate_path,
            tracks_affected=removed_count,
            backup_path=backup,
        )

    def rename_crate(
        self, old_path: str, new_path: str
    ) -> CrateWriteResult:
        """Rename a crate by creating a new file and deleting the old one."""
        old_file = self._to_filepath(old_path)
        new_file = self._to_filepath(new_path)

        if not old_file.exists():
            return self._not_found(old_path, 'rename')
        if new_file.exists():
            return CrateWriteResult(
                success=False,
                operation='rename',
                crate_name=old_path,
                error=f'Destination already exists: {new_file.name}',
            )

        backup = self._backup(old_file)
        new_file.parent.mkdir(parents=True, exist_ok=True)
        raw_data = read_crate_file(old_file)
        self._write_atomic(new_file, raw_data)
        old_file.unlink()

        logger.info("Renamed crate: %s → %s", old_path, new_path)
        return CrateWriteResult(
            success=True,
            operation='rename',
            crate_name=new_path,
            backup_path=backup,
        )

    def duplicate_crate(
        self, source_path: str, dest_path: str
    ) -> CrateWriteResult:
        """Copy a crate's contents to a new name."""
        src_file = self._to_filepath(source_path)
        dst_file = self._to_filepath(dest_path)

        if not src_file.exists():
            return self._not_found(source_path, 'duplicate')
        if dst_file.exists():
            return CrateWriteResult(
                success=False,
                operation='duplicate',
                crate_name=source_path,
                error=f'Destination already exists: {dst_file.name}',
            )

        dst_file.parent.mkdir(parents=True, exist_ok=True)
        raw_data = read_crate_file(src_file)
        track_count = len(self._extract_tracks(raw_data))
        self._write_atomic(dst_file, raw_data)

        logger.info("Duplicated crate: %s → %s", source_path, dest_path)
        return CrateWriteResult(
            success=True,
            operation='duplicate',
            crate_name=dest_path,
            tracks_affected=track_count,
        )

    def delete_crate(self, crate_path: str) -> CrateWriteResult:
        """
        Delete a .crate file.  Creates a backup before deletion.
        Note: the GUI is responsible for confirming with the user before calling this.
        """
        file_path = self._to_filepath(crate_path)
        if not file_path.exists():
            return self._not_found(crate_path, 'delete')

        backup = self._backup(file_path)
        file_path.unlink()

        logger.info("Deleted crate: %s (backup: %s)", crate_path, backup.name)
        return CrateWriteResult(
            success=True,
            operation='delete',
            crate_name=crate_path,
            backup_path=backup,
        )

    def reorder_tracks(self, crate_path: str, new_order: list[str]) -> CrateWriteResult:
        """Reorder tracks in an existing crate to match new_order."""
        file_path = self._to_filepath(crate_path)
        if not file_path.exists():
            return self._not_found(crate_path, 'reorder')
        backup = self._backup(file_path)
        raw_data = read_crate_file(file_path)
        self._write_atomic(file_path, self._rebuild_data(raw_data, new_order))
        logger.info("Reordered %d tracks in crate: %s", len(new_order), crate_path)
        return CrateWriteResult(success=True, operation='reorder', crate_name=crate_path,
                                tracks_affected=len(new_order), backup_path=backup)

    def create_subcrate(
        self,
        parent_path: str,
        name: str,
        tracks: Optional[list[str]] = None,
    ) -> CrateWriteResult:
        """Create a subcrate under an existing parent crate."""
        child_path = f'{parent_path}/{name}'
        return self.create_crate(child_path, tracks)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _to_filepath(self, crate_path: str) -> Path:
        """
        Convert a crate_path ("Blues/Jump Blues") to its filesystem path.

        Crate paths with a leading segment that is a real subdirectory of Subcrates
        map to a file inside that subdirectory; others map to the Subcrates root.

        Examples:
          "Blues/Jump Blues"      → Subcrates/Blues%%Jump Blues.crate
          "Blues"                 → Subcrates/Blues.crate
          "Videos/Hip-Hop/Beats"  → Subcrates/Videos/Hip-Hop%%Beats.crate
        """
        parts = crate_path.split('/')
        subdir = self._subcrates_dir / parts[0]
        if subdir.is_dir() and len(parts) > 1:
            filename = '%%'.join(parts[1:]) + '.crate'
            return subdir / filename
        else:
            filename = '%%'.join(parts) + '.crate'
            return self._subcrates_dir / filename

    def _backup(self, file_path: Path) -> Path:
        """Create a timestamped backup and return the backup path."""
        self._backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self._backup_dir / f'{file_path.stem}_{ts}.crate.bak'
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _write_atomic(self, target: Path, data: list[tuple[str, Any]]) -> None:
        """Write data to a temp file, then atomically rename to target."""
        tmp = target.with_suffix('.tmp')
        try:
            write_crate_file(tmp, data)
            tmp.replace(target)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _extract_tracks(self, raw_data: list[tuple[str, Any]]) -> list[str]:
        """Extract ptrk path strings from raw decoded crate data."""
        tracks: list[str] = []
        for tag, value in raw_data:
            if tag == 'otrk':
                for inner_tag, inner_val in value:
                    if inner_tag == 'ptrk':
                        tracks.append(inner_val)
        return tracks

    def _rebuild_data(
        self,
        raw_data: list[tuple[str, Any]],
        new_tracks: list[str],
    ) -> list[tuple[str, Any]]:
        """
        Rebuild crate data with a new track list, preserving all non-track
        records (vrsn, osrt, ovct column display settings, etc.).
        """
        non_track = [(tag, val) for tag, val in raw_data if tag not in ('otrk',)]
        track_records = [('otrk', [('ptrk', t)]) for t in new_tracks]
        # Preserve original record order: vrsn + non-track + tracks
        return non_track + track_records

    def _not_found(self, crate_path: str, operation: str) -> CrateWriteResult:
        return CrateWriteResult(
            success=False,
            operation=operation,
            crate_name=crate_path,
            error=f'Crate not found: {self._to_filepath(crate_path).name}',
        )


# ---------------------------------------------------------------------------
# Standalone helpers for neworder.pref (Serato crate display order)
# ---------------------------------------------------------------------------

_NEWORDER_FILE = 'neworder.pref'
_NEWORDER_ENCODING = 'utf-16-be'


def _cratesort_to_serato_path(cs_path: str) -> str:
    """Convert CrateSort '/'-separated path to Serato '%%'-separated format."""
    return cs_path.replace('/', '%%')


def _serato_to_cratesort_path(serato_path: str) -> str:
    """Convert Serato '%%'-separated path to CrateSort '/'-separated format."""
    return serato_path.replace('%%', '/')


def read_crate_order(serato_dir: str | Path) -> list[str]:
    """
    Read `neworder.pref` and return crate paths in CrateSort's internal format
    ('/' as separator). Returns an empty list if the file doesn't exist or
    cannot be parsed.
    """
    neworder = Path(serato_dir) / _NEWORDER_FILE
    if not neworder.exists():
        return []
    try:
        raw = neworder.read_bytes()
        # Strip BOM if present, then decode
        if raw[:2] in (b'\xfe\xff', b'\xff\xfe'):
            text = raw.decode('utf-16')
        else:
            text = raw.decode(_NEWORDER_ENCODING, errors='replace')
        paths: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith('[crate]'):
                serato_name = line[len('[crate]'):]
                paths.append(_serato_to_cratesort_path(serato_name))
        return paths
    except Exception as exc:
        logger.warning('Failed to read %s: %s', neworder, exc)
        return []


def write_crate_order(serato_dir: str | Path, ordered_crate_paths: list[str]) -> bool:
    """
    Write `neworder.pref` with the given crate display order.

    `ordered_crate_paths` is a flat depth-first list of every crate and
    subcrate in CrateSort's internal '/' format.  The file is written
    atomically (temp → rename) as UTF-16 BE with BOM.

    Virtual-parent entries that exist in the current neworder.pref but have
    no corresponding .crate file are preserved: they are inserted before the
    first child that belongs to them.
    """
    serato_dir = Path(serato_dir)
    neworder   = serato_dir / _NEWORDER_FILE

    # Collect virtual parents from the existing file (entries with no .crate)
    existing = read_crate_order(serato_dir)
    subcrates_dir = serato_dir / 'Subcrates'
    existing_file_names = {
        f.stem for f in subcrates_dir.rglob('*.crate')
    } if subcrates_dir.exists() else set()

    def _has_crate_file(cs_path: str) -> bool:
        # Match by the last component and parent structure
        serato_name = _cratesort_to_serato_path(cs_path)
        # Check top-level file
        if (subcrates_dir / f'{serato_name}.crate').exists():
            return True
        # Check inside parent subdirectory (Serato nested layout)
        parts = cs_path.split('/')
        if len(parts) > 1:
            parent_dir = subcrates_dir / parts[0]
            child_file = '%%'.join(parts[1:]) + '.crate'
            if (parent_dir / child_file).exists():
                return True
        return False

    virtual_in_existing = {p for p in existing if not _has_crate_file(p)}

    # Build the new ordered set; inject virtual parents before their first child
    new_set = set(ordered_crate_paths)
    final_list: list[str] = []
    injected: set[str] = set()

    for cs_path in ordered_crate_paths:
        # Before adding this entry, inject any virtual ancestors not yet added
        parts = cs_path.split('/')
        for depth in range(1, len(parts)):
            ancestor = '/'.join(parts[:depth])
            if ancestor in virtual_in_existing and ancestor not in injected and ancestor not in new_set:
                final_list.append(ancestor)
                injected.add(ancestor)
        final_list.append(cs_path)

    # Build file content
    lines = ['[begin record]']
    for cs_path in final_list:
        lines.append(f'[crate]{_cratesort_to_serato_path(cs_path)}')
    lines.append('[end record]')
    content = '\n'.join(lines) + '\n'

    # Atomic write: temp file → rename
    tmp = neworder.with_suffix('.pref.tmp')
    try:
        tmp.write_bytes(content.encode(_NEWORDER_ENCODING))
        tmp.replace(neworder)
        logger.info('Wrote crate order to %s (%d entries)', neworder, len(final_list))
        return True
    except Exception as exc:
        logger.error('Failed to write %s: %s', neworder, exc)
        tmp.unlink(missing_ok=True)
        return False
