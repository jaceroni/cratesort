from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.utils.normalize import normalize_artist, normalize_title

# Duration tolerance for grouping: two entries are candidates if within this many seconds.
_DURATION_TOLERANCE = 3.0

# Tighter tolerance for Tier 1 (true duplicate): same physical file.
_TIER1_DURATION_TOLERANCE = 1.0

# Bitrate spread (kbps) within which we consider files the same encode.
_TIER1_BITRATE_SPREAD = 32

# File size spread (fraction) for strong physical match override.
# Files within 2% of each other in size are treated as the same encode
# even if a variant keyword appears in the filename.
_TIER1_SIZE_SPREAD = 0.02

# Keywords in filename that signal an intentional variant.
_VARIANT_KEYWORDS = re.compile(
    r'\b(remix|remixed|extended|instrumental|acapella|a[- ]?cappella|'
    r'edit|club|radio|dub|mix|12["\s]?inch|12"|remaster(?:ed)?|'
    r'original mix|live|acoustic|feat\.|ft\.)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class MetadataConflict:
    field: str
    values: dict[str, str]    # file_path_str → value


@dataclass
class DuplicateCopy:
    file_path: Path
    format: str
    bitrate: Optional[int]
    file_size: int
    duration: Optional[float]
    genre_tag: Optional[str]
    year_tag: Optional[str]
    comment: Optional[str]
    bpm: Optional[float]
    has_stems: bool
    crate_count: int           # how many crates reference this file
    play_count: Optional[int]  # from Serato database (Phase C Full — None until implemented)
    folder_context: str        # human-readable path context


@dataclass
class DuplicateGroup:
    canonical_title: str
    canonical_artist: str
    copies: list[DuplicateCopy]
    recommended_winner: Optional[DuplicateCopy]
    space_savings: int                           # bytes freed by consolidating
    metadata_conflicts: list[MetadataConflict]
    tier: str                                    # 'true_duplicate' or 'variant'


@dataclass
class DuplicateSummary:
    total_groups: int
    total_duplicate_files: int    # files that would be removed
    space_recoverable: int        # total bytes
    groups_with_conflicts: int
    groups_auto_approvable: int
    tier1_groups: int             # true duplicates
    tier2_groups: int             # variants needing review
    skipped_count: int = 0        # tracks without artist/title — not evaluated


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """
    Finds tracks that appear to be the same song in multiple locations.

    Tier 1 (true_duplicate): same file in multiple locations. Duration within
    ±1s, bitrate within ±32kbps, no variant keywords in filename.

    Tier 2 (variant): same song, different version. Duration or bitrate differs
    significantly, or filename contains remix/extended/etc. keywords.

    Nothing is written to disk. Caller provides crate_count_map so the winner
    scoring can weight files that are more connected to existing crates.
    """

    def detect(
        self,
        inventory: list[TrackRecord],
        crate_count_map: Optional[dict[str, int]] = None,
    ) -> tuple[list[DuplicateGroup], DuplicateSummary]:
        """
        crate_count_map: maps file_path (as posix str) → number of crates that
        reference it. Build from CrateLibrary before calling.
        """
        self._crate_count_map = crate_count_map or {}
        groups = self._fast_pass(inventory)
        summary = self._summarize(groups)
        return groups, summary

    # ── Fast pass ────────────────────────────────────────────────────────────

    def _fast_pass(self, inventory: list[TrackRecord]) -> list[DuplicateGroup]:
        buckets: dict[tuple[str, str], list[TrackRecord]] = defaultdict(list)
        self._skipped_count = 0
        for rec in inventory:
            if rec.artist and rec.title:
                key = (normalize_artist(rec.artist), normalize_title(rec.title))
            else:
                # Filename fallback: folder name → artist, filename stem → title.
                # Covers yt-dl / ripped files that landed with no tags.
                folder_artist  = normalize_artist(rec.path.parent.name)
                filename_title = normalize_title(rec.path.stem)  # normalize_title strips leading track numbers
                if not folder_artist or not filename_title:
                    self._skipped_count += 1
                    continue
                key = (folder_artist, filename_title)
            buckets[key].append(rec)

        groups: list[DuplicateGroup] = []
        for (norm_artist, norm_title), recs in buckets.items():
            if len(recs) < 2:
                continue
            clusters = self._cluster_by_duration(recs)
            for cluster in clusters:
                if len(cluster) < 2:
                    continue
                groups.append(self._build_group(cluster))

        return groups

    def _cluster_by_duration(
        self, recs: list[TrackRecord]
    ) -> list[list[TrackRecord]]:
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

        for rec in no_dur:
            clusters.append([rec])

        return clusters

    def _build_group(self, recs: list[TrackRecord]) -> DuplicateGroup:
        copies = [self._make_copy(r) for r in recs]
        tier = self._classify_tier(copies)
        winner = self._pick_winner(copies)
        conflicts = self._find_conflicts(copies)

        canonical_title = recs[0].title or ''
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
            tier=tier,
        )

    def _make_copy(self, rec: TrackRecord) -> DuplicateCopy:
        parts = rec.path.parts
        context = str(Path(*parts[-3:-1])) if len(parts) >= 3 else str(rec.path.parent)
        crate_count = self._crate_count_map.get(rec.path.as_posix(), 0)

        return DuplicateCopy(
            file_path=rec.path,
            format=rec.extension.lstrip('.').upper(),
            bitrate=rec.bitrate,
            file_size=rec.file_size,
            duration=rec.duration,
            genre_tag=rec.genre,
            year_tag=rec.year,
            comment=rec.comment,
            bpm=rec.bpm,
            has_stems=rec.stems_path is not None,
            crate_count=crate_count,
            play_count=None,   # Phase C Full: read from Serato database V2
            folder_context=context,
        )

    # ── Tier classification ───────────────────────────────────────────────────

    def _classify_tier(self, copies: list[DuplicateCopy]) -> str:
        """
        Tier 1 (true_duplicate): files are physically the same recording.
        - Strong physical match (duration ±1s, bitrate ±32kbps, size ±2%) overrides
          any variant keyword in the filename — physical evidence wins.
        - OR: no variant keywords AND duration/bitrate within tolerances.

        Tier 2 (variant): intentionally different versions.
        - Has variant keywords AND physical metrics don't all agree, OR
        - Duration spread > 1s, OR bitrate spread > 32kbps.
        """
        # Strong physical match overrides filename annotation.
        # If the bits agree this closely, the filename is irrelevant.
        if self._is_strong_physical_match(copies):
            return 'true_duplicate'

        # Variant keyword in any filename → Tier 2
        for c in copies:
            if _VARIANT_KEYWORDS.search(c.file_path.name):
                return 'variant'

        # Duration spread check
        durations = [c.duration for c in copies if c.duration is not None]
        if len(durations) >= 2:
            if max(durations) - min(durations) > _TIER1_DURATION_TOLERANCE:
                return 'variant'

        # Bitrate spread check
        bitrates = [c.bitrate for c in copies if c.bitrate is not None]
        if len(bitrates) >= 2:
            if max(bitrates) - min(bitrates) > _TIER1_BITRATE_SPREAD:
                return 'variant'

        return 'true_duplicate'

    def _is_strong_physical_match(self, copies: list[DuplicateCopy]) -> bool:
        """Duration, bitrate, AND file size all agree — physically the same file."""
        durations = [c.duration for c in copies if c.duration is not None]
        if len(durations) >= 2 and max(durations) - min(durations) > _TIER1_DURATION_TOLERANCE:
            return False

        bitrates = [c.bitrate for c in copies if c.bitrate is not None]
        if len(bitrates) >= 2 and max(bitrates) - min(bitrates) > _TIER1_BITRATE_SPREAD:
            return False

        sizes = [c.file_size for c in copies if c.file_size > 0]
        if len(sizes) >= 2 and (max(sizes) - min(sizes)) / max(sizes) > _TIER1_SIZE_SPREAD:
            return False

        return True

    # ── Winner selection ──────────────────────────────────────────────────────

    def _pick_winner(self, copies: list[DuplicateCopy]) -> Optional[DuplicateCopy]:
        if not copies:
            return None

        def score(c: DuplicateCopy) -> tuple:
            # Priority (descending): crate presence, play count, bitrate,
            # metadata completeness, has comment, has stems, clean filename
            crate_count       = c.crate_count
            play_count        = c.play_count or 0
            bitrate           = c.bitrate or 0
            meta_completeness = sum(1 for v in [c.genre_tag, c.year_tag, c.bpm] if v)
            has_comment       = int(bool(c.comment))
            has_stems         = int(c.has_stems)
            # Prefer filenames without leading track numbers (e.g. "02 Title.mp3")
            clean_filename    = 0 if re.match(r'^\d+[\s\.\-]', c.file_path.stem) else 1
            return (crate_count, play_count, bitrate, meta_completeness, has_comment, has_stems, clean_filename)

        return max(copies, key=score)

    def _winner_reasoning(self, winner: DuplicateCopy, _all_copies: list[DuplicateCopy]) -> str:
        """Human-readable explanation of why this copy was chosen."""
        reasons = []
        if winner.crate_count > 0:
            n = winner.crate_count
            reasons.append(f'in {n} crate{"s" if n != 1 else ""}')
        if winner.play_count and winner.play_count > 0:
            reasons.append(f'{winner.play_count} plays')
        if winner.bitrate:
            reasons.append(f'{winner.bitrate} kbps')
        if winner.format:
            reasons.append(winner.format)
        return ' · '.join(reasons) if reasons else 'best available copy'

    # ── Conflict detection ────────────────────────────────────────────────────

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
            if len(set(non_none)) > 1:
                # Genuine disagreement — both copies have a value but they differ
                conflicts.append(MetadataConflict(field=field_name, values=values))

        return conflicts

    # ── Deep pass (stub) ─────────────────────────────────────────────────────

    def fingerprint_pass(
        self, inventory: list[TrackRecord]
    ) -> list[DuplicateGroup]:
        """
        Audio fingerprint detection via chromaprint/pyacoustid.
        Catches duplicates where metadata is completely different but audio is identical.
        TODO: implement when pyacoustid + chromaprint binary are available.
        """
        return []

    # ── Summary ───────────────────────────────────────────────────────────────

    def _summarize(self, groups: list[DuplicateGroup]) -> DuplicateSummary:
        total_dupes = sum(len(g.copies) - 1 for g in groups)
        space = sum(g.space_savings for g in groups)
        with_conflicts = sum(1 for g in groups if g.metadata_conflicts)
        auto = sum(1 for g in groups if not g.metadata_conflicts)
        tier1 = sum(1 for g in groups if g.tier == 'true_duplicate')
        tier2 = sum(1 for g in groups if g.tier == 'variant')
        return DuplicateSummary(
            total_groups=len(groups),
            total_duplicate_files=total_dupes,
            space_recoverable=space,
            groups_with_conflicts=with_conflicts,
            groups_auto_approvable=auto,
            tier1_groups=tier1,
            tier2_groups=tier2,
            skipped_count=getattr(self, '_skipped_count', 0),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_crate_count_map(crate_library) -> dict[str, int]:
    """
    Build a file_path_posix → crate_count mapping from a CrateLibrary.
    Pass this into DuplicateDetector.detect() for accurate winner scoring.
    """
    counts: dict[str, int] = defaultdict(int)
    for crate in crate_library.crates.values():
        for track_path in crate.tracks:
            counts[track_path] += 1
    return dict(counts)


def fmt_bytes(n: int) -> str:
    """Human-readable file size: '4.1 GB', '342 MB', etc."""
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.1f} {unit}' if unit != 'B' else f'{n} {unit}'
        n //= 1024
    return f'{n:.1f} TB'
