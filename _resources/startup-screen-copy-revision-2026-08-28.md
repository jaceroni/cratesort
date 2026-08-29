# Startup Screen Copy Revision — 2026-08-28

**Routing:** Brandy (voice/tone review) → Cody (implementation)

## Context

The startup/directory-picker screen's current copy leads with a technical
constraint ("if they're in different locations you'll need to move them...")
instead of the underlying best practice. This was the first point of friction
Jace felt testing the app as a new user. Goal: reframe the messaging around
*why* a single parent folder is standard DJ practice, while keeping the
primary path skimmable for repeat users. Full explanation moves into an
expandable "Why?" section.

## What stays unchanged

- The card layout and visual structure (no Dez involvement needed — this is
  copy-only, not layout/hierarchy work)
- The **"Select Your Serato & Media Folder" button** — keep as-is, same
  position, same label
- The BETA badge near the top
- The bottom disclaimer line's position (bottom of card, small text)

## What changes

### 1. Primary paragraph (under the existing headline)

**Current:**
> If they're in different locations you'll need to move them into the same
> folder to enable crate management and export features.

**Proposed:**
> Select the parent folder that contains both — usually the root of your
> drive.

Headline above it ("Point CrateSort to your `_Serato_` folder and media
files.") stays as-is.

### 2. New element: expandable "Why?" link/toggle

Add directly under the primary paragraph, above the button:

> *Why does it need to be one folder? ▾*

When expanded, shows:

> Your `_Serato_` folder should sit right next to your music — not scattered
> across drives or folders. That's standard DJ practice, and it's the
> foundation CrateSort is built on.
>
> - CrateSort syncs your files and Serato crates in real time, so it can
>   only watch one location.
> - This is also step one of getting organized: everything lives in one
>   master folder, Serato and music side by side.
> - Plug that drive into any laptop with Serato and it just works — no
>   missing files, no broken paths.

### 3. Bottom disclaimer line

**Current:**
> ⚠ Beta build — back up your library before scanning.

**Proposed:**
> ⚠ Beta build — back up your library before organizing.

("scanning" → "organizing")

## Rationale (for Brandy's review)

- **Tone target:** mentorship over rule. The old copy reads as a limitation
  being imposed ("the app cannot..."); the new copy reframes the same
  constraint as insider knowledge being handed to the user — consistent with
  CrateSort's "get your shit together" positioning.
- **Progressive disclosure:** primary path stays short for users who already
  know the drill; the full context (best practice → mechanism → payoff) is
  available on demand via "Why?" rather than forced on every visit.
- **Cut for length/fit:** the record-shop analogy (genres in a building
  across the street vs. same building) was considered but cut from this
  screen — it's a strong teaching analogy but better suited to onboarding
  docs/help center where the user has more slack than a directory-picker
  blocking their workflow.
- **Bullet order in the "Why?" expansion is intentional:** mechanism (can't
  watch two places) → bigger purpose (consolidation is the actual goal) →
  payoff (drive portability at gigs). Open to reordering if Brandy feels the
  payoff should lead.

## Open questions for Brandy

- Does "That's standard DJ practice, and it's the foundation CrateSort is
  built on" land, or does it feel like a stretch/overclaim?
- Any adjustment to keep voice consistent with existing CrateSort copy
  elsewhere in the app (e.g. "Get your shit together" tagline energy)?

## Notes for Cody (once copy is locked)

- Implement the "Why?" as a collapsible/expandable element (accordion-style)
  under the primary paragraph, collapsed by default
- No layout changes needed otherwise — button, badge, and disclaimer line
  positions are unchanged
