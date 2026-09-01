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

### Add Tracks by Drag / File-Picker (bring files INTO the library from anywhere)
**Status: design agreed 2026-08-28, sequenced after 0.1.3-beta ships. Not started.**

Today the only way to add a file to the library is to drop it in the library folder in Finder and re-scan; the "Add Tracks" buttons just `open` that folder, and right-click → Add Tracks on a crate only offers already-scanned tracks. Jace hit this during testing — after consolidating duplicates he wanted to add a brand-new track to a crate and there was no in-app path.

**Core constraint / the fear to design against:** CrateSort works from a directory — a file it doesn't own can't be processed — so any file added from outside has to be **copied into the library root**. The risk is *silent duplication*: a user drags a file off their Desktop, a second copy appears in the library, and they never realize they now have two. The fix is a **mandatory pre-flight modal** on every add (drag or button), never a silent copy.

**Agreed shape:**
- **Two entry points, one modal:** drag onto the Library screen / onto a crate in the Crates screen, AND a real "Add Tracks" button (replaces the current open-Finder buttons; Library toolbar + Crates screen when a crate is selected). Both route through the same confirmation modal — drag is not "silent" if the drop always surfaces it.
- **The modal is a per-file pre-flight.** It classifies every dropped/picked file and states exactly what happens: *outside the library* → "a copy will be added to `…/Library/`, the file you dragged will not be changed or removed"; *already in the library folder but unscanned* → "already there, just indexing it, no copy"; *already in the library and scanned* (re-drag) → no-op / add-to-crate only; *audio duplicate of something already there* (run the Rinse detector on ingest) → "looks like a copy of 'X' — Add anyway / Skip". Mixed drops itemize: "3 copied in · 1 already in library · 1 possible duplicate".
- **Copy, never move.** One explicit opt-in: "Add and remove the source files" — deletes each source only after a verified byte-identical copy. Default OFF.
- **Placement (recommended):** loose at the library root, modal ends with "Run Organize to sort these into artist/genre folders." Predictable, no tag-guessing, reinforces that Organize is what files the library. (Alternative held as a refinement: auto-file by artist tag when clean, `…/Library/<Artist>/`, like YouTube import.)
- **Drop-on-crate in v1** of this feature: adds to library if new, then to that crate. Same modal. This is the exact friction Jace hit. Pro-tier 1 (crate management); drop-on-Library-screen is free tier.
- **Feedback:** dragover highlight; incremental add (no full rescan — reuse the `_new_track_paths` ◆-marker path); toast "Added N · Skipped M"; scroll to new rows.
- **Interim step (do first, right after 0.1.3 ships):** make the existing "Add Tracks" button a plain native file-picker that copies selected files into the library root + rescans, with a one-time explainer of where they went. Small, safe, kills ~80% of the friction without the full modal.

---

### Custom Workspace Layouts
Column order/width in the Library tree is currently a single global OS-level setting (`QSettings`), not tied to any particular library. That's correct default behavior — the app remembers how the DJ likes to work, independent of which library is loaded — but some users may want a named, savable layout (e.g., a "file audit" layout with Path pulled forward, vs. a default "browsing" layout).

**Use case:** A DJ who occasionally needs to eyeball file paths (e.g., checking Organize output) drags the Path column next to Artist, but doesn't want that as their permanent default — they want to toggle between a couple of saved column arrangements.

**Why it's tabled:** Raised during 2026-08-07 testing as a "long time from now" idea, not a request to build. Needs real user-testing signal on whether the single global default is ever actually a pain point before investing in named layout presets/toggles.

---

### Multi-location library (separate `_Serato_` + media-drive paths) — CONSIDERED AND DECLINED 2026-08-28
Idea: let the read-only features (scan / Rinse / metadata / artist reassignment) accept a `_Serato_` folder in one place and media in another (e.g. `~/Music/_Serato_` on the laptop + music on an external), keeping the single-folder requirement only for Organize.

**Why it's a fair idea:** Serato is genuinely multi-database — it keeps a `_Serato_` folder per drive and merges them at launch, so every gigging DJ with an external already has two. `LibraryScanner(*root_dirs)` (`cratesort/src/core/scanner.py`) is already variadic; the single-folder limit is only in the UI / `_ScanWorker` layer.

