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
    """Save crate_data + timestamp to checkpoint.json.

    crate_data: {crate_path: [track_path, ...]}  (list of path strings per crate)
    """
    p = _checkpoint_path(serato_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'timestamp': datetime.now().isoformat(),
        'crates': crate_data,
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
    p = str(Path(path))
    p = p.rstrip('/')
    if sys.platform in ('darwin', 'win32'):
        p = p.lower()
    return p


def _track_list(val) -> list[str]:
    """Return track list from a checkpoint value regardless of old/new schema.

    Old schema stored an int (track count).
    New schema stores a list of path strings.
    """
    if isinstance(val, list):
        return val
    return []   # old schema — no track data available


def _count(val) -> int:
    """Return track count from a checkpoint value regardless of old/new schema."""
    if isinstance(val, list):
        return len(val)
    if isinstance(val, int):
        return val
    return 0


def detect_changes(current: dict, previous: dict) -> list[dict]:
    """
    Compare current {crate_path: [track_paths]} against previous checkpoint.
    Returns list of change dicts.

    Each dict contains:
        type        — crate_added | crate_removed | renamed | tracks_added | tracks_removed
        description — human-readable summary
        crate_path  — path to the (new/current) .crate file
        prev_tracks — list of track paths from the checkpoint (for revert); [] if unavailable
        old_crate_path — (renamed only) path of the crate before it was renamed

    # TODO: metadata change detection (artist, title, BPM changes) requires per-track hashing
    """
    prev_crates = previous.get('crates', {})

    def _display_name(path: str) -> str:
        return path.split('/')[-1].removesuffix('.crate')

    norm_prev: dict[str, str] = {_normalize_path(p): p for p in prev_crates}

    def _prev_orig(current_path: str) -> Optional[str]:
        return norm_prev.get(_normalize_path(current_path))

    def _prev_count(current_path: str) -> Optional[int]:
        orig = _prev_orig(current_path)
        return _count(prev_crates[orig]) if orig and orig in prev_crates else None

    def _prev_tracks(current_path: str) -> list[str]:
        orig = _prev_orig(current_path)
        if orig and orig in prev_crates:
            return _track_list(prev_crates[orig])
        return []

    # --- Bucket 1: track-count changes on existing crates ---
    track_changes: list[dict] = []
    for path, curr_val in current.items():
        curr_count = _count(curr_val)
        pc = _prev_count(path)
        if pc is None:
            continue
        if curr_count == pc:
            continue
        delta = curr_count - pc
        name  = _display_name(path)
        pt    = _prev_tracks(path)
        if delta > 0:
            track_changes.append({
                'type': 'tracks_added',
                'description': f'{delta} track(s) added to "{name}"',
                'crate_path': path,
                'prev_tracks': pt,
            })
        else:
            track_changes.append({
                'type': 'tracks_removed',
                'description': f'{-delta} track(s) removed from "{name}"',
                'crate_path': path,
                'prev_tracks': pt,
            })

    # --- Bucket 2: new / removed crates ---
    new_crates:     list[dict] = []
    removed_crates: list[dict] = []

    norm_prev_keys: set[str] = set(norm_prev.keys())

    for path, curr_val in current.items():
        norm = _normalize_path(path)
        if norm not in norm_prev_keys:
            new_crates.append({'path': path, 'count': _count(curr_val)})

    for path, prev_val in prev_crates.items():
        norm = _normalize_path(path)
        current_match = next(
            (cp for cp in current if _normalize_path(cp) == norm), None
        )
        if current_match is None:
            removed_crates.append({
                'path': path,
                'count': _count(prev_val),
                'prev_tracks': _track_list(prev_val),
            })

    # --- Heuristic rename detection: same count → likely a rename ---
    changes: list[dict]      = []
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
                    'old_crate_path': rem['path'],
                    'prev_tracks': rem.get('prev_tracks', []),
                })
                matched_new.add(new['path'])
                matched_removed.add(rem['path'])
                break

    for c in new_crates:
        if c['path'] not in matched_new:
            changes.append({
                'type': 'crate_added',
                'description': f'New crate: {_display_name(c["path"])}',
                'crate_path': c['path'],
                'prev_tracks': [],
            })

    for c in removed_crates:
        if c['path'] not in matched_removed:
            changes.append({
                'type': 'crate_removed',
                'description': f'Crate removed: {_display_name(c["path"])}',
                'crate_path': c['path'],
                'prev_tracks': c.get('prev_tracks', []),
            })

    changes.extend(track_changes)
    return changes
