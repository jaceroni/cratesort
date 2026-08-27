from __future__ import annotations

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.serato.smart_crate import RuleComparison, RuleField, SmartCrateRule

# ---------------------------------------------------------------------------
# Rule evaluation against CrateSort's own scanned metadata (TrackRecord).
#
# Scope: only the fields CrateSort actually scans are supported here, so
# every match count shown in the UI reflects real data rather than a guess.
# Serato's smart-crate format supports more fields (Key, Grouping, Label,
# Composer, Remixer, Added, Plays) that CrateSort doesn't track — those are
# out of scope for rule-building in this app for now.
# ---------------------------------------------------------------------------

TEXT_COMPARISONS = (
    RuleComparison.STR_CONTAINS,
    RuleComparison.STR_DOES_NOT_CONTAIN,
    RuleComparison.STR_IS,
    RuleComparison.STR_IS_NOT,
)

INT_COMPARISONS = (
    RuleComparison.INT_IS_GE,
    RuleComparison.INT_IS_LE,
)

# Year is stored as text in the .scrate format (RULE_VALUE_TEXT, not
# RULE_VALUE_INTEGER — see _INTEGER_FIELDS below) but compared as a number,
# same as Serato's own "is before" / "is after" year rule — not a substring
# match, so it gets its own comparison set rather than TEXT_COMPARISONS.
DATE_COMPARISONS = (
    RuleComparison.STR_DATE_BEFORE,
    RuleComparison.STR_DATE_AFTER,
)

# Fields selectable in the rule builder, mapped to the TrackRecord attribute
# they filter against. Ordered for display.
SUPPORTED_FIELDS: list[RuleField] = [
    RuleField.GENRE,
    RuleField.ARTIST,
    RuleField.SONG,
    RuleField.ALBUM,
    RuleField.BPM,
    RuleField.YEAR,
    RuleField.COMMENT,
    RuleField.FILENAME,
]

_TEXT_TRACK_ATTR: dict[RuleField, str] = {
    RuleField.FILENAME: 'filename',
    RuleField.SONG: 'title',
    RuleField.ARTIST: 'artist',
    RuleField.ALBUM: 'album',
    RuleField.GENRE: 'genre',
    RuleField.COMMENT: 'comment',
    RuleField.YEAR: 'year',
}

FIELD_LABELS: dict[RuleField, str] = {
    RuleField.GENRE: 'Genre',
    RuleField.ARTIST: 'Artist',
    RuleField.SONG: 'Title',
    RuleField.ALBUM: 'Album',
    RuleField.BPM: 'BPM',
    RuleField.YEAR: 'Year',
    RuleField.COMMENT: 'Comment',
    RuleField.FILENAME: 'Filename',
}

COMPARISON_LABELS: dict[RuleComparison, str] = {
    RuleComparison.STR_CONTAINS: 'contains',
    RuleComparison.STR_DOES_NOT_CONTAIN: 'does not contain',
    RuleComparison.STR_IS: 'is',
    RuleComparison.STR_IS_NOT: 'is not',
    RuleComparison.INT_IS_GE: 'is at least',
    RuleComparison.INT_IS_LE: 'is at most',
    RuleComparison.STR_DATE_BEFORE: 'is before',
    RuleComparison.STR_DATE_AFTER: 'is after',
}


def comparisons_for_field(rule_field: RuleField) -> tuple[RuleComparison, ...]:
    if rule_field == RuleField.BPM:
        return INT_COMPARISONS
    if rule_field == RuleField.YEAR:
        # Keep the original text comparisons (existing saved crates may
        # already use "is"/"contains" on Year) and add the numeric
        # before/after pair alongside them, not in place of them.
        return TEXT_COMPARISONS + DATE_COMPARISONS
    return TEXT_COMPARISONS


def evaluate_rule(rule: SmartCrateRule, track: TrackRecord) -> bool:
    if rule.field == RuleField.BPM:
        if track.bpm is None:
            return False
        try:
            target = float(rule.value)
        except (TypeError, ValueError):
            return False
        if rule.comparison == RuleComparison.INT_IS_GE:
            return track.bpm >= target
        if rule.comparison == RuleComparison.INT_IS_LE:
            return track.bpm <= target
        return False

    if rule.field == RuleField.YEAR and rule.comparison in DATE_COMPARISONS:
        if not track.year:
            return False
        try:
            track_year = int(track.year)
            target_year = int(rule.value)
        except (TypeError, ValueError):
            return False
        if rule.comparison == RuleComparison.STR_DATE_BEFORE:
            return track_year < target_year
        if rule.comparison == RuleComparison.STR_DATE_AFTER:
            return track_year > target_year
        return False

    attr = _TEXT_TRACK_ATTR.get(rule.field)
    if attr is None:
        return False
    track_value = (getattr(track, attr, None) or '').strip().lower()
    rule_value = str(rule.value).strip().lower()

    if rule.comparison == RuleComparison.STR_CONTAINS:
        return rule_value in track_value
    if rule.comparison == RuleComparison.STR_DOES_NOT_CONTAIN:
        return rule_value not in track_value
    if rule.comparison == RuleComparison.STR_IS:
        return track_value == rule_value
    if rule.comparison == RuleComparison.STR_IS_NOT:
        return track_value != rule_value
    return False


def match_tracks(
    rules: list[SmartCrateRule],
    match_all: bool,
    inventory: list[TrackRecord],
) -> list[TrackRecord]:
    if not rules:
        return []
    matched: list[TrackRecord] = []
    for track in inventory:
        outcomes = [evaluate_rule(rule, track) for rule in rules]
        if (all(outcomes) if match_all else any(outcomes)):
            matched.append(track)
    return matched
