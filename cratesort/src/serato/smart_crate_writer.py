from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from cratesort.src.serato.smart_crate import (
    SMARTCRATES_DIR, SmartCrate, SmartCrateRule, read_smart_crate_file, write_smart_crate_file,
)

logger = logging.getLogger(__name__)

BACKUP_DIR = '_CrateSort_Backups'


@dataclass
class SmartCrateWriteResult:
    success: bool
    operation: str
    crate_name: str
    tracks_affected: int = 0
    backup_path: Optional[Path] = None
    error: Optional[str] = None


class SmartCrateWriter:
    """
    Writes and modifies Serato .scrate (Smart Crate) files.

    Safety guarantees mirror CrateWriter exactly:
    - Writes are atomic: temp file → rename.
    - Every write to an existing file creates a timestamped backup first.
    - NEVER touches audio files — only crate/rule definitions.
    """

    def __init__(self, serato_dir: str | Path):
        self._serato_dir = Path(serato_dir)
        self._smartcrates_dir = self._serato_dir / SMARTCRATES_DIR
        self._backup_dir = self._serato_dir / BACKUP_DIR

    # ── Public API ────────────────────────────────────────────────────────

    def create(
        self,
        name: str,
        rules: list[SmartCrateRule],
        match_all: bool,
        live_update: bool,
        tracks: list[str],
    ) -> SmartCrateWriteResult:
        """Create a new .scrate file. Fails if it already exists."""
        file_path = self._to_filepath(name)
        if file_path.exists():
            return SmartCrateWriteResult(
                success=False, operation='create', crate_name=name,
                error=f'Smart crate already exists: {file_path.name}',
            )

        file_path.parent.mkdir(parents=True, exist_ok=True)
        crate = SmartCrate(
            name=name, filepath=file_path, match_all=match_all,
            live_update=live_update, rules=list(rules), tracks=list(tracks),
        )
        self._write_atomic(file_path, crate)

        logger.info('Created smart crate: %s (%d rules, %d tracks)', name, len(rules), len(tracks))
        return SmartCrateWriteResult(
            success=True, operation='create', crate_name=name, tracks_affected=len(tracks),
        )

    def update(
        self,
        name: str,
        rules: list[SmartCrateRule],
        match_all: bool,
        live_update: bool,
        tracks: list[str],
    ) -> SmartCrateWriteResult:
        """Replace an existing smart crate's rules and materialized tracks."""
        file_path = self._to_filepath(name)
        if not file_path.exists():
            return self._not_found(name, 'update')

        backup = self._backup(file_path)
        crate = SmartCrate(
            name=name, filepath=file_path, match_all=match_all,
            live_update=live_update, rules=list(rules), tracks=list(tracks),
        )
        self._write_atomic(file_path, crate)

        logger.info('Updated smart crate: %s (%d rules, %d tracks)', name, len(rules), len(tracks))
        return SmartCrateWriteResult(
            success=True, operation='update', crate_name=name,
            tracks_affected=len(tracks), backup_path=backup,
        )

    def rename(self, old_name: str, new_name: str) -> SmartCrateWriteResult:
        old_file = self._to_filepath(old_name)
        new_file = self._to_filepath(new_name)

        if not old_file.exists():
            return self._not_found(old_name, 'rename')
        if new_file.exists():
            return SmartCrateWriteResult(
                success=False, operation='rename', crate_name=old_name,
                error=f'Destination already exists: {new_file.name}',
            )

        backup = self._backup(old_file)
        crate = read_smart_crate_file(old_file)
        crate.name = new_name
        crate.filepath = new_file
        self._write_atomic(new_file, crate)
        old_file.unlink()

        logger.info('Renamed smart crate: %s → %s', old_name, new_name)
        return SmartCrateWriteResult(success=True, operation='rename', crate_name=new_name, backup_path=backup)

    def duplicate(self, source_name: str, dest_name: str) -> SmartCrateWriteResult:
        src_file = self._to_filepath(source_name)
        dst_file = self._to_filepath(dest_name)

        if not src_file.exists():
            return self._not_found(source_name, 'duplicate')
        if dst_file.exists():
            return SmartCrateWriteResult(
                success=False, operation='duplicate', crate_name=source_name,
                error=f'Destination already exists: {dst_file.name}',
            )

        crate = read_smart_crate_file(src_file)
        crate.name = dest_name
        crate.filepath = dst_file
        self._write_atomic(dst_file, crate)

        logger.info('Duplicated smart crate: %s → %s', source_name, dest_name)
        return SmartCrateWriteResult(
            success=True, operation='duplicate', crate_name=dest_name, tracks_affected=len(crate.tracks),
        )

    def delete(self, name: str) -> SmartCrateWriteResult:
        """Delete a .scrate file. Creates a backup before deletion.
        Note: the GUI is responsible for confirming with the user before calling this."""
        file_path = self._to_filepath(name)
        if not file_path.exists():
            return self._not_found(name, 'delete')

        backup = self._backup(file_path)
        file_path.unlink()

        logger.info('Deleted smart crate: %s (backup: %s)', name, backup.name)
        return SmartCrateWriteResult(success=True, operation='delete', crate_name=name, backup_path=backup)

    def read(self, name: str) -> Optional[SmartCrate]:
        file_path = self._to_filepath(name)
        if not file_path.exists():
            return None
        return read_smart_crate_file(file_path)

    # ── Internal helpers ─────────────────────────────────────────────────

    def _to_filepath(self, name: str) -> Path:
        return self._smartcrates_dir / f'{name}.scrate'

    def _backup(self, file_path: Path) -> Path:
        self._backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self._backup_dir / f'{file_path.stem}_{ts}.scrate.bak'
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _write_atomic(self, target: Path, crate: SmartCrate) -> None:
        tmp = target.with_suffix('.tmp')
        try:
            write_smart_crate_file(tmp, crate)
            tmp.replace(target)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _not_found(self, name: str, operation: str) -> SmartCrateWriteResult:
        return SmartCrateWriteResult(
            success=False, operation=operation, crate_name=name,
            error=f'Smart crate not found: {self._to_filepath(name).name}',
        )
