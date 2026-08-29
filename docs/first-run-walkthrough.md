# CrateSort — First-Run Walkthrough (rough draft skeleton)

> **Purpose.** A screen-by-screen "showcase the experience" pass, written as a
> first-time user's traditional path through the app. For each screen: what you
> see, what you can do, the pivotal moments, and the feature → benefit → reason
> behind each one. Feeds the Knowledge Base structure and doubles as a manual
> test checklist. Rough — order and emphasis will move once Jace's annotated
> small-library test is in.
>
> Anticipated scenario: a working DJ on macOS, external drive with `_Serato_`
> and media at the drive root, opening CrateSort for the first time. Serato is
> closed.

---

## 0. Launch (macOS Gatekeeper)

**What happens:** Unsigned beta. First open needs right-click → Open to clear
Gatekeeper. App opens to the Dashboard.

- **Pivotal:** the very first thing on screen is the Dashboard in its
  first-run welcome state — not a wizard, not a settings page.
- **Reason:** one door in. No multi-step onboarding to abandon.

**Test tonight:** right-click → Open works; window opens centered at a sane
size; no console errors on a real external drive.

---

## 1. First-run welcome (Dashboard, state 0)

**What you see:** CrateSort logo (elastic grow-in), tagline "Get your shit
together.", BETA badge, and one card: heading *"Point CrateSort to your
_Serato_ folder and media,"* subtext *"They must be in the same location…
usually the root of your media drive,"* and a single button
**Select _Serato_ Folder & Media Location**.

