# CrateSort — Dashboard Redesign

**Sonnet, high effort. Read every referenced file completely before writing any code.**

---

## Overview

Replace the existing dashboard (stack index 2 in `DashboardWidget`) with a redesigned layout. The new layout has four sections: stat cards, action cards, recent activity feed, and footer. Several existing methods are being deleted and replaced with new ones. Follow the spec exactly — card copy, order, colors, and grouping are all locked.

---

## Files to Read First

Read these files completely before writing any code:
- `cratesort/src/gui/dashboard.py` — full file
- `cratesort/src/gui/theme.py` — full file (verify color constants before using any hex values)

---

## What Gets Deleted

Remove these methods entirely from `DashboardWidget`:
- `_build_stats_strip()` — replaced by `_build_stat_cards_section()`
- `_stats_cell()` — no longer needed
- `_build_changes_section()` — replaced by `_build_activity_section()`
- `_build_recent_tracks_section()` — merged into `_build_activity_section()`
- `_build_health_section()` — removed entirely, not replaced
- `_build_header_section()` — replaced by `_build_action_cards_section()`
- `_build_action_buttons_section()` — replaced by `_build_action_cards_section()`

---

## What Gets Built

### `_populate_dashboard()` — rewrite

Replace the existing `_populate_dashboard()` body with:

```python
def _populate_dashboard(self) -> None:
    layout = self._dashboard_layout
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    summary    = self._summary
    inv        = self._inventory
    serato_dir = self._library_path / '_Serato_' if self._library_path else None

    layout.addWidget(self._build_stat_cards_section(summary, inv))
    layout.addWidget(self._build_action_cards_section())
    layout.addWidget(self._build_activity_section(serato_dir))
    layout.addWidget(self._build_footer_bar(serato_dir))
    layout.addStretch()
```

---

### `_build_stat_cards_section()` — new method

Four cards in a horizontal row. Each card is a `QFrame` with:
- Background: `#2F2F2F`
- Border: `0.5px solid #3a3a3a`
- Border radius: `10px`
- Padding: `16px 14px`
- Contents (top to bottom): icon label, large number, small label

Use a `QHBoxLayout` with `spacing=10` and no margins for the outer row. Each card uses `QSizePolicy.Expanding` horizontally.

**Card definitions (in order):**

| Icon (text) | Value source | Label |
|---|---|---|
| ♪ | `f'{summary.total_files:,}'` if summary else `'—'` | `Total Tracks` |
| ⊞ | crate count (count `.crate` files in `serato_dir/Subcrates` via `rglob`) | `Total Crates` |
| ♟ | `f'{len(summary.unique_artists):,}'` if summary else `'—'` | `Unique Artists` |
| ◷ | total hours: `sum(r.duration for r in inv if r.duration)` → divide by 3600 → format as `f'{hours:,.0f}h'`; `'—'` if no inventory | `Hours of Music` |

**Number styling:** `font-size: 26px; font-weight: 500; color: #f1e3c8`

**Label styling:** `font-size: 11px; color: #7a6a55; text-transform: uppercase; letter-spacing: 0.08em`

**Icon styling:** `font-size: 16px; color: #7a6a55`

Wrap the four cards in an outer `QWidget` with a `QVBoxLayout`. Add a `QLabel` eyebrow above the card row:
- Text: `YOUR LIBRARY`
- Style: `font-size: 10px; color: #5a5a5a; letter-spacing: 0.12em`
- Bottom margin: `8px`

---

### `_build_action_cards_section()` — new method

Two groups of clickable cards. No eyebrow labels. All cards use the same base component.

**Base card style (Go To group):**
- Background: `#2F2F2F`
- Border: `0.5px solid #3a3a3a`
- Border radius: `10px`
- Padding: `16px 14px`
- On hover: border color `#5a5a5a`
- Contents: icon (top), title below, description below title

**Create group card style:**
- Background: `#2a2218`
- Border: `0.5px solid #4a3520`
- On hover: border color `#D17D34`
- Icon color: `#D17D34`
- Everything else same as base

Use a `QGridLayout` with `spacing=10` for each group. Go To cards: 4 cards in one row (`columns=4`). Create cards: 2 cards in one row (`columns=2`). Both grids are full width.

**Go To cards (in order, left to right):**

| Title | Description | Action on click |
|---|---|---|
| Change Library | Set active library path | `self._on_select_library()` |
| Classify Library | Reassign artists and genres | `self.classify_requested.emit()` |
| Manage Crates | Build crates and edit tracks | emit a new signal `crates_requested` (add to class signals) |
| Organize Media | Manage folders and file locations | emit a new signal `organize_requested` (add to class signals) |

**Create cards (in order, left to right):**

| Title | Description | Action on click |
|---|---|---|
| New Crate | Start with a fresh crate | emit a new signal `new_crate_requested` |
| New Smart Crate | Create a rule-based crate | emit a new signal `new_smart_crate_requested` |

**Card title styling:** `font-size: 13px; font-weight: 500; color: #f1e3c8`

**Card description styling:** `font-size: 11px; color: #7a6a55`

**Icon styling (Go To):** `font-size: 20px; color: #7a6a55`

