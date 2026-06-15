# CrateSort — Library Sidebar Polish & Bug Fixes

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt addresses visual polish and bug fixes in `library_browser.py` following the Library/Classification merge. The Crates tab is the visual reference standard — the genre sidebar must feel like a sibling of the crates tree panel, not a foreign element. No architectural changes.

---

## Files in scope

- `src/gui/library_browser.py` — primary
- `src/gui/main_window.py` — timing signal connection

---

## Locked design standards (non-negotiable)

These values are app-wide standards. Do not deviate.

- Track row height: 36px
- Column header height: 45px
- Sidebar genre item row height: 36px (for "All") or 48px (for genres/unclassified)
- Orange left bar on selected item: 5px, `#D17D34`
- Selected item background: `#573d26`
- Selected item text: `#f1e3c8`
- Unselected item text: `#aaa`
- Muted subline text: `#666`
- Dark sidebar background: `#1e1e1e`
- Row separator: `#2a2a2a`
- Teal action: `#428175`
- Orange selection/CTA: `#D17D34`
- Red destructive/warning: `#C75B5B`
- Never swap teal and orange roles

---

## Fix 1 — Genre sidebar visual redesign

Replace the current system list bullet dots and layout with a custom-painted `QListWidget` using a custom `QStyledItemDelegate` (named `GenreSidebarDelegate`). This ensures visual parity with the Crates tree delegates and avoids layout stutters or selection styling bleed.

### Delegate Size & Layout Specs

- **Item Data Mapping**:
  - `Qt.ItemDataRole.UserRole`: genre filter key (`'All'`, `'Unclassified'`, or raw genre name)
  - `Qt.ItemDataRole.UserRole + 1`: display name string
  - `Qt.ItemDataRole.UserRole + 2`: artist count (int)
  - `Qt.ItemDataRole.UserRole + 3`: track count (int)
  - `Qt.ItemDataRole.UserRole + 4`: type string (`'all'`, `'genre'`, or `'unclassified'`)
- **Row Heights**:
  - `"All"` item (type `'all'`): **36px**
  - Genre items (type `'genre'`): **48px**
  - Unclassified item (type `'unclassified'`): **56px** (48px for the item + 8px top margin)
- **Text Spacing & Typography**:
  - **Left padding**: 14px (both name and subline align here)
  - **Right padding**: 10px
  - **Genre name**: 12px (11px for "All"), weight Bold, color `#aaa` (or `#f1e3c8` when selected/hovered)
  - **Subline**: "X artists · X tracks" (formatted with commas) — 10px, weight Normal, color `#666`
    - Stacking: For 48px rows, draw Name at `rect.top() + 8` and Subline at `rect.top() + 26`. For 36px row ("All"), draw Name at `rect.top() + 4` and Subline at `rect.top() + 18`.

### Item States & Backgrounds

- **Selected State**:
  - Background: `#2a1515` for unclassified, `#573d26` for other items
  - Left border bar: 5px solid bar. Color is `#C75B5B` for unclassified, `#D17D34` for other items
  - Text: `#f1e3c8`
  - Subline: `#a07850` (or red-tinted `#C75B5B` at 70% opacity for unclassified)
- **Hover State** (not selected):
  - Background: `#251a1a` for unclassified, `#252525` for other items
  - Text: `#f1e3c8`
  - Subline: `#666` (or red-tinted `#C75B5B` at 70% opacity for unclassified)
- **At-Rest State**:
  - Background: `#1f1a1a` for unclassified, transparent for other items
  - Text: `#aaa` (red `#C75B5B` for unclassified)
  - Subline: `#666` (red `#C75B5B` at 70% opacity for unclassified)

### Unclassified Separator
- Draw a `1px` horizontal separator line (`#2a2a2a`) at `rect.top() + 4` for the `unclassified` item.
- Shift all painting (background fill, left border bar, texts) for the `unclassified` item down by 8px using `rect = rect.adjusted(0, 8, 0, 0)`.

### Sidebar Header
- Label: "GENRES" — 9px, uppercase, `#555`, letter-spacing 1px
- Padding: 12px 14px 8px
- No divider line below header.

---

## Fix 2 — Sidebar resizable via QSplitter

Replace the fixed layout with a `QSplitter(Qt.Orientation.Horizontal)` between the sidebar and the track table.

- **Splitter configuration**:
  - Stylesheet: `QSplitter::handle { background-color: #2a2a2a; }`
  - Handle width: 4px
  - Stretch factors: sidebar = 0, track table = 1
- **Sidebar size constraints**:
  - Set `minimumWidth(160)` and `maximumWidth(320)` on the sidebar frame widget.