**What you can do:**
- Click the button → native folder picker → pick the drive root.
- Click the **Settings** tab in the left nav (the only other tab that's live).
- Nothing else — Library, Crates, Organize are disabled.

**Pivotal points:**
- **Only two reachable places on first run: this button, and Settings.**
  Everything else is gated until a library is loaded. Reason: you can't do
  library work without a library; don't show doors that go nowhere.
- **Single-folder model.** One folder = your whole library; `_Serato_` and
  media must sit side by side under it. Reason: CrateSort reads/writes only
  inside that folder, and it needs `_Serato_` in the same tree to keep crates
  and files in sync. (Multi-location selection was considered and deliberately
  declined.)
- **Settings on first run** shows the same "Change Library" control plus the
  auto-load-on-startup checkbox and the "How to use CrateSort" steps — so a
  cautious user can read before pointing at anything.

**Feature / benefit / reason:**
| Feature | Benefit | Why it works this way |
|---|---|---|
| Folder picker as the only first action | Zero decisions to make | The app can't function without it; make it unmissable |
| `_Serato_` + media must be co-located | Crate references stay valid | CrateSort rewrites `.crate` paths relative to that root |
| Nav tabs disabled pre-library | No dead ends | App-state model: state 1 = no library |

**Test tonight:** pick the real drive root; confirm it detects `_Serato_`;
confirm picking a folder with **no** `_Serato_` still loads but leaves Crates
disabled (state 2); confirm a previously-used path that's now offline shows the
"previous library could not be found" card.

---

## 2. Scan + analysis (scanning state)

**What you see:** welcome logo shrinks away → "SCANNING YOUR LIBRARY" panel with
a pulsing mascot, a sweeping light beam (a "still working" cue, **not** a
progress bar), and five stat cards counting up: Files Analyzed, Files
Recognized, Files Unrecognized, Artists Recognized, Genres Recognized. Status
bar shows "Scanning library…" (amber dot). All nav except Dashboard is
disabled.

**Pivotal points:**
- **Scan and the classification-prep pass now read as one continuous stage** —
  no second "Analyzing Library" popup like older builds.
- **Incremental scan:** re-runs only re-read what changed since last time;
  first run reads everything. Settings → Force Full Rescan overrides.
- **"Unrecognized" = a file CrateSort couldn't read metadata from.** This
  number is the honest cost of a messy library and feeds what you'll fix in
  Library.
- **Nav stays locked during scan.** Nothing downstream is ready.

**Feature / benefit / reason:**
| Feature | Benefit | Why |
|---|---|---|
| % progress on the analyze modal, beam is decorative only | You know how long, and you're never lied to | No-fake-progress rule: a bar means "measured completion" |
| Pulsing mascot | "It's alive" without a spinner | House pattern for indeterminate waits |
| Live stat cards | The scan pays off visually as it runs | Turns a wait into a reveal |
| Min display floors (1.5s scan / 1s classify) | Cards animate instead of flashing | Small libraries would otherwise blink past |

**Test tonight (large library — this is the big one):**
- How long does the full first scan take? Does the beam/mascot keep animating
  the whole time (no freeze)?
- Do the five counts land on **real** numbers that match what you know of the
  library? Files Analyzed ≈ your file count; Unrecognized plausible.
- Does canceling mid-scan behave (returns cleanly, no half-state)?
- Quit and relaunch → does the incremental scan come back fast?

---

## 3. Dashboard (loaded — command center)

**What you see, top to bottom:**
1. **Stat cards:** Total Tracks, Total Crates, Unique Artists, Hours of Music —
   each animates up on load; click one (or the mascot) to replay all.
2. **Banners (only when relevant):**
   - **Serato Crate Changes Detected** — if Serato altered crates since your
     last session. Opens a per-change review: each row has an outcome-named
     radio pair ("Keep Crate" / "Delete Crate", "Leave Removed" / "Restore
     Crate", etc.), nothing written until **Apply & Continue**.
   - **N Potential Duplicates Found in Your Library** — "X MB of space could be
     reclaimed if you consolidate the duplicates • This will not affect your
     crates." Button → Rinse.
   - **N Tracks In Your Crates Have Been Found Outside of Your Library** — crate
     tracks whose real files live in Downloads / Desktop / ~/Music etc. (not
     under your library folder). "CrateSort can only manage files in the
     directory selected on startup • Bring them in to manage them." Button →
     **Move Them In**: opens the "Move Tracks Into Library" confirm dialog — a
     per-source-folder picker that moves the selected files into `Media/`
     (copy → verify → delete original) and re-points every crate reference.
     Logged + rollback-able from the Organize history. "Don't ask me to move
     these files again" hides a straggler you meant to leave put.
3. **Three action cards:**
   - **01 Manage Library** — "Start here… review and update metadata and
     filenames." Highlighted (teal) until you've accepted a classification.
   - **02 Manage Crates** — "Once your media is cleaned… browse, create, edit,
     export your Serato crates."
   - **03 Organize Media** — "Consolidate duplicates and reorganize… without
     affecting your Serato crates." Footer states the target structure:
     `Library Folder > Media > Genre > Artist > Files`.
4. **YouTube to MP3 / MP4** cards, **Audio to MP3 / Video to MP4** convert
   cards.
5. **Recent Activity — last 30 days:** tracks added in Serato, reorg runs,
   rollbacks, detected changes. "No activity" when empty.
6. **Footer bar:** "Last session: <timestamp>" / "First session"; sync status
   dot — "Library synced" (teal) or "Review Serato changes" (amber, clickable).

**Pivotal points:**
- **The Dashboard is the hub every flow returns to.** Finish Rinse → back here.
  Finish Organize → back here. Undo → jumps to the tab that owns the change.
- **The sync guard:** if a Serato-changes review is pending, trying to leave
  the Dashboard bounces you back with "review and sync first." Reason: don't
  let you build on top of a library state you haven't acknowledged.
- **The highlight on Manage Library is the app telling you where to start.**
- **Numbers are all live** — no placeholders anywhere on this screen.

**Feature / benefit / reason:**
| Feature | Benefit | Why |
|---|---|---|
| Carfax-style Serato change detection | You find out at the Dashboard, not mid-set | Independent local checkpoint of how crates should look |
| Outcome-named revert buttons | No "undo the removal or keep it?" ambiguity | A real accidental crate deletion happened with generic verbs |
| Duplicate banner before classify | Clean before you categorize | Fewer files to review, no dupes polluting genre counts |
| Action cards numbered 01/02/03 | Implies an order without forcing one | Lifecycle is Scan → Rinse → Classify → Organize, but all optional |

**Test tonight:**
- Stat cards match reality (cross-check Total Crates against Serato).
- If your test drive has had Serato activity: does the changes banner fire, and
  is each change described correctly?
- Duplicate banner count + reclaimable space believable for a big library;
  "skipped — no metadata" count present.
- **Straggler banner:** if your crates reference files outside the library
  folder, the "N Tracks Outside Your Library" banner appears. Open it → folders
  grouped correctly, sizes shown. Bring in a small folder's worth → files land
  loose in `Media/`, gone from the source, and the Crates tab shows those rows
  resolving afterward. Check `_CrateSort/reorganization_log_*.json` has
  `"kind": "straggler_gather"`, and that the Organize history shows the run with
  a working Rollback.
- Activity feed shows real recent adds.

---

## 4. Library tab — metadata + Classify

**What you see (before classifying):** empty-ish state — *"Your library hasn't
been classified yet. Hit Classify Library to assign genres, clean up filenames,
and get organized."* Genre sidebar on the left ("GENRES", with a **ⓘ Why Only
These Genres?** link), toolbar with search and a **Classify Library** button.

### 4a. Classify Library flow

1. Click **Classify Library** → **Analyzing Library…** modal: *"If your library
   is big, this'll take a while…"* Five stat cards (Files Analyzed / Recognized
   / Unrecognized / Artists / Genres), a real % progress bar, footer: *"This
   stage… helps determine where your files go during Organize."*
