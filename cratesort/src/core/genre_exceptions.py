"""Track-level genre exceptions.

An artist has ONE primary genre, but any individual track can live in a
different genre bucket (a rock artist's Christmas song belongs in Seasonal,
the way a record shop files it). A track's *effective* genre is its
exception if it has one, otherwise the artist's primary.

Stored in library_edits.json under the track path as ``genre_override``:
    absent  -> no explicit choice; Seasonal signals may auto-detect one
    ''      -> explicitly pinned to the artist's primary genre
    'Rock'  -> explicit exception to that genre

This is deliberately separate from the per-track ``genre`` staging that
Approve/Accept write for every track — that value can't distinguish "the
user chose this" from "Approve stamped the artist's genre on everything".
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

SEASONAL = 'Seasonal'

# Folder names (any ancestor of the file) that mean "these are seasonal".
_SEASONAL_FOLDER_NAMES = frozenset({
    'christmas', 'xmas', 'x-mas', 'holiday', 'holidays', 'seasonal',
    'christmas music', 'holiday music', 'christmas songs', 'holiday songs',
    'halloween', 'halloween music',
})

# Unambiguous title words only. "Holiday" is deliberately NOT here —
# Madonna / Green Day tracks would be swept into Seasonal.
_SEASONAL_TITLE_RE = re.compile(r'\b(christmas|xmas|x-mas)\b', re.IGNORECASE)


def _tag_is_seasonal(genre_tag: Optional[str]) -> bool:
    if not genre_tag:
        return False
    from cratesort.src.core.classifier import STYLE_MAP
    tag = genre_tag.strip().lower()
    return tag == 'seasonal' or STYLE_MAP.get(tag) == SEASONAL


def is_seasonal_signal(path, title: Optional[str], genre_tag: Optional[str]) -> bool:
    """True when the folder, title, or genre tag marks this track seasonal."""
    try:
        parts = {p.lower() for p in Path(str(path)).parts[:-1]}
    except Exception:
        parts = set()
    if parts & _SEASONAL_FOLDER_NAMES:
        return True
    if title and _SEASONAL_TITLE_RE.search(title):
        return True
    return _tag_is_seasonal(genre_tag)


def effective_override(edit: dict, path, title: Optional[str],
                       genre_tag: Optional[str]) -> Optional[str]:
    """Return the genre this track is an exception to, or None when it simply
    follows its artist's primary genre."""
    if 'genre_override' in edit:
        return edit['genre_override'] or None
    if is_seasonal_signal(path, title, genre_tag):
        return SEASONAL
    return None
