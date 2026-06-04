# Serato DJ Pro File Format Reference

Technical reference for Serato DJ Pro's file formats, used to guide CrateSort's `serato/` integration layer.

---

## 1. Directory Structure on Disk

Serato stores its database and crate files in a `_Serato_` folder adjacent to the music library root:

| Platform | Default location |
|----------|-----------------|
| macOS    | `~/Music/_Serato_/` |
| Windows  | `C:\Users\<Username>\Music\_Serato_\` |
| Linux    | Not officially supported |

### Key subdirectories

```
_Serato_/
  Subcrates/          # .crate files (one per crate, recursive for nested crates)
  database V2         # Main library database (binary, track index)
  BPMpd/              # BPM cache files
  Smartcrates/        # Smart crate definitions (.scrate files)
  Metadata/           # AAC/XML metadata sidecar files
  Recording/          # Recorded sets
```

Nested crates use `%%` as the path separator in filenames:
- `Hip-Hop%%Golden Era.crate` = "Hip-Hop > Golden Era" in the Serato UI

---

## 2. .crate File Format

### Overview

`.crate` files are binary files using a **tag-length-value (TLV)** record format. Each file is a flat sequence of records; nested records (`o*` type) contain their own record sequences.

### Record Structure

```
[4-byte ASCII tag][4-byte big-endian length][variable-length data]
```

All integers are big-endian. Text is UTF-16 big-endian unless noted.

### Tag Type Prefixes

| Prefix | Data type |
|--------|-----------|
| `o*`   | Nested sequence of records |
| `t*`   | UTF-16 big-endian text |
| `p*`   | UTF-16 big-endian path (relative to drive root) |
| `u*`   | Unsigned 32-bit big-endian integer |
| `s*`   | Signed 32-bit big-endian integer |
| `b*`   | Single byte |
| `vrsn` | Crate format version string |

### Standard Records

| Tag    | Description |
|--------|-------------|
| `vrsn` | Version string: `"1.0/Serato ScratchLive Crate"` |
| `otrk` | Track entry container (one per track in the crate) |
| `ptrk` | Track file path (inside `otrk`), UTF-16 BE, relative to drive root |
| `otag` | Column sort/display settings container |
| `ttyp` | Column type tag |
| `tnam` | Display name |
| `brev` | Reverse sort flag (byte) |
| `uWID` | Column width (uint32) |
| `spos` | Sort position (int32) |

### Path Encoding

- Paths are **relative to the drive root**, not the library root.
- Separator is always `/` (forward slash), even on Windows in the stored data.
- Example: `Music/Hip-Hop/Jay-Z/99 Problems.mp3`
- The crate's name and hierarchy live only in the **filename**, not inside the file.

### Parsing Example (Python pseudocode)

```python
import struct

def read_record(f):
    tag = f.read(4).decode('ascii')
    length = struct.unpack('>I', f.read(4))[0]
    data = f.read(length)
    return tag, data

def read_crate(path):
    tracks = []
    with open(path, 'rb') as f:
        while chunk := f.read(8):
            tag, data = tag[:4], ...
            if tag == 'otrk':
                # parse nested ptrk record
                pass
    return tracks
```

### Recommended Python Library

**python-serato-crates** (`pip install serato-crate`):
- GitHub: https://github.com/stephanlensky/python-serato-crates
- License: AGPL-3.0
- Reads and writes `.crate` files with a clean API

**Serato-lib** (lower-level reference):
- GitHub: https://github.com/jesseward/Serato-lib
- Good for understanding the raw binary format

---

## 3. Serato Custom ID3 GEOB Frames

Serato embeds metadata in MP3 files using ID3v2 **GEOB** (General Encapsulated Object) frames. Each frame has:

```
GEOB frame:
  encoding:  1 (UTF-16)
  mime:      "application/octet-stream"
  filename:  "" (empty)
  desc:      "Serato <FrameName>"
  data:      <binary or base64-encoded binary>
```

The binary data in most frames is **base64-encoded** (no padding), with linefeeds every 72 characters. The base64 shell wraps raw binary structures described below.

### GEOB:Serato Analysis

- **Purpose**: Marks that the track has been analyzed; stores analysis version.
- **Format**: 2 raw bytes — `[major_version, minor_version]`
- **Example**: `02 01` = version 2.1

### GEOB:Serato Autotags

- **Purpose**: Stores auto-detected BPM and gain.
- **Format** (base64-encoded):
  - BPM as ASCII text with 2 decimal places, null-terminated (e.g., `"120.50\x00"`)
  - Gain value as ASCII text, null-terminated
- **Safe to read; do not modify** — Serato will re-analyze if missing.

### GEOB:Serato BeatGrid

- **Purpose**: Stores the beat grid (anchor points for sync).
- **Format** (base64-encoded binary, big-endian):

```
Bytes 0-1:  Unknown (2 bytes)
Bytes 2-5:  Marker count (uint32 big-endian)

For each non-terminal marker:
  Position:  float32 (seconds from start)
  Beats:     uint32 (beats until next marker)

Terminal marker:
  Position:  float32 (seconds from start)
  BPM:       float32

Final byte: 1 byte footer (seemingly random/checksum)
```

- **Critical**: Never overwrite — this is the sync anchor for Serato's engine.

### GEOB:Serato Markers_ (Legacy)

- **Purpose**: Stores first 5 hotcues, first 9 saved loops, and track color.
- **Format**: Sequence of typed entries.

```
Entry format:
  Type:     null-terminated ASCII string ("CUE", "LOOP", "COLOR")