2. On completion the bar is replaced by **Review Results**.
3. **Classify (review) mode:** teal banner — *"Here's your library as we see
   it: sorted and grouped by artist. Double-click an artist row to reveal
   files. Right-click a file to approve or edit artist association… If unsure,
   mark it Unclassified."* Tree shows artist → tracks, with a proposed genre +
   confidence per artist.
4. Correct anything: right-click / double-click an artist to **Change Genre**,
   **Reassign Artist**, or **Edit Style Tags**.
5. **Accept Reclassifications** (or Cancel). Leaving with unsaved changes prompts
   *"Classifications Not Saved… won't be written to your files until you do."*

**Pivotal points:**
- **Classify writes tags only — never renames or moves a file.** That's
  Organize's job, later, deliberately.
- **Nothing is committed until you Accept.** A flag file records that you did.
- **"Unclassified" is a valid, safe answer** — you can revisit.
- **Confidence is shown** so you know which of CrateSort's guesses to scrutinize.
- **13-genre taxonomy on purpose** — the ⓘ link explains why (small, DJ-set-
  oriented, style tags carry the nuance).

### 4b. Everyday metadata editing (free tier)

- Double-click or right-click a cell → inline editor. **Enter commits with a
  teal flash, Escape cancels.** Writes straight to disk immediately — no save
  step, and the JSON staging copy updates too.
- Search bar filters artist / title / album; Clear Filters resets.
- Album art: the sidebar art panel takes image drops and has a right-click
  Replace / Remove / Save As menu.

**Feature / benefit / reason:**
| Feature | Benefit | Why |
|---|---|---|
| Tag-only classify, move-files later | Get the *data* right before touching disk | Reversible mistakes; Organize consumes this data |
| Grouped by artist, not file list | Classify 500 tracks in ~50 decisions | Genre is really an artist-level call most of the time |
| Confidence + reason on each guess | Spend review time where it matters | Don't rubber-stamp; don't re-check everything |
| Immediate disk writes for edits | What you see is what Serato gets | Free tier delivers real value, not a staged trial |
| "Why Only These Genres?" in-app | Heads off "where's Trap?" | The taxonomy is a deliberate design choice |

