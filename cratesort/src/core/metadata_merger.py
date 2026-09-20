from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratesort.src.serato.database_reader import read_track_metadata, _normalize_pfil_keys
from cratesort.src.serato.database_writer import update_play_count, update_comment
from cratesort.src.serato.markers_reader import CuePoint, read_cue_points
from cratesort.src.serato.markers_writer import write_cue_points

logger = logging.getLogger(__name__)

# Cue points within this many ms are treated as the same point (keep winner's).
_CUE_POSITION_TOLERANCE_MS = 200

# Maximum Serato cue slots.
_MAX_CUE_SLOTS = 8


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class MergeResult:
    play_count_merged:   bool = False
    play_count_total:    int  = 0
    comment_merged:      bool = False
    comment_final:       Optional[str] = None
    cues_merged:         int  = 0      # number of loser cues folded in
    cues_lost:           int  = 0      # loser cues that couldn't fit (all slots full)
    lost_cue_details:    list[str] = field(default_factory=list)
    errors:              list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_metadata(
    winner_path:    Path,
    loser_paths:    list[Path],
    winner_comment: Optional[str],
    loser_comments: list[Optional[str]],
    serato_dir:     Path,
) -> MergeResult:
    """
    Merge play counts, comments, and cue points from every loser into the winner.

    Rules:
    - Play count: sum all copies. Winner's existing count + all loser counts.
    - Comments: collect all unique non-empty values, join with ', '.
    - Cue points: position-dedup first (±200ms = same cue, keep winner's).
      Unmatched loser cues fill empty winner slots. On slot conflict, winner
      keeps its cue. Cues that don't fit (all 8 slots full) are logged.

    Returns a MergeResult describing what was changed.
    Never raises — all errors are captured in MergeResult.errors.
    """
    result = MergeResult()

    # ── 1. Play counts ────────────────────────────────────────────────────────
    _merge_play_counts(winner_path, loser_paths, serato_dir, result)

    # ── 2. Comments ───────────────────────────────────────────────────────────
    _merge_comments(winner_path, winner_comment, loser_comments, serato_dir, result)

    # ── 3. Cue points ─────────────────────────────────────────────────────────
    _merge_cue_points(winner_path, loser_paths, result)

    return result


# ---------------------------------------------------------------------------
# Play count merge
# ---------------------------------------------------------------------------

def _merge_play_counts(
    winner_path: Path,
    loser_paths: list[Path],
    serato_dir:  Path,
    result:      MergeResult,
) -> None:
    db_metadata = read_track_metadata(serato_dir)

    def _play_count_for(path: Path) -> int:
        posix = path.as_posix()
        # Try all normalized key variants
        for key in _normalize_pfil_keys(posix):
            entry = db_metadata.get(key)
            if entry and entry.play_count is not None:
                return entry.play_count
        # Also try just the filename stem
        entry = db_metadata.get(posix)
        if entry and entry.play_count is not None:
            return entry.play_count
        return 0

    winner_plays = _play_count_for(winner_path)
    loser_plays  = [_play_count_for(p) for p in loser_paths]
    total_plays  = winner_plays + sum(loser_plays)

    result.play_count_total = total_plays

    # DISABLED 2026-09-19: this called update_play_count() to patch Serato's
    # database V2 directly — same binary-patch mechanism (_patch_utpc) that
    # the now-disabled comment write mirrors (_patch_tcom). A real database
    # corruption incident happened on the exact drive this ran against
    # today, during heavy consolidation use. Disabling this too, out of the
    # same caution, even though this specific function predates today — not
    # worth writing to Serato's actual database on an unproven guess either
    # way. See the matching note in _merge_comments above.
    #
    # if total_plays != winner_plays and total_plays > 0:
    #     success = update_play_count(serato_dir, winner_path.as_posix(), total_plays)
    #     if success:
    #         result.play_count_merged = True
    #         logger.info(
    #             '[MetadataMerger] Play count: %d → %d for %s',
    #             winner_plays, total_plays, winner_path.name,
    #         )
    #     else:
    #         result.errors.append(
    #             f'play_count: failed to write {total_plays} to database V2 '
    #             f'for {winner_path.name}'
    #         )


# ---------------------------------------------------------------------------
# Comment merge
# ---------------------------------------------------------------------------

