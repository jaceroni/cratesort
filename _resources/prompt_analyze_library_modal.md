# FEATURE — Analyze Library Modal

## Role
You are Cody, Code Steward for the CrateSort project. This is a surgical implementation of a new visual modal takeover called `_AnalyzeLibraryModal` in `src/gui/library_browser.py` during first-run auto-classification. Read every line of the referenced file completely before writing any code. Follow all CLAUDE-CS.md standards — color roles, layout heights, and UI guidelines.

---

## Files in Scope
- `cratesort/src/gui/library_browser.py` [MODIFY]

---

## Locked Decisions & Styling Rules
1. **Progress Bar**: Determinate (`done / total * 100`) from the first progress update. Color must be Retro Teal (`#428175`) with a height of 4px and a background of `#383838`.
2. **Live Stats**: Pre-compile the `artist_name -> track_count` map from `self._inventory` before the worker starts. Count up artists and tracks processed live. The "Corrections Made" card must sit at 0 with a `# TODO` comment (real-time comparison signal is not yet available).
3. **Layout Motion**: The progress bar/container hides, and the "Review Results" button fades/appears at the same position. The modal's height and width must stay stable (no jumping layout).
4. **Resize Handling**: Register an event filter on the main window (`self.window()`) to ensure that the overlay and the modal dynamically reposition and resize to stay centered with zero gaps.
5. **Color Roles & Aesthetics**:
   - Primary Accent (Teal): `#428175`, Hover: `#38706a`
   - Primary Text (Cream): `#f1e3c8`
   - Muted/Secondary Text: `#a89b85`
   - Panel/Card Surface: `#2F2F2F`
   - Overlay Background: 85% opaque dark fill `rgba(26,26,26,217)` (with comment `# TODO: replace overlay with blur effect when PyQt6 blur support is confirmed`).
   - Cards inside the modal: `#1a1a1a` background, `1px solid #444444` border, 8px rounded corners, 12px padding.

---

## Technical Specifications

### 1. Custom Widget: `_AnimatedStatCardWidget`
Create this class inheriting from `QFrame` in `library_browser.py`:
- **Layout**: `QVBoxLayout` with margins `12px` and spacing `4px`, centered.
- **Widgets**:
  - `_value_label` (`QLabel`, default `"0"`): Set property `role="stat"`.
  - `_title_label` (`QLabel`, display title): Set property `role="stat_label"`.
- **Interpolation Animation**:
  - Maintain `self._current_value = 0` and `self._target_value = 0`.
  - Use a `QTimer` ticking at 16ms intervals connected to a `_tick()` slot.
  - In `_tick()`: Move `self._current_value` towards `self._target_value` using `step = max(1, int(diff * 0.15))` for positive difference, and `min(-1, int(diff * 0.15))` for negative difference. Update label text. If `diff == 0`, stop the timer.
  - `update_target(self, target)`: Updates `self._target_value = target` and starts the timer if not already running.

### 2. Custom Widget: `_ModalOverlay`
Create this class inheriting from `QWidget` in `library_browser.py`:
- **Parent**: Receives the main window (`parent_window`) as parent.
- **Style**: Styled with `background-color: rgba(26, 26, 26, 217);`.
- **Event Filtering**: Installs itself as an event filter on the `parent_window`. On `Resize` events, update its geometry to match `parent_window.rect()` and call `center_modal()` to keep the modal dialog perfectly centered.
- **Mouse Clicks**: Ensure mouse event handling is blocked so interactions cannot pass to widgets underneath.

### 3. Dialog: `_AnalyzeLibraryModal`
Create this class inheriting from `QDialog` in `library_browser.py`:
- **Window Flags**: Set `Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog` (or `Qt.WindowType.SubWindow` depending on windowing parent needs, but Frameless is absolute).
- **Attribute**: Set `Qt.WidgetAttribute.WA_TranslucentBackground`.
- **Dimensions**: Set fixed size of `520`px width by `280`px height.
- **Container**: Use a `QFrame` with object name `modal_container` inside a main layout to draw the styled border and rounded corners (`background-color: #2F2F2F; border: 1px solid #444444; border-radius: 12px;`).
- **Inner Content**:
  - Headline: `QLabel("Analyzing Library")` (role `"heading"`), centered.
  - Subtitle: `QLabel("Scanning files and proposing genre classifications...")` (role `"muted"`), centered.
  - Cards Row: Horizontal layout containing 3 `_AnimatedStatCardWidget` instances ("Tracks Analyzed", "Artists Classified", "Corrections Made").
  - Action Stack: A `QStackedWidget` of fixed height `45`px.
    - Page 0: Progress bar wrapper. Houses a `QProgressBar` styled with a height of 4px, `#383838` background, and Retro Teal (`#428175`) chunk. Set range `(0, 100)` and value `0`.
    - Page 1: Button wrapper. Houses the `Review Results` button. Styled with `secondary` property set to `True` (Teal), dimensions `180`px width by `36`px height. Connect its clicked signal to a custom slot that emits a custom signal or accepts the result.