**Why declined:** Real build cost — per-root scan-cache keying, a multi-path watcher, saved state as a list, and especially **write-back routing for crates that span two `_Serato_` databases** (Serato routes each track to the database for the drive it lives on; `crate_writer` / `path_rewriter` would need the same). Decision: keep the single-folder model and sell its benefit in the launch-screen copy instead. Latent gap worth an empirical check: Smart Crates + laptop-local-track crates live in `~/Music/_Serato_`, which CrateSort may not read when the user points at an external drive root.

---

## Rinse (Duplicate Detection)

### Artwork Thumbnail on Click in Rinse Review Screen
When reviewing duplicates, clicking a track row that has `ARTWORK: Yes` should display the embedded album art in a thumbnail on the card.

**Use case:** Lets the DJ visually confirm which copy has artwork before deciding which to keep. Useful when one copy has artwork and the other doesn't.

**Implementation note:** Artwork is already detected at scan time (`has_artwork` field on `DuplicateCopy`). The remaining work is reading the actual image data at click time via mutagen, creating a `QPixmap`, and rendering it in the card layout. Needs a click handler on the row and a thumbnail widget (e.g., 64×64px) that appears inline.

### Acoustic Fingerprinting for Duplicate Detection
`DuplicateDetector` currently groups two files only when their normalized `(artist, title)` strings match *exactly* — audio metrics (duration/bitrate/size) merely tier an already-formed group. This means it cannot catch the same recording when both copies have genuinely different metadata (a rename, a different featuring credit, wrong artist). The 2026-08-27 manual test exposed this: editing one copy's title (`(Bootleg)`) dropped the pair from detection entirely (fixed narrowly by making `normalize_title()` strip any trailing bracket group, but that only covers *suffixes*, not a rewritten core title).

**The real fix:** implement the existing `fingerprint_pass()` stub in `duplicate_detector.py` with `chromaprint` (`fpcalc`) + `pyacoustid` (already a project dependency). Compares actual audio content, so it catches the same song at any bitrate with any/no metadata.

**Cost to weigh:** bundling the `fpcalc` binary into the unsigned macOS DMG (no turnkey pip wheel like `imageio-ffmpeg`), plus a real `%`-progress phase for fingerprinting every track on a large library (slow first pass — cache fingerprints keyed by path + mtime). Feature-scale, not a patch. Overlaps with the **CrateCleaner** sister-tool idea below, which already envisions fingerprinting infra — could be shared.

---

## Crates

### Detect & gather "straggler" tracks — crate files that live outside the scanned library
**Status: FIRST VERSION SHIPPED 2026-08-28.** Dashboard banner → pre-flight
dialog (per-source-folder checkboxes) → move (copy + sha256 verify + delete
original) into `<library>/Media/` loose → `PathRewriter` re-points every crate
ref → rollback log in Organize's format (rollback works from the Organize
history). New: `core/straggler_detector.py`, `gui/straggler_dialog.py`; wiring in
`dashboard.py`. Resolver wrong-match fuzzy fallback removed in `crate_manager.py`
+ `crate_reader.py` at the same time. Full detail in `CLAUDE-CS.md` → "Locked
decision — August 28 2026 (Straggler gather)".

**Fast-follows still open:** per-file review UI (currently groups by source
folder only), cross-`/Volumes` straggler location (only `/` + volume-root of the
library are searched today), a Cancel button on the gather progress dialog.

Original design notes below (kept for rationale):

**The gap.** CrateSort scans exactly one folder tree (the library root the user
points at). Serato does not — it stores every crate track as a path relative to
the *volume* root and resolves it wherever it lives, so a working DJ's crates
routinely reference files in `~/Downloads`, `~/Music`, the Desktop, `~/Documents`,
etc. — files they dragged straight into Serato and never filed. Those references
are perfectly healthy in Serato and will always resolve there.

In CrateSort they don't. [`_CrateLoadWorker._resolve()`](../cratesort/src/gui/crate_manager.py)
matches each crate track against the **scanned inventory**; anything outside the
root fails the exact-path and `root / rel` checks, falls through to a **filename
match** and then a **fuzzy stem match** (`stem in cs or cs in stem`), and only
then renders as a greyed *"Not found in library"* row with an `X resolved,
Y unresolved` count in the crate status bar.