**Test tonight (large library):**
- Analyze modal % actually progresses; no freeze; "Review Results" appears.
- Artist grouping is sane; proposed genres reasonable; confidence varies.
- Unrecognized/Unclassified counts match the Dashboard/scan.
- Change Genre / Reassign Artist / Edit Tags each apply and show as Modified.
- Accept writes tags (spot-check a file in another tag editor); the Dashboard
  highlight on Manage Library clears afterward.
- Inline edit: Enter = teal flash + persists after relaunch; Escape = no change.
- Nav-away with unsaved classify changes → warning dialog fires.

---

## 5. Rinse — duplicate review (full-screen flow)

**Entry:** Dashboard duplicate banner → **Review Duplicates**.

**What you see:** *"Rinse Your Library — review potential duplicates before you
classify."* Two sections:
- **True duplicates** — same recording, different location. A "best copy" is
  pre-selected with the reason shown (lossless / higher bitrate / larger / more
  complete tags / already in more crates / has stems / clean filename).
- **Possible variants** — remix / edit / live / re-tag. Flagged for a human
  call, **not** pre-selected.

**What you can do per group:**
- Accept the pre-pick, or choose a different copy.
- **Keep All — Don't Ask Again** — keeps every copy and never re-flags this
  exact set (reset later in Settings → Reset Duplicate Alerts).
- **Consolidate Checked** runs it; **Cancel — Don't Consolidate** backs out.

**What consolidation actually does (per approved group):**
1. Loser file(s) deleted from disk (hashed first).
2. Winner stays exactly where it is — never moved or renamed, even if buried.
3. Every `.crate` referencing a loser is rewritten in place to point at the
   winner — written immediately, with a backup + rollback log.
4. Loser's play count / comment / cue points merged into the winner first.

Ends on a **"Rinsed."** celebration with counts, then back to the Dashboard and
a re-scan.

**Pivotal points:**
- **Detection is artist + title match (normalized), then audio metrics decide
  true-dup vs variant.** A wholesale retitle can still hide a pair — only real
  fingerprinting would catch that, and it's not in the beta.
- **Your crates are playable the instant Rinse saves** — no Organize required
  afterward. If you *do* run Organize later, it re-reads disk state and still
  works.
- **Nothing deleted without an explicit Consolidate click.**

**Feature / benefit / reason:**
| Feature | Benefit | Why |
|---|---|---|
| Variants split out from true dups | You don't accidentally delete a remix | Metrics can't tell intent; a human can |
| Crate re-point before delete | Serato never notices, no dead references | Folder is home, crate is a pointer |
| Cue/playcount merge into winner | No lost performance data | The whole point is a *cleaner* library, not a lossy one |
| "Keep All — Don't Ask Again" | The two-legit-copies case stops nagging | Some dupes are intentional (backup rig) |

**Test tonight:**
- Group counts + reclaimable space match the banner.
- "Skipped — no metadata" tracks are excluded, not mis-grouped.
- Winner reasons make sense; lossless beats in-crate MP3.
- Consolidate a small group, then open Serato: crate still resolves every track.
- Rollback log + backup written under `_CrateSort` / `_CrateSort_Backups`.

---

## 6. Crates tab (Pro) — Serato mirror with superpowers

**What you see:** two panes. Left = crate/subcrate tree matching Serato's
structure exactly, "All Tracks" at top, smart crates show a count. Right =
track table for the selected crate. Toolbar: crate search, track search,
**＋ New Crate**, **New Smart Crate**. Bottom: **Save Crates & Launch Serato**.

**What you can do:**
- Create / rename / delete crates and subcrates; drag to reorder; drag tracks
  onto a crate to add; **Add Tracks to Crate** dialog for search-based adds.
- **Smart Crates** — real rule-based `.scrate` files (genre / year is-before /
  is-after / etc.). Live preview count in the rule dialog. Right-click a smart
  crate → **Check for New Files** to refresh it on demand (no surprise live
  reshuffles).
- **Export Crate to Folder…** (right-click) — copies every track in the crate
  (wherever it lives) into one folder, ready for a USB stick. Progress dialog.
