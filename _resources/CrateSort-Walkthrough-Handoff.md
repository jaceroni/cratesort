# CrateSort Video Walkthrough — Session Handoff (2026-08-04/05)

**Purpose:** Continuation point for the CrateSort screen-by-screen walkthrough (source material for website content + in-app video onboarding). Fork this into a new chat alongside `CrateSort-Gemini-Transcript-Salvage.md` for full grounding. Written so a fresh conversation can pick up exactly where this one left off.

**Format of the walkthrough:** Jace narrates a screen/feature, Claude reflects back a clean summary, then they move to the next piece. Screenshots provided along the way as ground truth.

**Screens covered so far, in order:** Dashboard → Library. **Next up:** Crates.

**Corrections note (added 2026-08-05):** this version was audited against the live CrateSort codebase in Claude Code before being handed off. Four factual errors from the original walkthrough session were caught and fixed below — marked inline as `[CORRECTED]`. The most significant: the "Reclassify Library" button described as a locked decision doesn't exist in the shipped app — that exact feature was built, tested, and explicitly reverted in an earlier session (see `CLAUDE-CS.md` → "Classify Library button — hidden, not disabled"). Treat this file, not the original transcript, as ground truth going forward.

---

## DASHBOARD (fully covered)

- First launch: user selects one root folder containing both Serato folder and media files. Mismatched locations block Crate Management/export until consolidated.
- Deep scan runs once on first folder selection (mascot/comet animation, % complete). Every later launch does a fast diff/re-check, not a full rescan.
- Stat cards populate under "YOUR LIBRARY": Total Tracks, Total Crates, Unique Artists, Hours of Music.
- Three core workflow cards: Manage Library, Manage Crates, Organize Media — Manage Library is highlighted teal to encourage starting there; grayed out until scan finishes.
- Four always-active utility cards: YouTube to MP3, YouTube to MP4, Audio to MP3 (local conversion), Video to MP4 (local conversion) — metadata/artwork editing at conversion time. **[CORRECTED]** Output location differs by card type: YouTube imports default to the library root (user can browse to a different folder before downloading); local audio/video conversion always writes the converted file into the **same folder as the source file**, never the library root — there's no destination picker on that dialog. The original walkthrough said "all output land in the root directory," which is only true for YouTube imports.
- Recent Activity feed: combined view of crate changes, recently added tracks, and reorganization events (teal dot = reorg/addition, orange dot = rollback/removal), last 30 days, capped at 10 items.
- Sidebar always visible: logo, Dashboard/Library/Crates/Organize/Settings nav, Undo/Redo, artwork thumbnail area.

### Duplicate Detection / "Rinse Your Library" flow
- Orange strip appears when duplicates found: "N Potential Duplicate(s) Found — X MB could be reclaimed."
- Two categories: **True Duplicates** (identical file, multiple locations) and **Possible Variants** (same track name, different bitrate/size — flagged as possibly different recordings, not auto-merged).
- Suggested keeper highlighted teal with a stated reason (quality, tags present, etc.).
- "Keep All — Don't Ask Again" commits immediately on click — no need to hit Cancel or Consolidate Checked, and navigating away without further action still locks it in.
- If every group in a batch gets "Keep All," the Consolidate Checked button disappears since there's nothing left to merge.
- Post-consolidation: reroutes any Serato crate reference from a deleted duplicate to the surviving file, so crates never break. Metadata (Serato comments, BPM) from deleted duplicates merges into the winner's Comments field, separated by a hyphen.
- Settings → "Reset Duplicate Alerts" option (Maintenance section) clears all "Keep All" dismissals, forcing a fresh full duplicate review on next scan.

---

## LIBRARY SCREEN (fully covered)

