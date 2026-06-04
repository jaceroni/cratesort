# CrateSort — Scanner Module Implementation

## Context

The project scaffold is already in place from the previous session. The file 
`src/core/scanner.py` exists as an empty stub. The test library is at:

```
/Users/jacebrown/Desktop/cratesort-test-library
```

This is a deliberately messy test directory that mirrors a real DJ's library. 
Don't make any assumptions about what's inside — the scanner's job is to walk 
whatever directory it's pointed at and catalog every supported file it finds, 
regardless of folder names, nesting depth, or organizational state. Browse the 
test library first to see what's actually there before writing code.

## What to build

Implement the Scanner module (`src/core/scanner.py`) that:

1. **Walks a designated directory tree** and catalogs every audio and video file 
   it finds, no matter how the folders are organized. Supported formats (based on 
   what Serato DJ Pro supports):
   - Audio: `.mp3`, `.wav`, `.flac`, `.aif`, `.aiff`, `.m4a`, `.ogg`, `.wma`
   - Video: `.mp4`, `.m4v`, `.mov`, `.avi`
   - Serato stems: `.serato-stems` (catalog these but flag them as stems — they 
     are associated with a parent audio file in the same directory, not standalone 
     tracks. Match to their parent audio file by base filename.)

2. **Reads metadata/tags** from each supported file using `mutagen`. Extract:
   - Artist
   - Title (track name)
   - Album
   - Genre
   - Year
   - Duration (in seconds)
   - BPM (if tagged)
   - Comment field
   - File format / codec
   - Bitrate
   - Sample rate
   - File size
   - Full file path
   - Parent directory path
   - Filename (as-is, no cleaning)
   
   Different formats store metadata differently:
   - MP3: ID3 tags
   - M4A/MP4/M4V: iTunes-style MP4 atoms
   - FLAC: Vorbis comments
   - WAV: ID3 headers or INFO chunks
   - Handle each format's tag structure appropriately via mutagen's format-specific 
     classes

3. **Handles missing/malformed metadata gracefully.** Many files will have partial 
   or no tags. The scanner should never crash on a file — catalog what's there, 
   mark what's missing as None/null, and move on.

4. **Detects Serato stems files** (`.serato-stems`) and associates them with their 
   parent audio file in the same directory by matching the base filename. Store the 
   stems path as a field on the parent track's inventory record.

5. **Builds an in-memory inventory** as a list of dataclass or typed dict objects. 
   Each record represents one file with all extracted metadata plus file system info.

6. **Produces a scan summary** when complete:
   - Total files found (by format)
   - Total with complete metadata vs partial vs no metadata
   - Files with stems detected
   - Unique artists found
   - Unique genres found (as tagged — these may be wrong, that's expected)
   - Any files that couldn't be read (with error details)

## What NOT to build

- No genre classification or reclassification
- No filename cleaning or renaming
- No file moving or reorganization
- No Serato .crate file reading
- No "The" handling or artist consolidation
- No duplicate detection
- No GUI integration yet
- No writing to any files — the scanner is strictly read-only

## Testing

After implementing the scanner, write a simple test script (or add to `tests/`) 
that:

1. Points the scanner at `/Users/jacebrown/Desktop/cratesort-test-library`
2. Runs a full scan
3. Prints the summary report
4. Prints a few sample inventory records (showing the full metadata extracted)
5. Prints any files that had read errors or missing metadata

Also run the scanner and show me the actual output against the test library so I 
can see what it finds.

## Architecture notes

- The scanner should be a class (`LibraryScanner`) that can be instantiated with 
  one or more root directories
- Keep it modular — the scan results will be consumed by the classifier, duplicate 
  detector, and other modules later
- Use Python dataclasses for the inventory records
- Log progress during scan (file count, current directory) so we can see it working
- Performance matters — this will eventually scan tens of thousands of files. Use 
  efficient directory walking (os.scandir or pathlib) and don't load audio data, 
  just metadata
