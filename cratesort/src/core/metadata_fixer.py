from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.core.classifier import ClassificationResult, Confidence
from cratesort.src.utils.the_handler import TheHandler

# ---------------------------------------------------------------------------
# Album keywords that suggest a compilation or reissue date, not an original
# release year.  When an album title contains one of these, the year tag is
# flagged for user review.
# ---------------------------------------------------------------------------
_COMPILATION_KEYWORDS = frozenset({
    "greatest hits", "best of", "collection", "anthology", "compilation",
    "deluxe edition", "essential", "the complete", "the definitive",
    "the ultimate", "platinum edition", "gold edition", "retrospective",
    "anniversary edition", "remaster", "remastered",
    "years of",  # "30 Years of..."
})

# Serato custom ID3 frames — NEVER propose writing to these
_SERATO_FRAMES = frozenset({
    "Serato Analysis", "Serato Autotags", "Serato BeatGrid",
    "Serato Markers_", "Serato Markers2", "Serato Overview", "Serato Offsets_",
})


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class MetadataChange:
    field: str
    current_value: Optional[str]
    proposed_value: Optional[str]
    confidence: str          # "HIGH", "MEDIUM", "LOW"
    reason: str
    needs_review: bool = False


@dataclass
class MetadataProposal:
    file_path: Path
    artist: Optional[str]
    changes: list[MetadataChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)

    @property
    def review_count(self) -> int:
        return sum(1 for c in self.changes if c.needs_review)


# ---------------------------------------------------------------------------
# Fixer class
# ---------------------------------------------------------------------------

class MetadataFixer:
    """
    Analyzes TrackRecords + ClassificationResults and proposes metadata
    corrections.  Read-only — nothing is written to disk.

    Rules:
      - Genre tag updated to match classifier's parent genre
      - Sort-artist proposed for artists beginning with "The"
      - Year flagged when album suggests a compilation/reissue date
      - Comment field is never touched
      - Serato custom frames are never touched
    """

    def __init__(self, handle_a_an: bool = False):
        self._the_handler = TheHandler(handle_a_an=handle_a_an)

    def analyze(
        self,
        record: TrackRecord,
        classification: ClassificationResult,
    ) -> Optional[MetadataProposal]:
        changes: list[MetadataChange] = []

        self._check_genre(record, classification, changes)
        self._check_sort_artist(record, changes)
        self._check_year(record, changes)

        if not changes:
            return None
        return MetadataProposal(
            file_path=record.path,
            artist=record.artist,
            changes=changes,
        )

    def analyze_all(
        self,
        results: list[tuple[TrackRecord, ClassificationResult]],
    ) -> list[MetadataProposal]:
        proposals = []
        for record, classification in results:
            p = self.analyze(record, classification)
            if p:
                proposals.append(p)
        return proposals

    # ── Internal checkers ────────────────────────────────────────────────────

    def _check_genre(
        self,
        record: TrackRecord,
        classification: ClassificationResult,
        changes: list[MetadataChange],
    ) -> None:
        """Propose updating the genre tag to the classifier's parent genre."""
        if not classification.genre:
            return

        current = (record.genre or '').strip()
        proposed = classification.genre

        if current == proposed:
            return  # already correct

        confidence = classification.confidence.value
        needs_review = classification.confidence in (Confidence.LOW, Confidence.NONE)

        changes.append(MetadataChange(
            field='genre',
            current_value=current or None,
            proposed_value=proposed,
            confidence=confidence,
            reason=classification.reason,
            needs_review=needs_review,
        ))

    def _check_sort_artist(
        self,
        record: TrackRecord,
        changes: list[MetadataChange],
    ) -> None:
        """Propose writing a sort-artist (TSOP) value for 'The' artists."""
        if not record.artist:
            return

        proposal = self._the_handler.analyze(record.artist)
        if not proposal:
            return

        changes.append(MetadataChange(
            field='sort_artist',
            current_value=None,     # scanner doesn't read TSOP; always propose
            proposed_value=proposal.sort_name,
            confidence='HIGH',
            reason=f"Artist '{record.artist}' begins with article — sort form is '{proposal.sort_name}'",
        ))

    def _check_year(
        self,
        record: TrackRecord,
        changes: list[MetadataChange],
    ) -> None:
        """Flag year when album title suggests a compilation/reissue."""
        if not record.year or not record.album:
            return

        album_lower = record.album.lower()
        matched = next(
            (kw for kw in _COMPILATION_KEYWORDS if kw in album_lower),
            None,
        )
        if matched:
            changes.append(MetadataChange(
                field='year',
                current_value=record.year,
                proposed_value=None,   # can't auto-correct without an external source
                confidence='LOW',
                reason=(
                    f"Album '{record.album}' contains '{matched}' — "
                    f"year '{record.year}' may be compilation/reissue date, not original release"
                ),
                needs_review=True,
            ))
