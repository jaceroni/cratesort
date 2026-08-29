# CrateSort — Knowledge Base (working draft)

> **STATUS: in progress.** Section order and emphasis are provisional — they'll be
> re-shaped by Jace's annotated beta test (small library first) so the final
> structure matches how a real user moves through the app. This doc is the
> canonical plain-language "what each feature does, why, and every scenario"
> reference, and the source for eventual in-app help, a searchable KB, website
> copy, and support answers. It is **not** dev architecture — that's `CLAUDE-CS.md`.
>
> **Must be finished before the beta is handed to outside users** (so people can
> self-serve instead of DMing Jace).

Filled sections below are confirmed from testing + design dialogue. Stubbed
sections are placeholders to be written during / after the beta test pass.

---

## 1. The core model

- **Your library is a folder tree that CrateSort manages.** You point CrateSort at
  one folder; everything under it is "your library." CrateSort reads and writes
  files *inside* that folder — it can't process a file that lives outside it.
- **Crates are references, not copies.** A Serato crate is a list of *pointers* to
  files. Adding a track to a crate doesn't copy the audio; removing it doesn't
  delete the file. CrateSort edits the same `.crate` files Serato uses, so what
  you do in CrateSort is what Serato sees next time it opens.
- **Nothing is destructive without confirmation, and almost everything is
  reversible.** Deletions are confirmed; file moves and crate rewrites are logged
  and backed up (`_CrateSort_Backups/`, rollback logs under `_CrateSort/`).

## 2. The lifecycle

`Scan → Rinse → Classify → Organize`. Everything after **Scan** is optional and
independent — you can do one, all, or none, in any order, and come back later.

- **Scan** — CrateSort reads your library folder and builds its picture of what
  you have. Runs on launch and on demand; picks up anything new since last time.
- **Rinse** — finds and consolidates duplicate files. *(section 4)*
- **Classify** — writes genre/metadata tags. Never renames or moves files.
  *(section 5)*
- **Organize** — moves and renames files into a clean `Media/<genre>/<artist>/`
  structure, and updates every crate reference to follow. *(section 6)*

Many users will run the whole flow once for a deep clean and then only come back
for metadata edits or the conversion tools. That's a supported way to use it.

## 3. Scan

*(stub — to be written: what file types are picked up; incremental re-scan and
what "new since last scan" means; how special characters, files loose at the
library root, deeply nested subfolders, misnamed folders, and files with no
metadata at all are each handled; what "Unrecognized" means on the dashboard.)*

## 4. Rinse — duplicate detection & consolidation

### How duplicates are detected

- Two files are compared as possible duplicates only when their **artist + title**
  (after normalization — articles, punctuation, featured-artist and version
  suffixes stripped) match. Editing a title to add something like "(Bootleg)" no
  longer hides a pair (fixed 2026-08-27); a wholesale rewrite of the core title
  still would — only true audio fingerprinting would catch that, and it's not in
  the beta.
- Within a matched pair, **audio metrics** (duration, bitrate, file size) decide
  the *tier*: **true duplicate** (same recording, different location) vs
  **variant** (remix/edit/live — flagged for you to review, not auto-consolidated).

### What consolidation actually does

Consolidation **does not move or rename anything.** For each group you approve:

1. The **loser** file(s) are deleted from disk.
2. The **winner** stays exactly where it is — even if it's buried deep in a
   subfolder. It is never moved or renamed.
3. Every `.crate` file that referenced a loser is **rewritten in place** to point
   at the winner's real path. Written to disk immediately, with a backup and a
   rollback log.
4. The loser's **play count, comment, and cue points are merged into the winner**
   first, so you don't lose Serato performance data.

### Winner selection

Priority order: lossless format (FLAC/WAV/AIFF) → higher bitrate → larger file →
more complete metadata → **already used in more crates** → has stems → clean
filename. "Already in a crate" is only a tiebreaker — if the copy that was never
in a crate is a lossless file and the in-crate copy is an MP3, the lossless one
wins and your crate is *upgraded* to point at the better file.

### Common questions

**"Only one of my two duplicates was in a crate, and that's the one that got
deleted. Is my crate broken?"**
No. Before the loser is deleted, its crate reference is repointed to the winner.
The crate keeps the track — the pointer just follows the audio to the surviving
file. A crate can "adopt" a file that was never manually added to it; what gets
repointed is the *deleted* file's reference, wherever it lived.

**"Do I need to run Organize after Rinse?"**
No. Your crates are intact and playable the instant Rinse saves. Quit CrateSort,
open Serato, and every crate loads with every track resolving. Organize is a
separate, optional step.

**"If I *do* run Organize afterward, does it still work?"**
Yes. Organize moves files into `Media/<genre>/<artist>/` and rewrites every crate
reference to follow each move. It re-reads the current state of your crates and
library from disk, so it correctly picks up wherever Rinse left the winner —
including a buried folder. Order doesn't matter; both steps read from disk and
write back to disk.

**"What if both duplicates were in the same crate?"**
The crate ends up with a single reference to the winner, not two (fixed
2026-08-27).

**"What if neither was in any crate?"**
Nothing to rewrite — the loser is just deleted.

