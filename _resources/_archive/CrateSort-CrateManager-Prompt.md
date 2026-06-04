# CrateSort — Crate Manager View

## Context

The Dashboard, Classification view, and Library Browser are all built and 
polished. The Crate Reader, Crate Writer, and Path Rewriter engine modules 
are built and working (Phase 3). The Crate Manager replaces the "Crates — 
Coming in the next session" placeholder in the sidebar.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

It contains a real `_Serato_/` folder with 191 crates copied from a live 
DJ setup.

## What this view is

The Crate Manager is where the user sees, browses, and manages their 
Serato crates. It reads the existing crate structure from the `_Serato_/` 
directory and presents it as an interactive tree. The user can create, 
rename, duplicate, and delete crates, and add/remove tracks from crates.

This is the "front stage" — the performance layer. The Library is 
everything you own. Crates are how you organize what you want to play.

## Layout

**Left panel: Crate tree (sidebar-width, ~250px)**
- Hierarchical tree of all Serato crates
- Top-level crates at root, subcrates nested underneath
- Each crate shows its name and track count
- Click a crate to see its contents in the right panel
- Right-click for crate-level actions
- "All Tracks" entry at the top showing total unique tracks across all crates
- Search/filter field at the top of the tree to find crates by name

**Right panel: Crate contents (main area)**
- When a crate is selected, shows all tracks in that crate as a table
- Columns: Track Title, Artist, Album, Duration, Genre, Style Tags, 
  BPM, Format, Year, Bitrate, Comments, File Path
- All columns sortable, resizable, and draggable/reorderable 
  (setSectionsMovable). Column order persists via QSettings.
