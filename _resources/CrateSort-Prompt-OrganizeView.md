# CrateSort Prompt — File Organizer GUI View

## Context & Goal
Implement the **Organize tab** (tab index 3) in `src/gui/organize_view.py` and integrate it into `src/gui/main_window.py`. 

This view provides the user interface for the **File Organizer** workflow (Preview → Approve → Execute → Rollback) defined in `src/core/file_organizer.py`. It requires library classification data from `_CrateSort/classification_session.json` before enabling reorganization.

---

## 🎨 Visual Design Guidelines (CrateSort Theme)
Adhere strictly to the design system in `theme.py` and `CLAUDE-CS.md`:
- **Backgrounds:** Primary dark `#1a1a1a`, card/panel dark `#2F2F2F`.
- **Text:** Cream `#f1e3c8`, muted `#a89b85`.
- **Accents:** Selection Orange `#D17D34`, Action Teal `#428175`.
- **Row Heights:** 36px for all headers and table rows (`setDefaultSectionSize(36)`, etc.).
- **Grid Lines:** Full grid enabled, color `#383838`.
- **Table Colors:** Alternating row colors (`#242424` base, `#2a2a2a` alternate).

---

## ⚙️ Core Architecture & State Machine

`OrganizeView` must support four user states using a `QStackedWidget`:

### State 1: Gate Screen (Classifier Required)
* **Trigger:** Visited when `_CrateSort/classification_session.json` does not exist.
* **Layout:** Centered vertical layout with:
  1. A `QLabel` containing the message:
     > *"Before organizing your files, you'll need to classify your library so CrateSort knows where each track belongs. Go to the [Classifier tab] to review and confirm artist and genre assignments, then come back here to organize."*
     - The word **[Classifier tab]** must be hyperlinked. Wire the `linkActivated` signal to emit `navigate_to_classifier`.
  2. A smaller, muted note below:
     > *"Note: file organization is optional. The Crates tab is fully functional without it."*

### State 2: Plan Preview Screen
* **Trigger:** Classification session JSON exists.
* **Layout:** 
  1. **Stat Cards Strip (Top):** Horizontal cards showing:
     - **Files to Move** (value)
     - **Files Staying Put** (value)
     - **New Folders to Create** (value)
     - **Crates to Update** (value)
     - **Warnings/Conflicts** (value, highlighted orange/red if > 0).
  2. **Operations Table (Middle):** `QTableWidget` displaying all proposed moves with 4 columns:
     - `Filename` (Source filename)
     - `Action` (e.g. "Move & Rename" or "Move Only" or "Metadata Edit")
     - `Proposed Path` (Genre/Artist/Filename structure)
     - `Crates Affected` (Comma-separated list of affected crates)
     - Set column header heights to 36px, row heights to 36px, show full grid, enable alternating row colors.
  3. **Action Buttons (Bottom):**
     - Primary Teal Button (`#428175`): **"Execute Reorganization"**
     - Secondary Muted Button: **"Cancel/Reset"** (clears state, returning to Dashboard)

### State 3: Execution Progress
* **Trigger:** Clicked "Execute Reorganization".
* **Layout:** Centered vertical container with:
  - Teal progress bar.
  - Action label showing current step: *"Copying and verifying (12 of 450): track_name.mp3..."*
  - Muted Cancel button (disabled during database/crate writes).

### State 4: Completion & Rollback
* **Trigger:** Execution finishes.
* **Layout:** Centered vertical container:
  - Success icon/message: *"Reorganization complete! X files moved successfully."*
  - Primary Teal Button: **"Back to Dashboard"**
  - Danger/Secondary Button (`#C75B5B`): **"Rollback Reorganization"**
    - Clicking Rollback prompts confirmation. If confirmed, it executes `rollback()` in a worker thread and shows a rollback success page.

---

## 🧵 Threaded Workers (Anti-Freezing)

To keep the UI responsive, run calculations in background threads:

### 1. `_PlanWorker(QThread)`
Runs the pipeline to build the inputs and construct the plan.
* **Inputs:** `library_root` (Path), `serato_dir` (Path), `inventory` (list of `TrackRecord`), `session_path` (Path).
* **Process:**
  1. Load the `ClassificationSession` from the JSON.
  2. Convert the session's approved `ArtistEntry` states and final genres into a `classifications` dict: `dict[Path, ClassificationResult]`.
  3. Reconstruct `results` (list of `(TrackRecord, ClassificationResult)` tuples) for tracks in the inventory.
  4. Generate proposals:
     - `filename_proposals = FilenameCleaner().clean_all(inventory)`
     - `the_proposals = TheHandler().analyze_all({r.artist for r in inventory if r.artist})`
     - `meta_proposals = MetadataFixer().analyze_all(results)`
     - `consolidation = ArtistConsolidator().analyze(inventory)`
     - `crate_lib = CrateReader(serato_dir).read()`
  5. Run `FileOrganizer(library_root, serato_dir).build_plan(...)`.
* **Outputs:** Emits `finished(ReorganizationPlan)` or `errored(str)`.

### 2. `_ExecutionWorker(QThread)`
Executes the reorganization plan.
* **Process:** Calls `FileOrganizer.execute(plan, progress_callback)`.
* **Outputs:** Emits `progress(current, total, current_filename)`, `finished(ExecutionResult)`, or `errored(str)`.

### 3. `_RollbackWorker(QThread)`
Executes rollback on the database.
* **Process:** Calls `FileOrganizer.rollback(log_path)`.
* **Outputs:** Emits `finished(dict)`, `errored(str)`.

---

## 🛠 Integration Details

### `src/gui/organize_view.py` [NEW]
* Define `OrganizeView(QWidget)`:
  - Signals: `navigate_to_classifier`, `status_message(str, str)`.
  - Properties: `load(inventory, library_path, serato_path)`.
  - Check for session JSON exists in `library_path / '_CrateSort' / 'classification_session.json'`.
  - Handle all state layout transitions and wire worker threads.

### `src/gui/main_window.py` [MODIFY]
* Import `OrganizeView` from `cratesort.src.gui.organize_view`.
* Inside `_build_views()`:
  - Find the placeholder instantiation for index 3 (Organize) and replace it with `self._organize_view = OrganizeView()`.
  - Connect `self._organize_view.navigate_to_classifier` to `self._on_classify_requested`.
  - Connect `self._organize_view.status_message` to `self._update_status`.
* Inside `_on_nav()`:
  - Add condition: if `index == 3`, call `self._organize_view.load(inv, lib, serato_dir)` to load/preview the reorganization plan.
