"""
Unit tests for cratesort.src.utils.normalize.

Focus: normalize_title's trailing-bracket stripping, which gates duplicate
detection. See _resources/rinse-testing-findings-2026-08-27.md #1 — a user
appending "(Bootleg)" to one copy's title used to drop the pair from Rinse
entirely because the two normalized titles no longer matched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running from the cratesort/ project root without installing.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.utils.normalize import normalize_artist, normalize_title


class TestNormalizeTitleTrailingBrackets:
    def test_bootleg_suffix_matches_bare_title(self):
        """The exact regression from the 2026-08-27 manual test."""
        assert normalize_title("Pimpology (Bootleg)") == normalize_title("Pimpology")

    @pytest.mark.parametrize(
        "suffixed",
        [
            "Early in the Morning (VIP)",
            "Early in the Morning (Clean)",
            "Early in the Morning [Dirty]",
            "Early in the Morning (Dave's Edit)",
            "Early in the Morning (2024 rework)",
        ],
    )
    def test_arbitrary_user_suffix_collapses(self, suffixed):
        """Not an allow-list: any trailing (...)/[...] group is dropped so a
        distinguishing suffix on one copy can't hide a duplicate."""
        assert normalize_title(suffixed) == normalize_title("Early in the Morning")

    def test_chained_trailing_groups(self):
        assert normalize_title("Song (Remastered) (Live)") == "song"

    def test_leading_track_number_and_suffix_together(self):
        assert normalize_title("02 Pimpology (Bootleg)") == "pimpology"

    def test_existing_version_suffixes_still_stripped(self):
        assert normalize_title("Track (Original Mix)") == "track"
        assert normalize_title("Track (1982)") == "track"
        assert normalize_title("Track (Remaster 2012)") == "track"

    def test_guard_against_eating_whole_title(self):
        """A title that is nothing but a bracketed group keeps its content
        rather than normalizing to an empty string (which would over-merge
        every bracket-only title by the same artist)."""
        assert normalize_title("(Intro)") == "intro"
        assert normalize_title("[Skit]") == "skit"

    def test_non_trailing_parenthetical_preserved(self):
        """Only trailing groups are stripped; a mid-title parenthetical is
        part of the identity and stays."""
        assert normalize_title("Song (Part 1) Reprise") == "song part 1 reprise"

    def test_bucket_key_reunites_edited_duplicate(self):
        """End-to-end shape of the fix: the (artist, title) tuple that
        DuplicateDetector._fast_pass buckets on is identical for both copies
        after one has been given a distinguishing title + artist."""
        tagged = (normalize_artist("Do or Die"), normalize_title("Pimpology"))
        edited = (normalize_artist("Do Or Die"), normalize_title("Pimpology (Bootleg)"))
        assert tagged == edited
