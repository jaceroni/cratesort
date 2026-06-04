# CrateSort — Crate Manager Bug Fixes & Polish (Prompt 5)

> **Run this at Sonnet high effort. Read every referenced file completely before writing a single line of code. Do not skim. Do not make assumptions about column constants or row height values — verify everything before using it.**

You are working on CrateSort, a PyQt6 desktop app for organizing a DJ's digital music library and managing Serato DJ Pro crates.

## Core Philosophy

CrateSort is the single writer. Serato is the reader. Whatever CrateSort writes, Serato picks up on next launch. CrateSort owns the crate structure completely.

## Terminology

- **Crate tree** = the left panel in the Crates tab showing the crate hierarchy
- **Track panel** = the right panel in the Crates tab showing tracks within a selected crate

## Design Rule — Teal = Action

Teal (`#428175`) is the action color for all drag indicators and footer status text. Orange (`#D17D34`) is the selection color. Never mix these roles.

## Files to Read First

Read ALL of these completely before writing any code:

- `src/gui/crate_manager.py` — primary file, most changes live here
- `src/gui/main_window.py` — signal wiring, nav handling
- `src/gui/theme.py` — styling constants
- `src/serato/crate_reader.py` — crate data reading
- `src/serato/crate_writer.py` — crate data writing
- `src/gui/library_browser.py` — reference for visual patterns and row height

---

## Fix 1 — Crate Tree: Selection Colors and States

This is the most important fix in this prompt. The crate tree selection behavior and colors must match the spec below exactly. Reference the design mockup description carefully.

### The four states — memorize these:

**State A — Unselected crate (no interaction):**
- Background: dark (`#1a1a1a`)
- Text: cream (`#f1e3c8`)
- No left bar, no decoration

**State B — Selected crate, no sub-crates OR selected parent not yet expanded:**
- Background: full-width orange (`#D17D34`)
- Text: dark (`#1a1a1a`)
- No left bar needed — the full orange IS the indicator

**State C — Parent crate whose sub-crate is currently selected:**
- Background: black/charcoal (`#1a1a1a` or `#2F2F2F`)
- Left edge bar: solid orange (`#D17D34`), 4-5px wide, full row height
- Text: cream (`#f1e3c8`)
- This state only activates when a sub-crate within this parent is selected

**State D — Selected sub-crate:**
- Background: full-width burnt orange/warm brown (`#8B5E3C`)
- Text: cream (`#f1e3c8`)
- Left edge bar: solid bright orange (`#D17D34`), 4-5px wide, full row height

### State transition rules:

1. **Single click any crate** → State B (full orange). Load its tracks in the track panel.
2. **Double click a parent crate** → expand/collapse sub-crates. Parent stays State B (still orange — you're still in the parent). Sub-crates appear below.
3. **Single click a sub-crate** (after parent is expanded) → sub-crate goes State D. Parent transitions from State B to State C (orange → black with left bar). Track panel loads sub-crate tracks.
4. **Single click a completely different crate** (unrelated to current parent/sub-crate) → all previous highlighting clears. New crate goes State B. Previous parent loses State C entirely.

### Implementation notes:

- Do NOT use Qt's default selection highlight for this — override it completely via stylesheet
- The orange left bar (States C and D) must be implemented as a fixed-width left border or via `qlineargradient` — whichever produces a clean non-shifting result
- Text must NEVER shift position due to selection state changes
- Sub-crate indentation is fixed — selection state never affects indentation
- No connector lines, no vertical bars between rows, no extra decoration of any kind
- Keep it simple — the colors do all the work

---

## Fix 2 — Crate Tree: Expand/Collapse Behavior

The current implementation auto-expands on single click. This is wrong and must be changed.

### Correct behavior:

- **Single click** = select the crate, load its tracks. Never auto-expand or auto-collapse.
- **Double click** = toggle expand/collapse for crates that have sub-crates. Does not change which crate is selected or reload the track panel.
- A crate that has sub-crates must show a visible expand indicator (caret or arrow) in the left gutter. This indicator must NOT shift the text position. It lives entirely within the indent/gutter space.
- A crate with no sub-crates shows no expand indicator.

---

## Fix 3 — Row Heights: All the Same, No Exceptions

Every row in both panels — crate tree rows, track panel data rows, AND track panel column header row — must be the same explicit pixel height.

### Implementation — hardcode 34px everywhere:

**Crate tree:**
```
setUniformRowHeights(True)
stylesheet: QTreeWidget::item { height: 34px; min-height: 34px; max-height: 34px; }
```

**Track panel data rows (QTableWidget — does NOT have setUniformRowHeights):**
```
verticalHeader().setDefaultSectionSize(34)
verticalHeader().setMinimumSectionSize(34)
verticalHeader().setMaximumSectionSize(34)
```

**Track panel column header row:**
```
horizontalHeader().setFixedHeight(34)
```

**Both search fields:**
```
setFixedHeight(34)
```

Do not calculate row height dynamically anywhere. Every value is 34px, set explicitly. After this fix, all rows across both panels must be visually aligned when the app is running — scroll down any amount and they stay aligned.

---

## Fix 4 — Crate Reparenting via Drag: Fix Hover-to-Expand

Sibling reorder via drag is working. Reparenting (making a crate a sub-crate of another) is not — dragging onto a parent drops below it instead of inside it.

### Fix the hover-to-expand reparent:

- When the user drags a crate and hovers over a target crate (not between crates) for **1.5 seconds**, the target crate expands automatically
- During the hover delay, the target crate shows a subtle teal border to signal it will accept the drop
- On drop inside an expanded parent, the dragged crate becomes a sub-crate of that parent
- Write the new hierarchy to `.crate` files immediately on drop
- Teal footer text confirms: *"Moved '[Crate Name]' into [Parent Crate Name]"*

### The distinction between sibling drop and reparent drop:

- **Between rows** (teal horizontal line visible) = sibling reorder
- **On a row** (teal border on target crate, after 1.5s hover) = reparent as sub-crate

These must be mutually exclusive — the drop type is determined by cursor position relative to the target row.

---

## General Requirements

- **Always run at Sonnet high effort.** Read every file completely before making changes.
- Serato custom ID3 frames (cue points, beat grids, loops, color tags, markers) are never modified.
- Teal (`#428175`) = action color (drag indicators, footer text). Orange (`#D17D34`) = selection color. Never swap these roles.
- Tree expanded/collapsed state and crate selection must be preserved after every operation.
- After any operation that modifies crate contents, reload the track panel from the `.crate` file.
- Do not introduce any new visual elements not specified in this prompt — no connector lines, no extra borders, no shadows, no decorations beyond what is explicitly described here.
