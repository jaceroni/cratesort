from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches "The " at the very start (case-insensitive)
_THE_PREFIX = re.compile(r'^the\s+', re.IGNORECASE)

# Matches "A " or "An " at the very start (for optional A/An handling)
_A_AN_PREFIX = re.compile(r'^(an?)\s+', re.IGNORECASE)



# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class TheProposal:
    original_name: str
    display_name: str   # Proper-case display form: "The Doors"
    sort_name: str      # Sort form: "Doors, The"
    folder_name: str    # Folder-safe form: "Doors, The" (same as sort_name)


# ---------------------------------------------------------------------------
# Handler class
# ---------------------------------------------------------------------------

class TheHandler:
    """
    Detects artist names beginning with 'The', 'A', or 'An' and proposes
    sort/folder forms.  All proposals are read-only; nothing is written.
    """

    def __init__(self, handle_a_an: bool = False):
        self.handle_a_an = handle_a_an

    def analyze(self, artist: str) -> Optional[TheProposal]:
        """
        Return a TheProposal if the artist needs article handling, else None.
        """
        if not artist or not artist.strip():
            return None

        artist = artist.strip()

        # Already in sort form ("Gap Band, The") — skip
        if re.search(r',\s*(the|a|an)$', artist, re.IGNORECASE):
            return None

        # "The" handling
        if _THE_PREFIX.match(artist):
            rest = _THE_PREFIX.sub('', artist)
            # "The The" → sort as "The, The"
            if rest.strip().lower() == 'the':
                sort = 'The, The'
            else:
                sort = f'{rest}, The'
            display = _ensure_title_case(artist, article='The', rest=rest)
            return TheProposal(
                original_name=artist,
                display_name=display,
                sort_name=sort,
                folder_name=sort,
            )

        # "A" / "An" handling (off by default)
        if self.handle_a_an:
            m = _A_AN_PREFIX.match(artist)
            if m:
                article = m.group(1)
                rest = artist[m.end():]
                sort = f'{rest}, {article.capitalize()}'
                display = _ensure_title_case(artist, article=article.capitalize(), rest=rest)
                return TheProposal(
                    original_name=artist,
                    display_name=display,
                    sort_name=sort,
                    folder_name=sort,
                )

        return None

    def analyze_all(self, artists: Iterable[str]) -> list[TheProposal]:
        """Analyze a collection of artist names; return only those that need changes."""
        seen: set[str] = set()
        results: list[TheProposal] = []
        for artist in artists:
            if artist in seen:
                continue
            seen.add(artist)
            proposal = self.analyze(artist)
            if proposal:
                results.append(proposal)
        return sorted(results, key=lambda p: p.sort_name)


# ---------------------------------------------------------------------------
# Module-level helpers (kept for backward compatibility and direct use)
# ---------------------------------------------------------------------------

def _ensure_title_case(name: str, article: str, rest: str) -> str:
    """Return the artist name in proper title case, with the article capitalised."""
    # If the name is all-caps or all-lowercase, normalise it
    if name == name.upper() or name == name.lower():
        rest = string.capwords(rest)
    return f'{article.capitalize()} {rest}'


def move_the_to_end(name: str) -> str:
    """'The Doors' -> 'Doors, The'"""
    if _THE_PREFIX.match(name):
        rest = _THE_PREFIX.sub('', name)
        return f'{rest}, The'
    return name


def has_the_prefix(name: str) -> bool:
    return bool(_THE_PREFIX.match(name))


def sort_artist(name: str) -> str:
    return move_the_to_end(name)


def folder_name(artist: str) -> str:
    return move_the_to_end(artist)


def display_name(folder: str) -> str:
    """'Doors, The' -> 'The Doors'"""
    if folder.endswith(', The'):
        base = folder[: -len(', The')]
        return f'The {base}'
    return folder