- Two-panel layout: left = genre tree with counts (only genres actually present are shown; "Unclassified" always at bottom in red); right = artist-level table filtered by selected genre.
- Top banner: instructional copy about how to review/approve classifications. Buttons: Cancel / Accept Reclassifications.
- **Confidence column** (pre-classification, color-coded): **[CORRECTED]** five tiers, not four — MATCHED, HIGH (green), MEDIUM (orange/gold), LOW (red), NONE (red/fully unclassified). The original walkthrough dropped MEDIUM entirely and had the colors wrong (it said HIGH was teal and LOW was orange — neither is accurate; teal doesn't appear in this column at all).
- **Accept Reclassifications** commits all proposed changes at once — metadata only, no physical files move yet (that's Organize's job).
- **[CORRECTED]** After accepting: the same Confidence column relabels itself to **Status** rather than being swapped out for a different column, and it's persistent — visible any time classification data exists, not just right after Accept. Three states, not two: **✓ Approved** (green), **✎ Edited** (teal — a manual correction that differs from what the classifier originally proposed), **△ Unclassified** (red triangle, not a warning-triangle glyph). This lets you do an ongoing visual sweep of a genre bucket at any time, not just immediately after one classification pass.
- Artist reassignment: double-click expands an artist row to show tracks; right-click a track → context menu (Reassign Artist, Change Genre, Edit Style Tags, Show in Finder, Copy Artist/Title/Path).
- "Reassign Artist" modal: live-autocomplete, reassures that only artist grouping changes — comments, cue points, Serato data untouched.
- **Editable fields, three-tier model:**
  - Free-text inline (double-click): Title, Album, BPM, Year — row flashes teal ~4 seconds on save.
  - Genre: locked dropdown of 13 canonical genres via right-click → Change Genre modal. "Pop" is never valid. New genres require a special request to the CrateSort team.
  - Style Tags: free-text, comma-separated, via right-click → Edit Style Tags modal — the escape hatch for nuance the locked genre list can't capture. Never written to Serato frames.
- Comments field bidirectionally syncs with Serato's native comment field.
- Status column stays hidden until classification has actually run at least once (see below — it doesn't just stay "blank").

### **[CORRECTED]** What actually happens with the "Classify Library" button

The original walkthrough recorded a decision to rename this to "Reclassify Library," make it permanently active, and have it re-run a confidence sweep on click without disturbing approved entries. **That feature was built and tested in an earlier Claude Code session, then explicitly reverted the same day** — it does not exist in the shipped app, and shouldn't be described as a locked decision in outward-facing material.

What actually ships instead:
- The button is labeled **"Classify Library."** It's **hidden** (not renamed, not left active-but-muted) once there's nothing left unclassified — same convention the app uses for the duplicate-consolidation screen's "Consolidate" button once nothing's left to merge.
- The reasoning for not building an active reclassify button: the dashboard already re-runs classification automatically on **every single app launch**, so by the time you're looking at the Library tab, the session is already as fresh as a manual reclassify could make it. The one hypothetical extra value — catching a manual "Change Genre…" mis-edit — doesn't hold up either, since "Change Genre…" never writes to the audio file itself (only to the app's own edits log), so the classifier's own read of a track never changes just because someone overrode its genre. The persistent Status column above already surfaces that exact discrepancy live, with no button click required.
- Net effect for the walkthrough/tutorial: there is no user-facing "Reclassify" action to demonstrate. The story here is "classification just happens automatically, and the Status column always tells you where things stand" — not "click this button to refresh things."
- The one real reset mechanism that *does* exist and is worth demonstrating instead: **Settings → Maintenance → "Force Full Rescan"** — a genuine escape hatch that clears the scan cache and forces a fully fresh read of every file, for the rare case some third-party tool changed a tag without touching the file's size or modified time.

---

## PENDING / NEXT STEPS

- **Next screen to walk through: Crates** (browsing, creating/editing Serato crates, smart crates, Export Crate to Folder). Cross-check against the Gemini transcript salvage doc's Crates section (§2) since real detail already exists there — confirm it rather than re-deriving from scratch.
- Then **Organize** tab in similar depth — cross-check against salvage doc §3 (Plan Reorganization table, title-to-filename mechanic, duplicate/variant philosophy, version history/rollback).
- Then **Settings** — cross-check against salvage doc §4.
- Persona/marketing riffing (power user / metadata purist / newer Serato DJ / established gigging DJ) flagged for a deeper dedicated session later — don't let it get lost.
- No CLAUDE-CS.md or other project files were opened/edited during the original walkthrough session — purely conversational content-capture with screenshots for grounding. This corrected version is the first pass that cross-checked the transcript against the real codebase.
