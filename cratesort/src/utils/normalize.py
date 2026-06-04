"""
Shared text normalization for artist and title comparison.
Used by ArtistConsolidator and DuplicateDetector.
"""
from __future__ import annotations

import re


def normalize_artist(name: str) -> str:
    """
    Normalize an artist name for comparison.
    Strips articles, punctuation, and connector variants so that
    'Gap Band, The', 'The Gap Band', and 'gap band' all become 'gap band'.
    """
    name = name.strip().lower()
    # Sort-form suffix: "Gap Band, The" → "gap band"
    name = re.sub(r',\s*(?:the|an?)$', '', name)
    # Leading article: "The Gap Band" → "gap band"
    name = re.sub(r'^(?:the|an?)\s+', '', name)
    # Normalize & / + → and
    name = re.sub(r'\s*[&+]\s*', ' and ', name)
    # Strip remaining non-word characters (apostrophes, periods, etc.)
    name = re.sub(r"[^\w\s]", ' ', name)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', name).strip()


def normalize_title(title: str) -> str:
    """
    Normalize a track title for duplicate comparison.
    Strips parenthesized version suffixes that don't affect musical identity,
    then strips punctuation.
    """
    title = title.strip().lower()
    # Strip parenthesized/bracketed version suffixes
    title = re.sub(
        r'\s*[\(\[]\s*'
        r'(?:remaster(?:ed)?(?:\s+\d{4})?'
        r'|original\s+mix'
        r'|single\s+version'
        r'|mono|stereo'
        r'|bonus\s+track)\s*[\)\]]',
        '', title, flags=re.I,
    )
    # Strip punctuation
    title = re.sub(r"[^\w\s]", ' ', title)
    return re.sub(r'\s+', ' ', title).strip()