### Serato note

If the winning file is one Serato had genuinely never analyzed, Serato will
generate its waveform/beatgrid the first time it loads that crate — a few silent
seconds, not a break. Cue points survive because they're merged into the file
itself. Always close Serato before running consolidation.

## 5. Classify

*(stub — to be written: writes ID3/metadata tags only, filenames and locations
never change; the 13-genre taxonomy and why it's deliberately small — cross-ref
the in-app "Why Only These Genres?" explainer; style tags and how they feed
classification; what "Unclassified" means and how to resolve it; the tag-only vs
move-files distinction between Classify and Organize.)*

## 6. Organize

*(stub — to be written: moves + renames into `Media/<genre>/<artist>/`; every
crate reference is rewritten to follow each move; destination-collision handling
(` (2)` suffix); files that can't be placed are skipped and logged, not lost;
rollback via the reorganization log; the "controlled chaos" user who never wants
to run this — that's fine, everything works without it.)*

## 7. Crates

*(stub — to be written: the reference model again from the crate side; smart
crates (rule-based `.scrate`, manual "Check for New Files" refresh, no live-update
reshuffle surprise); editing crates and track order; "Save Crates & Launch
Serato"; the `.crate` files are the source of truth and Serato re-reads them on
every launch.)*

### "Not found in library" tracks — files your crates point to that live outside your library folder

CrateSort only knows about files **inside the folder you pointed it at**. Serato
is looser — it can play a track from anywhere on the drive, so a lot of DJs have
crate tracks sitting in Downloads, the Desktop, a loose `~/Music` folder, etc.
Those still play fine in Serato. In CrateSort's Crates tab they show up greyed
out as *"Not found in library,"* with a `resolved / unresolved` count on the
crate.

Nothing is broken — CrateSort just can't clean, tag, de-dupe, or organize a file
it can't see.

**Moving them in.** After a scan, if any crate tracks live outside your
library folder, the Dashboard shows a **"N Tracks In Your Crates Have Been Found
Outside of Your Library"** banner. Click **Move Them In** to open the "Move
Tracks Into Library" dialog, which shows every out-of-library file grouped
by which folder it's in (Downloads, Desktop, ~/Music…). Choose which folders to
move and confirm: each file is copied into your library's `Media/` folder,
verified, and the original is removed from its old location; every crate that
referenced it is re-pointed automatically. The files are now normal managed
tracks — Classify, Rinse, and Organize can all see them. If you run Organize
later, they get filed into `Media/<genre>/<artist>/` like everything else.

The move is logged and reversible from the Organize tab's history (Rollback puts
the files back and restores the crates). "Don't ask me to move these files
again" hides a straggler you deliberately want to leave where it is.

## 8. Metadata editing

*(stub — free tier; edits write straight to disk immediately (no separate save
step); inline editor: double-click or right-click a cell, Enter commits with a
teal flash, Escape cancels.)*

## 9. Conversion tools

*(stub — convert local files between formats; YouTube import (audio + artwork
picker), filenames are title-only with the artist going in the folder;
ffmpeg is bundled, no separate install.)*

## 10. Playback

*(stub — the built-in preview player in the bottom bar; click a track's note icon
to play, click again to pause, again to resume; the row shows which track is
loaded; this is a preview aid, not a performance player.)*

## 11. Tiers

*(stub — Free: metadata editing, conversion, YouTube import, scan, Classify.
Pro 1: crate management (create/edit crates, smart crates, add-to-crate).
Pro 2: [to confirm]. What's gated and the reasoning.)*

## 12. Safety & trust

- **Backups.** Every crate file CrateSort modifies is copied to
  `_CrateSort_Backups/` first. File moves and consolidations write rollback logs
  under `_CrateSort/`.
- **Nothing leaves your machine.** CrateSort works entirely on your local files.
- **Nothing is deleted silently.** Deletions are always confirmed; consolidation
  hashes each file before removing it.
- **Your library data is never touched by the uninstaller** — it removes only the
  app and its preferences, never anything inside your library folder.
- **Close Serato before running Rinse or Organize** so it isn't holding the
  `.crate` files open.
- **This is a beta, and it's unsigned.** Right-click → Open the first time to get
  past macOS Gatekeeper. Back up your library before the first big pass — not
  because CrateSort is unsafe, but because a lifelong collection deserves a
  belt-and-suspenders copy before any bulk operation.

## 13. Scenarios / FAQ

Running list of specific questions and confirmed answers (grow this from real
testing + support):

- **Consolidated a duplicate; only one copy was in a crate; that copy was
  deleted.** → Crate is fine, repointed to the winner. See section 4.
- **The winning file is buried in a weird folder. Will Organize find it later?**
  → Yes. Organize re-reads current state from disk. See section 4.
- **My crate shows tracks as "Not found in library" but they play fine in
  Serato.** → Those files live outside the folder you pointed CrateSort at.
  Serato plays from anywhere; CrateSort only manages what's inside your library
  folder. Use the Dashboard's "…Found Outside of Your Library" banner → **Move
  Them In** to move them into `Media/` and re-point the crates automatically.
  See section 7.
- *(add as they come up)*
