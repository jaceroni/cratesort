# CrateSort — Artist Consolidation Detector & Duplicate Detector

## Context

The following modules are complete and working:
- Scanner (`src/core/scanner.py`) — produces `TrackRecord` dataclasses
- Classifier (`src/core/classifier.py`) — produces `ClassificationResult` objects
- Filename Cleaner (`src/core/filename_cleaner.py`) — proposes filename changes
- "The" Handler (`src/utils/the_handler.py`) — proposes sort-name corrections
- Metadata Fixer (`src/core/metadata_fixer.py`) — proposes tag corrections

Two stub files are ready for implementation:
- `src/core/artist_consolidator.py`
- `src/core/duplicate_detector.py`

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

Browse the test library first to see real examples of fragmented artists and 
duplicate files before writing code.

## Important: These modules are PROPOSAL engines, not executors

Same as Phase 2 — these modules analyze and propose. They do NOT move files, 
delete files, merge folders, or write metadata. They return structured proposals 
for user review. The actual execution happens later when the user approves.

---

## Module 1: Artist Consolidation Detector (`src/core/artist_consolidator.py`)

### What it does

Detects artist names in the library that likely refer to the same person or band 
but are stored under different names. Proposes merge candidates for user review.

### Real-world examples this must catch

- "Bob Seger" / "Bob Seger And The Silver Bullet Band" / "Bob Seger System"
- "Gap Band, The" / "The Gap Band"
- "Sly Stone" / "Sly & The Family Stone" / "Sly and the Family Stone"
- "DJ Premier" / "DJ Premier & Bumpy Knuckles" / "Gang Starr" (same person, 
  different projects — this is an edge case the user might decline)
- "Snoop Dogg" / "Snoop Doggy Dogg" / "Snoop Lion" (name changes over career)

### Detection methods

**Pass 1 — Substring matching**
If one artist name is contained within another (case-insensitive, ignoring 
leading "The"), they're candidates.
- "Bob Seger" is a substring of "Bob Seger And The Silver Bullet Band" → match
- "Gap Band" matches "The Gap Band" after "The" is stripped → match

**Pass 2 — Fuzzy matching**
Use string similarity (Levenshtein distance, or similar) to catch near-matches:
- Threshold: 85% similarity after normalization
- Normalize: lowercase, strip "the", strip common connectors ("and", "&", "of"), 
  strip punctuation
- "Sly & The Family Stone" vs "Sly and the Family Stone" → near-identical

**Pass 3 — Common variation patterns**
Detect known patterns that indicate the same artist:
- Name + "And The" + Band Name (solo artist with backing band)
- Name + "& The" + Band Name
- Name + "'s" + Band Name (e.g., "Bill Haley's Comets")
- Name with/without middle name or initial
- Name with different honorifics or titles
- "&" vs "and" vs "+" variations

### False positive protection

Present candidates but make it easy to dismiss false positives:
- "Queen" vs "Queen Latifah" — substring match but clearly different artists
- "Ice Cube" vs "Ice-T" — similar pattern but different people
- The detector should flag confidence level on each match:
  - HIGH: Substring + same genre classification → very likely same artist
  - MEDIUM: Fuzzy match or pattern match → probably same artist
  - LOW: Weak similarity → might be coincidence, user should verify

### Output

