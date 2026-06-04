from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import mutagen
import mutagen.id3
import mutagen.mp4
import mutagen.flac

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.core.classifier import ClassificationResult
from cratesort.src.core.filename_cleaner import FilenameProposal
from cratesort.src.core.metadata_fixer import MetadataProposal, MetadataChange
from cratesort.src.utils.the_handler import TheProposal
from cratesort.src.core.artist_consolidator import ConsolidationCandidate
from cratesort.src.utils.sanitizer import sanitize_path_component

sys.path.insert(0, '/opt/homebrew/lib/python3.14/site-packages')

logger = logging.getLogger(__name__)

# Folder name prefixes that mark a folder as protected by default.
# Files inside protected folders are catalogued but never moved.
DEFAULT_PROTECTED_PREFIXES = ('_',)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FileMoveOp:
    source_path: Path
    destination_path: Path
    reason: str
    filename_change: Optional[tuple[str, str]] = None  # (old_name, new_name)
    metadata_changes: list[MetadataChange] = field(default_factory=list)
    crates_affected: list[str] = field(default_factory=list)  # crate full_paths
    # Filled during execution
    status: str = 'pending'   # 'completed' | 'failed' | 'skipped'
    error: Optional[str] = None
    sha256_source: Optional[str] = None
    sha256_copy: Optional[str] = None
    executed_at: Optional[str] = None


@dataclass
class ConflictReport:
    destination_path: Path
    sources: list[Path]
    resolution: str = 'unresolved'  # 'unresolved' | 'rename' | 'skip'


@dataclass
class PlanSummary:
    total_scanned: int
    files_to_move: int
    files_staying: int
    files_renamed: int           # filename changes (within moves)
    files_with_metadata: int     # have approved metadata changes
    crates_to_update: int        # crate files that would be rewritten
    new_folders: int
    empty_folders_after: int
    protected_skipped: int
    conflict_count: int


@dataclass
class ReorganizationPlan:
    library_root: Path
    serato_dir: Optional[Path]
    operations: list[FileMoveOp]
    stays_put: list[Path]
    new_folders: list[Path]
    empty_folders_after: list[Path]
    protected_skipped: list[tuple[Path, str]]   # (file_path, reason)
    conflicts: list[ConflictReport]
    summary: PlanSummary


@dataclass
class ExecutionResult:
    completed: list[FileMoveOp]
    failed: list[FileMoveOp]
    skipped: list[FileMoveOp]
    rollback_log_path: Optional[Path]
    crate_rewrite_summary: Optional[dict]
    duration_seconds: float


# ---------------------------------------------------------------------------
# Rollback log
# ---------------------------------------------------------------------------

