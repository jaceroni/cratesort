# CrateSort — GUI Phase 1: App Shell & Startup Sync

## Context

The full engine is built and working:
- Scanner, Classifier, Filename Cleaner, "The" Handler, Metadata Fixer, 
  Artist Consolidator, Duplicate Detector, Crate Reader, Crate Writer, 
  Path Rewriter, File Organizer

Stub files exist at:
- `src/gui/main_window.py` (has a basic QMainWindow shell)
- `src/gui/theme.py` (has color constants defined)
- `src/gui/dashboard.py` (empty stub)
- `src/gui/setup_wizard.py` (empty stub)

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

## What to build in THIS session

Just the app shell, custom theme, and startup sync screen. This is the 
container — the skeleton that every future GUI view plugs into. Keep it 
focused and tight.

## Scope — ONLY these three things:

### 1. Custom Theme (`src/gui/theme.py`)

Build out the full CrateSort theme as a PyQt6 stylesheet. The app should 
look like a professional DJ tool, not a system dialog.

**Color palette** — Dark background with warm CrateView brand tones. The 
CrateView brand palette is: Parchment Cream (#f2dbb3), Vintage White (#f1e3c8), 
Satsuma Orange (#d17d34), Retro Teal (#428175). We're inverting this for a 
dark app while keeping the same warmth and essence.

- Dark background: `#1a1a1a`
- Dark panels/cards: `#2F2F2F`
- Primary text (cream): `#f1e3c8`
- Secondary text (parchment): `#f2dbb3`
- Muted text: `#a89b85`
- Primary accent (orange): `#D17D34`
- Secondary accent (teal): `#428175`
- Input/field background: `#383838`
- Border/separator: `#444444`
- Success state: a soft green that matches the warm tone — `#6B9E78` 
  (not a harsh neon green)
- Warning/amber state: `#D4A04A` (warm gold, not harsh yellow)
- Error state: `#C75B5B` (muted red, not harsh)

All system colors (success, warning, error) should feel like they belong 
in the same room as the orange and teal — soft, warm, not jarring.

**Typography**: 
- Headlines/branding: Charter (font files are in `assets/fonts/`). Load 
  these via QFontDatabase at app startup.
- Body/UI text: Open Sans or system sans-serif fallback. 
- Sizes: 13px body, 18px headings, 11px small/muted text.

**Logo assets**: SVG logo files are in `assets/logo/` — a horizontal 
wordmark lockup and a mascot-only version. Use the wordmark in the 
welcome screen and the sidebar header. Use the mascot in the About 
dialog. Load via QSvgWidget or QPixmap from SVG.

**Apply to all standard widgets**: QPushButton, QLabel, QLineEdit, QComboBox, 
QTableWidget, QTreeWidget, QTabWidget, QProgressBar, QScrollBar, QMenuBar, 
QToolBar, QStatusBar, QSplitter, QCheckBox, QRadioButton, QGroupBox, 
QMessageBox, QDialog.

Orange accent on primary buttons, hover states, active tabs, selected items, 
and progress bars. Teal as a secondary accent — use for links, secondary 
buttons, or informational highlights. Dark panels for cards and grouped 
content. Cream text on dark backgrounds throughout.

### 2. Main Window (`src/gui/main_window.py`)

The app's main window with:

- **Title bar**: "CrateSort" with version number
- **Menu bar**: File (Settings, Quit), View (placeholder entries for future 
  views), Help (About)
- **Left sidebar navigation**: Vertical button list for switching views:
  - Dashboard (home icon)
  - Library (grid/list icon)
  - Crates (folder/tree icon)
  - Organize (wrench/tool icon)
  - Settings (gear icon)
  Navigation buttons highlight with the orange accent when active.
- **Main content area**: A QStackedWidget that swaps between views based on 
  sidebar selection. For now, only the Dashboard view is real — the others 
  show a placeholder label ("Library Browser — Coming Soon", etc.)
- **Status bar**: Shows current library path and sync state

The window should open at a reasonable default size (1200x800) and be 
resizable. Remember the last window position/size between sessions using 
QSettings.

### 3. Startup Sync / Dashboard (`src/gui/dashboard.py`)

This is the first thing the user sees after launch. It implements the 
startup sync sequence from the project plan:

**State 1 — No Library Configured**
If no library path is saved in settings, show a welcome screen with:
- CrateSort wordmark logo (load SVG from `assets/logo/`)
- "Get your shit together." tagline in Charter font
- "Select your music library" button that opens a directory picker
- Minimal and clean — just enough to get started

**State 2 — Amber / Scanning**
Once a library path is configured (or on subsequent launches):
- Show "Scanning library..." with an animated progress indicator
- Display file count as it progresses
- Run the scanner in a background thread (QThread) so the UI stays 
  responsive. This is critical — scanning tens of thousands of files 
  cannot block the UI.
- Status bar shows amber state

**State 3 — Scan Complete / Dashboard**
After scan completes, transition to the dashboard view:
- **Library stats card**: Total files, total artists, total genres found, 
  formats breakdown
- **Scan summary**: Quick overview of what was found
- **Classification preview**: Genre distribution (text-based for now — 
  a simple table showing genre name and track count)
- **Action buttons**: 
  - "Classify Library" (runs the classifier — future session)
  - "Manage Crates" (switches to crate view — future session)
  - "Organize Files" (switches to organize view — future session)
  These buttons exist but can show "Coming Soon" dialogs for now.
- Status bar shows green state with "Library synced. Ready."

**Background threading rules**:
- Scanner runs in QThread, emits progress signals
- UI updates via signals/slots — never access Qt widgets from worker thread
- Cancel button available during scan
- Error handling: if scan fails, show error in the UI, don't crash

## What NOT to build

- No library browser view (future session)
- No crate manager view (future session)
- No classification approval UI (future session)
- No reorganization preview UI (future session)
- No settings page beyond what's needed for the library path
- No setup wizard (the dashboard's "no library" state handles first launch)

## Testing

After building, the app should:
1. Launch and show the themed main window with sidebar
2. Show the "no library configured" welcome screen
3. Let you pick the test library directory
4. Run the scanner with progress updates (not frozen)
5. Show the dashboard with real stats from the test library
6. Sidebar navigation should switch between dashboard and placeholder views

Launch the app and verify it works. Show me a screenshot or describe what 
you see if screenshots aren't possible.

## Architecture notes

- Use PyQt6 (already in requirements.txt)
- Theme is a single stylesheet string applied to QApplication — not per-widget
- Background threads via QThread with signals for progress/completion/error
- QSettings for persisting library path and window geometry
- Keep views modular — each view is its own widget class in its own file, 
  added to the QStackedWidget in main_window.py
- Entry point is `main_window:main` (already configured in pyproject.toml)
