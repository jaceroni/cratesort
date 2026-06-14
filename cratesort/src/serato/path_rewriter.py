from __future__ import annotations

import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure serato_crate (Homebrew install) is on the path in non-venv dev environments.
import sysconfig as _sysconfig
_brew_sp = '/opt/homebrew/lib/python' + _sysconfig.get_python_version() + '/site-packages'
if _brew_sp not in sys.path:
    sys.path.insert(0, _brew_sp)
del _sysconfig, _brew_sp
from serato_crate.crate_file import read_crate_file, write_crate_file

logger = logging.getLogger(__name__)

SUBCRATES_DIR = 'Subcrates'
BACKUP_DIR = '_CrateSort_Backups'


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class PathChange:
    old_path: str    # path as stored in crate (relative to drive root, posix)
    new_path: str    # replacement path (relative to drive root, posix)


@dataclass
class PathChangeRecord:
    crate_full_path: str    # human-readable crate path ("Blues/Jump Blues")
    crate_file: Path        # absolute path to .crate file
    old_track_path: str
    new_track_path: str


@dataclass
class RewriteResult:
    crates_modified: int
    paths_rewritten: int
    crates_unchanged: int
    changes_log: list[PathChangeRecord] = field(default_factory=list)
    backup_paths: list[Path] = field(default_factory=list)
    dry_run: bool = False
    errors: list[tuple[Path, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Path rewriter
# ---------------------------------------------------------------------------

class PathRewriter:
    """
    Updates .crate file track references after files have been moved.

    After CrateSort reorganizes files on disk, call rewrite() with a list of
    PathChange objects mapping old paths to new paths.  Every matching reference
    in every .crate file is updated atomically.

    Safety guarantees:
    - Creates a backup of every .crate file before modifying it.
    - Non-matching paths are never touched.
    - dry_run=True reports what would change without writing anything.
    - All column display settings (osrt/ovct) are preserved.
    """

    def __init__(self, serato_dir: str | Path):
        self._serato_dir = Path(serato_dir)
        self._subcrates_dir = self._serato_dir / SUBCRATES_DIR
        self._backup_dir = self._serato_dir / BACKUP_DIR

    def rewrite(
        self,
        changes: list[PathChange],
        dry_run: bool = False,
    ) -> RewriteResult:
        """
        Apply path changes to all .crate files.

        Args:
            changes: List of PathChange(old_path, new_path) pairs.
            dry_run: If True, report what would change without writing.

        Returns:
            RewriteResult with counts and a full change log.
        """
        if not self._subcrates_dir.exists():
            logger.warning("Subcrates directory not found: %s", self._subcrates_dir)
            return RewriteResult(
                crates_modified=0,
                paths_rewritten=0,
                crates_unchanged=0,
                dry_run=dry_run,
            )

        # Build lookup: old_path → new_path
        change_map: dict[str, str] = {c.old_path: c.new_path for c in changes}

        result = RewriteResult(
            crates_modified=0,
            paths_rewritten=0,
            crates_unchanged=0,
            dry_run=dry_run,
        )

        # Snapshot each crate's bytes before modification so we can restore all
        # already-written crates if the loop fails mid-way (atomic set guarantee).
        written_originals: list[tuple[Path, bytes]] = []

        for crate_file in sorted(self._subcrates_dir.rglob('*.crate')):
            mods_before = result.crates_modified
            pre_bytes   = crate_file.read_bytes() if not dry_run else b''
            try:
                self._process_crate(crate_file, change_map, result, dry_run)
                if not dry_run and result.crates_modified > mods_before:
                    written_originals.append((crate_file, pre_bytes))
            except Exception as exc:
                logger.error("Error processing %s: %s", crate_file.name, exc)
                result.errors.append((crate_file, str(exc)))
                if not dry_run and written_originals:
                    logger.warning(
                        "Rewrite failed — restoring %d crate(s) to pre-rewrite state",
                        len(written_originals),
                    )
                    for orig_path, orig_bytes in written_originals:
                        try:
                            orig_path.write_bytes(orig_bytes)
                            logger.info("Restored: %s", orig_path.name)
                        except Exception as restore_exc:
                            logger.error(
                                "CRITICAL: could not restore %s: %s",
                                orig_path.name, restore_exc,
                            )
                break

        mode = 'DRY RUN' if dry_run else 'APPLIED'
        logger.info(
            "[%s] Crates modified: %d | Paths rewritten: %d | Unchanged: %d",
            mode,
            result.crates_modified,
            result.paths_rewritten,
            result.crates_unchanged,
        )
        return result

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _process_crate(
        self,
        crate_file: Path,
        change_map: dict[str, str],
        result: RewriteResult,
        dry_run: bool,
    ) -> None:
        raw_data = read_crate_file(crate_file)
        crate_display = self._display_name(crate_file)

        new_data: list[tuple[str, Any]] = []
        crate_changes: list[PathChangeRecord] = []

        for tag, value in raw_data:
            if tag == 'otrk':
                inner_records: list[tuple[str, Any]] = []
                for inner_tag, inner_val in value:
                    # Serato inconsistently stores ':' as U+F022 in some crates.
                    # Normalise before lookup so both variants match the same key.
                    normalised = inner_val.replace('', ':') if inner_tag == 'ptrk' else inner_val
                    if inner_tag == 'ptrk' and normalised in change_map:
                        new_path = change_map[normalised]
                        crate_changes.append(PathChangeRecord(
                            crate_full_path=crate_display,
                            crate_file=crate_file,
                            old_track_path=inner_val,
                            new_track_path=new_path,
                        ))
                        inner_records.append(('ptrk', new_path))
                        logger.debug(
                            "  %s: %s → %s", crate_file.name, inner_val, new_path
                        )
                    else:
                        inner_records.append((inner_tag, inner_val))
                new_data.append(('otrk', inner_records))
            else:
                new_data.append((tag, value))

        if not crate_changes:
            result.crates_unchanged += 1
            return

        result.changes_log.extend(crate_changes)
        result.crates_modified += 1
        result.paths_rewritten += len(crate_changes)

        if not dry_run:
            backup = self._backup(crate_file)
            result.backup_paths.append(backup)
            self._write_atomic(crate_file, new_data)

    def _display_name(self, crate_file: Path) -> str:
        """Convert crate filepath to a human-readable display path."""
        try:
            rel = crate_file.relative_to(self._subcrates_dir)
            return rel.as_posix().replace('%%', '/')[: -len('.crate')]
        except ValueError:
            return crate_file.name

    def _backup(self, file_path: Path) -> Path:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Mirror the Subcrates subdirectory so Blues/Rock.crate → _CrateSort_Backups/Blues/Rock_ts.crate.bak.
        # This avoids filename collisions between same-name crates in different subdirs and
        # preserves enough path info for rollback to reconstruct the original location.
        try:
            rel_dir = file_path.parent.relative_to(self._subcrates_dir)
        except ValueError:
            rel_dir = Path('.')
        target_dir = self._backup_dir / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        backup_path = target_dir / f'{file_path.stem}_{ts}.crate.bak'
        shutil.copy2(file_path, backup_path)
        return backup_path

    def _write_atomic(
        self, target: Path, data: list[tuple[str, Any]]
    ) -> None:
        tmp = target.with_suffix('.tmp')
        try:
            write_crate_file(tmp, data)
            tmp.replace(target)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
