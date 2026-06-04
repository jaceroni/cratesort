# CrateSort — Phase 2 Engine Modules: Filename Cleaner, "The" Handler, Metadata Fixer

## Context

The Scanner (`src/core/scanner.py`) and Genre Classifier (`src/core/classifier.py`) 
are complete and working. The scanner produces `TrackRecord` dataclasses with full 
metadata. The classifier produces `ClassificationResult` objects with artist-level 
genre assignments.

Three stub files are ready for implementation:
- `src/core/filename_cleaner.py`
- `src/utils/the_handler.py`
- `src/core/metadata_fixer.py`

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Browse the test library first to see real examples of dirty filenames, "The" 
artists, and messy metadata before writing code.

## Important: These modules are PROPOSAL engines, not executors

None of these modules write to disk or modify files. They analyze the current 
state, propose changes, and return structured results. The actual execution 
(renaming files, writing tags) happens later when the user approves. Build them 
as pure functions that take input and return proposed changes.

---

## Module 1: Filename Cleaner (`src/core/filename_cleaner.py`)

### What it does

Takes a filename (as-is from the scanner) and proposes a cleaned version where 
the filename = song title only. No artist prefix, no track number, no album name, 
no format tags.

### What to strip

- **Track numbers**: Leading digits, with or without separators
  - `01 - Song Title.mp3` → `Song Title.mp3`
  - `01. Song Title.mp3` → `Song Title.mp3`
  - `1-01 Song Title.mp3` → `Song Title.mp3` (disc-track format)
  - `track_12_song_title.mp3` → `Song Title.mp3`
  
- **Artist prefixes**: When the artist name appears at the start of the filename
  - `Artist Name - Song Title.mp3` → `Song Title.mp3`
  - `Artist_Name_-_Song_Title.mp3` → `Song Title.mp3`
  - The artist name comes from the ID3 tag, not guessed from the filename.
    Only strip if the filename starts with a string that closely matches the 
    tagged artist (fuzzy match — handle minor spelling differences, underscores 
    for spaces, missing "The", etc.)

- **Album name references**: When the album name appears in the filename after 
  the song title
  - `Song Title - Album Name.mp3` → `Song Title.mp3`
  - Same fuzzy matching against the ID3 album tag

- **Common junk suffixes/tags**:
  - `(Remastered)`, `(Remaster)`, `(Remastered 2024)`, `[Remastered]`
  - `(12 Inch Version)`, `(12" Version)`, `(12'' Mix)`
  - `(Bonus Track)`, `[Bonus]`
  - `(Explicit)`, `[Explicit]`, `[Clean]`
  - `(Official Video)`, `(Official Audio)`, `(Audio)`, `(Video)`
  - `(Lyrics)`, `(Lyric Video)`
  - These should be CONFIGURABLE — some DJs might want to keep version info 
    like "(12 Inch Version)". Default: strip remaster tags, keep version/mix 
    tags. Implement as a settings-friendly list.

- **Underscores to spaces**: `song_title` → `Song Title`

- **Corrupted characters**: Replace common encoding artifacts:
  - `?` where an apostrophe should be (common in transfers)
  - `â€™` and similar UTF-8 mojibake → proper apostrophe
  - Double spaces → single space
  - Leading/trailing whitespace

- **Cross-platform sanitization**: Ensure proposed filename is valid on 
  Mac, Windows, and Linux. Strip/replace: `/ \ : * ? " < > |`
  Preserve the original characters in ID3 tags — only sanitize the filename.

### What NOT to strip

- Mix/remix identifiers the DJ might want: `(DJ Premier Remix)`, `(Pete Rock Mix)`
- Featured artist tags: `(feat. Artist)`, `(ft. Artist)`
- Live indicators: `(Live)`, `(Live at Fillmore)`
- These are musically meaningful, not metadata junk.

### Output

A `FilenameProposal` for each track:
- `original_filename`: The current filename
- `proposed_filename`: The cleaned version
- `changes_made`: List of what was stripped/changed and why
- `needs_review`: Boolean — True if the cleaner wasn't confident about a change

---

## Module 2: "The" Handler (`src/utils/the_handler.py`)

### What it does

Detects artist names that start with "The" and proposes the corrected sort form. 
This affects folder names and the ID3 sort-artist field, NOT the display artist name.

### Rules

- `The Doors` → folder: `Doors, The/` → sort-artist: `Doors, The` → 
  display/ID3 artist: `The Doors` (unchanged)
- `The Rolling Stones` → folder: `Rolling Stones, The/`
- `The Gap Band` → folder: `Gap Band, The/`

