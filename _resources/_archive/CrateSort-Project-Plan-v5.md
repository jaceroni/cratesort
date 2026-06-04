# CrateSort — Project Plan v5

**Get your shit together.**

CrateSort is a standalone desktop app that organizes a DJ's digital music library and manages their Serato crates. It handles all the librarian work — genre classification, folder structure, metadata cleanup, duplicate detection, crate management, and Serato sync — so that Serato can focus on being the performance interface.

CrateSort is the single writer. Serato is the reader. The DJ never organizes inside Serato again.

CrateSort is the digital counterpart to **CrateView** (vinyl collection management). Together, they form the **Crate suite** — CrateView for wax, CrateSort for MP3s. Each works independently; together, they give full visibility across both formats.

---

## The Problem

Tens of thousands of MP3s (and music videos) accumulated over years of DJing. The library works, but it's full of friction:

- **Flat genre explosion**: Genre and style folders all live at the same level. Six Funk variants, multiple Blues variants — no hierarchy, no consistency.
- **Convenience folders**: Folders like "Breakdance / Park Jams" and "Funk / Electro" were created under time pressure. They contain files from multiple genres that should be filed properly.
- **Duplicate files**: The same track exists in multiple folders. Serato crates reference different physical copies.
- **Wrong years**: Compilation years instead of original release years. DJs think in decades — "what year does it sound like" matters.
- **Dirty filenames**: Artist names, track numbers, album names baked into filenames. Target is just the song title.
- **"The" sorting problem**: "The Rolling Stones" and "The Doors" both sort under T.
- **Fragmented artist folders**: Same artist under multiple names (e.g., "Bob Seger" / "Bob Seger And The Silver Bullet Band" / "Bob Seger System").
- **Inaccurate genre tags**: Sources frequently mislabel genres — tagging Soul artists as "Pop", labeling Synth-Pop as "Electronic" instead of Rock.
- **No intake workflow**: Adding new music means manually dragging files into folders, fixing tags, adding to crates.
- **Crate management in Serato is clunky**: Building crates, especially smart crates, is tedious. No way to surface unfiled tracks.
- **Files scattered across drives**: MP3s in one place, videos in another, downloads folder has strays. No central organizational system.

---

## The Vision

### Target folder structure (within the user's designated directory)

CrateSort works **in place**. It reorganizes within whatever directory the user points it at. It never creates new parent directories, never moves files between drives, and never renames the root folder.

```
[User's designated MP3 directory]/
  Blues/
    Buddy Guy/
      Damn Right I Got the Blues.mp3
  Funk-Soul/
    James Brown/
      Get Up (I Feel Like Being a) Sex Machine.mp3
    Fela Kuti/
      Zombie.mp3
  Hip-Hop-Rap/
    Redman/
      Time 4 Sum Aksion.mp3
  Rock/
    Doors, The/
      Riders on the Storm.mp3
    Bob Seger/
      Bob Seger/
        Night Moves.mp3
      Bob Seger And The Silver Bullet Band/
        Old Time Rock and Roll.mp3
  R&B/
    Jodeci/
      ...
  Jazz/
    Bob James/
      ...
  Specialty/
    DJ Drops/
      ...

[User's designated Music Videos directory — same or different drive]/
  (Same genre/artist structure, managed independently)
```

### Directory setup (first launch wizard)

On first launch, a setup wizard asks:
1. "Where are your audio files?" → user points to a directory (e.g., `/Volumes/DJ Drive/MP3/`)
2. "Do you have music videos?" → user points to another directory or skips
3. "Where is your Serato library?" → auto-detect `_Serato_/` folder or manual selection

Each directory is managed independently. MP3s on Drive A and videos on Drive B both get organized using the same genre/artist taxonomy, but they never cross. CrateSort never reaches into directories the user hasn't explicitly designated. Additional directories can be added later.

### Hierarchy rules