def _merge_comments(
    winner_path:    Path,
    winner_comment: Optional[str],
    loser_comments: list[Optional[str]],
    serato_dir:     Path,
    result:         MergeResult,
) -> None:
    all_comments = [winner_comment] + loser_comments
    seen:  set[str] = set()
    parts: list[str] = []

    for c in all_comments:
        if c:
            normalized = c.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                parts.append(normalized)

    if len(parts) <= 1:
        # Nothing to merge — winner already has the only comment (or none at all)
        result.comment_final = parts[0] if parts else None
        return

    merged = ', '.join(parts)
    result.comment_merged = True
    result.comment_final  = merged

    try:
        _write_comment(winner_path, merged)
        logger.info(
            '[MetadataMerger] Comment merged for %s: %r', winner_path.name, merged
        )
    except Exception as exc:
        result.errors.append(f'comment: write failed for {winner_path.name} — {exc}')

    # DISABLED 2026-09-19: this called update_comment() to also patch Serato's
    # database V2 directly (its `tcom` field), so a merged comment would show
    # up inside Serato, not just in the file's own tag. That binary patcher
    # was only ever verified against a small synthetic test file, never
    # against a real, large, production database V2 — and a real corruption
    # incident happened on the exact drive this ran against today. Whether
    # this specific code caused it is unconfirmed, but it cannot be ruled
    # out, and writing to Serato's actual database is not something to keep
    # doing on an unproven guess. Reverted to the previously-safe behavior:
    # comment merge only writes the file's own tag. Do not re-enable without
    # actually testing _patch_tcom / _patch_otrk_tcom (database_writer.py)
    # against a real, full-size database V2 copy first.
    #
    # if not update_comment(serato_dir, winner_path.as_posix(), merged):
    #     result.errors.append(
    #         f'comment: failed to write merged comment to Serato database for {winner_path.name}'
    #     )


def _write_comment(file_path: Path, comment: str) -> None:
    """Write a comment to an audio file's standard comment tag via mutagen."""
    import mutagen
    ext = file_path.suffix.lower()

    audio = mutagen.File(str(file_path), easy=False)
    if audio is None:
        raise ValueError(f'mutagen could not open {file_path}')

    if ext in ('.mp3', '.aiff', '.aif'):
        import mutagen.id3 as id3_mod
        # Remove all existing COMM frames, add one clean one
        keys_to_remove = [k for k in audio.tags if k.startswith('COMM')]
        for k in keys_to_remove:
            del audio.tags[k]
        audio.tags.add(id3_mod.COMM(encoding=3, lang='eng', desc='', text=[comment]))

    elif ext == '.flac':
        audio['comment'] = [comment]

    elif ext in ('.m4a', '.mp4', '.aac'):
        audio['\xa9cmt'] = [comment]

    elif ext in ('.ogg', '.opus'):
        audio['comment'] = [comment]

    else:
        raise ValueError(f'Unsupported format for comment write: {ext}')

    audio.save()


# ---------------------------------------------------------------------------
# Cue point merge
# ---------------------------------------------------------------------------

def _merge_cue_points(
    winner_path: Path,
    loser_paths: list[Path],
    result:      MergeResult,
) -> None:
    winner_cues = read_cue_points(winner_path)
    if not winner_cues and not loser_paths:
        return

    # Collect all loser cues
    all_loser_cues: list[CuePoint] = []
    for lp in loser_paths:
        all_loser_cues.extend(read_cue_points(lp))

    if not all_loser_cues:
        return  # Nothing to merge

    # Build a mutable slot map from winner cues (index 0-7)
    slot_map: dict[int, CuePoint] = {c.index: c for c in winner_cues}

    # Find empty slots
    empty_slots = [i for i in range(_MAX_CUE_SLOTS) if i not in slot_map]

    cues_merged = 0
    cues_lost   = 0
    lost_details: list[str] = []

    for loser_cue in all_loser_cues:
        # Check if this cue is already represented in the winner
        # (same position within tolerance, regardless of slot index)
        if _has_near_match(loser_cue, list(slot_map.values())):
            continue  # Deduplicated — winner already has this cue

        # Try to place in the loser's original slot first
        if loser_cue.index not in slot_map:
            slot_map[loser_cue.index] = loser_cue
            if loser_cue.index in empty_slots:
                empty_slots.remove(loser_cue.index)
            cues_merged += 1
            continue

        # Slot is occupied by winner — try next available empty slot
        if empty_slots:
            slot = empty_slots.pop(0)
            slot_map[slot] = CuePoint(
                index=slot,
                position_ms=loser_cue.position_ms,
                color_rgb=loser_cue.color_rgb,
                name=loser_cue.name,
            )
            cues_merged += 1
        else:
            # All 8 slots full — this cue is lost
            cues_lost += 1
            lost_details.append(
                f'slot {loser_cue.index} "{loser_cue.name}" @ {loser_cue.position_ms}ms'
            )

    result.cues_merged     = cues_merged
    result.cues_lost       = cues_lost
    result.lost_cue_details = lost_details

    if cues_merged > 0:
        merged_cues = list(slot_map.values())
        success = write_cue_points(winner_path, merged_cues)
        if not success:
            result.errors.append(
                f'cue_points: write failed for {winner_path.name}'
            )
        else:
            logger.info(
                '[MetadataMerger] %d loser cue(s) merged into %s (%d lost)',
                cues_merged, winner_path.name, cues_lost,
            )

    if cues_lost > 0:
        logger.warning(
            '[MetadataMerger] %d cue(s) could not fit (all slots full) for %s: %s',
            cues_lost, winner_path.name, '; '.join(lost_details),
        )


def _has_near_match(cue: CuePoint, existing: list[CuePoint]) -> bool:
    """True if any existing cue is within _CUE_POSITION_TOLERANCE_MS of this cue."""
    for e in existing:
        if abs(e.position_ms - cue.position_ms) <= _CUE_POSITION_TOLERANCE_MS:
            return True
    return False