A list of `ConsolidationCandidate` objects:
- `primary_name`: The longest/most complete name (suggested winner)
- `variant_names`: List of other names detected as variants
- `track_counts`: Dict of {name: track_count} for each variant
- `confidence`: HIGH / MEDIUM / LOW
- `match_method`: How the match was detected (substring / fuzzy / pattern)
- `genres`: What genre(s) the variants are classified as (if they're in 
  different genres, that's a signal it might be a false positive)
- `sample_tracks`: A few example tracks from each variant (for user review)

### Merge proposal (generated alongside candidates)

For each approved candidate, the consolidator should also propose:
- `winning_name`: Which name to use (default: the longest/most complete, but 
  user can override)
- `use_subfolders`: Boolean — should the merged folder contain subfolders for 
  each project/band? (e.g., `Bob Seger/Bob Seger And The Silver Bullet Band/`)
  Default: True when variants represent genuinely different projects; False when 
  they're just spelling/formatting variations.

---

## Module 2: Duplicate Detector (`src/core/duplicate_detector.py`)

### What it does

Finds tracks that appear to be the same song in multiple locations. This is the 
module that solves the "Aaron Neville's Hercules is in three folders" problem.

### Detection passes

**Fast pass — Metadata matching**
Compare normalized artist + normalized title + duration (±3 seconds tolerance):
- Normalize: lowercase, strip punctuation, strip common suffixes like 
  "(Remastered)", "(Original Mix)", etc.
- Duration tolerance accounts for different rips/encodings of the same track
- This catches exact duplicates and near-duplicates with minor tag differences

**Deep pass — Audio fingerprinting (future)**
Using chromaprint/pyacoustid for acoustic matching. This catches duplicates 
where metadata is completely different but the audio is the same.
- **For now: stub this out.** Implement the interface and data structures but 
  don't implement the actual fingerprinting. Leave a clear TODO and a method 
  that returns an empty list. We'll add the actual fingerprint logic later.
- The fast pass alone will catch the majority of duplicates in a DJ library.

### What to surface for each duplicate group

A `DuplicateGroup` containing:
- `canonical_title`: The best version of the song title (cleanest metadata)
- `canonical_artist`: The best version of the artist name
- `copies`: List of `DuplicateCopy` objects, each with:
  - `file_path`: Full path
  - `format`: MP3 / WAV / FLAC / etc.
  - `bitrate`: For quality comparison
  - `file_size`: For space calculation
  - `genre_tag`: Current genre tag
  - `year_tag`: Current year
  - `comment`: The comment field (DJs store important info here)
  - `bpm`: If tagged
  - `has_stems`: Whether a .serato-stems file is associated
  - `folder_context`: What folder it's in (so the user understands WHY it's 
    there — "this copy is in your _Samples folder, that copy is in Funk/Soul")
- `recommended_winner`: Which copy the detector thinks should survive, based on:
  1. Highest bitrate
  2. Most complete metadata
  3. Has stems file attached
  4. If all else equal, the one in the genre-correct folder
- `space_savings`: How much disk space would be freed by consolidating
- `metadata_conflicts`: List of fields where the copies disagree (genre, year, 
  comment, BPM) — these need user resolution before consolidation

### Metadata conflict handling

This is critical. Before a duplicate group can be consolidated, every conflict 
must be surfaced:

- **Comment conflicts**: "Copy A has comment 'Redman Sample', Copy B has no 
  comment. Migrate comment to winner?" — Comments are SACRED. Never silently 
  drop a comment.
- **Genre conflicts**: "Copy A tagged Funk, Copy B tagged R&B. Winner is 
  tagged Funk. Keep?" — This often reveals why the duplicate exists (the user 
  filed it in two genres).
- **BPM conflicts**: "Copy A = 118 BPM, Copy B = 120 BPM. Keep which?"
- **Year conflicts**: "Copy A = 1978, Copy B = 2005. Keep 1978?" — The older 
  year is usually the original release; the newer is usually the compilation.

### Output

A list of `DuplicateGroup` objects (as described above), plus a summary:
- Total duplicate groups found
- Total duplicate files (across all groups)
- Total space that could be recovered
- Groups with metadata conflicts (need user resolution)
- Groups with no conflicts (could be auto-approved)

---

## Testing

Write a test runner (`tests/run_consolidation.py`) that:

1. Runs the scanner on the test library
2. Runs the classifier on the scan results
3. Runs the artist consolidation detector
4. Runs the duplicate detector
5. Prints all consolidation candidates with confidence and reasoning
6. Prints all duplicate groups with copy details and metadata conflicts
7. Prints summary stats

Run it against the test library and show me the actual output.

## Architecture notes

- `ArtistConsolidator` class — takes list of `TrackRecord` objects
- `DuplicateDetector` class — takes list of `TrackRecord` objects
- Both return proposal dataclasses — no side effects
- The duplicate detector's fast pass should be efficient — normalize once, 
  then compare. This will run on libraries with 10,000+ tracks.
- Audio fingerprint deep pass is stubbed for future implementation
- Keep the normalization logic (for title/artist comparison) in a shared utility 
  if both modules need it — DRY