class RollbackLog:
    """
    JSON-based log of every operation performed during a reorganization.
    Can replay operations in reverse to restore the library to its prior state.
    """

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._data: dict = {
            'version': '1',
            'library_root': '',
            'serato_dir': '',
            'executed_at': '',
            'moves': [],
            'metadata_changes': [],
            'crate_backup_paths': [],
        }

    def set_context(
        self,
        library_root: Path,
        serato_dir: Optional[Path],
    ) -> None:
        self._data['library_root'] = str(library_root)
        self._data['serato_dir'] = str(serato_dir) if serato_dir else ''
        self._data['executed_at'] = datetime.now().isoformat()

    def log_move(self, op: FileMoveOp) -> None:
        self._data['moves'].append({
            'source': str(op.source_path),
            'destination': str(op.destination_path),
            'sha256': op.sha256_source or '',
            'executed_at': op.executed_at or '',
            'status': op.status,
        })

    def log_metadata(
        self,
        file_path: Path,
        field: str,
        value_before: Optional[str],
        value_after: Optional[str],
    ) -> None:
        self._data['metadata_changes'].append({
            'file_path': str(file_path),
            'field': field,
            'value_before': value_before,
            'value_after': value_after,
        })

    def log_crate_backup(self, backup_path: Path) -> None:
        self._data['crate_backup_paths'].append(str(backup_path))

    def save(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2)
        logger.info("Rollback log saved: %s", self.log_path)

    @classmethod
    def load(cls, log_path: str | Path) -> 'RollbackLog':
        log = cls(Path(log_path))
        with open(log_path, encoding='utf-8') as f:
            log._data = json.load(f)
        return log

    def rollback(self) -> dict:
        """
        Undo the reorganization described in this log.
        Returns a dict with counts of restored/failed/skipped operations.
        """
        restored = 0
        failed = 0
        skipped = 0
        errors: list[str] = []

        # Reverse file moves: destination → source
        for entry in reversed(self._data['moves']):
            if entry['status'] != 'completed':
                skipped += 1
                continue
            src = Path(entry['destination'])
            dst = Path(entry['source'])
            try:
                if not src.exists():
                    errors.append(f"Rollback source missing: {src}")
                    failed += 1
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                logger.info("Rolled back: %s → %s", src.name, dst)
                restored += 1
            except Exception as exc:
                errors.append(f"Failed to roll back {src}: {exc}")
                failed += 1

        # Restore Serato crate backups
        for backup_str in self._data.get('crate_backup_paths', []):
            backup = Path(backup_str)
            if not backup.exists():
                continue
            # Strip _CrateSort_Backups/<name>_TIMESTAMP.crate.bak → original
            original_name = '_'.join(backup.stem.split('_')[:-2]) + '.crate'
            subcrates_dir = backup.parent.parent / 'Subcrates'
            original = subcrates_dir / original_name
            try:
                shutil.copy2(str(backup), str(original))
                logger.info("Restored crate: %s", original.name)
            except Exception as exc:
                errors.append(f"Failed to restore crate {original}: {exc}")

        # Cleanup: remove any now-empty directories that were created
        library_root = Path(self._data.get('library_root', ''))
        if library_root.exists():
            self._remove_empty_dirs(library_root)

        return {
            'restored': restored,
            'failed': failed,
            'skipped': skipped,
            'errors': errors,
        }

    def _remove_empty_dirs(self, root: Path) -> None:
        """Remove any empty directories under root (bottom-up)."""
        for dirpath in sorted(root.rglob('*'), reverse=True):
            if dirpath.is_dir():
                try:
                    dirpath.rmdir()  # only succeeds if empty
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# File Organizer
# ---------------------------------------------------------------------------

