from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, '/opt/homebrew/lib/python3.14/site-packages')
from serato_crate import SeratoCrate

logger = logging.getLogger(__name__)

SUBCRATES_DIR = 'Subcrates'


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Crate:
    name: str                        # Display name, e.g. "Jump Blues"
    full_path: str                   # Hierarchical key, e.g. "Blues/Jump Blues"
    filename: str                    # .crate filename on disk
    filepath: Path                   # Absolute path to .crate file
    tracks: list[str]                # Track paths as stored (relative to drive root)
    parent: Optional[str]            # Parent's full_path, or None for top-level
    children: list[str] = field(default_factory=list)   # Children's full_paths
    track_count: int = 0
    resolved_count: int = 0
    unresolved_count: int = 0
    read_error: Optional[str] = None


@dataclass
class CrateLibrary:
    serato_dir: Path
    crates: dict[str, Crate]         # full_path → Crate
    top_level: list[str]             # full_paths of top-level crates (sorted)
    total_crates: int = 0
    total_tracks_referenced: int = 0
    unique_tracks_referenced: int = 0
    orphan_tracks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class CrateReader:
    """
    Reads all .crate files from a _Serato_ directory and builds a complete
    picture of the crate structure including hierarchy and track membership.

    All operations are read-only — nothing is written.
    """

    def __init__(self, serato_dir: str | Path):
        self._serato_dir = Path(serato_dir)
        self._subcrates_dir = self._serato_dir / SUBCRATES_DIR
        self._library_root = self._serato_dir.parent

    def read(
        self,
        inventory_paths: Optional[set[Path]] = None,
    ) -> CrateLibrary:
        """
        Read all crates and return a CrateLibrary.

        Args:
            inventory_paths: Optional set of absolute file paths from the
                LibraryScanner.  Used to resolve crate track references against
                the local library.  If None, all tracks are marked unresolved.
        """
        if not self._subcrates_dir.exists():
            logger.warning("Subcrates directory not found: %s", self._subcrates_dir)
            return CrateLibrary(
                serato_dir=self._serato_dir,
                crates={},
                top_level=[],
            )

        crates: dict[str, Crate] = {}

        # --- Pass 1: collect all .crate files and parse their tracks ---
        for crate_file in sorted(self._subcrates_dir.rglob('*.crate')):
            full_path, parent_path, display_name = self._parse_filepath(crate_file)
            tracks, error = self._read_tracks(crate_file)

            resolved, unresolved = self._resolve_tracks(tracks, inventory_paths)

            crate = Crate(
                name=display_name,
                full_path=full_path,
                filename=crate_file.name,
                filepath=crate_file,
                tracks=tracks,
                parent=parent_path,
                track_count=len(tracks),
                resolved_count=resolved,
                unresolved_count=unresolved,
                read_error=error,
            )
            crates[full_path] = crate
            logger.debug("Read crate: %s (%d tracks)", full_path, len(tracks))

        # --- Pass 2: wire up parent/child relationships ---
        # Create phantom parents for crates whose parents don't have a .crate file
        self._build_hierarchy(crates)

        top_level = sorted(fp for fp, c in crates.items() if c.parent is None)

        # --- Build summary stats ---
        all_track_refs: list[str] = []
        for c in crates.values():
            all_track_refs.extend(c.tracks)

        unique_tracks = set(all_track_refs)
        orphan_tracks = [
            t for t in unique_tracks
            if not self._resolve_single(t, inventory_paths)
        ]

        lib = CrateLibrary(
            serato_dir=self._serato_dir,
            crates=crates,
            top_level=top_level,
            total_crates=len(crates),
            total_tracks_referenced=len(all_track_refs),
            unique_tracks_referenced=len(unique_tracks),
            orphan_tracks=orphan_tracks,
        )
        return lib

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _parse_filepath(self, crate_file: Path) -> tuple[str, Optional[str], str]:
        """
        Convert a .crate filepath to (full_path, parent_path, display_name).

        Examples:
          Subcrates/Blues%%Jump Blues.crate
            → full_path="Blues/Jump Blues", parent="Blues", name="Jump Blues"
          Subcrates/Blues.crate
            → full_path="Blues", parent=None, name="Blues"
          Subcrates/Videos/Hip-Hop%%Eastcoast.crate
            → full_path="Videos/Hip-Hop/Eastcoast", parent="Videos/Hip-Hop", name="Eastcoast"
        """
        # Relative path from Subcrates dir, e.g. "Videos/Hip-Hop%%Eastcoast.crate"
        rel = crate_file.relative_to(self._subcrates_dir)

        # Replace %% with / to normalise hierarchy, then strip .crate extension
        # Use as_posix() so subdirectory separator is always /
        rel_str = rel.as_posix().replace('%%', '/')[: -len('.crate')]

        components = rel_str.split('/')
        display_name = components[-1]
        parent_path = '/'.join(components[:-1]) if len(components) > 1 else None
        return rel_str, parent_path, display_name

    def _read_tracks(self, crate_file: Path) -> tuple[list[str], Optional[str]]:
        """Return (track_path_strings, error_message_or_None)."""
        try:
            crate = SeratoCrate.load(crate_file)
            # Convert Path objects to posix strings (forward slashes everywhere)
            return [t.as_posix() for t in crate.tracks], None
        except Exception as exc:
            logger.warning("Failed to read crate %s: %s", crate_file.name, exc)
            return [], str(exc)

    def _resolve_tracks(
        self,
        tracks: list[str],
        inventory_paths: Optional[set[Path]],
    ) -> tuple[int, int]:
        """Return (resolved_count, unresolved_count)."""
        resolved = sum(1 for t in tracks if self._resolve_single(t, inventory_paths))
        return resolved, len(tracks) - resolved

    def _resolve_single(
        self,
        track_path: str,
        inventory_paths: Optional[set[Path]],
    ) -> bool:
        """
        Check whether a track path resolves to a local file.
        Tries: (1) as an absolute path, (2) relative to library root,
        (3) match by filename against inventory.
        """
        # Try relative to library root (most common case)
        candidate = self._library_root / track_path
        if candidate.exists():
            return True

        # Try absolute path as-is (path from original drive might resolve)
        if Path(track_path).exists():
            return True

        # Try matching just the filename against the provided inventory
        if inventory_paths:
            fname = Path(track_path).name
            for p in inventory_paths:
                if p.name == fname:
                    return True

        # Stem-based fallback for renamed files (e.g. "Track - 12in Mix.mp3" → "track.mp3")
        if inventory_paths:
            stem = Path(track_path).stem.lower()
            if len(stem) >= 5:
                for p in inventory_paths:
                    ps = p.stem.lower()
                    if ps == stem or stem in ps or ps in stem:
                        return True

        return False

    def _build_hierarchy(self, crates: dict[str, Crate]) -> None:
        """
        Wire up parent.children lists.  Create phantom Crate objects for any
        parent path that has children but no .crate file of its own.
        """
        # Collect all parent paths referenced
        phantom_needed: set[str] = set()
        for crate in list(crates.values()):
            if crate.parent and crate.parent not in crates:
                phantom_needed.add(crate.parent)

        # Create phantom parents (structural nodes with no real .crate file)
        for phantom_path in sorted(phantom_needed):
            parts = phantom_path.split('/')
            parent_of_phantom = '/'.join(parts[:-1]) if len(parts) > 1 else None
            phantom = Crate(
                name=parts[-1],
                full_path=phantom_path,
                filename='(virtual)',
                filepath=Path(),
                tracks=[],
                parent=parent_of_phantom,
            )
            crates[phantom_path] = phantom
            # Phantom might need its own parent too — handled on next iteration
            if parent_of_phantom and parent_of_phantom not in crates:
                phantom_needed.add(parent_of_phantom)

        # Wire children
        for crate in crates.values():
            if crate.parent and crate.parent in crates:
                parent = crates[crate.parent]
                if crate.full_path not in parent.children:
                    parent.children.append(crate.full_path)
                    parent.children.sort()

    def format_tree(self, lib: CrateLibrary, indent: int = 2) -> str:
        """Return a human-readable indented tree of the crate hierarchy."""
        lines: list[str] = []

        def _walk(full_path: str, depth: int) -> None:
            crate = lib.crates[full_path]
            prefix = ' ' * (depth * indent)
            status = f'{crate.track_count} tracks'
            if crate.read_error:
                status = f'ERROR: {crate.read_error}'
            elif crate.track_count == 0:
                status = 'empty'
            lines.append(f'{prefix}{crate.name}  [{status}]')
            for child_path in crate.children:
                _walk(child_path, depth + 1)

        for top in lib.top_level:
            _walk(top, 0)

        return '\n'.join(lines)