- Case variations: `the doors`, `THE DOORS`, `the Doors` → all normalize to 
  `The Doors` for display, `Doors, The` for sorting

- Do NOT move "The" for:
  - `Them` (it's the band's actual name, not "The M")
  - `The The` (band name — becomes `The, The` which is weird but correct)
  - `Theory of a Deadman` (doesn't start with standalone "The")
  - Names where "The" is not a leading article — detect this by checking if 
    removing "The " from the start leaves a viable name

- Also handle "A" and "An" if the user enables it (off by default):
  - `A Tribe Called Quest` → `Tribe Called Quest, A`
  - This is a settings toggle. Not everyone wants this.

### Output

A `TheProposal` for each affected artist:
- `original_name`: The current artist name
- `display_name`: The corrected display form (proper case: `The Doors`)
- `sort_name`: The sort form (`Doors, The`)
- `folder_name`: The folder-safe version (`Doors, The`)

---

## Module 3: Metadata Fixer (`src/core/metadata_fixer.py`)

### What it does

Analyzes track metadata and proposes corrections. Does NOT write anything — 
returns a list of proposed fixes for user review.

### What it fixes

1. **Genre tags** — Proposes updating the ID3 genre tag to match the classifier's 
   genre assignment.
   - Current tag: "Other" → Proposed: "Blues"
   - Current tag: "Pop" → Proposed: "Rock" (per classifier)
   - Current tag: "Funk/Old School" → Proposed: "Funk/Soul"
   - Only proposes changes when the current tag doesn't match the classified genre
   
2. **Style tags** — Proposes writing style information to the appropriate ID3 frame.
   - Uses the styles found during classification
   - Stores in a consistent format for Serato to read

3. **Sort-artist field** — Proposes writing the "The"-handled sort name to the 
   ID3 sort-artist frame (TPE1 sort / TSOP).
   - `The Doors` → sort-artist: `Doors, The`
   - Only for artists with "The" prefix

4. **Year correction** — Flags tracks where the year looks like a compilation year 
   rather than an original release year.
   - Heuristic: If the album name contains "Greatest Hits", "Best Of", "Collection", 
     "Anthology", "Compilation", "Remastered", "Deluxe Edition", or similar patterns, 
     AND the year is significantly later than the artist's active period, flag it.
   - The fixer can't know the correct original year without an external source, 
     so it flags these for user review rather than proposing a specific year.
   - Mark as `needs_review: True` with reason: "Year may be compilation date, 
     not original release"

5. **Comment preservation** — When proposing metadata changes, NEVER touch the 
   comment field. DJs store important notes there (sample sources, mix notes, 
   cue point reminders). The comment field is sacred.

6. **Serato metadata** — NEVER propose changes to any Serato custom ID3 frames 
   (BeatGrid, Markers_, Markers2, etc.). These are completely off-limits. 
   Read-only always.

### What it does NOT fix

- BPM (separate module later)
- Album art
- Track duration (calculated from audio, not a tag)
- Anything in Serato's custom ID3 frames

### Output

A `MetadataProposal` for each track that needs changes:
- `file_path`: Path to the track
- `artist`: The artist name
- `changes`: List of `MetadataChange` objects, each with:
  - `field`: Which field (genre, style, sort_artist, year)
  - `current_value`: What's there now
  - `proposed_value`: What it should be (or None if flagged for review)
  - `confidence`: HIGH / MEDIUM / LOW
  - `reason`: Why the change is proposed
  - `needs_review`: Boolean

---

## Testing

Write a test runner (`tests/run_phase2.py`) that:

1. Runs the scanner on the test library
2. Runs the classifier on the scan results
3. Runs the filename cleaner on every track
4. Runs the "The" handler on every artist
5. Runs the metadata fixer on every track (using classifier results)
6. Prints a summary of all proposed changes:
   - Filename changes (show before → after for each)
   - "The" handling (show artists affected)
   - Metadata fixes by type (genre corrections, year flags, sort-artist updates)
7. Prints total counts: how many files would be renamed, how many tags would 
   change, how many need user review

Run it against the test library and show me the actual output.

## Architecture notes

- Each module is a class: `FilenameCleaner`, `TheHandler`, `MetadataFixer`
- All three take `TrackRecord` objects as input (from the scanner)
- `MetadataFixer` also takes `ClassificationResult` objects (from the classifier)
- All return proposal dataclasses — no side effects, no file writes
- Keep the strippable patterns (remaster tags, junk suffixes) as configurable 
  lists at the top of the file — easy to add/remove entries later
- Cross-platform path/filename safety throughout
