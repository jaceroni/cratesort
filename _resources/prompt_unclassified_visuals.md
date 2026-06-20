# CrateSort — Empty State Button, Artist Genre Persistence, Sidebar Bucketing & Unclassified Visual Hierarchy

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

Four targeted fixes in `library_browser.py`. No other files in scope unless the artist genre write path trace explicitly requires it. Follow the blast radius protocol before touching anything.

---

## Files in scope

- `src/gui/library_browser.py` — primary
- `src/core/classifier.py` — read only, for understanding the session data model
- `library_edits.json` — understand the schema before fixing the write path

---

## Locked design standards

- Orange `#D17D34` = selection/CTA. Teal `#428175` = action. Never swap.
- Red `#C75B5B` = Unclassified artist indicator
- Amber `#c9a87a` = track-level warning indicator
- Cream text: `#f1e3c8`. Muted text: `#666`.
- Artist genre is always the authority for sidebar bucketing. Track genre is metadata only.
- Never touch Serato metadata, comments, or cue points.

---

## Fix 1 — Empty state: add inline Classify Library button

### `src/gui/library_browser.py`

The current empty state tells the user to find the Classify Library button in the toolbar. This is wrong — the action must be available right there in the message.

### Changes

Add a teal "Classify Library" button directly inside the empty state pane, below the subline text.

- Button style: teal background `#428175`, cream text `#f1e3c8`, 11px, weight 500, same styling as the toolbar Classify Library button
- Button label: "Classify Library"
- On click: triggers classify mode immediately — same behavior as clicking the toolbar Classify Library button
- Entering classify mode from the empty state button must switch the stack to the track table (index 1) AND activate classify mode columns and banner simultaneously. The user should land directly in classify mode with proposed genres visible — not on a blank track table.
- Connect this new button to the exact same `_on_classify_clicked` slot that the toolbar button uses.

The toolbar Classify Library button remains unchanged — both buttons trigger the same classify mode entry method.

---

## Fix 2 — Artist genre not persisting through Accept Reclassifications

### `src/gui/library_browser.py`

**This is a data integrity issue. Trace the full write path before writing any fix.**

Reported behavior: User right-clicks an artist, changes genre to Funk/Soul, clicks OK. The artist genre cell updates on screen. User then clicks Accept Reclassifications. After accept, the artist is found in the wrong genre bucket — only the track genres were saved, not the artist genre.

### Root Cause & Fix Specs

1. In `_exit_classify_mode_accept` (around line 1520), the accept loop iterates over top-level items and does:
   ```python
   if proposed and proposed not in _UC and proposed != current_genre:
       edits.setdefault(f'__artist__{artist}', {})['genre'] = proposed
   ```
   This overwrites the user's manual right-click override in `library_edits.json` back to the classifier's proposed genre.
2. Fix this by checking if the artist key already has a user-defined genre override, and if so, skip writing the proposed genre:
   ```python
   artist_key = f'__artist__{artist}'
   if artist_key in edits and 'genre' in edits[artist_key]:
       continue
   ```
3. Ensure after an artist's genre is updated via the context menu (`_change_genre_for_selection`), the styles and text colors of any visible children track items are also updated in-place to reflect whether the artist is now classified.

---

## Fix 3 — Sidebar bucketing by artist genre only

### `src/gui/library_browser.py`

The genre sidebar must bucket artists by their artist-level genre assignment. Track-level genre tags are metadata for crates and ID3 tags — they do not determine which sidebar bucket an artist appears in.

### Fallback Bucketing Rules

In `_rebuild_tree` (around line 656) when resolving the genre of an artist, implement the following order of precedence:
1. Read the artist's genre override from `library_edits.json` (`f'__artist__{artist}'` key) if present.
2. Fall back to the classifier's proposed genre for that artist if it exists in the session.
3. Fall back to the most common genre tag across the artist's tracks as a last resort (iterate over the tracks, resolve their active edits/overrides/tags, and find the most common non-empty genre using `collections.Counter`).
4. Fall back to `''` (which places the artist in the Unclassified bucket).

Update `_populate_genre_sidebar()` to use this resolved artist genre structure.

---

## Fix 4 — Unclassified bucket visual hierarchy

### `src/gui/library_browser.py`

When a user drills into the Unclassified bucket and sees artists with nested tracks, they cannot currently tell whether the artist, the tracks, or both are unclassified. 

### Visual Treatment (implement in `_make_artist_item` and `_make_track_child`)

**Artist rows in Unclassified bucket:**
- Artist name: `#C75B5B` (red)
- Genre cell: "Unclassified" in `#C75B5B`
- Tooltip on artist row: "Classify this artist to move all tracks out of Unclassified."

**Track rows nested inside an Unclassified artist:**

Two cases:

Case A — track has no genre tag (truly unclassified):
- Track name and cells: `#C75B5B` (red), same as artist
- Genre cell: empty or "—"

Case B — track has a genre tag but its artist is still Unclassified:
- Track name and cells: `#c9a87a` (warm amber) — visually distinct from the red artist row
- Genre cell: shows the track's genre tag in `#c9a87a` plus a suffix warning indicator: `[Genre] ⚠ Artist unclassified`
- Tooltip: "This track has a genre tag but will remain in Unclassified until its artist is classified."

---

## Verification checklist

Before marking complete:

1. Empty state shows a teal Classify Library button below the subline text
2. Clicking the empty state button enters classify mode immediately — proposed genre columns visible, classify banner shown, track table visible
3. Toolbar Classify Library button still works independently
4. Right-click artist genre change followed by Accept Reclassifications correctly saves and applies the artist genre — artist appears in the correct sidebar bucket after accept
5. Sidebar buckets are driven by artist genre only — changing a track genre does not move an artist between sidebar buckets
6. Artist with Unclassified genre appears in Unclassified bucket regardless of track genre tags
7. In Unclassified bucket: artist rows are red, truly unclassified track rows are red
8. In Unclassified bucket: tracks with a genre tag but an unclassified artist show in amber with "⚠ Artist unclassified" indicator
9. Tooltip on unclassified artist row: "Classify this artist to move all tracks out of Unclassified."
10. Tooltip on amber track row: "This track has a genre tag but will remain in Unclassified until its artist is classified."
11. Classifying an artist via right-click immediately moves it and all its tracks to the correct sidebar bucket — no nav required
12. Teal = action, Orange = CTA, Red = unclassified/warning — no role swaps
