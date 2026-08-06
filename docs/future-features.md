# CrateSort — Future Feature Considerations

Ideas and capabilities tabled during development. Not committed to any release timeline. 
Intended as a living reference for roadmap planning, beta feedback conversations, and marketing.

---

## Library

### Track Associations
Link two tracks together with a relationship label so that finding one surfaces the other in search results.

**Use case:** A DJ knows either the original soul record or the hip-hop song that sampled it, but not always both. Linking them means searching for either one returns both. Relationships could be labeled: "samples", "sampled by", "flip of", "edit of", etc.

**Why it matters:** DJs currently work around this by putting notes like "Redman sample" in the comment field of the original track. That's a misuse of the comment field and it breaks down — you have to remember the exact wording, and it only works in one direction.

**Implementation note:** Would live entirely in CrateSort's own metadata layer (`_CrateSort/associations.json`). No Serato dependency. Many-to-many. Surfaced in the track detail view and search results.

---

### "◆ New" Marker for Recently-Added Tracks
`LibraryBrowserView._new_track_paths` already exists as a field the tree renderer checks to show a "◆ new" marker next to a track — but nothing in the codebase ever populates it, so the marker never appears.

**Use case:** After adding tracks to the library folder (import, copy from another drive, etc.), the DJ can see at a glance which tracks are new since the last time they opened the app, without hunting for them.

**Why it's tabled, not built:** Came up during the 2026-08 incremental-scan work (`scanner.py`'s new per-file cache, see `CLAUDE-CS.md`) — that change gives the scanner an exact list of "paths present in this scan but absent from last scan's cache" for free, which is exactly what this marker needs. Left alone this pass to keep that work scoped strictly to scan speed.

**Implementation note:** Thread the incremental scan's "added paths" list (new module `cratesort/src/core/scan_cache.py`) through `dashboard.py` → `main_window.py` → `LibraryBrowserView.load()`, and set `_new_track_paths` from it instead of leaving it perpetually empty.

---

## Rinse (Duplicate Detection)

### Artwork Thumbnail on Click in Rinse Review Screen
When reviewing duplicates, clicking a track row that has `ARTWORK: Yes` should display the embedded album art in a thumbnail on the card.

**Use case:** Lets the DJ visually confirm which copy has artwork before deciding which to keep. Useful when one copy has artwork and the other doesn't.

**Implementation note:** Artwork is already detected at scan time (`has_artwork` field on `DuplicateCopy`). The remaining work is reading the actual image data at click time via mutagen, creating a `QPixmap`, and rendering it in the card layout. Needs a click handler on the row and a thumbnail widget (e.g., 64×64px) that appears inline.

---

## Crates

*(nothing tabled yet)*

---

## Classify

### Online-Assisted Classification — Graduate Beyond Local-Only Pattern Matching
Right now `GenreClassifier` (`classifier.py`) is purely local and has zero knowledge of who any artist actually is. It classifies in strict tiers — exact tag match → user Style Tag resolved via style map (added 2026-08-06, see `CLAUDE-CS.md` → "Style Tags feed classification") → genre-tag style-map lookup → comment/genre/Style-Tag token analysis → folder-name hint (deliberately skipped inside "purpose" folders like `_samples`/`_tributes`/`_instrumentals`, since those describe use-case, not genre) → Unclassified. If a file's own tag, folder, comment, and any user-added Style Tags are all empty or unhelpful, the classifier has nothing left to reach for — no internet lookup, no artist database, no cross-referencing, regardless of how famous or well-documented the artist is.

**Confirmed real example (2026-08):** Aaron Neville's "Hercules" — correctly tagged with the real artist name and title, sitting in a `.../Hip-Hop : Rap/_Samples/Aaron Neville/` folder — came back Unclassified/no-confidence. The genre tag was literally `"Sample"` (a DJ convention, not a real genre), the folder hint was correctly suppressed (it's a sample-source folder, not a genre folder — a soul record filed there for hip-hop producers to find is not itself hip-hop), and there was no comment data to fall back on. The classifier behaved exactly as designed, but the result — total silence on a very well-known artist — read as broken/deceptive rather than "working as intended," and directly exposed the ceiling of a purely local, tag-dependent approach: classification quality is entirely bounded by how well the user already tagged their files before CrateSort ever sees them.

**The vision (Jace, 2026-08):** graduate from purely local pattern-matching to an optional, network-assisted tier — not replacing the current tiers (confirmed those stay as the core, working foundation), but added as a supporting last resort before giving up entirely. Longer-term idea: as more users classify their libraries, CrateSort could (with explicit opt-in, discussed with the user base first) aggregate anonymized "what did users end up calling this artist/track" patterns across its install base, cross-reference that against external sources, and use that combined signal to fill in genre gaps that today just fall through to Unclassified — effectively crowdsourced + AI-assisted metadata resolution, not just a single external API call.

