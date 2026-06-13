# CrateSuite Project Workspace Source (CrateSort & CrateView Reference)

Welcome to the **CrateSuite** workspace reference document. This single-source-of-truth file compiles all instructions, specifications, architecture blueprints, visual design rules, Serato database formats, and historical context for the CrateSuite project. It is designed to be fed directly into your Gemini web app / NotebookLM workspace to provide complete contextual memory of the codebase.

---

# PART 1: The CrateSuite Ecosystem

CrateSuite is a professional digital and vinyl music library management ecosystem consisting of two core projects:
1. **CrateSort**: A cross-platform desktop application (macOS-first) that organizes a DJ's digital music files (MP3s, AIFFs, WAVs, and music videos) and manages their Serato DJ Pro crate structure on disk.
2. **CrateView**: A custom WordPress child theme for vinyl record collection management and shelf mapping.

### Core Philosophy: The Single Writer / Reader Separation
* **CrateSort is the Single Writer; Serato is the Reader.** Performance software like Serato is built to read and mix music, not to organize files. CrateSort owns the file structures, directory nesting, file renaming, metadata tagging, and crate organization. When Serato launches, it simply reads the outputs prepared by CrateSort.
* **The Folder is the Home; The Crate is the Connection.** Every audio/video file lives in exactly one physical location on disk (structured by Genre and Artist). A Serato crate is a virtual connection—one physical file can be referenced in multiple crates.
* **Inform First, Act Second.** Every organizational change must first be presented as a safe preview before the user clicks to execute.
* **Non-Destructive by Default.** When files are organized, original folders are quarantined (not deleted), and a detailed JSON rollback log is generated so a user can completely undo the organization with one click.

---

# PART 2: CrateSort Core Architecture & Rules

### Tech Stack
* **Language**: Python 3.x (Homebrew on macOS)
* **GUI Framework**: PyQt6 (using custom styled widgets and QSS, bypassing OS native styles)
* **Metadata Parsing**: `mutagen` for ID3 tags
* **Crate Parsing**: `serato-crate` library for reading/writing Serato `.crate` files
* **Acoustic Fingerprinting**: `chromaprint` / `pyacoustid` (for duplicate detection)

