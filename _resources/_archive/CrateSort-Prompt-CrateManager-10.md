# CrateSort — Crate Tree Delegate Rewrite + App-Wide Row Height (Prompt 10)

> **Run this at Sonnet high effort. Read every referenced file completely before writing a single line of code. Do not skim.**

## Files to Read First

- `src/gui/crate_manager.py` — primary file
- `src/gui/library_browser.py` — for row height standardization
- `src/gui/theme.py` — color constants

---

## The Core Problem

Every attempt to style the crate tree using `setItemWidget` + `CrateRowWidget` has failed on macOS because Qt's native tree renderer paints around and over the widget, causing color overrides, gaps, bleeds, and state loss on tab switch. 

**The solution: remove `CrateRowWidget` and `setItemWidget` entirely. Replace with a `QStyledItemDelegate` that overrides `paint()`.** A delegate gives complete control over what Qt draws for each cell — no widget overlay, no fighting the native renderer.

---

## Fix 1 — Replace CrateRowWidget with a Custom Delegate

### Step 1: Remove CrateRowWidget entirely
Delete the `CrateRowWidget` class and all `setItemWidget` calls. Remove all `setText(0, '')` calls that were added to suppress Qt's own text rendering — the delegate will handle text rendering directly.

### Step 2: Implement CrateItemDelegate

```python
class CrateItemDelegate(QStyledItemDelegate):
    
    ROW_HEIGHT = 36  # single source of truth for crate tree row height
    BAR_WIDTH = 5    # orange left bar width in pixels
    
    # State constants
    STATE_A = 'a'  # unselected
    STATE_B = 'b'  # selected, no active sub-crate
    STATE_C = 'c'  # parent of active sub-crate
    STATE_D = 'd'  # selected sub-crate
    
    # Colors
    BG_A = QColor('#2F2F2F')   # unselected — matches panel
    BG_B = QColor('#573d26')   # selected warm brown
    BG_C = QColor('#2F2F2F')   # active parent — matches panel, bar distinguishes it
    BG_D = QColor('#573d26')   # selected sub-crate warm brown
    BAR_COLOR = QColor('#D17D34')   # always bright orange
    TEXT_COLOR = QColor('#f1e3c8')  # always cream
    
    def __init__(self, tree: QTreeWidget, parent=None):
        super().__init__(parent)
        self._tree = tree
        # item path → state string
        self._states: dict[str, str] = {}
    
    def set_item_state(self, path: str, state: str) -> None:
        self._states[path] = state
        # find the item and trigger repaint
        self._tree.viewport().update()
    
    def get_item_state(self, path: str) -> str:
        return self._states.get(path, self.STATE_A)
    
    def clear_all_states(self) -> None:
        self._states.clear()
        self._tree.viewport().update()
    
    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self.ROW_HEIGHT)
    
    def paint(self, painter, option, index) -> None:
        painter.save()
        
        # Get item path from UserRole
        path = index.data(Qt.ItemDataRole.UserRole) or ''
        state = self._states.get(path, self.STATE_A)
        
        # Choose background color
        bg_colors = {
            self.STATE_A: self.BG_A,
            self.STATE_B: self.BG_B,
            self.STATE_C: self.BG_C,
            self.STATE_D: self.BG_D,
        }
        bg = bg_colors.get(state, self.BG_A)
        
        # Fill entire cell background — no gaps, no bleeds
        painter.fillRect(option.rect, bg)
        
        # Draw orange left bar for State C and D only
        if state in (self.STATE_C, self.STATE_D):
            bar_rect = QRect(
                option.rect.left(),
                option.rect.top(),
                self.BAR_WIDTH,
                option.rect.height()
            )
            painter.fillRect(bar_rect, self.BAR_COLOR)
        
        # Draw text — always cream, always at consistent left padding
        text = index.data(Qt.ItemDataRole.DisplayRole) or ''
        text_rect = option.rect.adjusted(
            self.BAR_WIDTH + 8,  # left: bar width + 8px padding
            0,
            -4,                  # right: 4px margin
            0
        )
        painter.setPen(self.TEXT_COLOR)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text
        )
        
        painter.restore()
```

### Step 3: Install the delegate and restore item text

In `_build_crate_panel`:
```python
self._crate_delegate = CrateItemDelegate(self._crate_tree)
self._crate_tree.setItemDelegate(self._crate_delegate)
```

In `_add_crate_item`, restore `item.setText(0, crate_display_name)` — the delegate reads `DisplayRole` for text rendering. Remove all `setText(0, '')` calls.

### Step 4: Update `_on_tree_selection_changed`

Replace all `widget.set_state_*()` calls with delegate state calls:

```python
def _on_tree_selection_changed(self, current, previous):
    if current is None:
        return
    
    # Reset previous selection
    if self._prev_selected_item:
        prev_path = self._prev_selected_item.data(0, Qt.ItemDataRole.UserRole) or ''
        self._crate_delegate.set_item_state(prev_path, CrateItemDelegate.STATE_A)
    if self._prev_parent_item:
        prev_parent_path = self._prev_parent_item.data(0, Qt.ItemDataRole.UserRole) or ''
        self._crate_delegate.set_item_state(prev_parent_path, CrateItemDelegate.STATE_A)
    
    # Apply new states
    current_path = current.data(0, Qt.ItemDataRole.UserRole) or ''
    parent_item = current.parent()
    
    if parent_item and parent_item.data(0, Qt.ItemDataRole.UserRole):
        # Sub-crate selected
        self._crate_delegate.set_item_state(current_path, CrateItemDelegate.STATE_D)
        parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole) or ''
        self._crate_delegate.set_item_state(parent_path, CrateItemDelegate.STATE_C)
        self._prev_parent_item = parent_item
    else:
        # Top-level crate selected
        self._crate_delegate.set_item_state(current_path, CrateItemDelegate.STATE_B)
        self._prev_parent_item = None
    
    self._prev_selected_item = current
```

### Step 5: Restore selection colors after tab switch

Connect to the crate view's `showEvent`:
```python
def showEvent(self, event):
    super().showEvent(event)
    # Reapply selection state after returning to this tab
    if self._prev_selected_item:
        # Re-trigger selection change to reapply delegate states
        self._on_tree_selection_changed(self._prev_selected_item, None)
```

---

## Fix 2 — App-Wide Row Height Standardization

The crate tree rows are the correct height. All other tables must match.

**Single source of truth:** Define `ROW_HEIGHT = 36` in `theme.py` (or use `CrateItemDelegate.ROW_HEIGHT`). Apply this value everywhere:

**Track panel (crate_manager.py):**
```python
self._track_table.verticalHeader().setDefaultSectionSize(36)
self._track_table.verticalHeader().setMinimumSectionSize(36)
self._track_table.verticalHeader().setMaximumSectionSize(36)
self._track_table.horizontalHeader().setFixedHeight(36)
```

**Library browser (library_browser.py):**
- Find wherever the library table row height is set and update to 36px
- Apply the same `setDefaultSectionSize(36)` / `setMinimumSectionSize(36)` / `setMaximumSectionSize(36)` pattern
- Update the column header height to 36px as well

**Search fields:**
- Both "Search crates..." and "Search tracks..." fields: `setFixedHeight(36)`

---

## Fix 3 — Crate Tree Stylesheet: Clean and Minimal

Replace the current crate tree stylesheet with this minimal version — the delegate handles all item rendering now:

```python
self._crate_tree.setStyleSheet("""
    QTreeWidget {
        background-color: #2F2F2F;
        border: none;
        border-right: 1px solid #444444;
        outline: none;
    }
    QTreeWidget::item {
        padding: 0px;
        border: none;
    }
    QTreeWidget::branch {
        background-color: #2F2F2F;
    }
    QTreeWidget::branch:has-children:!has-siblings:closed,
    QTreeWidget::branch:closed:has-children:has-siblings {
        image: url(none);
    }
    QTreeWidget::branch:open:has-children:!has-siblings,
    QTreeWidget::branch:open:has-children:has-siblings {
        image: url(none);
    }
""")
```

Also disable Qt's selection highlight completely:
```python
palette = self._crate_tree.palette()
palette.setColor(QPalette.ColorRole.Highlight, QColor('#2F2F2F'))
palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#f1e3c8'))
self._crate_tree.setPalette(palette)
```

---

## Fix 4 — Expand Indicators

Since the delegate now handles all rendering, the branch expand/collapse arrows from Qt's `::branch` stylesheet are suppressed. The expand indicator must be shown in the delegate's `paint()` method instead.

In `CrateItemDelegate.paint()`, after drawing the text, check if the item has children and draw a ▶ or ▼ indicator right-aligned in the row:

```python
# Draw expand indicator for items with children
item = self._tree.itemFromIndex(index)
if item and item.childCount() > 0:
    indicator = '▼' if item.isExpanded() else '▶'
    indicator_rect = option.rect.adjusted(
        option.rect.width() - 20, 0, 0, 0
    )
    painter.setPen(self.TEXT_COLOR)
    painter.drawText(
        indicator_rect,
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        indicator
    )
```

---

## General Requirements

- **Always run at Sonnet high effort**
- Remove `CrateRowWidget` class entirely — it must not exist after this prompt
- Remove all `setItemWidget` and `setText(0, '')` calls from the crate tree
- The delegate is the single source of truth for all crate tree visual rendering
- Serato custom ID3 frames are never modified
- Tree expanded/collapsed state and crate selection must be preserved after every operation and after tab switches
- Do not change drag logic, expand/collapse behavior, or any other view beyond what is specified here