1. **Tier 1 — Genre folder**: Broad genre folders inside the designated root. Only created when files exist for that genre.
2. **Tier 2 — Artist folder**: One folder per artist inside each genre. Natural naming (first name first). "The" moved to end with comma.
3. **Tier 2a — Project subfolders (on consolidated artists only)**: When an artist is merged from multiple names (e.g., Bob Seger + Silver Bullet Band + Bob Seger System), the consolidated folder contains subfolders for each project/band. Optional — user can choose flat merge instead.
4. **Tier 3 — Track files**: Loose files inside the artist folder (or project subfolder). Filename = song title only. Metadata carries the rest.
5. **No style subfolders on disk.** Style is metadata and crate-level organization only.
6. **No empty genre folders.** Created on the fly when files arrive.

### Supported file formats

- **Audio**: MP3 (primary), plus any audio format Serato supports
- **Video**: MP4, M4V, MOV, and other formats Serato supports
- Same organizational logic for both. Managed as separate directory trees.

---

## Genre Taxonomy

### The 12 parent genres

| Genre | What belongs here | The record store test |
|-------|-------------------|----------------------|
| **Blues** | Chicago Blues, Delta Blues, Electric Blues, Jump Blues, Texas Blues, Acoustic Blues, Country Blues | The blues bins — Buddy Guy, B.B. King, Lightnin' Hopkins |
| **Country** | Classic Country, Country Western, Honky-Tonk, Outlaw Country | The country section — Willie Nelson, Johnny Cash |
| **Electronic** | Ambient, Breakbeat, Downtempo, Drum & Bass, Electro, Trip-Hop | Where electronic production IS the point — Kraftwerk, Portishead |
| **Funk/Soul** | Afro Funk, Brazilian Funk, Breakdance / Park Jams, Chicano Soul, Classic Funk, Classic Soul, Disco, Go-Go, Instrumental Funk, Modern Funk, Neo Soul, Northern Soul, P-Funk, Psychedelic Soul, Rare Groove | The funk and soul bins — James Brown, Barry White, Marvin Gaye. If it could be in the funk or soul bins, it's here. |
| **Hip-Hop/Rap** | Boom Bap, Conscious, G-Funk, Gangsta, Golden Era, Hardcore, Instrumental Hip-Hop, Jazzy Hip-Hop, Old School, Southern, Underground, West Coast | The hip-hop section |
| **House** | Acid House, Chicago House, Deep House, Garage, Soulful House, Tech House | Its own world — not Electronic, not Funk. Enough depth to stand alone. |
| **Jazz** | Avant-Garde, Bebop, Bossa Nova, Cool Jazz, Fusion, Hard Bop, Jazz-Funk, Latin Jazz, Library, Lo-Fi, Modal, Smooth Jazz, Soul-Jazz, Swing | The jazz section |
| **R&B** | Classic R&B, Contemporary R&B, Freestyle, New Jack Swing, Quiet Storm, Slow Jams, '50s R&B / Doo-Wop | The R&B bins — Jodeci, Mariah Carey, SWV. Not the funk/soul bins. |
| **Reggae** | Dancehall, Dub, Roots Reggae, Ska | The reggae section |
| **Rock** | Alternative, Art Rock, Blues Rock, Boogie Rock, Country Rock, Early Rock & Roll, Folk Rock, Garage Rock, Hard Rock, Heartland Rock, New Wave, Oldies, Pop Rock, Progressive Rock, Psychedelic Rock, Soft Rock, Southern Rock, Surf Rock, Synth-Pop | The rock section. Synth-Pop and New Wave are rock bands with synths, not Electronic. |
| **Seasonal** | Holiday, Christmas, Halloween | Seasonal/themed gig music |
| **Specialty** | DJ Drops, Scratch Records, Sound Effects, TV Themes, Break Records | Genreless DJ tools and utilities |

### Classification rules

- **One home per artist.** Each artist lives in exactly one genre folder.
- **The "record store test."** What section would you look in?
- **Style = metadata, not folders.** Styles written to ID3 tags for Serato sorting but don't create directories.
- **"Pop" is never a genre.** Everything labeled "Pop" gets reclassified based on actual styles.
- **Convenience folders get dissolved.** Files classified individually and moved to correct genres. Serato crates for those folders survive with updated paths.
- **The engine is opinionated but transparent.** "Discogs says Pop, we think Rock based on styles Blues Rock and Pop Rock. What say you?"
- **No API keys required.** Classification runs entirely from local metadata and internal mapping logic.
- **Title Case for all genre and style terms.** Blues Rock, New Jack Swing, Instrumental Hip-Hop.

