from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratesort.src.serato.smart_crate import SMARTCRATES_DIR, SmartCrate, read_smart_crate_file

logger = logging.getLogger(__name__)


@dataclass
class SmartCrateLibrary:
    serato_dir: Path
    crates: dict[str, SmartCrate]  # name → SmartCrate
    names: list[str] = field(default_factory=list)  # sorted display order


class SmartCrateReader:
    """
    Reads all .scrate files from a _Serato_ directory.

    Smart crates are flat (no %%-style nesting) — each file's stem is its
    display name. All operations are read-only — nothing is written.
    """

    def __init__(self, serato_dir: str | Path):
        self._serato_dir = Path(serato_dir)
        self._smartcrates_dir = self._serato_dir / SMARTCRATES_DIR
        self._library_root = self._serato_dir.parent

    def read(self, inventory_paths: Optional[set[Path]] = None) -> SmartCrateLibrary:
        if not self._smartcrates_dir.exists():
            return SmartCrateLibrary(serato_dir=self._serato_dir, crates={}, names=[])

        crates: dict[str, SmartCrate] = {}
        for scrate_file in sorted(self._smartcrates_dir.glob('*.scrate')):
            try:
                crate = read_smart_crate_file(scrate_file)
            except Exception as exc:
                logger.warning('Failed to read smart crate %s: %s', scrate_file.name, exc)
                continue
            crates[crate.name] = crate

        return SmartCrateLibrary(
            serato_dir=self._serato_dir,
            crates=crates,
            names=sorted(crates.keys()),
        )

    def resolve_single(self, track_path: str, inventory_paths: Optional[set[Path]]) -> bool:
        """Check whether a materialized track path resolves to a local file.
        Mirrors CrateReader._resolve_single's fallback strategy exactly."""
        candidate = self._library_root / track_path
        if candidate.exists():
            return True
        if Path(track_path).exists():
            return True
        if inventory_paths:
            fname = Path(track_path).name
            for p in inventory_paths:
                if p.name == fname:
                    return True
        if inventory_paths:
            stem = Path(track_path).stem.lower()
            if len(stem) >= 5:
                for p in inventory_paths:
                    ps = p.stem.lower()
                    if ps == stem or stem in ps or ps in stem:
                        return True
        return False
