# CrateSort — Undo/Redo System: Phase 1 (Crate Manager) (Prompt 17)

> **Run this at Sonnet high effort. Read every referenced file completely before writing a single line of code. This is a significant architectural addition — take your time and plan before implementing.**

## Files to Read First

- `src/gui/main_window.py` — where UndoManager lives and sidebar buttons go
- `src/gui/crate_manager.py` — all actions that need undo support
- `src/gui/theme.py` — color constants
- `src/serato/crate_writer.py` — to understand what write operations need reversing
- `src/serato/crate_reader.py` — to understand how to read state for before/after snapshots

---

## Architecture Overview

Implement the Command pattern for undo/redo. Every user action that modifies crate state becomes a `Command` object with `execute()` and `undo()` methods. An `UndoManager` maintains a stack of up to 10 commands.

Do NOT store full snapshots of the entire library state. Each command stores only the minimum data needed to reverse its specific action.

---

## Step 1 — UndoManager Class

Create `UndoManager` in `src/gui/main_window.py` (or a new `src/utils/undo_manager.py` if cleaner):

```
class UndoManager:
    MAX_STATES = 10
    
    - _undo_stack: list of Command objects (max 10)
    - _redo_stack: list of Command objects (max 10)
    - _on_change: callable — called after any push/undo/redo to update button states
    
    def push(command: Command) -> None
        # Execute the command, push to undo stack, clear redo stack
        # If stack exceeds MAX_STATES, drop the oldest
    
    def undo() -> Optional[str]
        # Pop from undo stack, call command.undo(), push to redo stack
        # Return description string for teal footer text
        # Return None if stack empty
    
    def redo() -> Optional[str]
        # Pop from redo stack, call command.execute(), push to undo stack
        # Return description string for teal footer text
        # Return None if stack empty
    
    def can_undo() -> bool
    def can_redo() -> bool
    def clear() -> None
```

The `UndoManager` instance lives on `MainWindow` as `self._undo_manager` and is passed to `CrateManagerView` on construction.

---

## Step 2 — Command Base Class

```
class Command:
    description: str  # Human-readable, e.g. "Remove 'Night Moves' from Rock Classics"
    source_tab: str   # Which tab this action came from, e.g. "crates"
    
    def execute(self) -> None: ...
    def undo(self) -> None: ...
```

---

## Step 3 — Implement Command Classes for All Crate Manager Actions

Implement a Command subclass for each of these actions. Each command stores the before/after state needed to reverse itself:

### AddTracksCommand
- Stores: `crate_path`, `track_paths` (list of added paths)
- `execute()`: adds tracks to crate via writer
- `undo()`: removes those tracks from crate via writer, reloads track panel
- Description: "Added [X] track(s) to [Crate Name]"

### RemoveTracksCommand
- Stores: `crate_path`, `track_paths`, `original_positions` (indices where they were)
- `execute()`: removes tracks from crate
- `undo()`: re-inserts tracks at their original positions, reloads track panel
- Description: "Removed [X] track(s) from [Crate Name]"

### ReorderTracksCommand
- Stores: `crate_path`, `old_order` (list of paths), `new_order` (list of paths)
- `execute()`: writes new_order to .crate file
- `undo()`: writes old_order to .crate file, reloads track panel
- Description: "Reordered tracks in [Crate Name]"

### CreateCrateCommand
- Stores: `crate_path`, `crate_name`
- `execute()`: creates the .crate file
- `undo()`: deletes the .crate file, removes from tree
- Description: "Created crate '[Crate Name]'"

### DeleteCrateCommand
- Stores: `crate_path`, `crate_name`, `track_paths` (all tracks that were in it), `parent_path` (if sub-crate)
- `execute()`: deletes the .crate file
- `undo()`: recreates the .crate file with all original tracks, restores in tree
- Description: "Deleted crate '[Crate Name]'"

### RenameCrateCommand
- Stores: `old_path`, `new_path`, `old_name`, `new_name`
- `execute()`: renames via writer
- `undo()`: renames back to old name via writer
- Description: "Renamed '[Old Name]' to '[New Name]'"

### ReorderCratesCommand
- Stores: `parent_path`, `old_order` (list of crate names), `new_order`
- `execute()`: writes new_order to crate_order.json
- `undo()`: writes old_order to crate_order.json, rebuilds tree
- Description: "Reordered crates"

### ReparentCrateCommand
- Stores: `crate_name`, `old_parent_path`, `new_parent_path`
- `execute()`: moves crate to new parent via writer
- `undo()`: moves crate back to old parent via writer, rebuilds tree
- Description: "Moved '[Crate Name]' to [destination]"

---

## Step 4 — Wire Commands into CrateManagerView

Replace every direct write operation in `crate_manager.py` with a command push. Instead of calling writer methods directly, create the appropriate Command and call `self._undo_manager.push(command)`.

The `push()` method calls `execute()` internally, so the action still happens immediately — the only change is that it's now tracked and reversible.

---

## Step 5 — Undo/Redo Buttons in Sidebar

In `main_window.py`, add Undo and Redo buttons below the album art panel in the left sidebar.

- Layout: two buttons side by side, labeled "Undo" and "Redo" with ← → arrows
- **Active state** (can undo/redo): teal (`#428175`) color, clickable
- **Inactive state** (stack empty): muted/dim, not clickable
- Sufficient padding below the album art so buttons don't feel attached to it
- Buttons update their state after every push/undo/redo via `_undo_manager._on_change`

---

## Step 6 — Keyboard Shortcuts

In `main_window.py`:
- `Cmd+Z` (macOS) / `Ctrl+Z` (Windows/Linux) → undo
- `Cmd+Shift+Z` (macOS) / `Ctrl+Shift+Z` (Windows/Linux) → redo

Use `QShortcut` on the main window so shortcuts work regardless of which tab is focused.

---

## Step 7 — Auto-Tab Switch

When `undo()` or `redo()` is called, check the command's `source_tab`. If it differs from the currently active tab, switch to that tab automatically before executing the undo/redo so the user can see what changed.

---

## Step 8 — Teal Footer Text

After every undo or redo operation, update the teal footer status bar with:
- Undo: *"Undone: [command.description]"*
- Redo: *"Redone: [command.description]"*

---

## General Requirements

- **Always run at Sonnet high effort**
- Serato custom ID3 frames are never modified
- Every command's `undo()` must leave the app in exactly the state it was before `execute()` was called — no side effects
- After any undo/redo, rebuild only the affected portion of the UI — not the entire app
- The undo stack is cleared on app close and on library change (selecting a different library directory)
- Do not break any existing crate manager functionality — commands wrap existing operations, they don't replace the underlying writer calls
