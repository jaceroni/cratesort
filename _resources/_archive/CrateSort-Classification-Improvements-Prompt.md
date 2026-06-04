# CrateSort — Classification View Improvements

## Context

The classification view is built and working. The user has tested it against 
the test library and identified several issues and improvements. This session 
addresses all of them.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

## Fixes and improvements

### 1. Blue selection highlight → orange (app-wide)

When selecting a row in any table or tree widget, Qt's default blue selection 
color appears. Override this GLOBALLY in the app theme stylesheet. Selected 
rows should use:
- Background: #D17D34 (orange accent)
- Text: #f1e3c8 (cream)
This applies to QTreeWidget, QTableWidget, QListWidget — every selectable 
widget in the entire app, not just the classification view.

### 2. File path column

Add a "File Path" column as the LAST column on the right side of the 
classification results table. For artist rows (parent), show the common 
directory path if all tracks share one, or "Multiple locations" if they're 
spread across folders. For track rows (expanded children), show the full 
file path. This helps the user identify where files live and quickly open 
them in Finder if needed.

### 3. Short duration + purpose folder = Specialty

Update the classifier to apply this rule BEFORE artist-level grouping:

If a file meets ALL of these conditions:
- Duration under 30 seconds
- Lives in a folder whose name matches a purpose pattern (case-insensitive 
  substring match): drops, fx, effects, sfx, sound effects, shoutout, 
  shoutouts, promo, promos, jingle, jingles
  
Then:
- Classify it as Specialty with HIGH confidence
- EXCLUDE it from artist-level genre voting — a 9-second 2Pac drop should 
  not pull 2Pac's genre away from Hip-Hop/Rap

This means the same artist can have tracks in their main genre AND 
individual tracks classified as Specialty. The artist-level genre is 
determined only by their non-Specialty tracks.

Update `src/core/classifier.py` to implement this rule.

### 4. Separate "DJ Tools (untagged)" bucket

In the classification results view, files that meet ALL of these conditions:
- No artist tag (empty or "Unknown Artist")
- Lives in a purpose folder (drops, fx, effects, sfx, etc.)
- Short duration (under 60 seconds)

Should be grouped separately from the main artist list under a special 
entry called "DJ Tools (untagged)" instead of "Unknown Artist." This 
group appears at the bottom of the artist list with a distinct visual 
treatment (slightly different background or a label indicating these are 
utility files, not music tracks).

The user can still expand this group, see individual files, and reassign 
them to proper artists via the track-level context menu (see item 5).

### 5. Track-level context menu

When the user RIGHT-CLICKS on an individual TRACK row (the expanded child 
row under an artist), show a context menu with:

- **Reassign Artist...** — opens a small dialog with a text input field. 
  The user types a new artist name. On confirm:
  - If an artist group with that name already exists, move the track into it
  - If no matching group exists, create a new artist entry with this track
  - Update the source group's track count (remove the track from it)
  - If the source group is now empty, remove it from the list
  - The new/updated group inherits the genre of the destination group, or 
    if it's a new group, keeps the track's current proposed genre
  
- **Change Genre...** — opens the genre picker dialog to override the genre 
  for just this specific track (not the whole artist group)

- **Show in Finder** — opens the file's parent directory in macOS Finder 
  (use `subprocess` with `open -R <filepath>` on macOS). On Windows, use 
  `explorer /select,<filepath>`. Cross-platform.

This is SEPARATE from the existing artist-level context menu (which has 
Approve, Change Genre, Mark for Review). The artist-level menu stays as-is. 
Track-level actions only appear when right-clicking an expanded child row.

### 6. Classifier: don't let purpose folders override real metadata

The classifier currently gives folder path hints (Tier 3) too much weight 
when files are in purpose folders like _Samples. This caused Aaron Neville 
to be classified as Specialty because his file was in the _Samples folder, 
even though he's clearly R&B/Funk-Soul.

Fix: When a file lives in a known purpose folder (_Samples, _Tributes, 
_Unsorted, etc.), the folder path should NOT be used as a genre hint. 
Purpose folders describe the file's USE CASE, not its genre. Only use 
folder path hints from folders that look like genre names (Blues, Rock, 
Hip-Hop, Funk, etc.).

Add a PURPOSE_FOLDERS set to the classifier (similar to the scanner's 
SKIP_DIRS) containing common purpose folder patterns:
_Samples, _Tributes, _Unsorted, _Drops, _Instrumentals, _Commercials, 
_Movie Clips, Samples, Tributes, Unsorted

If a file's folder path matches any of these, skip Tier 3 for that file. 
Let Tier 1 and Tier 2 handle it, or mark it unclassified if those don't 
resolve.

### 7. Various-artist and compilation handling

Entries like "D'Angelo, AZ, DJ Premier" and "Big L, 2Pac" are showing up 
as their own artist groups. These are collaboration tracks or compilation 
entries. The classifier should detect when an "artist" field contains 
multiple known artists (comma-separated, "feat.", "ft.", "&", "and", "vs.") 
and either:

a) Classify under the FIRST/PRIMARY artist (before the comma or feature tag)
b) Or flag them as "Collaboration" for user review

For now, option (b) is safer — flag them so the user can decide where they 
belong. Add a "Collaboration" indicator in the classification view for 
these entries.

## Testing

After implementing all changes:
1. Launch the app and load the test library
2. Click Classify Library
3. Verify no blue selection highlights anywhere — should be orange
4. Verify File Path column appears as the last column
5. Check that 2Pac's main entry is Hip-Hop/Rap (not Specialty) and his 
   drop file is separately classified as Specialty
6. Check that Aaron Neville is no longer Specialty
7. Check that "DJ Tools (untagged)" appears for the untagged short drops
8. Right-click a track under "DJ Tools (untagged)" and use "Reassign 
   Artist" to give it a name — verify it creates a new artist group
9. Right-click a track and use "Show in Finder" — verify it opens the 
   right folder
10. Check that collaboration entries like "D'Angelo, AZ, DJ Premier" are 
    flagged appropriately
11. Verify all previous fixes still work (hover states, splitter, etc.)

Launch the app and verify everything works.
