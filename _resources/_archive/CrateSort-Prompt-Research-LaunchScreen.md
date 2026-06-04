# CrateSort — Research Only: Launch Screen & Welcome Dialog

**No changes. Read only. Report back.**

---

## Task

Read the app entry point and any files related to the launch sequence. Report back specific sections. Do not modify anything.

---

## Files to Read

### 1. App entry point
Read `main.py` (or equivalent entry point file) and report back:
- The full launch sequence — what gets instantiated first, what shows before the main window
- What triggers the welcome back dialog
- What triggers the "Select Music Library..." background screen
- How the app determines whether this is a first launch or a returning user

### 2. Welcome Back dialog
Find and read the file containing the "Welcome Back" dialog (the popup with "Welcome back to CrateSort", the library path display, the "Always load my last library" checkbox, and the "Choose Different Library" / "Load Library" buttons). Report back:
- The full file path
- The complete class definition
- Every widget being created and how it's laid out
- What signals/callbacks the buttons connect to
- Where the "always load" preference is stored and read from

### 3. Library selection background screen
Find and read the file containing the background screen (the one with the CrateSort wordmark, "Get your shit together." tagline, and "Select Music Library..." orange button). Report back:
- The full file path
- The complete class definition
- Every widget being created and how it's laid out
- What the "Select Music Library..." button does when clicked

---

## What to Paste Back

Paste the full source of:
- The launch sequence section of `main.py`
- The complete Welcome Back dialog class
- The complete library selection screen class

Do not summarize. Paste the actual code.