CUE entry (17 additional bytes):
  Position: uint32 little-endian (milliseconds)
  Padding:  1 byte
  Color:    3 bytes RGB (e.g., CC 00 00 = red)
  Name:     UTF-8, null-terminated

LOOP entry:
  Start:    uint32 LE (ms)
  End:      uint32 LE (ms)
  Padding:  ...
  Name:     UTF-8, null-terminated

COLOR entry:
  8 bytes including RGB track color
```

### GEOB:Serato Markers2 (Current)

- **Purpose**: Extended marker storage — supports all hotcues, loops, and track color.
- **Format**: Base64-encoded (no padding, linefeeds every 72 chars), wrapping:

```
Header:   02 05 (2 bytes)

Followed by entries:
  Entry length: uint32 little-endian
  Entry type:   null-terminated ASCII string
  Entry data:   type-specific binary

CUE entry data:
  Index:    uint8 (cue number 0-7)
  Position: uint32 LE (ms)
  Color:    3 bytes RGB
  Name:     UTF-8, null-terminated

LOOP entry data:
  Index:       uint8
  Start:       uint32 LE (ms)
  End:         uint32 LE (ms)
  Color:       3 bytes RGB
  Name:        UTF-8, null-terminated
  Locked flag: uint8

COLOR entry data:
  Color: 4 bytes (00 RR GG BB)
```

- **Markers_ vs Markers2**: Both may be present. Markers2 is the authoritative current format; Markers_ is kept for backward compatibility with older Serato versions.

### GEOB:Serato Overview

- **Purpose**: Stores the cached waveform overview image shown in Serato's deck.
- **Format**: Binary waveform data (pixel intensity values).
- **Safe to ignore** — Serato regenerates this on analysis.

### Summary Table

| Frame | Contains | Safe to write? |
|-------|----------|----------------|
| `Serato Analysis` | Analysis version | No — let Serato set |
| `Serato Autotags` | BPM, gain | No — let Serato set |
| `Serato BeatGrid` | Sync beat anchors | Never overwrite |
| `Serato Markers_` | Cues, loops, color (legacy) | Read-only for CrateSort |
| `Serato Markers2` | Cues, loops, color (current) | Read-only for CrateSort |
| `Serato Overview` | Waveform display cache | Safe to ignore |

**CrateSort policy**: Read Serato GEOB frames to detect state (analyzed, has cues, etc.). Never overwrite them. Only write standard ID3 tags (TIT2, TPE1, TCON, TDRC, TPE2) via mutagen.

---

## 4. Format Support Across File Types

| Tag | MP3/AIFF | FLAC | MP4/M4A | Ogg Vorbis |
|-----|----------|------|---------|-----------|
| Analysis | GEOB (ID3) | Vorbis Comment | Custom atom | No |
| Autotags | GEOB (ID3) | Vorbis Comment | Custom atom | No |
| BeatGrid | GEOB (ID3) | Vorbis Comment | Custom atom | No |
| Markers_ | GEOB (ID3) | Vorbis Comment | Custom atom | No |
| Markers2 | GEOB (ID3) | Vorbis Comment | Custom atom | No |
| Overview | GEOB (ID3) | Vorbis Comment | Custom atom | No |

FLAC stores these as Vorbis Comments with base64-encoded values. MP4/M4A uses `----` custom atoms under the `com.serato.dj` namespace.

CrateSort v1 targets MP3 primarily; FLAC and MP4 support are future scope.

---

## 5. Python Library Recommendations

### For .crate files

| Library | PyPI | Notes |
|---------|------|-------|
| `serato-crate` | `pip install serato-crate` | Best maintained; read/write |
| `Serato-lib` | GitHub only | Good binary format reference |
| `seratopy` | GitHub only | Simpler but less maintained |

**Recommended**: `serato-crate` (python-serato-crates) for production use.

### For ID3 / GEOB frames

| Library | Notes |
|---------|-------|
| `mutagen` | Primary. Full ID3v2.4 read/write, GEOB support |
| `serato-tools` | PyPI: `pip install serato-tools`. Higher-level Serato metadata API |

**Recommended**: `mutagen` for all standard ID3 writes. Use `serato-tools` as a reference implementation or optional dependency if direct GEOB manipulation is needed.

### For fingerprinting (duplicate detection)

| Library | Notes |
|---------|-------|
| `pyacoustid` | Python bindings for AcoustID/Chromaprint |
| `chromaprint` | Must be installed separately as a system binary |

---

## 6. Key External References

- [Holzhaus/serato-tags](https://github.com/Holzhaus/serato-tags) — Most thorough reverse-engineered GEOB documentation
- [bvandercar-vt/serato-tools](https://github.com/bvandercar-vt/serato-tools) — Active Python library with fileformats.md
- [stephanlensky/python-serato-crates](https://github.com/stephanlensky/python-serato-crates) — Crate read/write library
- [jesseward/Serato-lib](https://github.com/jesseward/Serato-lib) — Low-level crate parser reference
- [Mixxx Wiki: Serato Database Format](https://github.com/mixxxdj/mixxx/wiki/Serato-Database-Format) — Community-maintained format specs
- [Jan Holthuis's blog](https://homepage.ruhr-uni-bochum.de/jan.holthuis/reversing-seratos-geob-tags.html) — Reverse engineering methodology
