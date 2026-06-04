from __future__ import annotations
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
_CHECKPOINT_FILENAME = 'checkpoint.json'


def _checkpoint_path(serato_dir: str | Path) -> Path:
    return Path(serato_dir).parent / '_CrateSort' / _CHECKPOINT_FILENAME


def save_checkpoint(serato_dir: str | Path, crate_data: dict) -> None:
    """Save crate_data + timestamp to checkpoint.json."""
    p = _checkpoint_path(serato_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'timestamp': datetime.now().isoformat(),
        'crates': crate_data,   # {crate_path: track_count}
    }
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:
        logger.warning('Could not save checkpoint: %s', exc)


def load_checkpoint(serato_dir: str | Path) -> Optional[dict]:
    """Return checkpoint dict or None if missing/corrupt."""
    p = _checkpoint_path(serato_dir)
    if not p.exists():
        return None
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _normalize_path(path: str) -> str:
    """Normalize a crate file path for robust cross-session comparison."""
    p = str(Path(path))          # resolves separator differences
    p = p.rstrip('/')
    if sys.platform in ('darwin', 'win32'):
        p = p.lower()            # case-insensitive filesystems
    return p


def detect_changes(current: dict, previous: dict) -> list[dict]:
    """
    Compare current {crate_path: track_count} against previous checkpoint.
    Returns list of {type, description, crate_path}.

    Change types:
      crate_added    — new crate appeared
      crate_removed  — crate disappeared
      renamed        — heuristic: same track count, one gone and one new
      tracks_added   — same crate, more tracks
      tracks_removed — same crate, fewer tracks

    # TODO: metadata change detection (artist, title, BPM changes) requires per-track hashing — future enhancement
    """
    prev_crates = previous.get('crates', {})

    def _display_name(path: str) -> str:
        return path.split('/')[-1].removesuffix('.crate')

    # Build a normalized → original path mapping for prev_crates so we can
    # match against current paths even if the path format shifted between sessions.
    norm_prev: dict[str, str] = {_normalize_path(p): p for p in prev_crates}

    def _prev_count(current_path: str) -> Optional[int]:
        """Return the previous count for a path, or None if not found."""
        orig = norm_prev.get(_normalize_path(current_path))
        return prev_crates.get(orig) if orig else None

    # --- Bucket 1: track-count changes on existing crates ---
    track_changes: list[dict] = []
    for path, count in current.items():
        # Skip failed scans in either direction
        if count is None:
            continue
        prev_count = _prev_count(path)
        if prev_count is None:
            continue          # not in previous, or previous scan failed — handled below
        if count == prev_count:
            continue          # no change
        delta = count - prev_count
        name  = _display_name(path)
        if delta > 0:
            track_changes.append({
                'type': 'tracks_added',
                'description': f'{delta} track(s) added to "{name}"',
                'crate_path': path,
            })
        else:
            track_changes.append({
                'type': 'tracks_removed',
                'description': f'{-delta} track(s) removed from "{name}"',
                'crate_path': path,
            })

    # --- Bucket 2: new / removed crates ---
    new_crates:     list[dict] = []
    removed_crates: list[dict] = []

    # Build a set of all normalized prev paths for fast membership check
    norm_prev_keys: set[str] = set(norm_prev.keys())

    for path, count in current.items():
        if count is None:
            continue   # failed scan this session — skip entirely
        norm = _normalize_path(path)
        if norm not in norm_prev_keys:
            # Genuinely new crate (not in previous checkpoint at all)
            new_crates.append({'path': path, 'count': count})
        # If norm IS in prev but _prev_count is None → prev scan failed, skip

    for path, prev_count in prev_crates.items():
        norm = _normalize_path(path)
        current_match = next(
            (cp for cp in current if _normalize_path(cp) == norm), None
        )
        if current_match is None:
            removed_crates.append({'path': path, 'count': prev_count})

    # --- Heuristic rename detection: same count → likely a rename ---
    changes: list[dict]   = []
    matched_new:     set[str] = set()
    matched_removed: set[str] = set()

    for rem in removed_crates:
        for new in new_crates:
            if new['path'] not in matched_new and rem['count'] == new['count']:
                old_name = _display_name(rem['path'])
                new_name = _display_name(new['path'])
                changes.append({
                    'type': 'renamed',
                    'description': f'Crate renamed: "{old_name}" → "{new_name}"',
                    'crate_path': new['path'],
                })
                matched_new.add(new['path'])
                matched_removed.add(rem['path'])
                break

    # Unmatched additions and removals
    for c in new_crates:
        if c['path'] not in matched_new:
            changes.append({
                'type': 'crate_added',
                'description': f'New crate: {_display_name(c["path"])}',
                'crate_path': c['path'],
            })

    for c in removed_crates:
        if c['path'] not in matched_removed:
            changes.append({
                'type': 'crate_removed',
                'description': f'Crate removed: {_display_name(c["path"])}',
                'crate_path': c['path'],
            })

    changes.extend(track_changes)
    return changes
