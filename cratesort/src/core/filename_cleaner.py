from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.utils.sanitizer import sanitize_filename

# ---------------------------------------------------------------------------
# Configurable strip patterns
# Each entry: (compiled_regex, human_readable_label)
# These are applied to the END of the filename stem.
# ---------------------------------------------------------------------------

# Stripped by default (these add no musical value to a filename)
_REMASTER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\s*[\(\[]\s*res?master(?:ed)?(?:\s+\d{4})?\s*[\)\]]', re.I), "remaster tag"),
    (re.compile(r'\s*-\s*\d{4}\s+res?master(?:ed)?$', re.I), "year+remaster suffix"),
    (re.compile(r'\s+res?mastered?$', re.I), "trailing remaster"),          # e.g. "That's It resmastered"
]

_EXPLICIT_CLEAN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\s*[\(\[]\s*explicit\s*[\)\]]', re.I), "explicit tag"),
    (re.compile(r'\s*[\(\[]\s*clean\s*[\)\]]', re.I), "clean tag"),
]

_SINGLE_BONUS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\s*[\(\[]\s*single\s*[\)\]]', re.I), "single tag"),
    (re.compile(r'\s*[\(\[]\s*bonus\s*(?:track)?\s*[\)\]]', re.I), "bonus track tag"),
]

_VIDEO_AUDIO_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\s*[\(\[]\s*official\s+(?:music\s+)?(?:video|audio)\s*[\)\]]', re.I), "official video/audio tag"),
    (re.compile(r'\s*[\(\[]\s*(?:audio|video)\s*[\)\]]', re.I), "audio/video tag"),
    (re.compile(r'\s*[\(\[]\s*lyric(?:s)?\s*(?:video)?\s*[\)\]]', re.I), "lyric video tag"),
]

# Requires spaces around separator to avoid matching within titles
_ARTIST_SEP_RE = re.compile(r'^(.+?)\s+[-–—]\s+(.+)$')

# Leading track number: "01 - ", "02.", "1-01 ", "track_12_"
_TRACK_NUM_RE = re.compile(
    r'^(?:\d{1,2}-)?'           # optional disc number "1-"
    r'\d{1,3}'                  # track number
    r'(?:[-.\s]+)',             # separator
    re.VERBOSE
)

# Unicode private-use area characters (often result of bad encoding)
_PRIVATE_USE_RE = re.compile(r'[-]')