### Non-Negotiable Core Rules
1. **Teal (#428175) = Action Color**: Drag target lines, operational status indicators, committed edit highlights, and active Undo/Redo buttons must always be Retro Teal.
2. **Orange (#D17D34) = Selection Color**: Hover highlights, selected tree nodes, and selected list rows must always be Satsuma Orange.
3. **Banned Taxonomy**: `"Pop"` is NEVER a valid parent genre. Standardize all styles into the 12-genre taxonomy.
4. **No Cascade**: Artist-level genre changes made by the user must never cascade to overwrite custom individual track-level genres.
5. **No Serato Comments Edits**: Never touch or write status logs to Serato database comments or tag files.

---

# PART 3: Visual Design Language & stylesheet Rules

CrateSort maintains an inverted dark visual identity with warm accents. The style definitions live in `theme.py`.

### Visual Palette
* **Dark Primary Background**: `#1a1a1a`
* **Dark Panel Background (Cards, Sidebar)**: `#2F2F2F`
* **Sub-Crate Background (Expanded list rows)**: `#222222`
* **Selected Crate/Item Background (Warm Brown)**: `#573d26`
* **Deepest Dark (Active parent crate)**: `#000000`
* **Satsuma Orange (Selection Accent)**: `#D17D34`
* **Retro Teal (Action Accent)**: `#428175`
* **Separators and Grid Lines**: `#383838`
* **Muted Labels / Text**: `#a89b85`
* **Vintage White / Text**: `#f1e3c8`

### Button Alignment & Sizing Standards
* All `QPushButton` instances are styled with standard border thicknesses and margins (`margin: 0px`, `border: 1px solid transparent` or `border: 1px solid #444444` for flat buttons).
* Flat buttons (`flat="true"`) must be styled with `font-weight: 400` to sit cleanly beside primary buttons.

### Track Table Standards
* All tables displaying tracks must have `setAlternatingRowColors(True)` enabled.
* Rows use a dark gray alternating background (`#242424` for base rows, `#2a2a2a` for alternating rows).
* Full vertical and horizontal grid lines must be visible (`setShowGrid(True)`) and styled in `#383838`.
* All table header heights and row heights are constrained to exactly `36px` (`setDefaultSectionSize(36)`).

---

# PART 4: Core Components & Layout Systems

### 1. Welcome & Launch Screen
* Built as a single context-aware viewport inside `DashboardWidget._build_welcome()` (index 0).
* **First Launch**: Shows logo lockup, tagline, and a single "Select Music Library..." button.
* **Returning User**: Shows the logo, saved path, a primary "Load Library" button, a "Choose Different Library" button, and an "Always load without asking" checkbox.

### 2. Command Dashboard
* The central hub (`src/gui/dashboard.py`) displays stats and activity feeds after loading.
* **Animated Stat Cards**: Extracted as `_AnimatedStatCard(QFrame)`. Value ease-out animation counts up from 0 when loaded. Click card to replay.
* **Workflow Cards**: Custom `_WorkflowCard` with active hover highlight borders.
* **Recent Activity Feed**: Computes diffs between Serato's database and CrateSort checkpoints over 30 days. Teal dot indicates additions, Orange dot indicates removals.

### 3. Crate Manager View
* Manages Serato's crate list (`src/gui/crate_manager.py`).
* **Custom Crate Item Delegate**: Crate trees use `CrateItemDelegate(QStyledItemDelegate)` for custom rendering. Native selection styling is bypassed to draw custom highlights, vertical selection bars, and right-aligned branch arrow icons.
* **Reload-After-Write Pattern**: After reordering tracks, adding items, or deleting rows, the view writes the binary `.crate` file to disk and refreshes the tree by reloading the files. It never modifies QTableWidget rows directly to avoid data corruption.
* **Crate Drag and Drop**: Manual drag implementation is used. Sibling reordering writes to `neworder.pref` (UTF-16 BE). Drop delays of 1.5 seconds auto-expand targets for nested reparenting.

### 4. Classifier View
* Built as `src/gui/classifier_view.py` for reviewing proposed metadata assignments.
* Loads library overrides from `_CrateSort/library_edits.json`.
* Done button styled in teal (`secondary="true"`).

### 5. Organize View
* Manages on-disk folder restructuring (`src/gui/organize_view.py`).
* **5 states**: Gate (0), Planning (1), Preview (2), Executing (3), Done (4).
* **Worker Threads**:
  - `_PlanWorker(QThread)`: Loads the library inventory, checks reassignments, and builds the plan.
  - `_ExecutionWorker(QThread)`: Performs the copy-verify-delete process.
  - `_RollbackWorker(QThread)`: Reverses the organization using a JSON execution log.
* **Table Height Constraint**: The operations table uses `setMinimumHeight(150)` to override default row-count-based minimum size hints, preventing the layout from pushing the footer buttons off-screen.
* **pastel Action Colors (No Icons)**:
  - `Move & Rename`: `#d98c52` (peach)
  - `Move & Tag`: `#9fa4c7` (lavender)
  - `Move Only`: `#e89ebb` (pastel pink)

---

# PART 5: Serato File Formats & Paths

CrateSort is built on custom parsing of Serato's proprietary database files:

### `.crate` Files
Binary playlist files containing absolute/relative paths of audio tracks. The path strings are wrapped inside `ptrk` blocks. No metadata tags or timestamps are stored here.

### `database V2`
A TLV (Type-Length-Value) binary database stored at `_Serato_/database V2`.
* Contains `otrk` (track record) structures, enclosing track paths (`pfil`) and the date added timestamp (`uadd`).
* **Folder Separator Replacement**: Serato replaces folder colons (`:`) with a private-use Unicode character `\uf022` (U+F022) inside its path records on macOS. CrateSort normalizes these strings on read.

### `neworder.pref`
A UTF-16 BE text file storing the canonical display order of crates in Serato's sidebar:
```text
[begin record]
[crate]Hip-Hop%%Golden Era
[crate]House%%Deep House
[end record]
```

---

# PART 6: Historical Debugging & Solved Bugs

### 1. Checkpoint Path Normalization
* **Symptom**: Dashboard reported thousands of false track additions/removals on startup.
* **Cause**: Path mount points, casing, and folder separators differed between the loaded memory scan and the stored `checkpoint.json`.
* **Fix**: Normalization helper standardizes paths before comparison, and failed scans are guarded with a `None` check.

### 2. Crate Tree Delegate Selection Resets
* **Symptom**: Large libraries suffered high latency when selecting parent crates.
* **Cause**: Tree updates called `update()` globally, repainting thousands of items.
* **Fix**: Paint logic tracks `_prev_selected_item` and only triggers updates on affected items, capping delegate updates at 4 per action.

### 3. QTreeWidgetItem Duplicate Removals
* **Symptom**: Reassigning artists crashed with `ValueError` in the tree child lists.
* **Cause**: Removing widgets by index or using direct value match failed when data models changed in memory.
* **Fix**: Reassigned tracks use path-based lookup and removal for safe in-memory list updates.

### 4. Table Sizing scroll Cutoff
* **Symptom**: The bottom footer buttons in the Organize Preview tab were pushed off the bottom window border.
* **Cause**: Standard `QTableWidget` has a large default minimum size hint based on the number of rows.
* **Fix**: Constrained the table to `setMinimumHeight(150)` so it shrinks dynamically to fit window viewports.
