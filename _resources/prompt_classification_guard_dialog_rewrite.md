# FIX — Classify Navigate-Away Guard Dialog Rewrite

## Role
You are Cody, Code Steward for the CrateSort project. This is a surgical copy fix on the classify mode navigate-away guard dialog. Read the file completely, make only the changes described, touch nothing else.

---

## Files in Scope
- `cratesort/src/gui/library_browser.py` [MODIFY]

---

## Technical Specifications

### 1. Body Text Update
In `cratesort/src/gui/library_browser.py`, find the `_UnsavedChangesDialog` class (around line 271).
Locate the `body` QLabel instantiation. Replace the copy with:

> "You haven't accepted your classifications yet — your genre corrections won't be written to your files until you do."

Format it properly in the python file:
```python
        body = QLabel(
            "You haven't accepted your classifications yet — "
            "your genre corrections won't be written to your files until you do."
        )
```

### 2. Verify Button Labels & Colors
Verify that the buttons in `_UnsavedChangesDialog` match the following specifications (they should already match, but confirm there are no variations):
- **Primary button (Teal `#428175`)**:
  - Label: `"Stay and Finish"`
  - Hover: `#38706a`
  - Pressed: `#2d6358`
- **Secondary button (Red `#C75B5B`)**:
  - Label: `"Leave Anyway"`
  - Hover: `#b24c4c`
  - Pressed: `#9c3b3b`

*Note: Since the dialog does not have a separate headline label from the window title, do not add one.*

---

## Verification Plan

### Automated Check
- Perform a manual syntax/compilation check.

### Manual Verification
1. Navigate to the Library tab when classification is incomplete (starts auto-classify mode).
2. Before accepting classifications, attempt to navigate away (e.g. click Dashboard or Crates in the nav menu).
3. Verify that the navigate-away guard dialog appears.
4. Verify that the body copy matches exactly:
   > "You haven't accepted your classifications yet — your genre corrections won't be written to your files until you do."
5. Confirm that the buttons are "Leave Anyway" (Red) and "Stay and Finish" (Teal).
6. Verify clicking "Stay and Finish" keeps you in classify mode.
7. Verify clicking "Leave Anyway" exits classify mode and navigates away.