**Two problems, not one:**
1. **The visible one:** a free-tier user (Library / Rinse / metadata only, no
   Organize) opens the Crates tab and sees a pile of "Not found in library"
   rows even though Serato opens the same crates cleanly. Reads as "CrateSort
   lost my tracks." There is no path out today — Organize also skips files
   outside the root ([`_is_under_root`](../cratesort/src/core/file_organizer.py)),
   so neither tier can currently ingest an out-of-root straggler. The only
   workaround is manually dragging files into the library folder in Finder.
2. **The hidden one:** the filename + fuzzy-stem fallback in `_resolve()` can
   silently bind a straggler (`Intro.mp3` in Downloads) to a *different*
   same-named file inside the library. Playback, metadata edits, and Export
   then act on the wrong file, and a later Organize could rewrite that crate
   pointer to the wrong file permanently. **Fix this regardless of the feature
   below** — drop the fuzzy fallback, or mark low-confidence matches visibly
   distinct so "not found" stays honest.

**Agreed shape:**
- **Detect on scan.** After the initial library scan, read the crates and count
  track references whose resolved location falls outside the library root. If
  it's non-trivial, raise a **Dashboard banner**: *"N tracks in your crates
  live outside your library folder — CrateSort can only manage files kept
  inside it. [Show me] [Bring into library]."* Converts a silent gap into a
  guided step.
