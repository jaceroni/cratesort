# CrateSort — GUI Polish Pass: Dashboard & Shell Fixes

## Context

The app shell, theme, sidebar, and dashboard are built and working. The user 
has tested the app and provided specific UI feedback. This session is 
strictly a polish pass — fix the items below, nothing else.

The test library is at:
```
/Users/jacebrown/Desktop/cratesort-test-library
```

## Fixes to make

### 1. Sidebar logo — center horizontally

The CrateSort wordmark logo in the sidebar header has uneven spacing. It 
looks like there's extra space on the right side. Center the logo 
horizontally within the sidebar with equal padding on the left and right.

### 2. Sidebar active indicator — double the width

The orange left-border accent on the active sidebar nav button is too thin. 
Double its width (e.g., if it's currently 3px, make it 6px).

### 3. Button hover states — darken, don't lighten

All buttons (orange primary and teal secondary) currently get lighter/brighter 
on hover. Reverse this — they should get slightly DARKER on hover. This 
applies to every clickable button in the app, not just the action buttons.

### 4. Directory picker — add instruction text

When the "Select Music Library..." button opens the directory picker dialog, 
there's no guidance about what to select. Add descriptive text to the dialog:
"Select the folder that contains your media files. CrateSort will scan 
everything inside it."

### 5. Scan loading minimum display time

On small libraries, the scanning state flashes by so fast the user might 
think nothing happened. Add a minimum display time of 1.5 seconds on the 
scanning/amber state. Even if the scan finishes in 200ms, the user should 
see the scanning UI for at least 1.5 seconds before transitioning to the 
dashboard. This gives visual confirmation that work was done.

### 6. Genre distribution table — resizable

The genre distribution table is a fixed height and doesn't show all rows 
(13 genre tags, only ~5 visible). Two fixes:

a) Make the table section resizable — add a drag handle at the bottom edge 
   of the table container so the user can pull it taller to see more rows.
   
b) Apply this resizable pattern to ANY tabled or listed content throughout 
   the app. Tables should never be permanently cramped when there's available 
   window space.

### 7. Status bar padding

The library path text in the bottom-left of the status bar is flush against 
the window edge. Add left padding (at least 12-16px) so it has breathing 
room. Check the right side too ("Library synced. Ready.") and make sure 
both sides have consistent comfortable padding.

### 8. Dashboard content should scale with window

When the application window is expanded (wider and taller), the dashboard 
content stays the same size and leaves a large empty area below the action 
buttons. The dashboard layout should expand to fill available space:
- Stat cards row should stretch with window width
- Format breakdown should stretch with window width
- Genre distribution table should grow taller with available vertical space
- The whole dashboard should feel like it uses the window, not like it's 
  a fixed-size card floating in empty space

### 9. First-time guidance / next steps

After the library scan completes and the dashboard is shown, a first-time 
user has no idea what to do next. Add a brief contextual guidance section 
just above the action buttons. Something like:

"What's next? Start by classifying your library — CrateSort will organize 
your files into 12 genre categories and show you what needs attention."

Keep it to 1-2 sentences. Not a tutorial, just a nudge. This could be 
dismissible (show a small X to close it) so it doesn't clutter the UI for 
returning users. Or only show it on first launch.

### 10. Scanner should skip DJ software directories

When scanning for media files, the scanner should automatically skip these 
directories:
- `_Serato_/`
- `_Rekordbox_/`
- `PIONEER/`
- Any directory starting with `._` (macOS resource forks)
- `.Spotlight-V100/`, `.Trashes/`, `.fseventsd/` (macOS system directories)

These contain application data, not media files. They should never appear 
in the scan results. Update `src/core/scanner.py` to skip these directories 
during the walk.

### 11. Auto-detect Serato library location

After scanning the media folder, check if a `_Serato_/` directory exists 
inside the selected root. If found:
- Store its path in QSettings
- Show a brief note on the dashboard: "Serato library detected" with the 
  path (can be subtle — in the stats area or near the status bar)

If NOT found inside the selected root:
- Don't show an error — it's normal for Serato to live elsewhere
- For now, just don't mention it. We'll add a "Locate Serato Library" 
  option in Settings later.

## Testing

After making all fixes:
1. Launch the app fresh (clear QSettings if needed to test first-launch flow)
2. Verify the sidebar logo is centered
3. Verify the active indicator is wider
4. Hover over buttons and verify they darken
5. Click "Select Music Library" and verify the instruction text appears
6. Select the test library and verify the scan shows for at least 1.5 seconds
7. Verify the dashboard fills the window when expanded
8. Verify the genre table is resizable
9. Verify the status bar has proper padding on both sides
10. Verify the first-time guidance text appears
11. Verify _Serato_ is not in the scan results but is auto-detected
12. Verify the scan file count is lower than before (since _Serato_ files 
    are now excluded)

Launch the app and confirm everything works.

## Important

This is a polish pass ONLY. Do not add new views, new features, or 
restructure the codebase. Fix these 11 items and confirm they work.
