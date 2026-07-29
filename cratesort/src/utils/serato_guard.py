"""Detect whether Serato DJ Pro is currently running."""
from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def is_serato_running() -> bool:
    """
    Return True if Serato DJ Pro appears to be running, False otherwise.

    Uses platform-native process listing. Never raises — any detection failure
    returns False so the user is never blocked by a guard error.
    """
    try:
        if sys.platform == 'darwin':
            result = subprocess.run(
                ['pgrep', '-i', 'Serato DJ Pro'],
                capture_output=True,
                timeout=3,
            )
            return result.returncode == 0

        elif sys.platform == 'win32':
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq Serato DJ Pro.exe'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return 'Serato DJ Pro.exe' in result.stdout

        else:
            result = subprocess.run(
                ['pgrep', '-i', 'serato'],
                capture_output=True,
                timeout=3,
            )
            return result.returncode == 0

    except Exception as exc:
        logger.debug("Serato running check failed (non-blocking): %s", exc)
        return False


def launch_serato() -> bool:
    """
    Launch (or foreground, if already running) Serato DJ Pro.

    Returns True if the launch command appears to have succeeded, False
    otherwise. Never raises — a failure here should surface as a friendly
    in-app message, not a crash.
    """
    try:
        if sys.platform == 'darwin':
            result = subprocess.run(
                ['open', '-a', 'Serato DJ Pro'],
                capture_output=True,
                timeout=8,
            )
            return result.returncode == 0

        elif sys.platform == 'win32':
            result = subprocess.run(
                ['cmd', '/c', 'start', '', 'Serato DJ Pro'],
                capture_output=True,
                timeout=8,
            )
            return result.returncode == 0

        else:
            return False

    except Exception as exc:
        logger.debug("Serato launch failed (non-blocking): %s", exc)
        return False