- **Save Crates & Launch Serato** — re-snapshots the crate state as the new
  checkpoint baseline, writes `.crate` files, opens Serato, closes CrateSort.
- Undo / Redo (sidebar buttons, Ctrl+Z / Ctrl+Shift+Z) covers every crate
  operation; undo jumps back to the originating tab.
- Now-playing marker follows the preview player across both track lists.

**Pivotal points:**
- **CrateSort is the single writer; Serato only reads.** You stop organizing
  inside Serato. `.crate` files are the source of truth, re-read every launch.
- **Reference model:** adding a track to five crates makes five pointers, not
  five copies. Deleting from a crate never deletes the file.
- **Everything is undoable** — no one-way doors.
- **Close Serato first** so it isn't holding `.crate` files open.

**Feature / benefit / reason:**
| Feature | Benefit | Why |
|---|---|---|
| Structure mirrors Serato 1:1 | No translation in your head | It *is* the same `.crate` files |
| Smart crates with manual refresh | Rules without the "why did my crate change?" | Predictability beats magic for a performance tool |
| Export Crate to Folder | USB prep in one click, no file hunting | Tracks are scattered across genre/artist folders |
| Save & Launch as one button | Hand-off is deliberate and logged | Sets the baseline for the next session's change diff |

**Test tonight:**
- Crate tree matches Serato exactly (names, nesting, order).
- Crate load time on a big library (background worker — does the UI stay
  responsive?).
- Create + populate a test crate, Save & Launch, confirm in Serato.
- Smart crate rule preview count is accurate; Check for New Files picks up adds.
- Export a mid-size crate — all tracks land, count matches, missing files are
  reported not silently dropped.
- Undo/redo across create / move / rename / delete.

---

## 7. Organize tab (Pro) — the only place files move

**What you see (gate screen):** explanation + **Plan Reorganization…**, plus
*"Have new tracks to add first?"* → **Open Library Folder** (drop files in
Finder, come back, re-plan — no Serato import needed). Below: **RECENT
REORGANIZATIONS** history, each past run with a **Rollback** button.

**Flow:**
1. **Plan Reorganization** → "Building reorganization plan…" (analyzing
   structure, filenames, crate assignments).
