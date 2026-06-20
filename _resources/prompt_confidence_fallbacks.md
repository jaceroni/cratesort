# CrateSort — Classification Fallback Chain & Confidence System Update

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt makes changes to `library_browser.py`, `src/core/classifier.py`, and `src/gui/classifier_view.py` to restore taxonomy-validated ID3 fallbacks and implement a five-state confidence system.

---

## Files in scope

- `src/gui/library_browser.py`
- `src/core/classifier.py`
- `src/gui/classifier_view.py` — NOTE: This file is in scope ONLY for modifying the backend models `ClassificationSession` and `_ClassifyWorker` (the legacy visual interface class `ClassifierView` was renamed to `_ClassifierViewLegacy` and is retired, but the file still serves as the data model and background worker module for the app).

---

## Locked rules

- The 13 valid parent genres are the only accepted taxonomy values: Blues, Country, Electronic, Funk/Soul, Hip-Hop/Rap, House, Jazz, R&B, Reggae, Rock, Seasonal, Specialty, Traditional
- Pop, Unclassified, Untagged, and empty string are never valid genres
- Raw ID3 tags are only trusted if they match one of the 13 parent genres exactly (case-insensitive)
- Teal `#428175` = action. Orange `#D17D34` = selection/CTA/LOW confidence. Never swap roles.
- Cream `#f1e3c8` = standard text / MATCHED confidence
- Never touch Serato metadata, comments, or cue points

---

## Change 1 — Restore taxonomy-validated ID3 fallback in `_rebuild_tree()`

### `src/gui/library_browser.py`

In `_rebuild_tree()` (around line 656), insert a **taxonomy-validated** ID3 tag fallback check as Step 3 in the chain.

The fallback chain in `_rebuild_tree()` must strictly be:
1. Artist override in `library_edits.json` — check `self._edits.get(f'__artist__{artist}', {}).get('genre')`
2. Classification session — check `self._classify_lookup(artist)` for `final_genre` then `proposed_genre`
3. **Taxonomy-validated ID3 majority vote** — iterate tracks, read `rec.genre` (checking edits/overrides first), and collect only values that exactly match one of the 13 parent genres (case-insensitive comparison). Use `collections.Counter` majority vote on these validated tags only. If the majority tag is a valid taxonomy genre, use it. If not, fall through.
4. **Default to `''`** — Unclassified

### Taxonomy validation set

```python
VALID_GENRES = {
    'Blues', 'Country', 'Electronic', 'Funk/Soul', 'Hip-Hop/Rap',
    'House', 'Jazz', 'R&B', 'Reggae', 'Rock', 'Seasonal',
    'Specialty', 'Traditional'
}
```
Normalize tags case-insensitively against this set (e.g. `blues` -> `Blues`, `hip-hop/rap` -> `Hip-Hop/Rap`). Only exact case-insensitive matches are accepted; all others ("Pop", "Hip Hop", "Alternative Rock") are ignored.

---

## Change 2 — Five-state confidence system

### `src/core/classifier.py`

1. Update the `Confidence` enum to include `MATCHED`:
   ```python
   class Confidence(Enum):
       MATCHED = "MATCHED" # Existing ID3 tag matches taxonomy
       HIGH = "HIGH"
       MEDIUM = "MEDIUM"
       LOW = "LOW"
       NONE = "NONE"
   ```
2. In `GenreClassifier.classify()` (around line 751), update the Tier 1 check (Already a valid parent genre) to do a case-insensitive check against `PARENT_GENRES`. If matched, return `Confidence.MATCHED` and the canonical title-cased parent genre string:
   ```python
   # Case-insensitive check
   canonical_parent = next((g for g in PARENT_GENRES if g.lower() == genre_lower), None)
   if canonical_parent:
       return ClassificationResult(
           genre=canonical_parent,
           confidence=Confidence.MATCHED,
           reason="Genre tag is a valid parent genre",
           original_genre_tag=raw_genre,
       )
   ```

### `src/gui/classifier_view.py`

Update the overall confidence resolver in `_ClassifyWorker.run()` (around line 425):
```python
overall_conf = (
    'LOW'     if ('LOW' in conf_for_genre or 'NONE' in conf_for_genre) else
    'MEDIUM'  if 'MEDIUM' in conf_for_genre else
    'HIGH'    if 'HIGH' in conf_for_genre else
    'MATCHED'
)
```

### `src/gui/library_browser.py`

Update `_populate_classify_columns()` to render MATCHED confidence and proposed genre cells in cream, with no status text:

1. Use this color mapping for the confidence cell:
   ```python
   conf_color = {
       'MATCHED': '#f1e3c8',
       'HIGH':    '#428175',
       'MEDIUM':  '#9fa4c7',
       'LOW':     '#D17D34',
       'NONE':    '#C75B5B',
   }.get(confidence, '#aaa')
   ```
2. If `confidence == 'MATCHED'`:
   - Set the Proposed Genre cell foreground to cream `#f1e3c8` (instead of light green/teal).
   - Set the Status cell text to empty `""` (no "Modified" status drawn).
   - The row should draw no attention.

### `_exit_classify_mode_accept()` Guard

In `_exit_classify_mode_accept()`, add a guard to skip writing overrides for unchanged `MATCHED` entries:
- Read the confidence text: `confidence = item.text(LC_CLS_CONF)`
- If `confidence == 'MATCHED'` and `proposed == current_genre`, skip writing an artist override to `library_edits.json`.

---

## Verification checklist

Before marking complete:

1. Fresh library load — artists with valid taxonomy-matching ID3 tags appear in correct genre buckets immediately
2. Fresh library load — artists with non-taxonomy ID3 tags ("Pop", "Alternative Rock", etc.) land in Unclassified
3. Fresh library load — artists with no genre tags land in Unclassified
4. After fresh load, nav away and return — genre buckets unchanged, no phantom moves
5. Classify Library opened — MATCHED artists show cream confidence text, no special treatment
6. Classify Library opened — HIGH artists show teal confidence text
7. Classify Library opened — MEDIUM artists show lavender `#9fa4c7` confidence text
8. Classify Library opened — LOW artists show orange confidence text
9. Classify Library opened — NONE artists show red confidence text
10. Accept Reclassifications — MATCHED artists not written to `library_edits.json` unnecessarily
11. Accept Reclassifications — HIGH/MEDIUM/LOW/NONE confirmed artists written to `library_edits.json` correctly
12. After Accept, nav away and return — all artists remain in correct buckets
13. "Hip-Hop/Rap" exact match → MATCHED. "Hip Hop" → NONE. "Pop" → NONE. "Blues" → MATCHED. "Blues Rock" → NONE.
14. Teal = action/HIGH confidence. Orange = LOW confidence. No role confusion.
