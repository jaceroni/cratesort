# CrateSort — Library Screen Color Investigation (Confidence, Status, Proposed Genre)

## Context

This is an investigate-and-report prompt only. No code changes, no color swaps — just findings and recommendations. This is scoped narrowly to the Library screen's Confidence column, Status column, and Proposed Genre column. Do not perform a full app-wide color audit.

## Background

Two issues surfaced while reviewing a screenshot of a freshly-scanned library in the Library screen:

### Issue 1 — Unidentified color in "High" confidence and "Proposed Genre" text

In the Confidence column, the "HIGH" label and the Proposed Genre column's text both render in a color that reads visually as an in-between seafoam/sage tone — not a clean match for either the locked Retro Teal (#428175) or a true green. It's unclear whether this is:
- An alpha-blended or reduced-opacity version of the locked teal rendering lighter/greener against the dark background, or
- A separate, untracked color that was never formally added to the locked palette.

Please locate the actual color value(s) used for the "HIGH" confidence label and the Proposed Genre column text in the stylesheet/theme source, report the exact hex (or rgba) values, and identify whether they trace back to the locked teal or are something else entirely.

### Issue 2 — No visual precedent for "Medium" confidence

The locked Confidence tiers are: Matched, High, Medium, Low, None. In the reviewed library scan, no tracks landed in the Medium tier, so there's no existing visual reference for what color Medium currently uses (or is supposed to use). Please report what color Medium is currently coded to use, if defined at all.

### Issue 3 — "Edited" status color too close to "Approved"

Post-acceptance, the Status column has three states: Approved (intended green), Edited (intended teal), Unclassified (red triangle). In practice, the teal used for Edited reads too close to the green used for Approved — at a glance in a scrolled table it's hard to tell an Edited row from an Approved row.

## What to report back

Please report the exact hex (or rgba) value for every color currently in use across all of the following, not just the ones in question — we want the full picture in one pass rather than following up issue by issue:

- Confidence column: Matched, High, Medium, Low, None
- Status column: Approved, Edited, Unclassified
- Proposed Genre column text color

For each color reported:
1. The exact hex/rgba value and where in the codebase it's defined (file + line/selector if possible).
2. Whether it's a direct reference to an already-locked CrateSuite palette color (e.g. Retro Teal #428175, Satsuma Orange #D17D34), a derivative of one (opacity/tint adjustment), or a standalone value not currently part of the locked palette.

Additionally:
3. A short list of already-existing colors in the locked CrateSuite palette that could reasonably serve as a clearer, more distinct "Edited" status color without overlapping Approved-green or reusing Teal (action) or Orange (selection) roles — this is a suggestion list only, not a decision. Final color choice will be made by Jace after this report.

## What NOT to do

- Do not change any color values.
- Do not touch unrelated screens, components, or stylesheets outside the Library screen's Confidence/Status/Proposed Genre columns.
- Do not perform a full palette audit beyond what's needed to answer the items above.
