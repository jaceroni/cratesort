from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DISMISSED_FILENAME = 'dismissed_duplicates.json'


def _dismissed_path(library_path: Path) -> Path:
    return library_path / '_CrateSort' / _DISMISSED_FILENAME


def load_dismissed(library_path: Path) -> set[str]:
    """Fingerprints (see duplicate_detector.group_fingerprint) the user has
    told CrateSort to stop asking about — 'Keep All, Don't Ask Again'."""
    path = _dismissed_path(library_path)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return set(data.get('fingerprints', []))
    except Exception as exc:
        logger.warning('[DupDismiss] Failed to read %s: %s', path, exc)
        return set()


def save_dismissed(library_path: Path, fingerprints: set[str]) -> None:
    path = _dismissed_path(library_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({'fingerprints': sorted(fingerprints)}, indent=2),
        encoding='utf-8',
    )


def add_dismissed(library_path: Path, fingerprint: str) -> None:
    current = load_dismissed(library_path)
    current.add(fingerprint)
    save_dismissed(library_path, current)


def remove_dismissed(library_path: Path, fingerprint: str) -> None:
    current = load_dismissed(library_path)
    current.discard(fingerprint)
    save_dismissed(library_path, current)
