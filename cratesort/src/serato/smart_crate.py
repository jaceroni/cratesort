from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# .scrate binary format
#
# Same outer TLV container as regular .crate files (4-byte ASCII tag + 4-byte
# big-endian length + value), but tags starting with 'r' are ALSO nested
# structs (used only for the smart-crate-specific rule/flag containers) —
# the vendored `serato_crate` package only understands 'o' as a struct
# prefix and cannot read/write these files, so this module implements its
# own minimal codec rather than reusing it.
#
# Verified against a real .scrate fixture (hex-dumped byte-for-byte, not
# just read from a third party's code) — see the Smart Crates plan doc for
# the trace. One gap: the numeric rule path (BPM/Plays via 'urpt' +
# cond_greq_uint/cond_lseq_uint) has no confirmed byte example in the
# fixture used — it's inferred from the otherwise fully self-consistent
# type-prefix system. Verify it against real Serato before trusting it blindly.
# ---------------------------------------------------------------------------

SMARTCRATES_DIR = 'Smartcrates'
SMART_CRATE_VERSION = '1.0/Serato ScratchLive Smart Crate'

TAG_VERSION          = 'vrsn'
TAG_TRACK            = 'otrk'
TAG_TRACK_PATH       = 'ptrk'
TAG_SORTING          = 'osrt'
TAG_COLUMN_NAME      = 'tvcn'
TAG_REVERSE_ORDER    = 'brev'
TAG_COLUMN           = 'ovct'
TAG_COLUMN_WIDTH     = 'tvcw'
TAG_MATCH_ALL        = 'rart'
TAG_LIVE_UPDATE      = 'rlut'
TAG_RULE             = 'rurt'
TAG_RULE_COMPARISON  = 'trft'
TAG_RULE_FIELD       = 'urkt'
TAG_RULE_VALUE_TEXT  = 'trpt'
TAG_RULE_VALUE_DATE  = 'trtt'
TAG_RULE_VALUE_INT   = 'urpt'
TAG_BOOL_FLAG        = 'brut'  # generic bool payload inside rart/rlut


class RuleField(IntEnum):
    FILENAME = 4
    SONG     = 6   # Title
    ARTIST   = 7
    ALBUM    = 8
    GENRE    = 9
    BPM      = 15
    COMMENT  = 17
    GROUPING = 19
    REMIXER  = 20
    LABEL    = 21
    COMPOSER = 22
    YEAR     = 23
    ADDED    = 25
    KEY      = 51
    PLAYS    = 79


class RuleComparison(StrEnum):
    STR_CONTAINS          = 'cond_con_str'
    STR_DOES_NOT_CONTAIN  = 'cond_dnc_str'
    STR_IS                = 'cond_is_str'
    STR_IS_NOT             = 'cond_isn_str'
    STR_DATE_BEFORE       = 'cond_bef_str'
    STR_DATE_AFTER        = 'cond_aft_str'
    TIME_IS_BEFORE        = 'cond_bef_time'
    TIME_IS_AFTER         = 'cond_aft_time'
    INT_IS_GE             = 'cond_greq_uint'
    INT_IS_LE             = 'cond_lseq_uint'


# Fields whose value is compared numerically (RULE_VALUE_INTEGER); everything
# else uses RULE_VALUE_TEXT.
_INTEGER_FIELDS = {RuleField.BPM, RuleField.PLAYS}


@dataclass
class SmartCrateRule:
    field: RuleField
    comparison: RuleComparison
    value: Any  # str for text/date rules, int for numeric rules


@dataclass
class SmartCrate:
    name: str
    filepath: Path
    match_all: bool = True
    live_update: bool = False
    rules: list[SmartCrateRule] = field(default_factory=list)
    tracks: list[str] = field(default_factory=list)  # materialized track paths


# ---------------------------------------------------------------------------
# Generic TLV codec
# ---------------------------------------------------------------------------

def _type_id(tag: str) -> str:
    return 't' if tag == TAG_VERSION else tag[0]


def _decode_entries(data: bytes) -> list[tuple[str, Any]]:
    entries: list[tuple[str, Any]] = []
    i, n = 0, len(data)
    while i < n:
        tag = data[i:i + 4].decode('ascii')
        length = int.from_bytes(data[i + 4:i + 8], 'big')
        i += 8
        raw = data[i:i + length]
        i += length

        type_id = _type_id(tag)
        if type_id in ('o', 'r'):
            value: Any = _decode_entries(raw)
        elif type_id in ('t', 'p'):
            value = raw.decode('utf-16-be')
        elif type_id == 'u':
            value = int.from_bytes(raw, 'big')
        elif type_id == 'b':
            value = raw != b'\x00'
        else:
            raise ValueError(f'unsupported tag type for {tag!r}')
        entries.append((tag, value))
    return entries