### Artist naming rules

- **First name first.** `Eric Clapton`, not `Clapton, Eric`.
- **"The" moved to end with comma.** `Doors, The/` under D. `Rolling Stones, The/` under R. Full name preserved in ID3 artist tag.
- **Settings toggle** for last-name-first preference. Default: off.
- **Special characters sanitized** in folder/filenames. Originals preserved in ID3 tags.

### Artist consolidation

- Detects multiple folders for the same artist via substring + fuzzy matching.
- Presents candidates: "Bob Seger (4) + Bob Seger And The Silver Bullet Band (9) + Bob Seger System (2) = 15 records. Merge?"
- User picks the winning name.
- **Project subfolders option**: merged folder can contain subfolders for each band/project, or merge flat. User chooses.
- Merges folders on disk AND updates all Serato crate references.
- False positives presented for dismissal ("Queen" vs "Queen Latifah").
- Never automatic — always suggest-and-confirm.

---

## Serato Integration

### Golden rule: Serato's edits always win

The file on disk is always the source of truth. Any changes made in Serato since the last CrateSort session are absorbed, never overwritten.

### Startup sync sequence

Every launch follows a mandatory sync. UI locked until complete.

1. **Amber — "Scanning library..."** Reading files, comparing against last checkpoint. UI visible but locked.
2. **Changes detected — change review screen.** Before/after for each modification. User can:
   - **Accept all** → new checkpoint, go green.
   - **Restore previous** → roll back to last checkpoint (with confirmation).
   - **Line-by-line** → accept some, reject others.
3. **Green — "Library synced. Ready."** UI unlocks. Safe to edit.

Checkpoint history: lightweight metadata snapshots (JSON/SQLite). Multiple checkpoints deep.

### Crate rules

1. **Crates are sacred.** Only file paths are updated during reorganization. Structure/membership never touched.
2. **Special crate preservation.** Genre reclassification doesn't remove tracks from vibe-based crates.
3. **Full crate management in GUI.** Create, rename, duplicate, delete crates. Drag tracks between crates.
4. **Smart crate management.** Create/edit Serato smart crates from CrateSort — cleaner than Serato's UI. Filter library visually, then "Save as Smart Crate."
5. **No file deletion.** Can remove tracks from crates and delete crates, but cannot delete files from drive. Exception: user-approved duplicate consolidation (quarantine, not permanent delete).
6. **No independent file moves.** Outside of reorganization (explicitly triggered), CrateSort never moves files.

### Duplicate consolidation — metadata merge

Before removing duplicate copies, CrateSort performs a metadata diff across all copies:

- Shows side-by-side comparison: bitrate, genre tags, comments, BPM, crate references
- Flags conflicts: "Copy B has a comment ('Redman Sample') that the winner doesn't. Migrate?"
- Flags genre disagreements: "Copy A tagged Funk, Copy C tagged R&B. Winner is tagged Funk. Keep?"
- Flags BPM differences: "Copy A = 118 BPM, Copy C = 120 BPM. Keep 118?"
- User resolves each conflict before consolidation executes
- All Serato crate references across all copies repoint to the surviving file
- Winner absorbs the best metadata from all copies — nothing lost unless user explicitly declines

---

## Architecture

### Platform

- **Cross-platform desktop app.** macOS-first, Windows and Linux from day one.
- **Python 3.x** with PyQt6/PySide6.
- **Custom branded UI.** Not a system-themed app. CrateSort has its own visual identity — dark theme, custom colors, typography, and layout inspired by the CrateView brand (warm tones, parchment/cream accents, script logotype elements, dark backgrounds). Looks like a professional DJ tool, not a settings dialog.
- **No internet required. No API keys. No server.**
- **Lightweight.** Handles tens of thousands of files without hogging resources.
- **Subscription-ready architecture.** Features built as modules that can be gated behind tiers:
  - **Free tier**: Serato crate management (view, create, rename, duplicate, delete, drag tracks). The entry point.
  - **Paid tier** (~$5-10/month or ~$100/year): Drive reorganization, export, duplicate detection, style suggestions, smart features. The power tools.
  - License check is periodic and offline-tolerant. Lapsed subscription drops to free tier — never locks users out of their library.
  - Not built in v1, but architecture supports adding it without a rewrite.
