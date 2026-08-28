"""
Unit + integration tests for cratesort.src.serato.path_rewriter.

Focus: after a duplicate consolidation rewrites loser paths to the winner,
a crate that referenced BOTH copies must not end up listing the winner twice.
See _resources/rinse-testing-findings-2026-08-27.md #2.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cratesort.src.serato.path_rewriter import (
    PathChange,
    PathRewriter,
    _dedupe_track_refs,
)

WIN = "Music/Funk/Pimpology.mp3"
LOSE = "Music/Old/Pimpology.mp3"
VRSN = "1.0/Serato ScratchLive Crate"


def _otrk(path: str):
    return ("otrk", [("ptrk", path)])


def _ptrks(data):
    return [inner[0][1] for tag, inner in data if tag == "otrk"]


class TestDedupeTrackRefs:
    def test_collapses_adjacent_duplicates(self):
        data = [("vrsn", VRSN), _otrk(WIN), _otrk(WIN), _otrk("Music/B.mp3")]
        out, dropped = _dedupe_track_refs(data)
        assert dropped == 1
        assert _ptrks(out) == [WIN, "Music/B.mp3"]

    def test_keeps_first_occurrence_position(self):
        data = [_otrk(WIN), _otrk("Music/X.mp3"), _otrk(WIN)]
        out, dropped = _dedupe_track_refs(data)
        assert dropped == 1
        assert _ptrks(out) == [WIN, "Music/X.mp3"]

    def test_non_track_tags_untouched_and_not_reordered(self):
        data = [("vrsn", VRSN), _otrk("a"), ("osrt", b".."), _otrk("b")]
        out, dropped = _dedupe_track_refs(data)
        assert dropped == 0
        assert [t for t, _ in out] == ["vrsn", "otrk", "osrt", "otrk"]

    def test_nothing_to_dedupe(self):
        data = [("vrsn", VRSN), _otrk("a"), _otrk("b"), _otrk("c")]
        out, dropped = _dedupe_track_refs(data)
        assert dropped == 0
        assert out == data


class TestRewriteRoundTrip:
    def _make_serato(self, tmp_path: Path) -> Path:
        sub = tmp_path / "_Serato_" / "Subcrates"
        sub.mkdir(parents=True)
        return sub

    def test_crate_with_both_copies_collapses_to_one_winner_row(self, tmp_path):
        from serato_crate.crate_file import read_crate_file, write_crate_file

        sub = self._make_serato(tmp_path)
        write_crate_file(
            sub / "Hip-Hop.crate",
            [("vrsn", VRSN), _otrk(WIN), _otrk("Music/Other.mp3"), _otrk(LOSE)],
        )

        result = PathRewriter(tmp_path / "_Serato_").rewrite(
            [PathChange(old_path=LOSE, new_path=WIN)], dry_run=False
        )

        assert not result.errors
        assert _ptrks(read_crate_file(sub / "Hip-Hop.crate")) == [WIN, "Music/Other.mp3"]

    def test_control_crate_with_only_loser_resolves_to_winner(self, tmp_path):
        from serato_crate.crate_file import read_crate_file, write_crate_file

        sub = self._make_serato(tmp_path)
        write_crate_file(sub / "Funk.crate", [("vrsn", VRSN), _otrk(LOSE)])

        PathRewriter(tmp_path / "_Serato_").rewrite(
            [PathChange(old_path=LOSE, new_path=WIN)], dry_run=False
        )

        assert _ptrks(read_crate_file(sub / "Funk.crate")) == [WIN]

    def test_untouched_crate_not_rewritten(self, tmp_path):
        """A crate with no matching paths keeps a pre-existing (unrelated)
        duplicate — dedupe is scoped to crates this pass actually modifies."""
        from serato_crate.crate_file import read_crate_file, write_crate_file

        sub = self._make_serato(tmp_path)
        write_crate_file(
            sub / "Untouched.crate",
            [("vrsn", VRSN), _otrk("Music/Z.mp3"), _otrk("Music/Z.mp3")],
        )

        result = PathRewriter(tmp_path / "_Serato_").rewrite(
            [PathChange(old_path=LOSE, new_path=WIN)], dry_run=False
        )

        assert _ptrks(read_crate_file(sub / "Untouched.crate")) == [
            "Music/Z.mp3",
            "Music/Z.mp3",
        ]
        assert result.crates_unchanged == 1