2. If unclassified tracks exist: **Unclassified Tracks Detected** — go back to
   Library, or **Proceed** (they'll be placed under an Unclassified path).
3. **Preview:** full plan before anything runs — files to move, renames, new
   folders, how many crates will be updated, plus a **Plan Warnings &
   Conflicts** detail dialog for anything risky.
4. **Execute Reorganization** → live progress (copy → verify → delete original),
   cancelable.
5. **Reorganization complete!** summary. **Rollback Reorganization** sits right
   there; history + rollback also persist on the gate screen after quitting.

**Pivotal points:**
- **This is the ONLY screen where files on disk change.** Never by surprise —
  plan first, approve, then run.
- **Target structure:** `Media/<genre>/<artist>/`. Every crate reference is
  rewritten to follow each move.
- **Copy-verify-delete**, not move — a failed file is skipped and logged, never
  lost. Destination collisions get a ` (2)` suffix.
- **Rollback works even after quitting and reopening** — the reorg log is on
  disk.
- **The "controlled chaos" user who never runs Organize is fine** — everything
  else works without it.

**Feature / benefit / reason:**
| Feature | Benefit | Why |
|---|---|---|
| Full plan preview | No blind bulk file operation | A lifelong collection; trust is the product |
| Crate refs auto-rewritten | Serato opens with zero broken tracks | Moves and pointers stay in lockstep |
| Copy-verify-delete | A crash can't destroy an original | Safety over speed |
| Persistent rollback | "Undo" survives a reboot | Bulk moves are scary; make them reversible forever |

**Test tonight:**
- Plan on the big library: does it build in reasonable time? Warnings dialog
  populated sensibly?
- Unclassified warning fires if you skipped some in Library.
- Preview counts (moves / renames / new folders / crates updated) look right.
- Execute a **small** subset if possible; verify files landed at
  `Media/genre/artist/`, crates still resolve in Serato.
- Rollback restores originals and re-points crates; quit/relaunch and confirm
  the history + rollback button are still there.

---

## 8. Settings tab

**Sections:**
- **Your Library** — current path, **Change Library**, **Auto-load last library
  on startup** checkbox.
- **Maintenance** — **Repair Crate Paths** (replay reorg logs → fix stale
  `.crate` paths after a move), **Reset Track Table Columns**, **Reset
  Duplicate Alerts** (un-dismiss "Keep All" groups), **Force Full Rescan**
  (drop the incremental cache).
- **About** — version, tagline, and a 5-step **How to use CrateSort**
  walkthrough.

**Pivotal points:**
- **Reachable from the very first launch** — the one tab besides the welcome
  button.
- **Change Library turns off auto-load** so the next start asks again.
- Destructive-ish resets confirm first ("Continue").

**Test tonight:**
- Change Library to a second folder and back; scan re-runs; nav state updates.
- Toggle auto-load; relaunch; confirm behavior.
- Force Full Rescan → next scan is a full re-read.
- ⚠️ **Known stale copy:** the "How to use CrateSort" steps still say
  "Classification tab" and "Go to Settings and choose the root folder" — the
  real first-run path is the welcome-screen button and a **Library** tab.
  Flag for the KB rewrite / fix the in-app copy.

---

## 9. Playback bar (global chrome — every screen)

**What it is:** a preview player pinned to the bottom, surviving tab switches.

- Click a track's note icon to play; click again to pause; again to resume
  (real play/pause toggle, not restart). The loaded row is marked in both the
  Library and Crates track lists.
- Skip previous / next walks the current list.
- Video files: a monitor appears in the sidebar; click it to pop out a floating
  window. Album art for the loaded track shows in the sidebar panel.

**Reason:** it's a *preview aid* for identifying tracks while you organize — not
a performance player. That's Serato's job.

**Test tonight:** play audio + a video file; toggle pause/resume; skip; pop the
video out and back; confirm now-playing marker tracks correctly across tabs.

---

## 10. Cross-cutting things to keep verifying

- **Nav gating by app-state:** state 1 (no library) locks Library/Crates/
  Organize; state 2 (no `_Serato_`) locks only Crates; state 3 unlocks all;
  any active scan locks everything but Dashboard.
- **Sync-required guard:** pending Serato-change review blocks leaving the
  Dashboard.
- **Undo/redo** routes back to the owning tab and shows a teal status line.
- **Safety net:** `_CrateSort_Backups/` for every modified `.crate`,
  `_CrateSort/` rollback logs for moves + consolidations. Nothing leaves the
  machine. Deletions always confirmed and hashed.
- **Beta reality:** unsigned (right-click → Open), back up the drive before the
  first big pass.

---

## 11. Suggested KB section order (derived from this walkthrough)

1. The core model (folder = library, crate = pointer, single-writer)
2. First run: pointing at your library (`_Serato_` + media co-located)
3. Scan & analysis (incremental, "Unrecognized", nav lock)
4. The Dashboard as hub (stat cards, banners, action cards, activity, sync)
5. Library & Classify (tag-only, artist grouping, confidence, Unclassified,
   the 13 genres, inline metadata editing)
6. Rinse (detection basis, true-dup vs variant, winner logic, crate re-point,
   Keep-All)
7. Crates (Serato mirror, reference model, smart crates + Check for New Files,
   Export to Folder, Save & Launch)
8. Organize (plan-first, `Media/genre/artist`, copy-verify-delete, rollback
   forever, the never-organize user)
9. Playback (preview aid, not performance)
10. Settings & maintenance (repair paths, resets, force rescan, auto-load)
11. Tiers (Free: scan, classify, metadata, convert, YouTube. Pro: crates,
    smart crates, Rinse, Organize, Export, CrateView bridge)
12. Safety & trust (backups, rollback logs, local-only, confirmations, beta
    notes)
13. Scenarios / FAQ (grow from the test pass)
