"""Single source of truth for the app version.

Bump this ONE constant per release. `main_window.py` (window title + the
About dialog) and `packaging/CrateSort.spec` (macOS bundle Info.plist,
which drives both the .app's own version and the DMG filename) both read
from here so they can't drift out of sync again — this constant was stuck
at "0.1.0" for nine straight beta releases while the packaged .app's own
Info.plist version silently climbed to 0.1.9, because bumping the spec
file was a manual, separate step nobody remembered to mirror here.
"""

VERSION = "0.2"
