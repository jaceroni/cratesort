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
    Strips version suffixes, featured artists, years, and track number
    prefixes that don't affect musical identity, then strips punctuation.
    """
    title = title.strip().lower()
    # Strip leading track numbers: "02 Title", "02. Title", "02 - Title"
    title = re.sub(r'^\d{1,3}[\s\.\-]+', '', title)
    # Strip parenthesized/bracketed version suffixes: "Title (Original Mix)"
    title = re.sub(
        r'\s*[\(\[]\s*'
        r'(?:remaster(?:ed)?(?:\s+\d{4})?'
        r'|original\s+mix'
        r'|single\s+version'
        r'|mono|stereo'
        r'|bonus\s+track)\s*[\)\]]',
        '', title, flags=re.I,
    )
    # Strip parenthesized years: "Title (1982)", "Title (2023)"
    title = re.sub(r'\s*[\(\[]\s*\d{4}\s*[\)\]]', '', title)
    # Strip hyphenated version qualifiers: "Title - Original", "Title - 12 Inch Mix"
    title = re.sub(
        r'\s*[-–]\s*(?:original|remix(?:ed)?|extended|instrumental|'
        r'radio\s+edit|club\s+mix|dub|live|acoustic|'
        r'remaster(?:ed)?|12["\s]?inch)\s*$',
        '', title, flags=re.I,
    )
    # Strip featured artist suffixes: "Title ft. Someone", "Title feat. Someone"
    title = re.sub(
        r'\s*(?:ft\.?|feat\.?|featuring|with)\s+.+$',
        '', title, flags=re.I,
    )
    # Strip punctuation
    title = re.sub(r"[^\w\s]", ' ', title)
    return re.sub(r'\s+', ' ', title).strip()