# Common UTF-8 mojibake sequences
_MOJIBAKE: list[tuple[str, str]] = [
    ('â', '’'),   # â€™ → '
    ('â', '“'),   # â€œ → "
    ('â', '”'),   # â€  → "
    ('â', '–'),   # â€" → –
    ('â', '—'),   # â€" → —
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class FilenameProposal:
    original_filename: str
    proposed_filename: str
    changes_made: list[str] = field(default_factory=list)
    needs_review: bool = False

    @property
    def has_changes(self) -> bool:
        return self.original_filename != self.proposed_filename


# ---------------------------------------------------------------------------
# Internal helpers (module-level, no state)
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Normalize a string for loose equality comparison."""
    s = unicodedata.normalize('NFC', s)   # canonical Unicode form
    s = s.lower().strip()
    s = re.sub(r'[_\-]+', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def _norm_for_match(s: str) -> str:
    """Normalize for artist/title fuzzy matching."""
    s = _norm(s)
    s = re.sub(r'^the\s+', '', s)          # ignore leading "The"
    s = re.sub(r'\bft\.?\b|\bfeat\.?\b', '', s, flags=re.I)
    s = re.sub(r'[^\w\s]', '', s)           # strip punctuation
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _norm_for_match(a), _norm_for_match(b)).ratio()


def _fix_encoding(stem: str) -> tuple[str, list[str]]:
    """Fix common encoding artifacts in a filename stem."""
    changes: list[str] = []
    original = stem

    # Mojibake sequences
    for bad, good in _MOJIBAKE:
        if bad in stem:
            stem = stem.replace(bad, good)

    # Unicode private-use area characters → remove
    if _PRIVATE_USE_RE.search(stem):
        stem = _PRIVATE_USE_RE.sub('', stem)

    # Double spaces
    stem = re.sub(r' {2,}', ' ', stem).strip()

    if stem != original:
        changes.append("encoding artifacts fixed")
    return stem, changes


def _strip_track_number(stem: str) -> tuple[str, list[str]]:
    """Strip a leading track/disc number if present."""
    m = _TRACK_NUM_RE.match(stem)
    if m:
        stripped = stem[m.end():].strip()
        if stripped:  # don't strip if nothing remains
            return stripped, [f"stripped track number '{stem[:m.end()].strip()}'"]
    return stem, []


def _strip_artist_prefix(
    stem: str, artist: str
) -> tuple[str, list[str], bool]:
    """
    Strip artist name from the front of stem if it's clearly a prefix.
    Requires a ' - ' (or em/en dash variant) separator.
    Returns (new_stem, changes, needs_review).
    """
    m = _ARTIST_SEP_RE.match(stem)
    if not m:
        return stem, [], False

    prefix, rest = m.group(1), m.group(2)
    sim = _similarity(prefix, artist)

    if sim >= 0.90:
        return rest, [f"stripped artist prefix '{prefix}' ({sim:.0%} match)"], False
    elif sim >= 0.70:
        return rest, [f"stripped artist prefix '{prefix}' ({sim:.0%} fuzzy match)"], True

    return stem, [], False


# ---------------------------------------------------------------------------
# Cleaner class
# ---------------------------------------------------------------------------

class FilenameCleaner:
    """
    Proposes cleaned filenames for TrackRecords.
    All changes are proposals only — nothing is written to disk.
    """

    def __init__(
        self,
        strip_remaster: bool = True,
        strip_explicit_clean: bool = True,
        strip_single_bonus: bool = True,
        strip_video_audio: bool = True,
        strip_version_tags: bool = False,    # 12" Version, Extended Mix — keep by default
    ):
        self._patterns: list[tuple[re.Pattern, str]] = []
        if strip_remaster:
            self._patterns.extend(_REMASTER_PATTERNS)
        if strip_explicit_clean:
            self._patterns.extend(_EXPLICIT_CLEAN_PATTERNS)
        if strip_single_bonus:
            self._patterns.extend(_SINGLE_BONUS_PATTERNS)
        if strip_video_audio:
            self._patterns.extend(_VIDEO_AUDIO_PATTERNS)

    def clean(self, record: TrackRecord) -> FilenameProposal:
        stem = record.path.stem
        ext = record.path.suffix
        changes: list[str] = []
        needs_review = False

        # Early exit: filename stem already matches title tag
        if record.title and _norm(stem) == _norm(record.title):
            return FilenameProposal(
                original_filename=record.filename,
                proposed_filename=record.filename,
                changes_made=[],
            )

        working = stem

        # Step 1: Fix encoding artifacts
        working, enc_changes = _fix_encoding(working)
        changes.extend(enc_changes)

        # Step 2: Strip leading track number
        stripped, num_changes = _strip_track_number(working)
        if num_changes:
            # Validate: if stripping gives us something close to the title, proceed
            if not record.title or _similarity(stripped, record.title) > _similarity(working, record.title):
                changes.extend(num_changes)
                working = stripped

        # Step 3: Strip artist prefix
        if record.artist:
            stripped, art_changes, review = _strip_artist_prefix(working, record.artist)
            if art_changes:
                changes.extend(art_changes)
                working = stripped
                needs_review = needs_review or review

        # Step 4: Strip junk suffixes
        for pattern, label in self._patterns:
            cleaned = pattern.sub('', working).strip()
            if cleaned != working:
                changes.append(f"stripped {label}")
                working = cleaned

        # Step 5: Cross-check with title tag
        if record.title:
            if _norm(working) == _norm(record.title):
                # Perfect match — use title tag for proper capitalisation
                working = record.title
            else:
                # Title tag doesn't match our result
                needs_review = True
                changes.append(
                    f"title tag mismatch: proposed '{working}' ≠ tag '{record.title}'"
                )
                # Prefer title tag when no changes were made yet (title tag is better starting point)
                if not changes or all('mismatch' in c for c in changes):
                    working = record.title

        # Step 6: Sanitize for cross-platform safety
        proposed_stem = sanitize_filename(working)
        proposed_filename = proposed_stem + ext

        # No actual change?
        if proposed_filename == record.filename and not changes:
            return FilenameProposal(
                original_filename=record.filename,
                proposed_filename=record.filename,
                changes_made=[],
            )

        return FilenameProposal(
            original_filename=record.filename,
            proposed_filename=proposed_filename,
            changes_made=changes,
            needs_review=needs_review,
        )

    def clean_all(self, inventory: list[TrackRecord]) -> list[FilenameProposal]:
        return [self.clean(rec) for rec in inventory]