- All content left-aligned — no right-aligned numbers, no centered text
- Column minimum widths must fit full header text (use QFontMetrics)
- Same row selection styling as other views (orange bg #D17D34, dark 
  text #2F2F2F, no left-side indicator, no border-radius on cells)
- Each track row gets a music note icon (♪) matching the Library Browser
- Single click on a track = highlight orange + update album art panel
- Tracks that exist in the scanned library show full metadata
- Tracks that reference files NOT in the scanned library (orphaned paths 
  from the external drive) show the file path in muted text with an 
  indicator: "Not found in library"

**Bottom bar: Crate info**
- Shows selected crate name, track count, total duration
- Status indicator: how many tracks resolved vs unresolved

## Crate tree behavior

### Reading crates
- On view activation, read all crates using the CrateReader module
- Build the hierarchy tree from the `%%` separator naming convention
- Show track counts per crate
- Crates with subcrates show as expandable nodes

### Right-click context menu on crate tree
- **New Crate** — creates a new empty crate (dialog for name input)
- **New Subcrate** — creates a subcrate under the selected crate
- **Rename Crate** — rename dialog with current name pre-filled
- **Duplicate Crate** — copies crate with all its track references
- **Delete Crate** — removes the crate (confirmation required since this 
  deletes the .crate file). Does NOT delete any audio files.
- **Add Tracks...** — opens a dialog to search/select tracks from the 
  library to add to this crate

### Right-click on empty area of crate tree
- **New Crate** — create a top-level crate

## Crate contents behavior

### Display
- When a crate is selected in the tree, load its track list
- Match track paths against the scanner inventory to enrich with metadata
- Unresolved paths (files not in scanned library) show the raw path with 
  "Not found" indicator — don't hide them

### Right-click on track in crate contents
Same track-level context menu as Library Browser — MUST be identical:
- Reassign Artist... (with autocomplete from existing artists)
- Change Genre... (dropdown of 13 CrateSort genres including Traditional)
- Edit Style Tags...
- Show in Finder
- Copy Artist
- Copy Title  
- Copy File Path
- **Remove from Crate** (additional option, specific to crate view) — 
  removes the track from this crate only. Does NOT delete the file.
  No confirmation dialog — just remove immediately.

### Inline editing
Double-click any editable cell on a track in the crate contents to edit 
inline — same behavior as the Library Browser. Editable fields: Title, 
Album, Style Tags, BPM, Year, Comments. Non-editable: Artist (use 
right-click Reassign), Genre (use right-click Change Genre), Duration, 
Format, Bitrate, File Path.

### Drag and drop
- Drag tracks FROM the Library Browser INTO the crate contents to add 
  them to the crate (future enhancement — stub the infrastructure but 
  don't implement full drag-drop yet)
- For now, use the "Add Tracks..." dialog from the crate right-click menu

## Add Tracks dialog

When user right-clicks a crate and selects "Add Tracks...":
- Opens a dialog with a search field
- Shows a filtered list of all tracks in the library (from scanner)
- User can search by artist, title, album
- Checkboxes to select multiple tracks
- "Add Selected" button adds checked tracks to the crate
- Tracks already in the crate are shown but grayed out / marked

## Crate operations — engine integration

All crate operations use the existing engine modules:
- **Create**: CrateWriter.create_crate()
- **Rename**: CrateWriter.rename_crate()
- **Duplicate**: CrateWriter.duplicate_crate()
- **Delete**: CrateWriter.delete_crate()
- **Add tracks**: CrateWriter.add_tracks()
- **Remove tracks**: CrateWriter.remove_tracks()

These write directly to .crate files in the _Serato_ directory. Changes 
are immediately reflected in Serato on its next launch.

## Album art panel

The sidebar album art panel should update when clicking tracks in the 
crate contents, same as it does in the Library Browser and Classification 
view. Emit the same track_selected/album_art_requested signal.

## Styling — must match other views exactly

- Same dark theme throughout (#1a1a1a background, #2F2F2F panels)
- Same font sizes as established (14px body, 20px headings, 12px muted)
- Crate tree uses the same tree widget styling as other views
- No system blue anywhere — QPalette overrides already in place
- Selected crate in the tree: orange highlight (#D17D34), dark text (#2F2F2F)
- Selected track in contents: orange highlight with dark text
- No left-side selection indicator on any rows
- No border-radius on cells (sharp rectangles, no corner artifacts)
- Unresolved tracks: muted text (#a89b85) with italic styling
- Track rows get music note icon (♪, 9px wide pixmap) matching Library Browser
- Checkboxes: #666666 border, cream fill when checked, visible on both 
  dark and orange backgrounds
- Hover on unselected rows: subtle #383838 background
- Album art panel clears when navigating away from Crates view 
  (already handled by main_window nav handler — just make sure the 
  Crates view emits the same album_art_requested/track_selected signal 
  as other views)
- Genre changes made in Crate Manager must sync to classification session 
  and library_edits.json (same cross-view sync as Library Browser)

## What NOT to build

- No drag-and-drop between views (stub only, future session)
- No Smart Crate builder (future session)  
- No crate suggestions / style matching (future session)
- No export functionality (future session)

## Testing

1. Launch app, load test library (which has _Serato_ folder)
2. Click "Crates" in sidebar — verify crate tree loads
3. Verify the hierarchy — subcrates nested under parent crates
4. Click a crate — verify track list shows in right panel
5. Verify resolved tracks show full metadata with all columns
6. Verify unresolved tracks show path with "Not found" indicator
7. Verify track rows have music note icon (♪)
8. Right-click a crate → New Crate — verify it creates
9. Right-click → Rename — verify rename works
10. Right-click → Duplicate — verify copy created
11. Right-click → Delete — verify deletion (no confirmation needed 
    for empty crates, confirmation for crates with tracks)
12. Right-click a crate → Add Tracks — verify dialog opens, search 
    works, adding tracks updates the crate
13. Right-click a track in crate → Remove from Crate — verify removal
14. Right-click a track → Show in Finder — verify it works
15. Right-click a track → Change Genre — verify 13 genres including 
    Traditional
16. Click a track in crate contents — verify album art updates in sidebar
17. Navigate away from Crates — verify album art clears
18. Search for a crate name in the tree filter — verify filtering
19. Double-click a track title — verify inline editing works
20. Verify all columns left-aligned, resizable, no clipped headers
21. Verify no system blue, correct selection colors throughout
22. Verify orange selection with dark text, no border-radius artifacts
23. Verify no left-side selection indicator

Launch and verify everything works.
