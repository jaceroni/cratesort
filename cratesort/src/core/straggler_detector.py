"""
Straggler detection — crate tracks that reference real files living *outside*
the scanned library folder.

CrateSort manages one folder tree. Serato does not: it stores each crate track
as a path relative to the volume root and resolves it wherever it lives, so a
working DJ's crates routinely point at files in ~/Downloads, ~/Music, the
Desktop, etc. Those references are healthy in Serato but CrateSort can't clean,
tag, de-dupe, or organize a file it never scanned. This module finds them so the
Dashboard can offer to move them into the library (see gui/straggler_dialog.py).

Pure logic, no Qt.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DISMISSED_FILENAME = 'dismissed_stragglers.json'
_SUBCRATES_DIR = 'Subcrates'


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

@dataclass
class Straggler:
    source_path: Path              # real absolute location of the file on disk
    size: int                      # bytes
    crate_refs: list[str] = field(default_factory=list)   # exact ptrk strings (verbatim for PathRewriter)
    crate_names: list[str] = field(default_factory=list)  # human-readable crate paths, for the dialog


# ---------------------------------------------------------------------------
# Dismiss list ("don't ask about these again") — mirrors duplicate_dismissals.py
# ---------------------------------------------------------------------------

def _dismissed_path(library_root: Path) -> Path:
    return library_root / '_CrateSort' / _DISMISSED_FILENAME


def load_dismissed_stragglers(library_root: Path) -> set[str]:
    path = _dismissed_path(library_root)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return set(data.get('paths', []))
    except Exception as exc:
        logger.warning('[Straggler] Failed to read %s: %s', path, exc)
        return set()


def save_dismissed_stragglers(library_root: Path, source_paths: set[str]) -> None:
    path = _dismissed_path(library_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({'paths': sorted(source_paths)}, indent=2),
        encoding='utf-8',
    )


def add_dismissed_stragglers(library_root: Path, source_paths: set[str]) -> None:
    current = load_dismissed_stragglers(library_root)
    current |= {str(p) for p in source_paths}
    save_dismissed_stragglers(library_root, current)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def library_drive_root(current_crates: dict, library_root: Path) -> str:
    """The volume-root prefix Serato stores crate paths relative to, for this
    library. Derived from any crate ref that already resolves under the library
    root; falls back to the mount point of `library_root`.
    """
    for refs in current_crates.values():
        if not refs:
            continue
        for ref in refs:
            r = ref.lstrip('/')
            if (library_root / r).exists():
                full = (library_root / r).as_posix()
                if full.endswith(r):
                    return full[: len(full) - len(r)].rstrip('/') or '/'
    # Fallback: on macOS an external drive is /Volumes/<name>, everything else
    # hangs off the boot volume root.
    parts = library_root.resolve().parts
    if len(parts) >= 3 and parts[1] == 'Volumes':
        return f'/Volumes/{parts[2]}'
    return '/'


def _locate_outside(ref: str, library_root: Path) -> Optional[Path]:
    """Given a crate ptrk string that did NOT resolve inside the library, return
    the real file's absolute path if it exists somewhere else, else None."""
    candidates: list[Path] = []
    if ref.startswith('/'):
        candidates.append(Path(ref))
    else:
        candidates.append(Path('/' + ref))
    for cand in candidates:
        try:
            if cand.is_file():
                # Guard: never treat an in-library file as a straggler.
                if not cand.resolve().is_relative_to(library_root.resolve()):
                    return cand
        except (OSError, ValueError):
            continue
    return None


def _crate_display_name(crate_file: Path, subcrates_dir: Path) -> str:
    try:
        rel = crate_file.relative_to(subcrates_dir)
        return rel.as_posix().replace('%%', '/')[: -len('.crate')]
    except ValueError:
        return crate_file.stem


def detect_stragglers(
    current_crates: dict,
    library_root: Path,
    serato_dir: Path,
) -> list[Straggler]:
    """
    Args:
        current_crates: {str(crate_file_path) -> [ptrk strings] | None}, exactly
            the dict DashboardWidget._check_serato_sync() already builds. None
            values (unreadable crates) are skipped.
        library_root: the scanned library folder.
        serato_dir: <library_root>/_Serato_.

    Returns a list of Straggler, one per unique out-of-library source file,
    sorted by source folder then filename, with the dismiss list applied.
    """
    subcrates_dir = serato_dir / _SUBCRATES_DIR
    dismissed = load_dismissed_stragglers(library_root)

    by_source: dict[str, Straggler] = {}

    for crate_file_str, refs in current_crates.items():
        if not refs:
            continue
        crate_name = _crate_display_name(Path(crate_file_str), subcrates_dir)
        for ref in refs:
            r = ref.lstrip('/')
            # In-library already? Nothing to do.
            if (library_root / r).exists():
                continue
            src = _locate_outside(ref, library_root)
            if src is None:
                continue  # genuinely missing — a different problem, leave it
            key = str(src)
            if key in dismissed:
                continue
            entry = by_source.get(key)
            if entry is None:
                try:
                    size = src.stat().st_size
                except OSError:
                    size = 0
                entry = Straggler(source_path=src, size=size)
                by_source[key] = entry
            if ref not in entry.crate_refs:
                entry.crate_refs.append(ref)
            if crate_name not in entry.crate_names:
                entry.crate_names.append(crate_name)

    return sorted(
        by_source.values(),
        key=lambda s: (str(s.source_path.parent).lower(), s.source_path.name.lower()),
    )
