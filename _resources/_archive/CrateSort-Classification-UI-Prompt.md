# CrateSort — GUI: Classification View & Approval Flow

## Context

The engine modules are all built and working:
- Scanner, Classifier, Filename Cleaner, "The" Handler, Metadata Fixer, 
  Artist Consolidator, Duplicate Detector, Crate Reader/Writer, Path Rewriter, 
  File Organizer

The GUI shell is built with a dashboard that has a "Classify Library" button 
currently showing a "Coming Soon" dialog. The Library sidebar view is a 
placeholder.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

## What to build

Wire up the "Classify Library" button on the dashboard AND build the 
classification results/approval view. This is the step where CrateSort 
analyzes every artist and proposes genre assignments for the user to 
review and approve.

## The flow

### Step 1: User clicks "Classify Library"

- Run the classifier in a background thread (QThread) so the UI stays 
  responsive
- Show a progress indicator: "Classifying artists..." with a count 
  (e.g., "34 of 67 artists classified")
- When complete, automatically switch to the Classification Results view

### Step 2: Classification Results View

This is a new view that shows the classifier's output grouped by genre. 
The user reviews and approves genre assignments here.

**Layout — two panels:**

**Left panel: Genre summary sidebar**
- List of all 12 CrateSort parent genres, each showing:
  - Genre name
  - Number of artists classified into it
  - Number of tracks
- An "Unclassified" entry at the bottom if any artists couldn't be resolved
- Clicking a genre filters the right panel to show only artists in that genre
- An "All" option at the top to show everything
- Color-coded confidence indicator per genre (e.g., small dot: green for 
  all HIGH, amber if any MEDIUM/LOW)

**Right panel: Artist list**
- Table/list of artists for the selected genre showing:
  - Artist name
  - Track count
  - Confidence level (HIGH / MEDIUM / LOW) with color indicator
  - Reasoning summary (short text: "Styles: Soul (4), Gospel (2) → Funk/Soul")
  - Current genre tags found (what the files are tagged with now)
  - A checkbox for selection (for batch operations)
- Sortable by any column
- Searchable — filter by artist name
- Expandable rows: clicking an artist shows their individual tracks with 
  file paths and metadata

**Confidence color coding:**
- HIGH confidence: subtle green indicator (#6B9E78)
- MEDIUM confidence: amber indicator (#D4A04A)  
- LOW confidence: muted red indicator (#C75B5B)
- These should be small dots or badges, not overwhelming color blocks

### Step 3: Approval actions

**Per-artist actions (right-click or action buttons):**
- "Approve" — accept the proposed genre for this artist
- "Change Genre" — dropdown to pick a different genre from the 12 options
- "Mark for Review" — flag for later decision

**Batch actions (for selected artists via checkboxes):**
- "Approve Selected" — accept all checked artists' proposed genres
- "Approve All HIGH" — one-click approve all HIGH confidence classifications
- "Approve All" — accept everything the classifier proposed

**Genre-level actions (in the genre summary sidebar):**
- "Approve All in [Genre]" — approve every artist classified in this genre

### Step 4: Approval state tracking

Each artist has a state:
- **Pending** — classified but not yet approved (default after classification)
- **Approved** — user confirmed the genre assignment
- **Changed** — user overrode the genre to something different
- **Flagged** — marked for review later

Show approval progress: "45 of 67 artists approved" somewhere visible.

The user doesn't have to approve everything in one session. The state 
persists (save to a JSON file in the CrateSort data directory) so they 
can come back to it.

### Step 5: Completion

When all artists are approved (or the user clicks "Done" to accept remaining 
as-is), the classification is locked in. This data is what the File Organizer 
and Library Browser will use.

Show a summary: "Classification complete. 67 artists classified into 8 genres. 
Ready to organize." with a button to go to the Organize view (placeholder 
for now) or back to the Dashboard.

## Important guidance text

The "What's next?" banner and the classification view header need CLEAR 
language about what classification does and doesn't do:

- Classification TAGS your artists with genres. It does NOT move any files.
- File reorganization is a separate step you trigger later from the Organize view.
- "Classify your library to assign genres to each artist. This step only 
  analyzes and tags — no files will be moved or renamed until you choose to 
  organize."

This language should appear:
- In the "What's next?" banner on the dashboard (update the existing text)
- As a subtitle/description at the top of the Classification Results view

## UI polish notes (carry forward from previous sessions)

- All buttons darken on hover (not lighten)
- Tables should be resizable where appropriate
- Use the established color palette: dark background, cream text, orange 
  primary accent, teal secondary accent
- Background threads for any processing with progress indicators
- Charter font for headings, sans-serif for body

## What NOT to build

- No Library Browser view yet (next session)
- No Organize/reorganization view yet (future session)
- No Crate Manager view yet (future session)
- No actual file moves or metadata writes — this is classification only
- No Settings page yet

## Also fix: Launch dialog for returning users

When the app opens and finds a previously saved library path, show a dialog:
- Display the saved path
- Two buttons: "Load Library" and "Choose Different Library"
- A checkbox: "Always load my last library (don't ask again)"
- If the checkbox was previously checked, skip the dialog and go straight 
  to scanning
- This setting should be reversible in Settings (when built) — for now 
  just respect the QSettings value

## Testing

After building:
1. Launch the app
2. Load the test library
3. Click "Classify Library" on the dashboard
4. Verify the classification runs with progress indicator
5. Verify the results view shows all artists grouped by genre
6. Click through genres in the left panel and verify filtering works
7. Expand an artist row to see their tracks
8. Approve a few artists individually
9. Use "Approve All HIGH" to batch approve
10. Change one artist's genre manually
11. Verify approval state persists if you switch views and come back
12. Close and reopen the app — verify the launch dialog appears

Launch the app and verify everything works.
