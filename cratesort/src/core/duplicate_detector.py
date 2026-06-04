from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.utils.normalize import normalize_artist, normalize_title

# Duration tolerance: two copies are considered the same song if their
# durations are within this many seconds of each other.
_DURATION_TOLERANCE = 3.0


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class MetadataConflict:
    field: str
    values: dict[str, str]    # file_path_str → value (so user can see which copy has what)


@dataclass
class DuplicateCopy:
    file_path: Path
    format: str
    bitrate: Optional[int]
    file_size: int
    genre_tag: Optional[str]
    year_tag: Optional[str]
    comment: Optional[str]
    bpm: Optional[float]
    has_stems: bool
    folder_context: str        # human-readable path context


@dataclass
class DuplicateGroup:
    canonical_title: str
    canonical_artist: str
    copies: list[DuplicateCopy]
    recommended_winner: Optional[DuplicateCopy]
    space_savings: int                          # bytes freed by consolidating
    metadata_conflicts: list[MetadataConflict]


@dataclass
class DuplicateSummary:
    total_groups: int
    total_duplicate_files: int   # files that would be removed
    space_recoverable: int       # total bytes
    groups_with_conflicts: int
    groups_auto_approvable: int


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """
    Finds tracks that appear to be the same song in multiple locations.

    Fast pass:  Normalized artist + normalized title + duration within ±3s.
    Deep pass:  Audio fingerprinting (stubbed — see fingerprint_pass()).

    Nothing is written to disk.
    """

    def detect(
        self, inventory: list[TrackRecord]
    ) -> tuple[list[DuplicateGroup], DuplicateSummary]:
        groups = self._fast_pass(inventory)
        # Deep pass is stubbed — would extend groups with fingerprint matches
        # groups.extend(self._fingerprint_pass(inventory))
        summary = self._summarize(groups)
        return groups, summary

    # ── Fast pass ────────────────────────────────────────────────────────────

    def _fast_pass(self, inventory: list[TrackRecord]) -> list[DuplicateGroup]:
        # Bucket by (normalized_artist, normalized_title)
        buckets: dict[tuple[str, str], list[TrackRecord]] = defaultdict(list)
        for rec in inventory:
            if not rec.artist or not rec.title:
                continue
            key = (normalize_artist(rec.artist), normalize_title(rec.title))
            buckets[key].append(rec)

        groups: list[DuplicateGroup] = []
        for (norm_artist, norm_title), recs in buckets.items():
            if len(recs) < 2:
                continue
            # Further filter: duration within tolerance
            clusters = self._cluster_by_duration(recs)
            for cluster in clusters:
                if len(cluster) < 2:
                    continue
                groups.append(self._build_group(cluster))

        return groups

    def _cluster_by_duration(
        self, recs: list[TrackRecord]
    ) -> list[list[TrackRecord]]:
        """Group records whose durations are within _DURATION_TOLERANCE of each other."""
        if not recs:
            return []

        # Sort by duration; use None-duration records as their own cluster
        with_dur = sorted(
            [r for r in recs if r.duration is not None],
            key=lambda r: r.duration,  # type: ignore[arg-type]
        )
        no_dur = [r for r in recs if r.duration is None]

        clusters: list[list[TrackRecord]] = []
        current: list[TrackRecord] = []

        for rec in with_dur:
            if not current:
                current.append(rec)
            elif rec.duration - current[0].duration <= _DURATION_TOLERANCE:  # type: ignore[operator]
                current.append(rec)
            else:
                clusters.append(current)
                current = [rec]
        if current:
            clusters.append(current)

        # Each no-duration record is its own cluster (can't confirm without timing)
        for rec in no_dur:
            clusters.append([rec])

        return clusters

    def _build_group(self, recs: list[TrackRecord]) -> DuplicateGroup:
        copies = [self._make_copy(r) for r in recs]
        winner = self._pick_winner(copies)
        conflicts = self._find_conflicts(copies)

        # Best title/artist from the winner (or the longest/most complete)
        canonical_title = winner.file_path.stem if winner else (recs[0].title or '')
        canonical_artist = recs[0].artist or ''
        for rec in recs:
            if rec.title and len(rec.title) > len(canonical_title):
                canonical_title = rec.title
            if rec.artist:
                canonical_artist = rec.artist

        total_size = sum(c.file_size for c in copies)
        winner_size = winner.file_size if winner else 0
        space_savings = total_size - winner_size

        return DuplicateGroup(
            canonical_title=canonical_title,
            canonical_artist=canonical_artist,
            copies=copies,
            recommended_winner=winner,
            space_savings=space_savings,
            metadata_conflicts=conflicts,
        )

    def _make_copy(self, rec: TrackRecord) -> DuplicateCopy:
        # Build a short human-readable folder context (last 2 path components)
        parts = rec.path.parts
        context = str(Path(*parts[-3:-1])) if len(parts) >= 3 else str(rec.path.parent)

        return DuplicateCopy(
            file_path=rec.path,
            format=rec.extension.lstrip('.').upper(),
            bitrate=rec.bitrate,
            file_size=rec.file_size,
            genre_tag=rec.genre,
            year_tag=rec.year,
            comment=rec.comment,
            bpm=rec.bpm,
            has_stems=rec.stems_path is not None,
            folder_context=context,
        )

    def _pick_winner(self, copies: list[DuplicateCopy]) -> Optional[DuplicateCopy]:
        if not copies:
            return None

        def score(c: DuplicateCopy) -> tuple:
            # Higher is better
            bitrate   = c.bitrate or 0
            meta_completeness = sum(1 for v in [c.genre_tag, c.year_tag, c.bpm] if v)
            has_stems = int(c.has_stems)
            return (bitrate, meta_completeness, has_stems)

        return max(copies, key=score)

    def _find_conflicts(self, copies: list[DuplicateCopy]) -> list[MetadataConflict]:
        conflicts: list[MetadataConflict] = []
        fields = {
            'genre':   lambda c: c.genre_tag,
            'year':    lambda c: c.year_tag,
            'comment': lambda c: c.comment,
            'bpm':     lambda c: str(round(c.bpm)) if c.bpm else None,
        }
        for field_name, getter in fields.items():
            values = {str(c.file_path): getter(c) for c in copies}
            non_none = [v for v in values.values() if v]
            # Conflict if there are multiple distinct non-None values
            if len(set(non_none)) > 1:
                conflicts.append(MetadataConflict(field=field_name, values=values))
            # Comment conflict: any copy has a comment but not all do
            elif field_name == 'comment' and non_none and len(non_none) < len(copies):
                conflicts.append(MetadataConflict(field='comment (migrate)', values=values))

        return conflicts

    # ── Deep pass (stub) ─────────────────────────────────────────────────────

    def fingerprint_pass(
        self, inventory: list[TrackRecord]
    ) -> list[DuplicateGroup]:
        """
        Audio fingerprint duplicate detection via chromaprint/pyacoustid.
        TODO: implement when pyacoustid and chromaprint binary are available.
        This pass catches duplicates where metadata is completely different
        but the audio is acoustically identical.
        """
        return []

    # ── Summary ───────────────────────────────────────────────────────────────

    def _summarize(self, groups: list[DuplicateGroup]) -> DuplicateSummary:
        total_dupes = sum(len(g.copies) - 1 for g in groups)
        space = sum(g.space_savings for g in groups)
        with_conflicts = sum(1 for g in groups if g.metadata_conflicts)
        auto = sum(1 for g in groups if not g.metadata_conflicts)
        return DuplicateSummary(
            total_groups=len(groups),
            total_duplicate_files=total_dupes,
            space_recoverable=space,
            groups_with_conflicts=with_conflicts,
            groups_auto_approvable=auto,
        )