class FileOrganizer:
    """
    Builds a complete ReorganizationPlan and (when approved) executes it.

    The plan is always built first — nothing happens until execute() is called.
    execute() uses copy-verify-delete for safety and writes a rollback log.

    Protected folders (default: any folder starting with '_') are skipped.
    """

    def __init__(
        self,
        library_root: str | Path,
        serato_dir: Optional[str | Path] = None,
        protected_prefixes: tuple[str, ...] = DEFAULT_PROTECTED_PREFIXES,
        data_dir: Optional[str | Path] = None,
    ):
        self._library_root = Path(library_root)
        self._serato_dir = Path(serato_dir) if serato_dir else None
        self._protected_prefixes = protected_prefixes
        self._data_dir = Path(data_dir) if data_dir else self._library_root / '_CrateSort'

    # ── Plan builder ─────────────────────────────────────────────────────────

    def build_plan(
        self,
        inventory: list[TrackRecord],
        classifications: dict[Path, ClassificationResult],
        filename_proposals: dict[Path, FilenameProposal],
        the_proposals: dict[str, TheProposal],           # artist_name → proposal
        meta_proposals: dict[Path, MetadataProposal],
        consolidation: dict[str, ConsolidationCandidate],  # artist_name → candidate
        crate_library=None,  # Optional[CrateLibrary]
    ) -> ReorganizationPlan:
        """
        Build a complete before/after picture without touching any files.
        """
        operations: list[FileMoveOp] = []
        stays_put: list[Path] = []
        protected_skipped: list[tuple[Path, str]] = []
        destination_map: dict[Path, list[Path]] = defaultdict(list)

        # Build crate reverse-lookup: crate_relative_path → [crate_full_paths]
        crate_lookup = self._build_crate_lookup(crate_library)

        for record in inventory:
            # Skip files outside the library root (shouldn't happen, but guard)
            if not self._is_under_root(record.path):
                continue

            # Protected folder check
            protection_reason = self._get_protection_reason(record.path)
            if protection_reason:
                protected_skipped.append((record.path, protection_reason))
                continue

            cls = classifications.get(record.path)
            if not cls or not cls.genre:
                # Can't classify → stays put
                stays_put.append(record.path)
                continue

            # Build destination path
            fp = filename_proposals.get(record.path)
            destination = self._build_destination(
                record=record,
                genre=cls.genre,
                filename_proposal=fp,
                the_proposals=the_proposals,
                consolidation=consolidation,
            )

            # If destination == source, file stays put
            if destination == record.path:
                stays_put.append(record.path)
                continue

            # Record destination for conflict detection
            destination_map[destination].append(record.path)

            # Filename change?
            fname_change: Optional[tuple[str, str]] = None
            if fp and fp.has_changes:
                fname_change = (record.filename, fp.proposed_filename)

            # Metadata changes
            mp = meta_proposals.get(record.path)
            meta_changes = mp.changes if mp else []

            # Crates affected
            crate_rel = record.path.as_posix().lstrip('/')
            crates_affected = crate_lookup.get(crate_rel, [])

            operations.append(FileMoveOp(
                source_path=record.path,
                destination_path=destination,
                reason=f"Genre: {cls.genre} [{cls.confidence.value}]",
                filename_change=fname_change,
                metadata_changes=meta_changes,
                crates_affected=crates_affected,
            ))

        # Detect conflicts (two sources → same destination)
        conflicts = [
            ConflictReport(destination_path=dest, sources=srcs)
            for dest, srcs in destination_map.items()
            if len(srcs) > 1
        ]

        # Detect destination files that already exist (not from our moves)
        all_moving_sources = {op.source_path for op in operations}
        for op in operations:
            if op.destination_path.exists() and op.destination_path not in all_moving_sources:
                existing = ConflictReport(
                    destination_path=op.destination_path,
                    sources=[op.source_path, op.destination_path],
                )
                if op.destination_path not in {c.destination_path for c in conflicts}:
                    conflicts.append(existing)

        # New folders to create
        new_folders = sorted({
            parent
            for op in operations
            for parent in op.destination_path.parents
            if not parent.exists() and self._is_under_root(parent)
        })

        # Empty folders after move
        source_dirs = {op.source_path.parent for op in operations}
        empty_after = [
            d for d in source_dirs
            if d.exists() and self._will_be_empty(d, all_moving_sources)
        ]

        # Unique crate files to update
        all_crate_names = {
            crate
            for op in operations
            for crate in op.crates_affected
        }

        summary = PlanSummary(
            total_scanned=len(inventory),
            files_to_move=len(operations),
            files_staying=len(stays_put),
            files_renamed=sum(1 for op in operations if op.filename_change),
            files_with_metadata=sum(1 for op in operations if op.metadata_changes),
            crates_to_update=len(all_crate_names),
            new_folders=len(new_folders),
            empty_folders_after=len(empty_after),
            protected_skipped=len(protected_skipped),
            conflict_count=len(conflicts),
        )

        return ReorganizationPlan(
            library_root=self._library_root,
            serato_dir=self._serato_dir,
            operations=operations,
            stays_put=stays_put,
            new_folders=new_folders,
            empty_folders_after=empty_after,
            protected_skipped=protected_skipped,
            conflicts=conflicts,
            summary=summary,
        )

    # ── Execution engine ─────────────────────────────────────────────────────

    def execute(
        self,
        plan: ReorganizationPlan,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ExecutionResult:
        """
        Execute the reorganization plan.
        Each file: copy → verify (SHA-256) → delete original → log.
        Metadata changes are written to the moved files.
        Serato crate paths are updated via PathRewriter.
        """
        import time
        start = time.time()

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = self._data_dir / f'reorganization_log_{ts}.json'
        rlog = RollbackLog(log_path)
        rlog.set_context(plan.library_root, plan.serato_dir)

        completed: list[FileMoveOp] = []
        failed: list[FileMoveOp] = []
        skipped: list[FileMoveOp] = []

        total = len(plan.operations)

        for i, op in enumerate(plan.operations):
            if progress_callback:
                progress_callback(i, total, op.source_path.name)

            # Skip if destination already exists as a conflict
            if op.destination_path.exists():
                op.status = 'skipped'
                op.error = f'Destination already exists: {op.destination_path.name}'
                skipped.append(op)
                logger.warning("Skipped (conflict): %s", op.source_path.name)
                continue

            try:
                self._execute_move(op, rlog)
                completed.append(op)
            except Exception as exc:
                op.status = 'failed'
                op.error = str(exc)
                failed.append(op)
                logger.error("Failed to move %s: %s", op.source_path.name, exc)

        # Apply metadata changes to moved files
        for op in completed:
            if op.metadata_changes:
                try:
                    self._apply_metadata(op.destination_path, op.metadata_changes, rlog)
                except Exception as exc:
                    logger.warning("Metadata write failed for %s: %s", op.destination_path.name, exc)

        # Update Serato crate paths
        crate_result = None
        if plan.serato_dir and plan.serato_dir.exists() and completed:
            crate_result = self._update_crate_paths(completed, plan.serato_dir, rlog)

        # Clean up approved empty folders
        for folder in plan.empty_folders_after:
            if folder.exists() and not any(folder.iterdir()):
                try:
                    folder.rmdir()
                    logger.info("Removed empty folder: %s", folder)
                except OSError:
                    pass

        rlog.save()
        duration = time.time() - start

        logger.info(
            "Execution complete: %d moved, %d failed, %d skipped in %.1fs",
            len(completed), len(failed), len(skipped), duration,
        )

        return ExecutionResult(
            completed=completed,
            failed=failed,
            skipped=skipped,
            rollback_log_path=log_path,
            crate_rewrite_summary=crate_result,
            duration_seconds=duration,
        )

    def rollback(self, log_path: str | Path) -> dict:
        """Undo a previous reorganization using its rollback log."""
        rlog = RollbackLog.load(log_path)
        return rlog.rollback()

    # ── Internal: single file move ────────────────────────────────────────────

    def _execute_move(self, op: FileMoveOp, rlog: RollbackLog) -> None:
        op.destination_path.parent.mkdir(parents=True, exist_ok=True)

        # Hash the source
        op.sha256_source = _sha256(op.source_path)

        # Copy
        tmp_dest = op.destination_path.with_suffix(op.destination_path.suffix + '.tmp')
        shutil.copy2(str(op.source_path), str(tmp_dest))

        # Verify
        op.sha256_copy = _sha256(tmp_dest)
        if op.sha256_source != op.sha256_copy:
            tmp_dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"Hash mismatch: {op.sha256_source} vs {op.sha256_copy}"
            )

        # Atomic rename
        tmp_dest.replace(op.destination_path)

        # Delete original
        op.source_path.unlink()

        op.status = 'completed'
        op.executed_at = datetime.now().isoformat()
        rlog.log_move(op)
        logger.info("Moved: %s → %s", op.source_path.name, op.destination_path)

    # ── Internal: metadata writer ─────────────────────────────────────────────

    def _apply_metadata(
        self,
        file_path: Path,
        changes: list[MetadataChange],
        rlog: RollbackLog,
    ) -> None:
        """Write approved metadata changes via mutagen. Never touches Serato frames or comments."""
        ext = file_path.suffix.lower()
        audio = mutagen.File(file_path, easy=False)
        if audio is None:
            return

        for change in changes:
            if change.needs_review or change.proposed_value is None:
                continue
            if change.field == 'genre':
                rlog.log_metadata(file_path, 'genre', change.current_value, change.proposed_value)
                self._write_genre(audio, ext, change.proposed_value)
            elif change.field == 'sort_artist':
                rlog.log_metadata(file_path, 'sort_artist', change.current_value, change.proposed_value)
                self._write_sort_artist(audio, ext, change.proposed_value)

        audio.save()

    def _write_genre(self, audio, ext: str, value: str) -> None:
        if ext in {'.mp3', '.wav', '.aif', '.aiff'}:
            if audio.tags is None:
                audio.add_tags()
            audio.tags['TCON'] = mutagen.id3.TCON(encoding=3, text=[value])
        elif ext in {'.m4a', '.mp4', '.m4v', '.mov'}:
            if audio.tags is not None:
                audio.tags['©gen'] = [value]
        elif ext == '.flac':
            audio['genre'] = [value]

    def _write_sort_artist(self, audio, ext: str, value: str) -> None:
        if ext in {'.mp3', '.wav', '.aif', '.aiff'}:
            if audio.tags is None:
                audio.add_tags()
            audio.tags['TSOP'] = mutagen.id3.TSOP(encoding=3, text=[value])
        elif ext in {'.m4a', '.mp4', '.m4v', '.mov'}:
            if audio.tags is not None:
                audio.tags['soar'] = [value]

    # ── Internal: crate path update ───────────────────────────────────────────

    def _update_crate_paths(
        self,
        completed_ops: list[FileMoveOp],
        serato_dir: Path,
        rlog: RollbackLog,
    ) -> dict:
        try:
            from cratesort.src.serato.path_rewriter import PathRewriter, PathChange

            changes = [
                PathChange(
                    old_path=op.source_path.as_posix().lstrip('/'),
                    new_path=op.destination_path.as_posix().lstrip('/'),
                )
                for op in completed_ops
            ]

            rewriter = PathRewriter(serato_dir)
            result = rewriter.rewrite(changes, dry_run=False)

            for backup in result.backup_paths:
                rlog.log_crate_backup(backup)

            return {
                'crates_modified': result.crates_modified,
                'paths_rewritten': result.paths_rewritten,
                'errors': len(result.errors),
            }
        except Exception as exc:
            logger.error("Crate path update failed: %s", exc)
            return {'error': str(exc)}

    # ── Internal: destination path builder ────────────────────────────────────

    def _build_destination(
        self,
        record: TrackRecord,
        genre: str,
        filename_proposal: Optional[FilenameProposal],
        the_proposals: dict[str, TheProposal],
        consolidation: dict[str, ConsolidationCandidate],
    ) -> Path:
        artist = record.artist or 'Unknown Artist'

        # Consolidation: determine the folder hierarchy
        candidate = consolidation.get(artist)
        if candidate:
            winner = candidate.merge_proposal.winning_name
            winner_folder = self._artist_folder_name(winner, the_proposals)
            if candidate.merge_proposal.use_subfolders and artist != winner:
                variant_folder = self._artist_folder_name(artist, the_proposals)
                artist_path = (
                    self._library_root
                    / Path(genre)
                    / sanitize_path_component(winner_folder)
                    / sanitize_path_component(variant_folder)
                )
            else:
                artist_path = (
                    self._library_root
                    / Path(genre)
                    / sanitize_path_component(winner_folder)
                )
        else:
            folder = self._artist_folder_name(artist, the_proposals)
            artist_path = (
                self._library_root
                / Path(genre)
                / sanitize_path_component(folder)
            )

        # Filename: use cleaned proposal if available, else original
        if filename_proposal and filename_proposal.has_changes:
            filename = filename_proposal.proposed_filename
        else:
            filename = record.filename

        return artist_path / sanitize_path_component(filename)

    def _artist_folder_name(
        self, artist: str, the_proposals: dict[str, TheProposal]
    ) -> str:
        """Return the on-disk folder name for an artist, applying "The" handling."""
        the_p = the_proposals.get(artist)
        return the_p.folder_name if the_p else artist

    # ── Internal: helpers ─────────────────────────────────────────────────────

    def _is_under_root(self, path: Path) -> bool:
        try:
            path.relative_to(self._library_root)
            return True
        except ValueError:
            return False

    def _get_protection_reason(self, path: Path) -> Optional[str]:
        """Return a reason string if this file is in a protected folder, else None."""
        try:
            rel = path.relative_to(self._library_root)
        except ValueError:
            return None
        for part in rel.parts[:-1]:  # exclude the filename itself
            for prefix in self._protected_prefixes:
                if part.startswith(prefix):
                    return f'Protected folder: {part}'
        return None

    def _will_be_empty(self, directory: Path, moving_sources: set[Path]) -> bool:
        """True if every file in directory is being moved."""
        for child in directory.rglob('*'):
            if child.is_file() and child not in moving_sources:
                return False
        return True

    def _build_crate_lookup(self, crate_library) -> dict[str, list[str]]:
        """Build track_crate_relative_path → [crate_full_paths] reverse lookup."""
        if not crate_library:
            return {}
        lookup: dict[str, list[str]] = defaultdict(list)
        for full_path, crate in crate_library.crates.items():
            for track in crate.tracks:
                lookup[track].append(full_path)
        return dict(lookup)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
