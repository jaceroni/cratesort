# CrateSort — Library Baseline Artist Sync

**Claude, high effort. Read every referenced file completely before writing any code.**

---

## What to Build

Currently, untagged tracks or tracks with different formatting are grouped differently by default:
* **The Classifier** groups them under proposed/virtual artist names (like `DJ Tools (untagged)`) using classification rules.
* **The Library Browser** groups them under raw metadata (falling back to `Unknown Artist` if empty).

This leads to a mismatch where cleanups made in the Library tab under `Unknown Artist` don't sync up with the Classifier's `DJ Tools (untagged)` group.

To resolve this, we will update the **Library Browser** to use the **Classifier's proposed artist** as the default baseline grouping for each track (if no manual `reassign_artist` override exists in `library_edits.json`).

---

## Implementation Details

### 1. Track-to-Artist Mapping in LibraryBrowser

#### [MODIFY] [library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py)

- In `LibraryBrowser.load()`, initialize a new instance dictionary `self._session_artists` to map each track path to its Classifier entry artist:
  ```python
          self._session_genre = {}
          self._session_artists = {}  # Maps track_path (str) -> entry.artist (str)
          self._track_overrides = {}
  ```
- Inside the loop where the classification session entries are loaded:
  ```python
                  for entry in session.entries:
                      self._session_genre[entry.artist] = (entry.display_genre, entry.confidence)
                      for track in entry.tracks:
                          self._session_artists[track.path] = entry.artist
                          if track.genre_tag:
                              self._track_overrides[track.path] = track.genre_tag
  ```

- In `LibraryBrowser._rebuild_tree()`, use the session artist mapping as the baseline group if the track path is present in `self._session_artists` and has no manual `'reassign_artist'` override:
  ```python
          for rec in self._inventory:
              edits = self._edits.get(str(rec.path), {})
              if 'reassign_artist' in edits:
                  canonical = edits['reassign_artist']
              elif str(rec.path) in self._session_artists:
                  canonical = self._session_artists[str(rec.path)]
              else:
                  primary, _ = _extract_primary_artist(rec.artist or 'Unknown Artist')
                  canonical  = _canonical_artist(primary)
              artist_tracks[canonical].append(rec)
  ```

---

## Verification Steps

1. **Verify Default Grouping Alignment**:
   - Reload the library and navigate to the Library tab.
   - Verify that untagged tracks are now grouped under `DJ Tools (untagged)` (or whichever virtual/proposed artist name the Classifier assigned to them) instead of `Unknown Artist`.
2. **Verify Relocation Cleanup**:
   - Relocate the tracks from the `DJ Tools (untagged)` folder to a new or existing artist.
   - Go back to the Classifier tab. Verify that the tracks have moved to the new artist, and the `DJ Tools (untagged)` entry has successfully disappeared.