- **API**:
  - `update_stats(self, tracks_count: int, artists_count: int)`: Updates target on the first two cards.
  - `update_percent(self, percent: int)`: Updates the progress bar value.
  - `on_classification_complete(self)`: Transitions the stacked widget to Page 1.

### 4. Integration in `LibraryBrowserView`
Surgically modify `_on_classify_clicked()` and `load()`:
- **Signature**: Change `_on_classify_clicked(self)` to `_on_classify_clicked(self, checked: bool = False, auto_classify: bool = False) -> None:`.
- **First Load Trigger**: At the end of `load()`, if `not self._is_classification_complete()`: call `self._on_classify_clicked(auto_classify=True)`.
- **Auto-Classify Logic**:
  - If `auto_classify` is `True`:
    - First check if `classification_session.json` exists. If it does, load it and call `self._enter_classify_mode(session)` immediately without showing the modal (this is identical to the current skip-session behavior).
    - If it does NOT exist:
      - Instantiate `_ModalOverlay` over `self.window()`.
      - Instantiate `_AnalyzeLibraryModal(overlay)`.
      - Center the modal and show both overlay and modal.
      - **Pre-compile the Artist & Track Counts**: Replicate the exact grouping logic of `_ClassifyWorker.run()` to pre-calculate `artist_name -> track_count` map and count of DJ tools tracks from `self._inventory`.
      - Set up state variables: `self._processed_artists = set()`, `self._processed_tracks_count = 0`.
      - Start `_ClassifyWorker`.
      - Connect progress/finished/error signals to dedicated auto-classify slots:
        - **Progress Slot**: On `progress(done, total, artist_name)`:
          - If `artist_name` not in `self._processed_artists`:
            - Add to `self._processed_artists`.
            - Increment `self._processed_tracks_count` by `dj_tools_count` if `artist_name == DJ_TOOLS_LABEL`, else by `artist_tracks[artist_name]`.
          - Update the modal's stats cards with `self._processed_tracks_count` and `len(self._processed_artists)`.
          - Calculate `percent = int((done / total) * 100)` and update progress bar.
        - **Finished Slot**: On `finished(session)`:
          - Save the session and apply edits:
            ```python
            session.save()
            session.apply_library_edits()
            self._auto_classify_session = session
            self._analyze_modal.on_classification_complete()
            ```
        - **Error Slot**: On `errored(message)`:
          - Cleanup overlay/modal, restore toolbar button state, and display critical dialog message.
  - If `auto_classify` is `False` (manual trigger):
    - Retain the exact existing behavior: disable toolbar button, run the worker, and connect to `_on_classify_finished` and `_on_classify_error`.
- **Review Button Wiring**:
  - Clicking `Review Results` in the modal must trigger `_on_review_results_clicked(self)`:
    - Call cleanup function `_cleanup_auto_classify_ui(self)` to safely delete overlay and modal.
    - Retrieve `self._auto_classify_session` and call `self._enter_classify_mode(self._auto_classify_session)`.
- **Cleanup**: Create `_cleanup_auto_classify_ui(self)` to remove event filters, close/delete widgets, and reset state fields.

---

## Verification Plan

### Automated Check
- Perform a manual syntax/compilation check.

### Manual Verification Flow
1. **First-run Auto-Classify Modal Activation**:
   - Ensure the classification accepted flag file does not exist (`classification_accepted.flag`).
   - Re-open/navigate to the Library browser.
   - Verify that the dark overlay covers the entire window, the frameless modal is perfectly centered, the progress bar starts at 0%, and the 3 cards display initialized counters.
2. **Count-up Animation & Progress Updates**:
   - Observe the progress bar animating.
   - Confirm that the count of tracks and classified artists counts up smoothly (animating towards their real-time targets) rather than jumping abruptly.
   - Verify that "Corrections Made" remains at 0 with a TODO in the source code.
3. **No Layout Jumps on Completion**:
   - Once classification is complete, the progress bar must hide, and the "Review Results" button must appear in the exact same location. Confirm the modal's height does not jump or change.
4. **Resizing Behavior**:
   - Resize the main window during classification. Confirm that the overlay dynamically resizes to have zero gaps and the modal window remains perfectly centered.
5. **Dismissal and Classify Mode Entry**:
   - Click "Review Results". Confirm that the overlay/modal are destroyed and the main Library table is populated in classify mode.
6. **Manual Toolbar Classify Isolation**:
   - Confirm that manually clicking "Classify Library" from the toolbar/sidebar does not trigger the modal takeover.
