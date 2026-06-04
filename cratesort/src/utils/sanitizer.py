import re

_ILLEGAL_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Strip or replace characters that are illegal in cross-platform filenames."""
    sanitized = re.sub(_ILLEGAL_CHARS, replacement, name).strip(". ")
    if sanitized.upper() in _WINDOWS_RESERVED:
        sanitized = f"{sanitized}{replacement}"
    return sanitized or replacement


def sanitize_path_component(name: str) -> str:
    return sanitize_filename(name)
