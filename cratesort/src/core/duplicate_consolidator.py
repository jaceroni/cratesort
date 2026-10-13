from __future__ import annotations

import errno
import hashlib
import os
import shutil
import stat
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from cratesort.src.core.duplicate_detector import DuplicateCopy, DuplicateGroup
from cratesort.src.core.file_organizer import FileMoveOp, RollbackLog
from cratesort.src.core.metadata_merger import merge_metadata
from cratesort.src.serato.crate_reader import CrateReader
from cratesort.src.serato.path_rewriter import PathChange, PathRewriter
from cratesort.src.utils.checkpoint import update_checkpoint_crates


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
    # winner file path (str) → merged comment, for every group where the
    # comment actually changed. The winner's in-memory TrackRecord (loaded at
    # the last library scan, held by dashboard._inventory) has no way to know
    # its .comment is now stale on disk — nothing re-scans after a
    # consolidation — so the caller must patch it directly with this, or the
    # Library/Crates views keep showing the pre-merge comment all session.
    comment_updates: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Consolidator
# ---------------------------------------------------------------------------

class DuplicateConsolidator:
    """
    Executes duplicate consolidation for a list of approved DuplicateGroups.

    For each group:
    1. The winner file stays in place.
    2. Loser files are moved to a trash staging area (_CrateSort/.dup_trash) —
       not deleted yet. A loser whose move fails keeps its own crate
       references untouched — they still point at a real file — rather than
       being repointed to the winner while the duplicate itself is silently
       left behind.
    3. Every successfully-trashed loser's file path is remapped to the winner
       path in all .crate files via PathRewriter (atomic, backed up).
    4. Only once that rewrite succeeds with zero errors are the group's
       trashed losers permanently deleted. Any rewrite failure (exception or
       even a single per-crate error) restores every trashed loser in that
       group back to its original path and leaves the crate(s) untouched —
       a loser's file is never gone while any of its crate entries might
       still be unresolved. This is what keeps delete and crate-reference
       update one atomic unit, per the project's FV-1 rule: a hard
       interruption (crash, force-quit, drive disconnect) between "file
       gone" and "crate updated" is exactly how a DJ's crates end up
       pointing at files that no longer exist — this consolidator must never
       create that window, even transiently.
    5. The operation is logged to a RollbackLog with duplicate=True so the
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
        approved_groups: list[tuple],
        commit: bool = True,
        progress_callback=None,
    ) -> ConsolidationResult:
        """
        approved_groups: list of (group, chosen_winner) pairs, or
        (group, chosen_winner, losers) triples where `losers` is the explicit
        subset of copies to consolidate into the winner. With a 2-tuple, every
        copy that isn't the winner is treated as a loser (legacy behavior).
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
        touched_crates: set[Path] = set()
        comment_updates: dict[str, str] = {}
        trash_dir = self._library_path / '_CrateSort' / '.dup_trash'
        trash_counter = 0

        for i, entry in enumerate(approved_groups):
            if len(entry) == 3:
                group, winner, losers = entry
            else:
                group, winner = entry
                losers = [c for c in group.copies if c.file_path != winner.file_path]

            if progress_callback:
                label = f'{group.canonical_artist} — {group.canonical_title}'
                progress_callback(i, total, label)

            # Guard: never remove the winner even if a caller included it.
            losers = [c for c in losers if c.file_path != winner.file_path]
            changes: list[PathChange] = []

            # Per-loser PathChange pairs (rel + abs variant), keyed by the
            # loser's own path so we can later reroute crate references only
            # for losers whose delete actually succeeded — see below.
            changes_by_loser: dict[Path, list[PathChange]] = {}
            for loser in losers:
                # Build relative path keys (how they appear in .crate files)
                try:
                    loser_rel  = loser.file_path.relative_to(self._library_path).as_posix()
                    winner_rel = winner.file_path.relative_to(self._library_path).as_posix()
                except ValueError:
                    loser_rel  = loser.file_path.as_posix()
                    winner_rel = winner.file_path.as_posix()

                # Both relative and absolute variants for crate compatibility
                pair = [
                    PathChange(old_path=loser_rel, new_path=winner_rel),
                    PathChange(
                        old_path=loser.file_path.as_posix(),
                        new_path=winner.file_path.as_posix(),
                    ),
                ]
                changes_by_loser[loser.file_path] = pair
                changes.extend(pair)

            if not changes:
                continue

            # Merge play counts, comments, and cue points from losers into winner
            # before deleting anything — once files are gone, this data is gone.
            if commit:
                loser_paths    = [l.file_path for l in losers]
                loser_comments = [l.comment for l in losers]
                merge_result   = merge_metadata(
                    winner_path=winner.file_path,
                    loser_paths=loser_paths,
                    winner_comment=winner.comment,
                    loser_comments=loser_comments,
                    serato_dir=self._serato_dir,
                )
                for err in merge_result.errors:
                    msg = f'{group.canonical_title}: merge — {err}'
                    all_errors.append(msg)
                    rlog.log_error(msg)
                if merge_result.comment_merged and merge_result.comment_final:
                    comment_updates[str(winner.file_path)] = merge_result.comment_final

            # Move loser files to trash staging FIRST, before rerouting any
            # crate references — but do NOT permanently delete them yet. A
            # loser's crate entries must only be repointed to the winner once
            # we know the loser's own file is actually gone, and the file
            # must only actually be gone once we know its crate entries were
            # successfully repointed. Trashing (not deleting) lets a failed
            # move leave that loser's crate entries pointing at its own
            # still-present, still-valid file — no broken reference, nothing
            # hidden — while also letting a failed/interrupted crate rewrite
            # restore an already-trashed file instead of it just being gone.
            trashed: dict[Path, Path] = {}   # loser.file_path -> trash_path
            pending_ops: dict[Path, FileMoveOp] = {}
            if commit:
                for loser in losers:
                    op = FileMoveOp(
                        source_path=loser.file_path,
                        destination_path=winner.file_path,
                        reason='duplicate_consolidation',
                        status='pending',
                    )
                    pending_ops[loser.file_path] = op
                    try:
                        op.sha256_source = _sha256(loser.file_path)
                        trash_dir.mkdir(parents=True, exist_ok=True)
                        trash_counter += 1
                        trash_path = trash_dir / f'{trash_counter:06d}_{loser.file_path.name}'
                        _move_with_flag_retry(loser.file_path, trash_path)
                        trashed[loser.file_path] = trash_path
                    except Exception as exc:
                        op.status = 'failed'
                        op.error  = str(exc)
                        all_errors.append(
                            f'{loser.file_path.name}: delete failed — {exc}'
                        )
                        rlog.log_move(op, duplicate=True)
            else:
                for loser in losers:
                    files_removed += 1
                    space_freed   += loser.file_size

            successful_changes: list[PathChange] = []
            for loser_path in trashed:
                successful_changes.extend(changes_by_loser[loser_path])

            # Reroute crate references for whichever losers were successfully
            # trashed — still one batched PathRewriter call per group (not
            # per loser), so a group with several losers still costs one
            # scan of the .crate tree and one backup per touched crate,
            # same as before.
            rewrite_result = None
            rewrite_ok = False
            if commit and successful_changes:
                try:
                    rewrite_result = PathRewriter(self._serato_dir).rewrite(
                        successful_changes, dry_run=False
                    )
                    # Any per-crate error (rewrite() catches these internally
                    # and still returns normally) means this group's crate
                    # state can't be trusted as fully updated — treat the
                    # whole group as not-safe-to-finalize, same as a hard
                    # exception, rather than guessing which specific loser's
                    # reference actually failed.
                    if rewrite_result.errors:
                        for crate_file, err in rewrite_result.errors:
                            msg = f'{group.canonical_title}: {crate_file.name} — {err}'
                            all_errors.append(msg)
                            rlog.log_error(msg)
                    else:
                        rewrite_ok = True
                        crates_updated += rewrite_result.crates_modified
                        for bp in rewrite_result.backup_paths:
                            rlog.log_crate_backup(bp)
                        touched_crates.update(r.crate_file for r in rewrite_result.changes_log)
                except Exception as exc:
                    msg = f'{group.canonical_title}: crate rewrite failed — {exc}'
                    all_errors.append(msg)
                    rlog.log_error(msg)

            # Finalize: only now, with the crate rewrite confirmed fully
            # successful, do the trashed files actually get deleted for
            # good. Otherwise every trashed loser in this group is restored
            # to exactly where it came from — no file is ever permanently
            # gone while its crate references might still be stale.
            if commit:
                for loser_path, trash_path in trashed.items():
                    op = pending_ops[loser_path]
                    if rewrite_ok:
                        try:
                            trash_path.unlink()
                            _cleanup_empty_parents(loser_path.parent, self._library_path)
                            op.status      = 'completed'
                            op.executed_at = datetime.now().isoformat()
                            loser = next(l for l in losers if l.file_path == loser_path)
                            files_removed += 1
                            space_freed   += loser.file_size
                        except Exception as exc:
                            op.status = 'failed'
                            op.error  = f'trash cleanup failed — {exc}'
                            all_errors.append(
                                f'{loser_path.name}: could not finish removing duplicate — {exc}'
                            )
                    else:
                        try:
                            _move_with_flag_retry(trash_path, loser_path)
                        except Exception as exc:
                            op.status = 'failed'
                            op.error  = f'restore-from-trash failed — {exc}'
                            all_errors.append(
                                f'{loser_path.name}: left in trash, could not restore — {exc} '
                                f'(file is at {trash_path})'
                            )
                        else:
                            op.status = 'failed'
                            op.error  = 'crate rewrite did not succeed — restored'
                    rlog.log_move(op, duplicate=True)

        if commit:
            rlog.save()

        if commit and touched_crates:
            # Fold the crates we just rewrote into the sync checkpoint using a
            # fresh read of each one, right now — ground truth from the same
            # process that just wrote them, not a later rescan that has to
            # guess. Every other crate's checkpoint entry is left untouched,
            # so a genuine external Serato-side edit made elsewhere is still
            # caught next session. See update_checkpoint_crates() docstring.
            reader = CrateReader(self._serato_dir)
            updates: dict[str, list[str]] = {}
            for crate_file in touched_crates:
                try:
                    tracks, _ = reader._read_tracks(crate_file)
                    updates[str(crate_file)] = tracks
                except Exception as exc:
                    all_errors.append(f'checkpoint refresh — {crate_file.name}: {exc}')
            update_checkpoint_crates(self._serato_dir, updates)

        if progress_callback:
            progress_callback(total, total, 'Done')

        return ConsolidationResult(
            groups_processed=total,
            files_removed=files_removed,
            space_freed=space_freed,
            crates_updated=crates_updated,
            errors=all_errors,
            rollback_log_path=log_path if commit else None,
            comment_updates=comment_updates,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MACOS_JUNK = frozenset({'.DS_Store', '.localized', '.Spotlight-V100', '.fseventsd'})


def _move_with_flag_retry(src: Path, dst: Path) -> None:
    """
    Move a file, retrying once after clearing the macOS user-immutable
    (uchg) flag if the first attempt fails with EPERM (Errno 1 — distinct
    from EACCES/Errno 13, a real permissions problem this doesn't touch).
    Files that moved over from Windows/NTFS or came out of certain
    backup/restore tools sometimes land with this flag set, which blocks
    a move/delete even though normal POSIX read/write permissions look
    fine. Only clears the user-level flag (no elevated privileges needed)
    — if that isn't the cause, or clearing it still doesn't allow the
    move, the original exception propagates unchanged. Used for both
    "move to trash" and "restore from trash" — same flag issue can block
    either direction.
    """
    try:
        shutil.move(str(src), str(dst))
        return
    except OSError as exc:
        if exc.errno != errno.EPERM:
            raise
        try:
            current_flags = os.stat(src).st_flags
            if current_flags & stat.UF_IMMUTABLE:
                os.chflags(src, current_flags & ~stat.UF_IMMUTABLE)
                shutil.move(str(src), str(dst))
                return
        except OSError:
            pass
        raise


def _cleanup_empty_parents(start: Path, stop_at: Path) -> None:
    """Walk up from start, removing each directory if empty. Stops at stop_at.
    Strips macOS metadata files (.DS_Store etc.) before checking emptiness."""
    current = start
    while current != stop_at and current != current.parent:
        try:
            if not current.exists():
                break
            # Remove macOS metadata files that would block rmdir
            for item in current.iterdir():
                if item.name in _MACOS_JUNK:
                    item.unlink(missing_ok=True)
            if not any(current.iterdir()):
                current.rmdir()
                current = current.parent
            else:
                break
        except Exception:
            break


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