**Icon styling (Create):** `font-size: 20px; color: #D17D34`

Use simple Unicode or text characters for icons — do not import any icon library. Suggested characters:
- Change Library: `⟳`
- Classify Library: `⊛`
- Manage Crates: `⊟`
- Organize Media: `⊞`
- New Crate: `＋`
- New Smart Crate: `✦`

Make each card a `QFrame` subclass or use `mousePressEvent` to handle click. The entire card surface is clickable, not just a button inside it. Use `setCursor(Qt.CursorShape.PointingHandCursor)` on each card.

Wrap both grids in an outer `QWidget` with a `QVBoxLayout`, spacing `10px` between the two grids. No eyebrow labels on either group.

---

### `_build_activity_section()` — new method

Combined feed of crate changes and recently added tracks, merged and sorted by recency. One panel, one eyebrow label.

**Eyebrow label:** `RECENT ACTIVITY — LAST 30 DAYS`

**Panel style:**
- Background: `#2F2F2F`
- Border: `0.5px solid #3a3a3a`
- Border radius: `10px`
- Padding: `16px 18px`

**Data sources:**

*Crate changes* — same logic as the old `_build_changes_section()`:
```python
current_crates: dict[str, int] = {}
subcrates = serato_dir / 'Subcrates'
if subcrates.exists():
    for crate_file in subcrates.rglob('*.crate'):
        try:
            from cratesort.src.serato.crate_reader import CrateReader
            reader = CrateReader(serato_dir)
            tracks, _ = reader._read_tracks(crate_file)
            current_crates[str(crate_file)] = len(tracks)
        except Exception:
            current_crates[str(crate_file)] = None

checkpoint = load_checkpoint(serato_dir)
changes = detect_changes(current_crates, checkpoint) if checkpoint else []
save_checkpoint(serato_dir, current_crates)
```

Each change item: `{'type': str, 'description': str}`. Assign `datetime.now()` as the display time for changes (they happened this session).

*Recently added tracks* — same logic as the old `_build_recent_tracks_section()`:
```python
add_dates = read_track_add_dates(serato_dir)
cutoff = datetime.now() - timedelta(days=30)
recent = [(p, dt) for p, dt in add_dates.items() if dt >= cutoff]
recent.sort(key=lambda x: x[1], reverse=True)
recent = recent[:10]
```

**Merging:** Build a unified list of activity items. Each item is a dict with:
- `dot_color`: `#428175` (teal) for additions/renames, `#D17D34` (orange) for removals
- `text`: display string (crate change description or track filename)
- `time_str`: formatted date string (`'Today'` if today, otherwise `'Mon DD'` format)

Sort the merged list by recency, cap at 10 items total.

**Row rendering:** Each row has:
- A colored dot (`●`, 6px, `QLabel`, fixed width 14px)
- Description text (`font-size: 13px; color: #c9b89a`, stretch=1)
- Time string (`font-size: 11px; color: #5a5a5a`, right-aligned)
- Separator line between rows: `border-top: 0.5px solid #383838` (skip on first row)

**Empty state:** If no activity items, show: `No activity in the last 30 days.` in muted style.

Wrap panel and eyebrow in an outer `QWidget` with `QVBoxLayout`.

---

### `_build_footer_bar()` — keep as-is

Do not modify the footer. It is correct and stays unchanged.

---

## New Signals

Add these four signals to `DashboardWidget` alongside the existing signals:

```python
crates_requested       = pyqtSignal()
organize_requested     = pyqtSignal()
new_crate_requested    = pyqtSignal()
new_smart_crate_requested = pyqtSignal()
```

These signals are emitted by the action cards but do not need to be connected to anything in this prompt — connections will be wired in `main_window.py` in a future prompt.

---

## Layout Spacing

All sections separated by a visual divider. Between each section in `_populate_dashboard()`, add:
```python
layout.addWidget(self._make_divider())
```

Add this helper method:
```python
def _make_divider(self) -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet('background-color: #2a2a2a; border: none;')
    return line
```

---

## Constraints

- Do not modify `_build_dashboard()` (the scroll container builder) — only `_populate_dashboard()` changes
- Do not modify `_build_scanning()` (stack index 1)
- Do not modify `_build_welcome()` (stack index 0)
- Do not modify `_build_footer_bar()`
- Do not add inline stylesheet strings for colors that are already defined as class constants — use the existing `self._PANEL`, `self._SEP`, `self._TEAL`, `self._CREAM`, `self._MUTED`, `self._VMUTED`, `self._ORANGE` constants wherever applicable
- Verify all imports — `datetime`, `timedelta`, `read_track_add_dates`, `CrateReader` must all be available
- Do not remove any existing signals that are already wired in `main_window.py`
- Title Case for all visible card text (titles, labels, eyebrows)

---

## Verification Steps

After writing all changes, confirm:
1. `_populate_dashboard()` calls exactly four section builders plus footer plus stretch
2. All seven deleted methods are gone
3. Four new signals are defined on the class
4. All six action cards have `setCursor(Qt.CursorShape.PointingHandCursor)`
5. Activity feed handles the empty state gracefully
6. No references remain to deleted methods anywhere in the file
