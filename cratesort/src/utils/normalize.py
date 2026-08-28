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
    # Strip ALL trailing parenthesized/bracketed groups, whatever they contain:
    # "(Original Mix)", "(Remaster 2012)", "(1982)", "(Bootleg)", "(VIP)",
    # "(dave's edit)", "(clean)", chained ones like "(Remastered) (Live)".
    # Deliberately not an allow-list: for duplicate *bucketing*, an over-merge
    # still surfaces to the user (tiered as a variant in the review list), but
    # an under-merge hides the file entirely. When a user tacks a suffix onto
    # one copy's title to distinguish it, both copies must still bucket together
    # so Rinse can catch them. Guard against eating the whole title.
    stripped = re.sub(r'(?:\s*[\(\[][^\(\)\[\]]*[\)\]])+\s*$', '', title).strip()
    if stripped:
        title = stripped
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
