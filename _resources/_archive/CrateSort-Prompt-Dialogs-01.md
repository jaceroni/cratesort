# CrateSort — Modal Dialog Style Fix (Prompt 19)

> **Run this at Sonnet high effort. Read all referenced files completely before making any changes.**

## Files to Read First

- `src/gui/crate_manager.py`
- `src/gui/main_window.py`
- `src/gui/classifier_view.py`
- `src/gui/dashboard.py`

---

## The Goal

All modal dialogs across the app have two problems:
1. Text and button labels are bold — everything must be normal weight (400)
2. Content is cramped — needs more padding and breathing room throughout

Apply the fixes below to every dialog instance in all four files.

---

## Fix 1 — QMessageBox Dialogs: Normal Weight Text + More Padding

For every `QMessageBox` instance in all files, apply this stylesheet:

```
msg.setStyleSheet("""
    QMessageBox {
        background-color: #2F2F2F;
    }
    QMessageBox QLabel {
        color: #f1e3c8;
        font-weight: 400;
        font-size: 13px;
        padding: 12px 16px;
    }
    QMessageBox QPushButton {
        background-color: #428175;
        color: #ffffff;
        font-weight: 400;
        font-size: 13px;
        padding: 8px 24px;
        border-radius: 6px;
        border: none;
        min-width: 80px;
    }
    QMessageBox QPushButton:hover {
        background-color: #4f9688;
    }
    QMessageBox QPushButton:pressed {
        background-color: #36675d;
    }
""")
```

Apply this to every `QMessageBox` instance — confirmation dialogs in `crate_manager.py`, warning dialogs in `main_window.py`, and the coming soon dialog in `dashboard.py`.

---

## Fix 2 — QInputDialog: Normal Weight Text + More Padding

For every `QInputDialog.getText(...)` call in `crate_manager.py`, the returned dialog cannot be directly styled before exec. Instead, find the dialog after creation using `QApplication.activeModalWidget()` or create a custom `QDialog` replacement.

The simplest approach: replace all three `QInputDialog.getText(...)` calls with a small custom `_NameInputDialog(QDialog)` that:
- Has a `QLabel` for the prompt text
- Has a `QLineEdit` for input (pre-filled when renaming)
- Has Cancel and OK `QPushButton`s
- Uses this stylesheet:

```
self.setStyleSheet("""
    QDialog {
        background-color: #2F2F2F;
    }
    QLabel {
        color: #f1e3c8;
        font-weight: 400;
        font-size: 13px;
    }
    QLineEdit {
        background-color: #1a1a1a;
        color: #f1e3c8;
        font-weight: 400;
        font-size: 13px;
        border: 1px solid #444444;
        border-radius: 4px;
        padding: 6px 8px;
    }
    QPushButton {
        background-color: #428175;
        color: #ffffff;
        font-weight: 400;
        font-size: 13px;
        padding: 8px 24px;
        border-radius: 6px;
        border: none;
        min-width: 80px;
    }
    QPushButton:hover {
        background-color: #4f9688;
    }
""")
```

Layout: `QVBoxLayout` with 20px margins, 12px spacing. Label on top, LineEdit below, then a `QHBoxLayout` with Cancel and OK buttons right-aligned at the bottom.

`_NameInputDialog.get_name()` returns the entered text or None if cancelled.

Replace the three `QInputDialog.getText(...)` calls with `_NameInputDialog(parent, title, prompt, prefill="").get_name()`.

---

## Fix 3 — Custom QDialog Classes: Normal Weight + More Padding

For `_AddTracksDialog` in `crate_manager.py`, `_ChangeGenreDialog`, `_ReassignArtistDialog`, and `_EditTagsDialog` in `classifier_view.py`, and `_LaunchDialog` in `main_window.py`:

In each custom dialog's `__init__`, ensure:
- All `QLabel` widgets: `setFont` or stylesheet `font-weight: 400`
- All `QPushButton` widgets: `font-weight: 400`, solid teal `#428175` background, white text, 6px border radius, 8px top/bottom padding, 24px left/right padding
- Dialog layout margins: minimum 20px on all sides
- Spacing between elements: minimum 12px

Do not redesign these dialogs — only fix font weight and add padding. Keep all existing functionality intact.

---

## General Requirements

- Normal weight (400) on ALL text in ALL dialogs — no bold, no 600, no 700
- Minimum 20px layout margins inside every dialog
- Minimum 12px spacing between dialog elements
- All action buttons: solid teal `#428175` fill, white text, 6px radius, normal weight
- Cancel buttons: solid muted gray `#3a3a3a` fill, cream text `#f1e3c8`, 6px radius, normal weight
- Do not change dialog logic, validation, or any non-visual behavior
