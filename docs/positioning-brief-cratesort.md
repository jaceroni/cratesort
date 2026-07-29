# CrateSort — Positioning & Feature/Benefit Brief

*Source material for promotional positioning, feature/benefit copy, and marketing conversations. This is not engineering documentation — for that, see `CLAUDE-CS.md`. For a plain tour of the app's screens, see `what-is-cratesort.md`. This doc exists to answer a different question: why does this app deserve to exist, and how should it talk about itself.*

---

## The one-line positioning

**CrateSort is the librarian that Serato, Traktor, and Rekordbox never bothered to build.** It's not a performance tool, not a streaming app, not a file browser — it's the thing that keeps a DJ's music library and Serato crates organized, clean, and safe, so the DJ never has to think about file management again.

**Tagline:** *Get your shit together.* (exact punctuation, lowercase, period at end — never softened or paraphrased in copy)

---

## The wound this app was built to heal

This is the origin story, and it should show up in marketing before any feature list does — it's the reason the features matter.

Every working DJ carries their music on an external hard drive and depends on laptop battery life. At some point, the drive disconnects unsafely or the battery dies mid-session. macOS throws up its "Disk Not Ejected Properly" warning. Most DJs click past it and move on with their night.

The real damage shows up the next time Serato opens:
- Crates get shuffled randomly through the crate tree.
- Nested subcrates reorganize or flatten entirely — expand `Hip-Hop → Best Of → Tupac` and find it scrambled.
- Track references get silently swapped. Two songs share a similar title — a sample flip, a remix, two artists with matching track names — and Serato's resolver crosses the wires. **You load up Method Man, hit play, and out comes a Dorothy Ashby harp instrumental. Mid-set. In front of a crowd.**

No warning. No dialog. The files on disk are completely untouched — it's the database's *memory* of where everything goes that broke, and nothing tells you it happened until you're the one finding out live.

Other failure modes that compound the trauma:
- Fat-finger a delete on a crate instead of a track. Gone. No undo. Recovery means a backup — if one exists, if it's recent, if that crate was even in it.
- Serato says a file can't be found. You can see it sitting right there in Finder. Relocate it by hand. Then it happens again. And again.
- Files tagged with rerelease years instead of original release years — a 1990s track shows up as 2018 because that's when the remaster dropped. Wrong genres from whoever tagged the file at the source. No style tags. No batch tools.
- Third-party fixes exist, but they charge too much for tools that still don't respect the DJ's time or intelligence.

**CrateSort exists to make that failure impossible to lose sleep over.** Not as a feature list — as a direct response to a specific, recurring, humiliating failure mode that every working DJ has either lived through or is one bad disconnect away from.

---

## The core idea (how it actually works, in one paragraph)

**CrateSort is the single writer. Serato is only the reader.** All the real organizational work — sorting by genre, cleaning up metadata, catching duplicates, building and arranging crates — happens inside CrateSort. Serato just opens afterward and reads the result. The second rule: **the folder is the home, the crate is the connection** — a song file lives in exactly one place on disk, and a Serato "crate" is just a pointer to it, never a copy. Dragging a track into five crates never creates five copies. Nothing on disk moves unless the DJ explicitly asks for it, in one specific place (Organize). Every action — including physical reorganization — can be undone, even after quitting and reopening the app.

## The "Carfax" model — the positioning hook

CrateSort isn't a one-time cleanup chore, it's a routine pre-flight check: **run your library through CrateSort before every gig, before you fire up Serato.** On launch, it checks the current state of files and crates against its own independent record and shows exactly what changed, what drifted, what needs attention — like a vehicle history report for your music library. This reframes CrateSort from a transactional utility (open once, fix, close, forget) to a habitual one (open before every gig, for peace of mind). That habitual-use angle is a strong marketing wedge — it's the difference between "a tool I used once" and "a tool I trust my night to."

---

## Who it's for

A **working DJ** — not a hobbyist. Someone who plays real gigs, manages a real library, and lives with the consequences of a messy hard drive. They've been burned by Serato scrambling their crates. They know exactly what it feels like to lose a carefully built playlist the night before a show.

They are not asking for a beautiful app. They're asking for a tool that works, that they can trust, and that doesn't make them feel stupid. If CrateSort also happens to be beautiful — and it is — that's what makes them recommend it to every other DJ they know. **Design for the DJ who has already been burned.** Every message, every feature, every piece of copy should read as if written for someone who has already lived the failure this app prevents.

---

## Features & benefits

Organized by tier, since the free/paid split is itself part of the trust story (see Monetization below). For each: what it does, and — more importantly — the specific pain it removes.

### Free tier — fixes the file

