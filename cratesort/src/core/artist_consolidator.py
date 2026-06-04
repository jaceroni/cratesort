from __future__ import annotations

import difflib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.utils.normalize import normalize_artist

# Minimum normalized-name length to attempt substring or fuzzy matching.
# Prevents single-word false positives like "Ice" matching "Ice Cube" and "Ice-T".
_MIN_MATCH_LEN = 4

# Fuzzy similarity thresholds
_FUZZY_HIGH = 0.92
_FUZZY_MEDIUM = 0.85

# Substring ratio thresholds  (len(shorter) / len(longer))
_SUB_MEDIUM = 0.50
# Anything below _SUB_MEDIUM is LOW


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class MergeProposal:
    winning_name: str    # the name to keep (default: longest / most complete)
    use_subfolders: bool # True when variants are genuinely different projects


@dataclass
class ConsolidationCandidate:
    primary_name: str                      # longest / most complete name
    variant_names: list[str]               # other names detected as variants
    track_counts: dict[str, int]           # name → number of tracks
    confidence: str                        # HIGH / MEDIUM / LOW
    match_method: str                      # how the match was detected
    genres: set[str]                       # genres across all variants
    sample_tracks: dict[str, list[str]]    # name → [track title, ...]
    merge_proposal: MergeProposal


# ---------------------------------------------------------------------------
# Consolidator
# ---------------------------------------------------------------------------

class ArtistConsolidator:
    """
    Detects artist names that likely refer to the same person or band but are
    stored under different names.  Returns ConsolidationCandidate proposals for
    user review.  Nothing is written to disk.
    """

    def analyze(self, inventory: list[TrackRecord]) -> list[ConsolidationCandidate]:
        # Build artist → tracks index
        artist_tracks: dict[str, list[TrackRecord]] = defaultdict(list)
        for rec in inventory:
            if rec.artist:
                artist_tracks[rec.artist].append(rec)

        artists = list(artist_tracks.keys())
        if len(artists) < 2:
            return []

        # Build similarity edges
        edges: list[tuple[str, str, str, str]] = []  # (a, b, confidence, method)
        for i in range(len(artists)):
            for j in range(i + 1, len(artists)):
                result = self._match(artists[i], artists[j])
                if result:
                    conf, method = result
                    edges.append((artists[i], artists[j], conf, method))

        # Union-find to cluster connected artists
        parent = {a: a for a in artists}
        edge_meta: dict[frozenset, tuple[str, str]] = {}  # {frozenset(a,b): (conf, method)}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: str, y: str) -> None:
            parent[find(x)] = find(y)

        for a, b, conf, method in edges:
            union(a, b)
            edge_meta[frozenset({a, b})] = (conf, method)

        # Group artists by component
        components: dict[str, list[str]] = defaultdict(list)
        for a in artists:
            components[find(a)].append(a)

        # Build candidates from multi-artist groups
        candidates: list[ConsolidationCandidate] = []
        for group in components.values():
            if len(group) < 2:
                continue
            candidates.append(self._build_candidate(group, artist_tracks, edge_meta))

        return sorted(candidates, key=lambda c: c.primary_name)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _match(
        self, a: str, b: str
    ) -> Optional[tuple[str, str]]:
        """
        Return (confidence, method) if a and b are likely the same artist,
        else None.
        """
        na, nb = normalize_artist(a), normalize_artist(b)

        # Pass 1 — exact after normalization
        if na == nb:
            return ('HIGH', 'exact_normalized')

        # Skip pairs where either normalized name is too short
        if len(na) < _MIN_MATCH_LEN or len(nb) < _MIN_MATCH_LEN:
            return None

        # Pass 2 — substring: one normalized name is a word-boundary prefix of the other
        shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
        if longer.startswith(shorter) and (
            len(longer) == len(shorter) or longer[len(shorter)] == ' '
        ):
            ratio = len(shorter) / len(longer)
            conf = 'MEDIUM' if ratio >= _SUB_MEDIUM else 'LOW'
            return (conf, 'substring')

        # Pass 3 — fuzzy similarity
        sim = difflib.SequenceMatcher(None, na, nb).ratio()
        if sim >= _FUZZY_HIGH:
            return ('HIGH', 'fuzzy')
        if sim >= _FUZZY_MEDIUM:
            return ('MEDIUM', 'fuzzy')

        return None

    def _build_candidate(
        self,
        group: list[str],
        artist_tracks: dict[str, list[TrackRecord]],
        edge_meta: dict[frozenset, tuple[str, str]],
    ) -> ConsolidationCandidate:
        # Gather all edges within this group
        group_set = set(group)
        group_edges = [
            (a, b, conf, method)
            for (a, b, conf, method) in (
                (a, b, *meta)
                for fs, meta in edge_meta.items()
                for a, b in [tuple(fs)]
                if {a, b} <= group_set
            )
        ]

        # Confidence = minimum across all edges (most conservative)
        _rank = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        min_conf = min(group_edges, key=lambda e: _rank[e[2]], default=('', '', 'LOW', ''))[2]

        # Method = set of methods used
        methods = sorted({e[3] for e in group_edges})
        method_str = ' + '.join(methods)

        # Track counts and genres
        track_counts = {name: len(artist_tracks[name]) for name in group}

        # Primary name = most tracks; ties prefer name without commas (solo
        # artist over collaboration), then longest name.
        def _primary_score(name: str) -> tuple:
            return (track_counts[name], 0 if ',' in name else 1, len(name))

        primary = max(group, key=_primary_score)
        variants = [n for n in group if n != primary]
        genres: set[str] = set()
        for name in group:
            for rec in artist_tracks[name]:
                if rec.genre:
                    genres.add(rec.genre)

        # Sample tracks (up to 2 per name)
        sample_tracks: dict[str, list[str]] = {}
        for name in group:
            titles = [r.title for r in artist_tracks[name] if r.title][:2]
            if titles:
                sample_tracks[name] = titles

        # Merge proposal
        # use_subfolders = True when method involves substring (different projects),
        # False when it's purely a formatting/spelling variation
        use_subfolders = 'substring' in method_str

        return ConsolidationCandidate(
            primary_name=primary,
            variant_names=variants,
            track_counts=track_counts,
            confidence=min_conf,
            match_method=method_str,
            genres=genres,
            sample_tracks=sample_tracks,
            merge_proposal=MergeProposal(
                winning_name=primary,
                use_subfolders=use_subfolders,
            ),
        )
