# CrateSort — GUI Polish Pass Round 2

## Context

Round 1 polish landed 11 fixes. The user has tested again and found 6 more 
items that need attention. This is strictly a fix pass — no new features.

## Fixes to make

### 12. Genre table drag handle — visible grip icon

The QSplitter between the genre table and the bottom section is invisible — 
the user has to guess where to hover to find it. Replace the bare splitter 
with a visible drag grip element:
- Add a small visual indicator centered at the bottom edge of the genre 
  table section — something like three short horizontal lines (≡) or a 
  row of dots (⋯⋯) that clearly communicates "drag me"
- The grip should be styled in the muted text color (#a89b85) and lighten 
  slightly on hover to confirm interactivity
- The cursor should change to a resize cursor when hovering over the grip

### 13. Splitter drag is glitchy / jumpy

The splitter handle hops around during drag instead of smooth continuous 
resizing. Check for:
- Conflicting minimum/maximum height constraints on the panels
- Size policy conflicts (the table and the bottom section may be fighting)
- Remove any setMaximumHeight or setMinimumHeight that could cause snapping
- Set sensible minimums only (e.g., table min 100px, bottom section min 80px)
- Test that dragging is smooth and continuous

### 14. "What's next?" dismiss button — proper styling

The dismiss button on the guidance banner is a tall narrow rectangle that 
looks like a glitched checkbox. Replace it with:
- A properly styled button that says "Got it" (not just an X icon)
- Style it as a small text button in the muted color that fits within the 
  banner — not a primary button, just a subtle dismissible action
- Properly sized — should not be taller than the banner text

### 15. Bring back guidance after dismissal

Once the user dismisses the "What's next?" banner, there's currently no way 
to bring it back. Add a small "Show tips" text link or button somewhere 
visible on the dashboard (perhaps near the ACTIONS header or in the stats 
area) that restores the guidance banner. This link should only appear when 
the banner has been dismissed.

Alternatively, add a "Show tips" toggle in Settings when we build that view. 
But for now, a simple link on the dashboard is sufficient.

### 16. Status bar left padding — still too tight

The library path in the bottom-left status bar is still too close to the 
window edge. The right side ("Library synced. Ready.") has comfortable 
spacing. Increase the left padding to at LEAST 16px — visually match 
what the right side looks like. If the current padding is 16px and it 
still looks tight, increase to 20-24px. Eyeball it until both sides feel 
balanced.

### 17. Verify all previous fixes still hold

Quickly confirm that the 11 fixes from round 1 are still working:
- Logo centered in sidebar
- Active indicator doubled width
- Button hover states darken
- Directory picker has instruction text
- Scan minimum display time works
- Genre table expands with window
- Dashboard content scales with window
- Serato directory skipped in scan
- Serato auto-detected

## Testing

Launch the app, select the test library, and verify:
1. The genre table has a visible drag grip
2. Dragging the grip resizes smoothly without jumping
3. The "What's next?" banner has a proper "Got it" button
4. After dismissing, a "Show tips" link appears to bring it back
5. Clicking "Show tips" restores the banner
6. The status bar path has balanced padding matching the right side
7. All round 1 fixes still work

## Important

Polish pass only. No new views, no new features, no restructuring.