**Why this isn't a contradiction of "no external APIs required":** that line in `CLAUDE-CS.md` lives under the tech-stack list, not as a marketed promise — checked both `docs/positioning-brief-cratesort.md` and `docs/what-is-cratesort.md`, neither claims "runs fully offline" as a selling point. There's also already a working precedent: `yt_import_dialog.py` already does an optional MusicBrainz lookup to fill in canonical tags after a YouTube download, gracefully degrading with no internet. Extending that same "optional, best-effort, offline-safe" pattern to classification would be consistent with existing app behavior, not a new category of risk.

**Real complexity to solve before building this (not yet scoped in detail):**
- MusicBrainz/Discogs genre data is freeform, community-tagged text — CrateSort's taxonomy is a fixed 12-genre list. Needs its own mapping layer, similar in spirit to the existing `STYLE_MAP`, translating arbitrary external tags into one of the 12 buckets.
- Network latency — a lookup per never-before-seen artist needs to not stall the classify pass; likely needs async/batched fetching plus per-artist caching (query once per artist name across all their tracks, not once per track).
- Must degrade cleanly with no internet connection — exactly like the YT import path already does — never a hard requirement for the app to function.
- The crowdsourced/aggregated-data half of the vision is a materially bigger, separate decision (user opt-in, anonymization, some kind of shared backend to collect and query pattern data) from "just add one external genre lookup" — worth scoping as two distinct phases, not one project.
- See also the related, already-tabled **CrateCleaner** sister-tool idea below, which already envisions audio fingerprinting + MusicBrainz/Discogs lookup for metadata correction — that's a separate standalone product, but the lookup/mapping infrastructure built for one could likely be shared with the other.

**Status:** explicitly tabled for later. Current local-only classifier confirmed as a good, correct core foundation — not being replaced, just potentially extended. Not urgent; revisit when ready to scope the network/mapping/opt-in work properly.

---

## Organize

*(nothing tabled yet)*

---

## General / UX

### Animated right-click context menus (Library, Crates, Tracks)
Right-click menus throughout the app ("Approve", "Change Genre", "Mark for Review", etc. in Library; equivalent menus in Crates/Tracks) are plain `QMenu` instances — confirmed and requested to get the same elastic/spring motion signature as dialogs and page transitions ("more fun," "more brand essence").

**Why it's tabled, not built:** `QMenu` renders as a native macOS menu with zero programmatic animation hook — Qt cannot attach a `QPropertyAnimation` to it, same category of constraint as native file pickers. Matching the dialog bounce requires building a fully custom frameless popup widget from scratch (own rows, hover states, keyboard nav, positioning, dismiss-on-outside-click) to replace `QMenu` in all three call sites (`library_browser.py`, `classifier_view.py`, `crate_manager.py`) — a real component build, not a tweak.

**Implementation note:** Model it on `_CrateSortDialog` (`overlays.py`) — frameless `QWidget`, `OutBack`/`InBack` overshoot 3.0 (size-based, matches dialogs) for entrance/exit. No existing non-native popup/dropdown precedent exists elsewhere in the codebase to reuse.

---

---

## Packaging & Distribution

### Code signing + notarization
Beta DMG is unsigned — testers hit a Gatekeeper "unidentified developer" warning on first launch. Requires an Apple Developer ID certificate ($99/yr) plus notarization via `notarytool`. Worth doing before a public (non-beta) release.

### Windows (.exe) and Linux (AppImage) packaging
Only macOS is built so far (PyInstaller, see `CLAUDE-CS.md` → Cody → "Packaging & Distribution"). Windows/Linux builds need their own PyInstaller spec pass on those platforms — can't be cross-compiled from macOS.

---

## CrateCleaner — Sister Tool (Separate Product)

A lightweight standalone companion app positioned as a free lead-gen piece for CrateSort. Lets users drop in any audio/video file, see all human-facing metadata fields, get AI-suggested corrections via audio fingerprinting + MusicBrainz/Discogs lookup, and write the cleaned metadata back to the file.

**Core concept:** The "Costco sample" — give someone a polished free tool that demonstrates CrateSuite's quality, speed, and personality before they commit to CrateSort.

**Key aha moments to design for:**
- "I didn't know my file was this bad" — visual health indicator on drop
- "I didn't know there were this many fields" — show all human-facing fields, empty ones included
- "My artwork is poor quality" — flag low-res art, offer to replace
- "I can add multiple artworks" — front/back/artist photo, most users don't know this exists
- Fingerprint moment — "we found this track, want us to fill everything in?"

**Scope:**
- Batch queue (HandBrake-style), no file limit or soft cap (~10)
- Metadata lookup + suggested fixes, not just manual editing
- Strictly human-facing fields only — no Hz, kbps, encoder junk
- Artwork read, replace, and multi-artwork support
- Strip encoder/muxer garbage fields in one tap

**Form factor:** Native desktop app (Tauri), custom-shaped window following the crate + mascot silhouette. The crate IS the window. Mascot reacts expressively to what he finds in the file.

**Status:** Needs design mockups and further research before build. Image generation prompts drafted — feed to Midjourney/Gemini/GPT to explore visual direction.

---

*Last updated: August 4, 2026*
