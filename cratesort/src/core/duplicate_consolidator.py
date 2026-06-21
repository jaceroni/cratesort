from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from cratesort.src.core.duplicate_detector import DuplicateCopy, DuplicateGroup
from cratesort.src.core.file_organizer import FileMoveOp, RollbackLog
from cratesort.src.serato.path_rewriter import PathChange, PathRewriter


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ConsolidationResult:
    groups_processed: int
    files_removed: int
    space_freed: int                       # bytes
    crates_updated: int
    errors: list[str] = field(default_factory=list)
    rollback_log_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Consolidator
# ---------------------------------------------------------------------------

class DuplicateConsolidator:
    """
    Executes duplicate consolidation for a list of approved DuplicateGroups.

    For each group:
    1. The winner file stays in place.
    2. Every loser file path is remapped to the winner path in all .crate files
       via PathRewriter (atomic, backed up).
    3. Loser files are deleted from disk.
    4. The operation is logged to a RollbackLog with duplicate=True so the
       repair_crate_paths flow can restore if needed.

    Nothing is written unless commit=True. Pass commit=False for a dry-run
    preview of what would happen.
    """

    def __init__(
        self,
        library_path: Path,
        serato_dir: Path,
    ):
        self._library_path = library_path
        self._serato_dir   = serato_dir

    def consolidate(
        self,
        approved_groups: list[tuple[DuplicateGroup, DuplicateCopy]],
        commit: bool = True,
        progress_callback=None,
    ) -> ConsolidationResult:
        """
        approved_groups: list of (group, chosen_winner) pairs.
        progress_callback: callable(done: int, total: int, label: str) or None.
        """
        total           = len(approved_groups)
        files_removed   = 0
        space_freed     = 0
        crates_updated  = 0
        all_errors: list[str] = []

        log_path = (
            self._library_path
            / '_CrateSort'
            / f'duplicate_consolidation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        rlog = RollbackLog(log_path)
        rlog.set_context(self._library_path, self._serato_dir)

        for i, (group, winner) in enumerate(approved_groups):
            if progress_callback:
                label = f'{group.canonical_artist} — {group.canonical_title}'
                progress_callback(i, total, label)

            losers = [c for c in group.copies if c.file_path != winner.file_path]
            changes: list[PathChange] = []

            for loser in losers:
                # Build relative path keys (how they appear in .crate files)
                try:
                    loser_rel  = loser.file_path.relative_to(self._library_path).as_posix()
                    winner_rel = winner.file_path.relative_to(self._library_path).as_posix()
                except ValueError:
                    loser_rel  = loser.file_path.as_posix()
                    winner_rel = winner.file_path.as_posix()

                # Both relative and absolute variants for crate compatibility
                changes.append(PathChange(old_path=loser_rel,  new_path=winner_rel))
                changes.append(PathChange(
                    old_path=loser.file_path.as_posix(),
                    new_path=winner.file_path.as_posix(),
                ))

            if not changes:
                continue

            # Reroute all crate references first (before deleting files)
            rewrite_result = None
            if commit:
                try:
                    rewrite_result = PathRewriter(self._serato_dir).rewrite(
                        changes, dry_run=False
                    )
                    crates_updated += rewrite_result.crates_modified
                    for bp in rewrite_result.backup_paths:
                        rlog.log_crate_backup(bp)
                except Exception as exc:
                    all_errors.append(
                        f'{group.canonical_title}: crate rewrite failed — {exc}'
                    )
                    continue

            # Delete loser files
            for loser in losers:
                op = FileMoveOp(
                    source_path=loser.file_path,
                    destination_path=winner.file_path,
                    reason='duplicate_consolidation',
                    status='pending',
                )
                if commit:
                    try:
                        op.sha256_source = _sha256(loser.file_path)
                        op.executed_at   = datetime.now().isoformat()
                        loser.file_path.unlink()
                        op.status = 'completed'
                        files_removed += 1
                        space_freed   += loser.file_size
                    except Exception as exc:
                        op.status = 'failed'
                        op.error  = str(exc)
                        all_errors.append(
                            f'{loser.file_path.name}: delete failed — {exc}'
                        )
                    rlog.log_move(op, duplicate=True)
                else:
                    files_removed += 1
                    space_freed   += loser.file_size

        if commit:
            rlog.save()

        if progress_callback:
            progress_callback(total, total, 'Done')

        return ConsolidationResult(
            groups_processed=total,
            files_removed=files_removed,
            space_freed=space_freed,
            crates_updated=crates_updated,
            errors=all_errors,
            rollback_log_path=log_path if commit else None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