| Feature | The benefit (the pain it removes) |
|---|---|
| **Dashboard** — vitals at a glance (total tracks, crates, artists, hours of music), recent activity feed, drift/attention banners | The DJ opens the app and immediately knows what's changed and what needs attention, instead of discovering a problem mid-set |
| **Classify** — one-click, whole-library genre/artist/style proposal, reviewed and approved before anything is touched | Hours of manual re-tagging collapse into a single review-and-approve pass — and nothing moves until the DJ explicitly says yes |
| **Library metadata editing** — fix wrong years (rerelease vs. original), correct genres, add style tags, fix filenames, reassign misattributed tracks | Every field a DJ has ever had to fix by hand in Serato's clunky editor, fixed properly, with edits writing straight to the file on disk immediately — real value, not a demo |
| **YouTube Import** — paste a link, get a properly tagged MP3/MP4 with metadata pre-filled (autocomplete from the DJ's own library) and MusicBrainz-verified | Turns "I found this track on YouTube" into a clean, correctly tagged library addition without a separate manual tagging pass |
| **Local audio/video conversion** (WAV→MP3, MOV→MP4) with metadata/artwork carried over automatically | No more hunting for a separate converter tool and re-tagging the output by hand afterward |
| **In-app audio/video playback preview** — a persistent player bar, inline video preview, and pop-out video window | Preview and confirm a track before committing it to a crate or gig set — without ever having to leave CrateSort to check what a file actually sounds/looks like |

### Paid Tier 1 — Crate Management

| Feature | The benefit |
|---|---|
| **Full crate manager** — create, rename, delete, reorder, drag tracks between crates, full undo/redo | Try things without fear. Crates are references, not files — dragging a track between crates never touches the file on disk. This alone separates CrateSort from every DJ tool that came before it |
| **Smart crates** — real rule-based auto-population (e.g. all Rock from the 1980s tagged Progressive with "house party" in comments) | No other DJ tool offers this combination of power and low friction |
| **Export Crate to Folder** — right-click any crate, pick a destination, every track (wherever it actually lives) lands in one folder | Ready for a USB stick in seconds, no manual file-hunting across scattered folders. A DJ who discovers this feature does not go back |
| **Rinse (duplicate detection & cleanup)** — flags true duplicates with a pre-selected best copy (reason shown) and possible variants for human judgment, crates auto-rerouted to the surviving file | Cleans a library of redundant files without ever breaking a crate reference — Serato notices nothing except a cleaner library |

### Paid Tier 2 — Organize

| Feature | The benefit |
|---|---|
| **Organize** — full plan preview (what moves, what renames, what folders get created, how many crates update) before anything executes, live progress, end-of-run summary | The single most consequential action in the app, and it feels like it — weighty, deliberate, fully previewable before commit |
| **Rollback** — undo a full reorganization even after quitting and reopening the app | The safety net that makes "big move" actions feel safe to actually use |

### The trust features (cut across every tier, worth their own callout)

- **Undo/redo everywhere** — the DJ can try things without fear, full stop.
- **Non-destructive by default** — nothing is permanent without explicit approval. Duplicates go to review, not the trash. Reorganization is always reversible.
- **CrateSort never surprises you** — no action that changes a file happens without the DJ seeing what's about to happen first.

---

## Monetization framing (useful for feature/benefit copy)

**The line: Free tier fixes the file. Paid tier moves the file.**

The free tier is genuinely complete — not a crippled trial. It's the on-ramp: a DJ can load a library, classify it, and clean every piece of metadata without paying anything, and it should feel like a real tool, not a demo. The paid tier is additive power (crate management, physical reorganization, duplicate cleanup) — never the removal of basic dignity from the free experience. Any copy around a tier boundary should read as "here's more power," never "here's what we took away."

---

## Brand voice (for copy that needs to sound like CrateSort)

- **Direct over decorative.** Say what the app is doing in plain language.
- **Confident, not aggressive.** "25 tracks need classification," never "WARNING: 25 unclassified tracks detected."
- **Respect the user's expertise.** This is a tool for working professionals, not a beginner tutorial.
- **Never vague, never alarming, never condescending** in error/status copy.
- CrateSort's personality within the CrateSuite family: if CrateView (the vinyl-side sister product) is the record store you browse on a Saturday afternoon — warm, exploratory, unhurried — **CrateSort is the tool you pick up when the library is a mess and it needs fixing** — direct, purposeful, no-nonsense.

---

## Family context (for anyone asking "what's CrateSuite?")

CrateSort is the digital half of **CrateSuite** — a shared brand family alongside **CrateView** (vinyl collection management, [mycrateview.com](https://www.mycrateview.com)). Both share the same mascot (an anthropomorphic vinyl record with rubber-hose cartoon styling, sitting in an orange milk crate), color palette, logotype, and motion language. CrateSort's mascot gesture: head down, digging through records — focused, purposeful, working. CrateView's: rock-horns gesture, eyes up — discovery, browsing. If positioning copy ever needs to explain the family relationship, that visual/personality contrast is the shorthand.

---

*Last updated: July 29, 2026. Pulls from `CLAUDE-CS.md` (Draper/Brandy sections + locked monetization decisions) and `what-is-cratesort.md`, plus the July 2026 playback/converter feature additions not yet reflected in the plain-language doc.*