def _encode_entry(tag: str, value: Any) -> bytes:
    type_id = _type_id(tag)
    if type_id in ('o', 'r'):
        data = _encode_entries(value)
    elif type_id in ('t', 'p'):
        data = str(value).encode('utf-16-be')
    elif type_id == 'u':
        data = int(value).to_bytes(4, 'big')
    elif type_id == 'b':
        data = b'\x01' if value else b'\x00'
    else:
        raise ValueError(f'unsupported tag type for {tag!r}')
    return tag.encode('ascii') + len(data).to_bytes(4, 'big') + data


def _encode_entries(entries: list[tuple[str, Any]]) -> bytes:
    return b''.join(_encode_entry(tag, value) for tag, value in entries)


# ---------------------------------------------------------------------------
# SmartCrate <-> entries
# ---------------------------------------------------------------------------

_DEFAULT_SORT_COLUMNS = ['song', 'artist', 'bpm', 'key', 'album', 'length', 'comment', 'added']


def _rule_value_tag(rule: SmartCrateRule) -> str:
    if rule.field in _INTEGER_FIELDS:
        return TAG_RULE_VALUE_INT
    if rule.comparison in (RuleComparison.TIME_IS_BEFORE, RuleComparison.TIME_IS_AFTER):
        return TAG_RULE_VALUE_DATE
    return TAG_RULE_VALUE_TEXT


def _build_rule_entries(rule: SmartCrateRule) -> list[tuple[str, Any]]:
    value_tag = _rule_value_tag(rule)
    value = int(rule.value) if value_tag == TAG_RULE_VALUE_INT else str(rule.value)
    return [
        (TAG_RULE_COMPARISON, rule.comparison.value),
        (TAG_RULE_FIELD, int(rule.field)),
        (value_tag, value),
    ]


def build_entries(crate: SmartCrate) -> list[tuple[str, Any]]:
    """Build the full TLV entry list for a SmartCrate, ready to encode."""
    entries: list[tuple[str, Any]] = [
        (TAG_VERSION, SMART_CRATE_VERSION),
        (TAG_MATCH_ALL, [(TAG_BOOL_FLAG, crate.match_all)]),
        (TAG_LIVE_UPDATE, [(TAG_BOOL_FLAG, crate.live_update)]),
    ]
    for rule in crate.rules:
        entries.append((TAG_RULE, _build_rule_entries(rule)))
    entries.append((TAG_SORTING, [(TAG_COLUMN_NAME, 'song'), (TAG_REVERSE_ORDER, False)]))
    for col_name in _DEFAULT_SORT_COLUMNS:
        entries.append((TAG_COLUMN, [(TAG_COLUMN_NAME, col_name), (TAG_COLUMN_WIDTH, '0')]))
    for track_path in crate.tracks:
        entries.append((TAG_TRACK, [(TAG_TRACK_PATH, track_path)]))
    return entries


def _parse_rule_entries(rule_entries: list[tuple[str, Any]]) -> Optional[SmartCrateRule]:
    comparison_raw: Optional[str] = None
    field_raw: Optional[int] = None
    value: Any = None
    for tag, val in rule_entries:
        if tag == TAG_RULE_COMPARISON:
            comparison_raw = val
        elif tag == TAG_RULE_FIELD:
            field_raw = val
        elif tag in (TAG_RULE_VALUE_TEXT, TAG_RULE_VALUE_DATE, TAG_RULE_VALUE_INT):
            value = val
    if comparison_raw is None or field_raw is None or value is None:
        return None
    try:
        rule_field = RuleField(field_raw)
        rule_comparison = RuleComparison(comparison_raw)
    except ValueError:
        return None  # unrecognized field/comparison — skip rather than crash
    return SmartCrateRule(field=rule_field, comparison=rule_comparison, value=value)


def parse_entries(entries: list[tuple[str, Any]], name: str, filepath: Path) -> SmartCrate:
    """Parse a decoded TLV entry list into a SmartCrate."""
    crate = SmartCrate(name=name, filepath=filepath)
    for tag, value in entries:
        if tag == TAG_MATCH_ALL:
            crate.match_all = any(v for t, v in value if t == TAG_BOOL_FLAG)
        elif tag == TAG_LIVE_UPDATE:
            crate.live_update = any(v for t, v in value if t == TAG_BOOL_FLAG)
        elif tag == TAG_RULE:
            rule = _parse_rule_entries(value)
            if rule is not None:
                crate.rules.append(rule)
        elif tag == TAG_TRACK:
            for inner_tag, inner_val in value:
                if inner_tag == TAG_TRACK_PATH:
                    crate.tracks.append(inner_val)
    return crate


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def read_smart_crate_file(path: Path) -> SmartCrate:
    raw = path.read_bytes()
    entries = _decode_entries(raw)
    return parse_entries(entries, name=path.stem, filepath=path)


def write_smart_crate_file(path: Path, crate: SmartCrate) -> None:
    entries = build_entries(crate)
    path.write_bytes(_encode_entries(entries))
