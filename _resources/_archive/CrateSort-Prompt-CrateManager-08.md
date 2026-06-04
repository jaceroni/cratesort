# CrateSort — Crate Tree Color Fix Only (Prompt 8)

> **Run this at Sonnet high effort. Read `src/gui/crate_manager.py` and `src/gui/theme.py` completely before writing a single line of code. Do not change anything except what is explicitly described in this prompt.**

You are fixing ONE thing: the crate tree panel background color and the four selection state colors. Nothing else.

---

## The Problem

The crate tree panel background is wrong and the selection state colors are not being applied correctly. This prompt fixes both with explicit color values.

---

## Fix — Crate Tree Panel Background and Selection Colors

### Step 1 — Set the crate tree panel background

The crate tree widget background must be `#2F2F2F` — the same dark panel color used in the sidebar navigation. Set this on the `QTreeWidget` itself:

```python
self._crate_tree.setStyleSheet("""
    QTreeWidget {
        background-color: #2F2F2F;
        border: none;
    }
""")
```

Do not set any other colors in this stylesheet. Selection colors are handled entirely by `CrateRowWidget` (see Step 2).

### Step 2 — Fix CrateRowWidget background colors

Find the `CrateRowWidget` class. The `set_state()` method (or equivalent) sets the widget background via `setStyleSheet`. Update the colors for each state to exactly these values:

**State A — unselected:**
```python
self.setStyleSheet("background-color: #2F2F2F;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.hide()
```

**State B — selected (no active sub-crate):**
```python
self.setStyleSheet("background-color: #D17D34;")
self._label.setStyleSheet("color: #1a1a1a; background-color: transparent;")
self._bar.hide()
```

**State C — parent of active sub-crate:**
```python
self.setStyleSheet("background-color: #000000;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.show()  # 5px orange #D17D34 left bar
```

**State D — selected sub-crate:**
```python
self.setStyleSheet("background-color: #8B5E3C;")
self._label.setStyleSheet("color: #f1e3c8; background-color: transparent;")
self._bar.show()  # 5px orange #D17D34 left bar
```

### Step 3 — Verify the orange left bar color

The `_bar` QFrame must have its background color set to `#D17D34` and its fixed width set to 5px. Verify this is set correctly in `CrateRowWidget.__init__()`:

```python
self._bar = QFrame()
self._bar.setFixedWidth(5)
self._bar.setStyleSheet("background-color: #D17D34;")
self._bar.hide()  # hidden by default (State A)
```

### Step 4 — Remove any conflicting stylesheet rules

Search the entire file for any stylesheet rules that set `QTreeWidget::item` background or selection colors. Remove them — they conflict with the `CrateRowWidget` approach and override the widget colors. The only `QTreeWidget` stylesheet rule that should remain is the panel background (`background-color: #2F2F2F`) set in Step 1.

---

---

## Fix 2 — Empty Crate Deletion: Always Show Confirmation Dialog

Currently empty crates are deleted silently with no confirmation. Every crate deletion must show a modal confirmation dialog regardless of whether the crate is empty or has tracks.

Find the delete crate handler (triggered by both Delete key and right-click → Delete). Replace any silent deletion of empty crates with the same modal dialog used for populated crates:

**Empty crate dialog:**
> Delete '[Crate Name]'? This cannot be undone.

Buttons: **Delete** / **Cancel**

**Populated crate dialog:**
> Delete '[Crate Name]'? It contains [X] tracks. This cannot be undone.

Buttons: **Delete** / **Cancel**

The dialog must be centered on screen and block all interaction until dismissed. Nothing is deleted until the user explicitly clicks Delete.

---

## Fix 3 — Drag Reparent: Works on Any Row Within the Parent Group

Currently reparenting only works when the dragged crate is dropped directly onto the parent crate row itself. Dropping onto a sub-crate row within the parent group causes the crate to disappear and reappear at the bottom.

Fix the drop logic so that when a crate is dropped in the reparent zone (middle third) of ANY row that is itself a sub-crate, the drop target becomes that sub-crate's parent:

- Detect if the target row is a sub-crate (its path contains `/`)
- If yes, resolve the parent: `parent_path = "/".join(target_path.split("/")[:-1])`
- Reparent the dragged crate under that parent
- The dragged crate becomes a sibling of the sub-crate it was dropped onto, nested under the same parent
- Write the change to `.crate` files immediately
- Teal footer text confirms: *"Moved '[Crate Name]' into [Parent Name]"*

---

## What NOT to Change

- Do not touch the track panel, track drag logic, or any column constants
- Do not touch the Library Browser, Dashboard, Organize, or Settings views
- Do not change expand/collapse behavior
- Do not change row heights
- Only change what is explicitly described in this prompt
