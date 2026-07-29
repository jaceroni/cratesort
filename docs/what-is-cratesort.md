# What is CrateSort?

CrateSort is a desktop app for DJs that keeps a music library and its Serato crates organized, clean, and safe — so the DJ never has to think about file management again.

**Tagline:** *Get your shit together.*

---

## The problem it solves

Every working DJ carries their music on an external hard drive and depends on laptop battery life. At some point, a drive disconnects unsafely or a battery dies mid-session. macOS throws up a warning. Most DJs click past it and move on with their night.

The real damage shows up the next time Serato opens. Crates get shuffled. Subcrates scramble or flatten entirely. Worse, track references get silently swapped — if two songs share a similar title (a common sample flip, a remix, two artists with the same track name), Serato's database can cross the wires and load the wrong track into the wrong crate. The files on the hard drive are completely fine. The *database's memory* of where everything goes is what broke, and nothing tells you it happened. A DJ finds out mid-set, when the wrong record drops.

There's no built-in undo for this. Recovery means digging through backups, if they exist at all.

**CrateSort exists to make that failure impossible to lose sleep over.** It keeps its own independent, local record of exactly how a library and its crates are supposed to look, so that if Serato's database ever gets scrambled, everything can be restored with a click.

## The core idea

CrateSort follows one rule above all others: **CrateSort is the single writer. Serato is only the reader.**

All the real organizational work — sorting by genre, cleaning up messy metadata, catching duplicate files, building and arranging crates — happens inside CrateSort. Serato just opens afterward and reads the result. The DJ stops organizing *inside* Serato altogether.

The second rule that makes this safe: **the folder is the home, the crate is the connection.** A song file lives in exactly one place on the hard drive. A "crate" in Serato isn't a copy of that file — it's just a pointer to it. That means dragging a track into five different crates never creates five copies of the file; it just creates five references to the same file. Nothing on disk moves unless the DJ explicitly asks for it, in one specific place (see "Organize," below).

Every action can be undone. Every reorganization can be rolled back, even after closing and reopening the app.

---

## The screens

CrateSort has five main screens, plus two special flows that take over the screen when needed. Here's the tour.

### 1. Dashboard — command center

The first thing a DJ sees when they open the app. On first launch, it's a clean welcome screen: pick your music folder, and CrateSort scans it. From then on, it remembers the library and jumps straight to it (with an option to pick a different one).

Once loaded, the Dashboard shows the vitals at a glance — total tracks, total crates, unique artists, hours of music, each number animating up on load — and three big action cards: **Manage Library**, **Manage Crates**, and **Organize Media**, which lead to the other three screens. A recent activity feed shows what changed in the last 30 days. If something needs attention — new unclassified tracks, potential duplicate files, or changes Serato itself made outside of CrateSort — a banner surfaces it right here, front and center, instead of letting it hide.

This is also where two YouTube import shortcuts live, letting a DJ pull a track straight off YouTube into their library as a properly tagged MP3 or MP4 (see below).

### 2. Library — the source of truth for metadata

This is where every track's information lives: title, artist, album, year, genre, style tags, BPM, comments. Tracks are organized by genre, then by artist, in a searchable tree.

The standout feature here is **Classify**: run it once, and CrateSort analyzes the whole library and proposes a full genre/artist organization automatically — showing exactly what it found and what it's suggesting, before anything is touched. A DJ reviews the proposal, corrects anything CrateSort got wrong with a right-click or double-click, and only then accepts it. Nothing is renamed or moved on disk during this step — it's purely about getting the *data* right first. That happens later, deliberately, in Organize.

### 3. Crates — a mirror of Serato, with superpowers

A two-pane view of every crate and subcrate, matching Serato's own structure exactly. Crates and tracks can be dragged and reordered, tracks dragged straight onto a crate to add them, and everything — creating a crate, deleting one, moving a track, renaming — goes through full undo/redo. Nothing here is a one-way door.

One particularly useful feature: **Export Crate to Folder**. Right-click any crate, pick a destination, and every track in it (wherever it actually lives on the drive) gets copied into one folder — ready to drop onto a USB stick for a gig, without hunting down files by hand.

### 4. Organize — where files actually move

This is the *only* screen where files on disk change. And it never happens by surprise: CrateSort builds a full plan first — what will move, what will get renamed, what new folders will be created, how many crates will be updated — and shows it as a complete preview before anything executes. A DJ approves the plan, watches it run with live progress, and gets a summary at the end.

If anything about a reorganization needs to be undone — even after quitting and reopening the app — there's a **Rollback** button sitting right next to the history of past runs.

### 5. Settings — the boring stuff, kept simple

Where the library path lives, whether to auto-load it on startup, a couple of maintenance tools (like repairing crate file paths after a move), and a quick "how to use CrateSort" walkthrough for anyone who wants a refresher.

### Special flow: Rinse (duplicate cleanup)

When CrateSort finds duplicate files — the same song downloaded twice, an alternate rip, a remix that might just be a re-tag of the original — it flags them on the Dashboard and offers **Rinse**. This is a dedicated full-screen review: true duplicates get a pre-selected "best copy" (with the reason shown — better quality, more complete tags, lossless format), while merely *similar* tracks are flagged as "possible variants" for a human judgment call. Nothing gets deleted without an explicit confirm, and crates automatically get rerouted to point at whichever copy survives — so Serato never notices a thing changed except a cleaner library.

### Special flow: YouTube Import

Paste a YouTube link, and CrateSort fetches the title, uploader, and year, pre-fills the metadata fields (with autocomplete pulled from the DJ's own existing artist/genre history), and downloads it as a properly tagged MP3 or MP4. It even checks MusicBrainz afterward for a more accurate match and offers to apply the correction. The end result lands in the library already clean — no separate metadata-fixing pass required.

---

## Who it's for, and the business shape

CrateSort is free to use for the core library work — the Dashboard, Classification, and Library metadata editing are all genuinely useful on their own, not a crippled trial. The paid tier unlocks the heavier lifting: crate creation and management, physical reorganization (Organize), Export Crate to Folder, duplicate detection (Rinse), smart crates, and the bridge to CrateView (its sister product for vinyl collectors).

CrateSort is the digital half of a larger family called **CrateSuite** — CrateView handles the vinyl side, CrateSort handles the digital side, and both share the same visual identity, mascot, and voice.

---

*This document is a plain-language overview for anyone who needs to understand what CrateSort does without reading the code. For technical architecture, brand standards, and locked engineering decisions, see `CLAUDE-CS.md`.*