- **Persistence**:
  - Restore sidebar width on load: `width = self._settings.value('library/sidebar_width', 200, type=int)`, then call `self._sidebar_splitter.setSizes([width, 100000])`.
  - Save sidebar width dynamically by connecting `self._sidebar_splitter.splitterMoved` to a slot/lambda that updates the QSettings key `library/sidebar_width` with the first element of `self._sidebar_splitter.sizes()`.

---

## Fix 3 — Sidebar timing bug on first load

Ensure the sidebar populates correctly on first visit and updates dynamically when scanning completes.

- **Wiring Scan Completion**:
  - In `MainWindow._build_ui()` ([main_window.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/main_window.py)), connect the `scan_finished` signal from `DashboardWidget` to a new slot method:
    ```python
    self._dashboard.scan_finished.connect(self._on_scan_finished)
    ```
  - In `MainWindow._on_scan_finished(self)`:
    - Call `self._apply_nav_state(self._get_app_state())`
    - Retrieve `inv` and `lib` from `self._dashboard`
    - If valid, call `self._library_browser.on_scan_finished(inv, lib)`
  - In [library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py), implement `on_scan_finished(self, inventory, library_path: Path)`:
    ```python
    def on_scan_finished(self, inventory, library_path: Path) -> None:
        self._library_path = library_path
        self._inventory = list(inventory)
        self._load_edits()
        self._rebuild_tree()
        self._populate_genre_sidebar()
    ```
- **Connection Timing**:
  - Verify `currentItemChanged` is connected on `_genre_sidebar_list` during `__init__` before any paint event can occur, which ensures immediate click filter reaction.

---

## Fix 4 — Column default widths

Apply the following default column widths in [library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py) on first launch (guarded by check for no saved QSettings header state):

| Column | Default width |
|---|---|
| Artist | 220px |
| Tracks | 60px |
| Album | 180px |
| Genre | 120px |
| Style Tags | 140px |
| Duration | 80px |
| Format | 80px |
| BPM | 70px |
| Year | 70px |
| Bitrate | 80px |
| Comments | 160px |
| File Path | 200px |

---

## Fix 5 — Classify mode columns positioning

Ensure the Proposed Genre, Confidence, and Status columns are positioned adjacent to the Genre column correctly when entering Classify mode.

- **Sequence**:
  1. Show columns 12, 13, 14 (`self._tree.setColumnHidden(...)`).
  2. Defer visual reordering by wrapping it inside `QTimer.singleShot(0, ...)` to ensure the tree has registered the visibility changes:
     - `self._tree.header().moveSection(12, 4)`
     - `self._tree.header().moveSection(13, 5)`
     - `self._tree.header().moveSection(14, 6)`
  3. Set default widths for these columns: Proposed Genre (120px), Confidence (80px), Status (80px).
  4. On exit (Cancel or Accept), hide columns 12, 13, 14 and restore their original visual sections:
     - `self._tree.header().moveSection(12, 12)`
     - `self._tree.header().moveSection(13, 13)`
     - `self._tree.header().moveSection(14, 14)`
     - `self._tree.setColumnHidden(col, True)`

---

## Fix 6 — Restore missing toolbar filters

Verify that the [library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py) toolbar layout only contains the following interactive elements (left-to-right):
- `_search` QLineEdit (Search artist, title, album)
- `_format_cb` QComboBox (All Formats filter)
- Spacer/Stretch
- `clear` QPushButton (Clear Filters)
- `self._classify_btn` QPushButton (Teal Classify Library button)

Do not add back a genre dropdown combo box — the sidebar is the genre filter now.

---

## Verification checklist

Before marking complete:

1. Genre sidebar shows full genre names — no truncation, no dots, no bullets.
2. Each genre item shows "X artists · X tracks" subline in muted text.
3. Selected genre has orange left bar and warm brown background — matches Crates tab selection visually.
4. Hover state works cleanly on all genre items.
5. Unclassified bucket has a red tint at rest and selected, separated by a 1px divider, only visible when count > 0.
6. Sidebar is resizable via drag — min 160px, max 320px, persists width across restarts.
7. On first load, sidebar populates with all genres immediately — no round-trip required.
8. Clicking any genre item filters the track table immediately on first visit.
9. Column widths are readable on first launch.
10. Classify mode columns appear adjacent to Genre column, not at far right.
11. Cancel and Accept both correctly show/hide the three classify columns and restore header order.
12. Toolbar has search, All Formats, Clear Filters, and Classify Library.
13. Row heights: 48px for genre sidebar items, 36px for track rows, 45px for column headers.
14. No dots, bullets, or system list styling anywhere in the sidebar.
15. Teal = action, Orange = selection, Red = warning — no role swaps.