- **Free one-click "bring into library."** Move just the out-of-root,
  crate-referenced files into the library, then re-point those crate refs with
  the existing `PathRewriter` (in place, backup + rollback log). This is a
  narrow, safe Organize that only ever touches files the user already trusts
  (they're in crates). Arguably *should* be free — it's the on-ramp that makes
  the free features actually cover the user's whole library.
- **Destination: loose at the root of `Media/`** — NOT a named holding folder.
  Rationale confirmed against the code: Organize runs `_remove_empty_dirs(
  library_root)` after every execution and deletes any now-empty directory
  under the root (even one holding only `.DS_Store`). A `Media/_Imported/`
  bucket would therefore be auto-deleted the instant Organize sweeps its files
  out to `Media/<genre>/<artist>/` — i.e. the app would create a folder and
  silently destroy it one step later. `Media/` itself never hits that path
  (it always still contains `Media/<genre>/<artist>/…`), so it's created once
  and stays forever. A loose file in `Media/` is also semantically identical
  to "an unsorted library file" — Organize already gives loose files under the
  root a real `Media/<genre>/<artist>/` destination with no special-casing.
  The "these came from outside" identity lives in the Dashboard banner +
  activity feed + a one-time summary toast, never in a folder that pretends to
  be permanent and then disappears.
- **Move semantics:** copy → verify byte-identical → delete original, written
  to a rollback log, reversible after quit — same contract as Organize / Rinse.
  The confirm modal must name the source locations explicitly ("moves N files
  out of Downloads, Desktop, ~/Music…"). Consider an opt-out "copy instead of
  move" for the cautious, though that reintroduces the duplicate Rinse would
  later flag.
- **Collisions:** two stragglers named `foo.mp3`, or one clashing with an
  existing `Media/foo.mp3` → ` (2)` suffix (Organize's existing rule).
- **Cross-volume stragglers** (file on the internal disk, library on an
  external) = a genuine cross-volume copy, slower — surface it in the progress
  UI, otherwise no different.

**Free user who never runs Organize:** the gathered files simply live loose in
`Media/` as normal unsorted library content. Acceptable — same end state as any
file they'd drag in themselves.

**Relationship to other entries:**
- Overlaps heavily with **"Add Tracks by Drag / File-Picker"** above — same core
  constraint (a file outside the directory must be brought in), same
  pre-flight-modal discipline, same "loose at root, Organize files it" placement
  call. The straggler feature is the *automatic, crate-driven* version of that
  manual flow; they should share the ingest + confirm code.
- The **declined multi-location entry** below names this same gap from the other
  side. If detect-and-gather proves insufficient in testing (e.g. users who
  genuinely can't consolidate onto one drive), the lighter fallback is an
  **auto multi-root scan** — `LibraryScanner(*root_dirs)` is already variadic;
  derive extra *read-only* roots from the crates' own out-of-root references so
  Crates/Library display them correctly even if nothing moves. No new setup
  dialog; it's inferred from the crates, not chosen by the user.

**Test signal needed (Jace's large-library run, 2026-08-28 evening):** after the
scan, open Crates and note which crates show `unresolved` counts and roughly how
many. That's the empirical read on how common stragglers actually are.

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

### YouTube import — make it more robust (PO-token provider + related options)
As of 2026-08-31 YouTube gates its normal (`web`/`tv`) player responses behind a **PO token** (proof-of-origin) that yt-dlp cannot generate on its own: an unauthenticated request gets "Sign in to confirm you're not a bot", and a cookie-authenticated one gets "The page needs to be reloaded". `yt_import_dialog.py` falls back to the `android` client (no cookies), which still returns a stream — but often only a low-quality progressive one (e.g. 360p / ~96 kbps AAC for gated videos). The dialog now has a QUALITY combo (default Fast = single `android` pass) and a `web_embedded` age-gate pass; copy and `_download_with_fallback()` reflect all this.

Separately, on 2026-08-31 heavy testing got the dev IP **soft-blocked**: videos that had worked hours earlier returned zero playable formats on *every* client. That's a volume-based rate limit on the IP, not a code issue — clears in hours→~1 day, or use a fresh IP. This is the recurring pain the options below are meant to reduce.

**Option A — PO-token provider (`bgutil-ytdlp-pot-provider`). The real ceiling-raiser.**
This *is* a token system: the PO token is the credential that makes the `web`/`tv` clients work and return full adaptive formats (1080p, 160 kbps opus). Requests carrying a valid token + a logged-in session also look legitimate, so YouTube soft-blocks far less aggressively — it doesn't grant immunity from volume limits, but it's the single biggest improvement. Needs a JavaScript runtime: a bundled Node.js binary (`nodejs-wheel` / `nodejs-bin`, ~50 MB added to the `.app`) that the app spawns as a local provider, or its Docker image (not viable for a shipped desktop app). Cost: the dependency + a managed subprocess + maintenance when bgutil/YouTube shift. ~1 day plus packaging verification on a clean machine.

**Option B — pair A with the existing browser-cookie support (`YOUTUBE LOGIN` combo).**
Already built. Authenticated requests get materially higher rate limits than anonymous ones. Weak on its own (hits the PO wall), strong *combined* with Option A. No extra work beyond A.

**Option C — throttle CrateSort's own request pattern. Cheap hygiene.**
The metadata auto-fetch fires on every debounce pause while typing a URL; the `best` cascade fires up to 3 requests per import. Fetch metadata only on paste/blur/explicit action, add small inter-request delays, cap retries. No dependencies, small gain, reduces how fast the heuristic trips.

**Rejected — not worth it for a shipped desktop utility:**
- **Rotating / residential proxies** — would defeat IP rate-limiting directly, but it's a paid subscription (~$3–15/GB), ToS-grey, and CrateSort would either ship credentials (bad) or make every user configure their own.
- **A CrateSort-hosted relay** (users get API tokens against our server that runs yt-dlp with PO tokens + rotating IPs + caching) — this is how commercial YouTube-to-MP3 sites work, and it's a business, not a feature: ongoing hosting bill, *we* become the IP YouTube blocks and DMCAs, real legal exposure as the redistributing party, plus scaling. 
- **Official YouTube Data API** — generous free quota, needs an API key, but returns metadata only, never stream URLs. Could make the title/artist auto-fill bulletproof (no bot-gating on that step); can't download anything, so yt-dlp is still needed for media.

**Recommendation:** when YouTube import matters enough, do **A + B**, optionally **C** alongside. Skip proxies and a relay. Revisit sooner if yt-dlp ships native PO-token handling. Tested 2026-08-31: yt-dlp nightly (2026.08.30) does **not** fix the PO wall; 2026.8.19 is the latest stable.

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

*Last updated: August 31, 2026*
