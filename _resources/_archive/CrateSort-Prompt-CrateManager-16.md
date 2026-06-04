# CrateSort — Library & Classification: Grid Lines and Alternating Rows (Prompt 16)

> **Run this at Sonnet high effort. Read all referenced files completely before making any changes.**

## Files to Read First

- `src/gui/library_browser.py`
- `src/gui/classifier_view.py`

---

## The Goal

The Library Browser and Classification view both use QTreeWidget for their track displays. They need the same visual treatment as the Crates track panel:

- Full grid lines — both vertical column separators AND horizontal row borders
- Grid color: `#383838`
- Alternating row colors: `#242424` (odd rows) and `#2a2a2a` (even rows)

---

## Change 1 — Library Browser QTreeWidget

In `src/gui/library_browser.py`, find the main track/artist listing QTreeWidget. Apply:

- `setAlternatingRowColors(True)`
- Set palette: Base `#242424`, AlternateBase `#2a2a2a`
- Add to its stylesheet:

```
QTreeWidget {
    gridline-color: #383838;
}
QTreeWidget::item {
    border-right: 1px solid #383838;
    border-bottom: 1px solid #383838;
    padding-left: 0px;
    margin-left: 0px;
}
```

The left-edge artifact (border being cut off on the left side of rows) is caused by the tree's branch/indent area overlapping the item border. Fix by ensuring the item border starts flush with the left edge of the visible cell content — set `QTreeWidget::branch { border: none; }` to prevent the branch area from interfering with the item border rendering.

---

## Change 2 — Classification View QTreeWidget

In `src/gui/classifier_view.py`, find the track/artist listing QTreeWidget. Apply the exact same treatment as Change 1:

- `setAlternatingRowColors(True)`
- Set palette: Base `#242424`, AlternateBase `#2a2a2a`
- Same stylesheet with `border-right`, `border-bottom`, and branch fix

---

## What NOT to Change

- Do NOT touch `src/gui/crate_manager.py` — the crates track panel is already correct
- Do NOT touch `src/gui/dashboard.py` — the genre distribution table is a stats summary, not a track listing
- Do NOT touch row heights anywhere
- Do NOT change column widths, sort behavior, or any other functionality