- **Future-proof.** Serato DJ Pro first. Rekordbox and Engine DJ modules later.

### Design language

CrateSort inherits the Crate suite visual identity from CrateView:
- **Dark primary background** with warm accent tones
- **Color palette**: Warm browns, oranges, creams (hex values from CrateView: dark bg ~#1a1a1a, cream text ~#f1e3c8, orange accents ~#D17D34, dark panels ~#2F2F2F)
- **Typography**: Clean sans-serif for UI, script/display font for branding (matching CrateView logotype style)
- **Mascot/logo**: Crate-themed character consistent with CrateView's mascot. "CrateSort" in the same script style as "CrateView."
- **Overall feel**: Professional DJ tool. Dark, warm, focused. Not flashy, not minimal — functional and good-looking.

### Component overview

```
┌─────────────────────────────────────────────────────┐
│                   CrateSort GUI                      │
│  Welcome dashboard · Library browser · Crate manager │
│  Intake workflow · Style suggestions · Settings      │
│  Duplicate reviewer · Export manager                 │
├─────────────────────────────────────────────────────┤
│                   Core Engine                        │
│  Scanner · Genre classifier · Style suggester        │
│  Metadata fixer · Filename cleaner · "The" handler   │
│  File organizer · Duplicate detector · File locking  │
│  Artist consolidation detector                       │
├─────────────────────────────────────────────────────┤
│           DJ Software Integration Layer              │
│  Serato DJ Pro · Rekordbox (future) · Engine DJ (f.) │
├─────────────────────────────────────────────────────┤
│                  Export Engine                        │
│  Serato · Pioneer/Rekordbox · Universal (M3U+folder) │
├─────────────────────────────────────────────────────┤
│                Optional Plugins                      │
│  CrateView Bridge (vinyl/digital alignment)          │
└─────────────────────────────────────────────────────┘
```

### Core engine components

#### 1. Scanner / Inventory
- Walks designated directory trees (audio and video roots independently)
- Reads ID3 tags (artist, title, album, genre, year, comment, duration, BPM)
- Reads Serato custom ID3 frames (BPM, cue points, beat grids, color tags)
- Maps file paths to Serato crate references
- Catalogs existing Serato crate structure — marks all as sacred
- Detects artist consolidation candidates

#### 2. Genre Classification Engine
- Classifies each artist into one of the 12 parent genres
- Does NOT blindly trust external genre tags. Analyzes styles, catalog patterns, era context.
- Transparent: "Discogs says Pop, we think Rock. What say you?"
- User confirms or overrides every classification
- No API keys. No internet. Works from local metadata + internal mapping.

#### 3. Style Suggestions Engine
- Tags tracks with suggested styles from metadata analysis
- Crates can be tagged with a style (genre-level for v1)
- Surfaces unfiled tracks: "25 Psychedelic Rock tracks not in your Psychedelic Rock crate"
- Welcome dashboard shows suggestion counts per style-tagged crate
- Semi-automatic: creating a crate named "Psychedelic Rock" prompts style tag association
- Passive — never moves files or creates crates without user action

#### 4. Duplicate Detector
- Inform-first. Never auto-deletes.
- Fast pass: normalized artist + title + duration (±2 sec)
- Deep pass: audio fingerprint (Chromaprint/AcoustID)
- Full metadata diff before consolidation — comments, genre tags, BPM conflicts surfaced
- User resolves per group or bulk. Quarantine, not permanent delete.
- All Serato crate references repointed to surviving file.

#### 5. Metadata Fixer
- Year correction (compilation → original) from local heuristics
- Genre/style tag updates per taxonomy
- Comment preservation + structured tags (`[sampled-by:Redman]`)
- Sort-artist field ("The"-handled version)
- Serato metadata (cue points, beat grids, loops) NEVER overwritten

#### 6. Filename Cleaner
- Strips artist prefixes, track numbers, album references
- Sanitizes special characters cross-platform
- Result: filename = song title only

#### 7. "The" Handler
- `The Doors` → folder `Doors, The/` → sorts under D
- Full name in ID3 artist tag for Serato display
- Settings toggle for last-name-first (default: off)

#### 8. File Organizer
- Moves files into Genre/Artist/track hierarchy within designated directory
- Creates genre folders only when files exist
- Full move log for rollback
- Non-destructive option (copy-verify-delete)
- Re-organize available anytime (messy drive, new files, etc.)
- Respects file lock status

#### 9. Artist Consolidation
- Substring + fuzzy matching detection
- Project subfolder option on merge
- User picks winning name, approves merge
- Updates both disk and Serato references
- Never automatic

#### 10. File Locking
- Lock/unlock any file via GUI
- Locked = protected from metadata/filename changes
- Lock state in CrateSort's internal database
- Useful for shared drives

### Serato Integration Module (DJ Pro)

- Reads/writes `.crate` files
- Path rewriter after file moves
- Database sync
- Smart crate builder (cleaner than Serato's UI)
- Full crate CRUD via GUI
- Never modifies crate structure unless user-initiated

### Export Engine

- **Serato**: Folder structure + `.crate` files
- **Pioneer / Rekordbox** (future): Folder structure + Rekordbox XML + `PIONEER/` directory
- **Universal**: Folder structure + M3U playlist
- Copies files from master library — originals untouched
- Maintains genre/artist structure in export
- "Re-export" option to refresh existing exports

### CrateView Bridge (Optional Plugin)

- Reads CrateView JSON cache for vinyl/digital alignment
- Cross-format badge: "You have this on vinyl too"
- Read-only — never writes to CrateView data
- Not required. Soft marketing touchpoint in settings.

---

## GUI

Ships with GUI from day one. No terminal phase. Custom branded UI — not system themed.

### Welcome dashboard (after sync goes green)

- Sync summary (expandable)
- Suggestion feed: "Rock: 6 tracks match your Psychedelic Rock crate." Clickable.
- Library health snapshot
- Toggle: show/hide on startup

### Main views

1. **Library browser** — browse by genre, artist, or flat list. Sortable, searchable, filterable columns. Right-click any track → "Show in Finder/Explorer."
2. **Crate manager** — tree view of all crates. Drag-and-drop. Create, rename, duplicate, delete. Smart crate builder.
3. **Intake** — drag-and-drop new files. App proposes genre/style/filename. User confirms.
4. **Style suggestions** — filter by style, see unfiled tracks, drag into crates.
5. **Duplicate reviewer** — side-by-side with metadata diff and conflict resolution.
6. **Export manager** — select crate, choose profile, pick destination, export.
7. **Settings** — genre taxonomy, "The" toggle, last-name-first toggle, file locking, directory management, CrateView bridge, dashboard toggle.

### Crate builder suggestions

While building any crate, CrateSort surfaces tracks matching the emerging pattern (decade, genre, style, BPM range). Non-intrusive: "6 tracks match this crate's vibe." Same logic as CrateView's complimentary albums.

---

## Process: Initial Library Cleanup

1. **Setup wizard** — user designates audio directory, video directory (optional), Serato location
2. **Scan** — full inventory, Serato crates cataloged, artist consolidation candidates flagged
3. **Genre classification** — engine proposes, user confirms (transparent reasoning)
4. **Style analysis** — background tagging, available in suggestions view
5. **Duplicate detection** — fast pass then deep pass. Metadata diff on each group. User approves.
6. **Metadata fixes** — years, genres, styles, filenames, "The" handling, artist consolidation
7. **Preview & approve** — full reorganization plan displayed
8. **Execute** — files moved, duplicates quarantined, convenience folders dissolved, full rollback log
9. **Serato sync** — all crate paths updated, structure preserved
10. **Verify** — re-scan, health report

---

## Ongoing Workflow

1. Open CrateSort → startup sync (amber → review → green)
2. Drag new files into intake
3. App proposes classification, user confirms
4. Files cleaned, organized, Serato updated
5. Next Serato launch picks up changes

---

## Technical Stack

- **Language**: Python 3.x
- **GUI**: PyQt6 or PySide6 (custom themed, not system default)
- **ID3 tags**: `mutagen`
- **Audio fingerprinting**: `chromaprint` / `pyacoustid`
- **Serato parsing**: custom or community library
- **No external APIs for core functionality**
- **Optional future enrichment** (power-user settings): MusicBrainz, Discogs
- **CrateView bridge**: direct JSON reads (optional)
- **Packaging**: PyInstaller → `.app` (macOS), `.exe` (Windows), AppImage (Linux)

### Cross-platform (day one)

- Path abstraction (`/` and `\`)
- Case sensitivity handling
- Serato folder auto-detection per OS
- Special character sanitization for all OS
- Drive format detection: exFAT, APFS, NTFS, HFS+, ext4

---

## Key Principles

1. **Standalone. No internet. No API keys.** Install, point at drive, go.
2. **Genre = folder. Style = metadata + crates.**
3. **One home per artist.**
4. **Filename = song title only.**
5. **Title Case for all genre and style terms.**
6. **"The" sorts correctly.** Full name in metadata.
7. **Crates are sacred.**
8. **Serato's edits always win.**
9. **Inform first, act second.**
10. **The engine is opinionated but transparent.**
11. **"Pop" is not a genre.**
12. **No file deletion** outside user-approved duplicate consolidation.
13. **No independent file moves** outside user-triggered reorganization.
14. **CrateSort works in place.** Reorganizes within designated directories. Never reaches outside them.
15. **Non-destructive by default.** Preview → approve → execute. Rollback. Quarantine.
16. **Metadata merge on duplicates.** Comments, tags, BPM — nothing lost without user consent.
17. **Lightweight and efficient.**
18. **Cross-platform from day one.**
19. **Subscription-ready architecture.** Free tier (crate management) + paid tier (power tools).
20. **Custom branded UI.** Not system themed — a professional DJ tool with the Crate suite identity.
21. **Keep it simple.** Every feature serves one purpose: help the DJ find their music faster.

---

## Monetization (future)

- **Free tier**: Serato crate management — view, create, rename, duplicate, delete crates, drag tracks. Enough to get DJs in the door.
- **Paid tier** (~$5-10/month or ~$100/year): Drive reorganization, export, duplicate detection, style suggestions, smart crate builder, CrateView bridge. The power tools.
- License check: periodic, offline-tolerant. Lapsed subscription → free tier (never locked out of library).
- Not built in v1. Architecture supports gating features without rewrite.

---

## Roadmap

### Phase 1: Foundation
- Serato DJ Pro file format research
- Python project scaffolding (cross-platform)
- Core Scanner module
- GUI shell with custom Crate suite theme (startup sync: amber/green states)
- Directory setup wizard

### Phase 2: The Engine
- Genre Classification Engine
- Filename Cleaner + "The" Handler
- Metadata Fixer
- File Organizer (in-place reorganization, rollback)
- Artist Consolidation (with project subfolder option)

### Phase 3: Serato Integration
- Crate file reader/writer
- Path rewriter
- Database sync
- Crate management GUI
- Smart crate builder

### Phase 4: Duplicate Detection & Style Suggestions
- Duplicate detector (fast + deep passes)
- Metadata merge flow for consolidation
- Duplicate reviewer GUI
- Style Suggestions Engine + crate tagging
- Welcome dashboard with suggestion feed

### Phase 5: Export & Polish
- Export engine (Serato, Pioneer/Rekordbox, Universal)
- File locking
- Intake workflow
- Library health dashboard
- Crate builder complementary suggestions
- Right-click "Show in Finder/Explorer"
- Checkpoint/rollback system
- Package standalone apps

### Phase 6: Integration & Future
- CrateView Bridge plugin
- Rekordbox module
- Engine DJ module
- Subscription/licensing system
- Genre spectrum visualization (dashboard eye candy)
- Commercial release

---

## Project Identity

**Name**: CrateSort
**Tagline**: Get your shit together.
**Suite**: Part of the Crate suite — CrateView (vinyl), CrateSort (digital).
**Design**: Dark theme, warm CrateView tones (browns, oranges, creams), script logotype, crate mascot.
