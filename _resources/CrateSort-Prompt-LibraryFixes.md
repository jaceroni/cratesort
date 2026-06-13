# CrateSort — Library Overrides: Multi-Track Reassignment & Cross-View Sync

**Claude, high effort. Read every referenced file completely before writing any code.**

---

## What to Build

We are addressing a bug and an architectural gap in how manual edits/reassignments made in the Library tab propagate to other screens:

1. **Multi-Track Artist Reassignment (Bug)**: Selecting multiple tracks in the Library tab and choosing "Reassign Artist" should move all selected tracks to the new artist folder, not just the single right-clicked track.
2. **Library Empty Folder cleanup (Bug)**: When a track is relocated, removing it from its parent folder's track list can fail silently because `TrackRecord` is a dataclass without a custom `__eq__` method. Any in-memory edits to a track's tags cause Python's strict comparison (`parent_tracks.remove(rec)`) to raise a `ValueError`. This leaves empty folders stuck in the tree showing stale track counts. We must match and remove tracks by their unique file path instead.
3. **Classifier Sync (Gap)**: When the user goes back to the Classifier screen, manual artist reassignments made in the Library Browser should be recognized. The track should be listed under the new artist, and the old artist entry should be updated or removed if empty.
4. **Organize Tab Sync (Gap)**: When building the reorganization plan, the Organize tab must use the manually reassigned artist and genre overrides from `library_edits.json` to compute the correct on-disk destination paths and update file metadata tags.

---

## Implementation Details

### 1. Classification Session Updates

#### [MODIFY] [classifier_view.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/classifier_view.py)

- Add a new method `apply_library_edits(self)` directly to the `ClassificationSession` dataclass:
  ```python
  def apply_library_edits(self) -> None:
      """Apply any genre overrides and artist reassignments from library_edits.json on top of the loaded session."""
      edits_file = self.library_path / '_CrateSort' / 'library_edits.json'
      if not edits_file.exists():
          return
      try:
          with open(edits_file, encoding='utf-8') as f:
              edits = json.load(f)
      except Exception:
          return

      # 1. Handle Artist Reassignments
      reassignments = {}
      for path, track_edit in edits.items():
          if 'reassign_artist' in track_edit:
              reassignments[path] = track_edit['reassign_artist']

      if reassignments:
          # Find tracks and move them
          for entry in list(self.entries):
              moved_tracks = []
              for track in list(entry.tracks):
                  if track.path in reassignments:
                      new_artist = reassignments[track.path]
                      moved_tracks.append((track, new_artist))
                      entry.tracks.remove(track)
              
              # Mark entry as edited if tracks were removed from it
              if moved_tracks and entry.state == 'pending':
                  entry.state = 'edited'
              
              # If entry is now empty, remove it
              if not entry.tracks:
                  self.entries.remove(entry)

              # Add moved tracks to their new entries
              for track, new_artist in moved_tracks:
                  # Find or create destination entry
                  dest_entry = next((e for e in self.entries if e.artist == new_artist), None)
                  if dest_entry:
                      dest_entry.tracks.append(track)
                      dest_entry.state = 'edited'
                  else:
                      dest_entry = ArtistEntry(
                          artist=new_artist,
                          proposed_genre=track.genre_tag or 'Unclassified',
                          confidence='LOW',
                          reason='Manually reassigned in Library',
                          tracks=[track],
                          original_genres=[track.genre_tag] if track.genre_tag else [],
                          state='edited',
                      )
                      self.entries.append(dest_entry)

      # 2. Apply Genre Overrides (both artist-level and track-level)
      for entry in self.entries:
          artist_key = f'__artist__{entry.artist}'
          if 'genre' in edits.get(artist_key, {}):
              new_genre = edits[artist_key]['genre']
              entry.final_genre = new_genre
              if entry.state in ('pending', 'flagged'):
                  entry.state = 'edited'
          for track in entry.tracks:
              if 'genre' in edits.get(track.path, {}):
                  track.genre_tag = edits[track.path]['genre']
  ```
- Modify `ClassifierView._load_session()` to invoke `self._session.apply_library_edits()` and remove its local view-only `_apply_library_edits()` call.

---

### 2. Library Browser Updates

#### [MODIFY] [library_browser.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/library_browser.py)

- Rewrite `_reassign_track(self, child: QTreeWidgetItem, rec)` to handle multiple selected tracks:
  - Find all selected track items: `selected = [item for item in self._tree.selectedItems() if item.parent()]`. If `child` is not in this list, default/set `selected = [child]`.
  - Gather a list of track records and their parents: `tracks_to_move = [(item, item.data(LC_PATH, Qt.ItemDataRole.UserRole), item.parent()) for item in selected]`.
  - Prompt the user for the new artist name **once** using `_ReassignArtistDialog`. If canceled or empty, early return.
  - Find or create the destination artist group (`dest_item`) in the tree for the new artist name.
  - Move each track:
    - Remove the track child item from the tree: `parent_item.takeChild(parent_item.indexOfChild(child_item))`.
    - Safe path-based removal from the parent's in-memory tracks list:
      ```python
      parent_data = parent_item.data(LC_ARTIST, Qt.ItemDataRole.UserRole) or {}
      parent_tracks = parent_data.get('tracks', [])
      for r in list(parent_tracks):
          if str(r.path) == str(track_rec.path):
              parent_tracks.remove(r)
              break
      ```
    - Update parent count label: `parent_item.setText(LC_TRACKS, str(len(parent_tracks)))`.
    - Persist edits to `self._edits` for each track:
      ```python
      original_artist = parent_data.get('artist', '')
      self._edits.setdefault(str(track_rec.path), {})['reassign_artist'] = new_artist
      self._edits.setdefault(str(track_rec.path), {})['original_artist'] = original_artist
      ```
    - Append the `track_rec` to `dest_tracks` and make the child in `dest_item`.
  - Clean up parent items: check all modified parents. If a parent has `len(tracks) == 0`, remove it from the tree:
    ```python
    top_idx = self._tree.indexOfTopLevelItem(parent_item)
    if top_idx >= 0:
        self._tree.takeTopLevelItem(top_idx)
    ```
  - Call `self._save_edits()` on completion.

---

### 3. Organize View Updates

#### [MODIFY] [organize_view.py](file:///Users/jacebrown/Dropbox/Design/Career/JWBC/Clients/CrateSort/_dev/cratesort/src/gui/organize_view.py)

- Ensure `json` is imported at the top of the file.
- Update `_PlanWorker.run()` to apply the manual artist reassignments to the in-memory `TrackRecord` inventory before building the plan:
  - Load `library_edits.json`.
  - For each `record` in `self._inventory`, check if it has a `'reassign_artist'` edit. If so, mutate the in-memory `record.artist = edit['reassign_artist']`. This ensures that all downstream modules (like file path generation and metadata updates) use the manually corrected artist!
  - Call `session.apply_library_edits()` on the loaded `ClassificationSession` object to keep classifications aligned with the new artist groups.

---

## Verification Steps

1. **Test Single & Multi-Track Reassignment**:
   - Open the Library tab. Select multiple tracks under an artist, right-click, and select "Reassign Artist". Verify that all selected tracks are successfully moved to the new artist group in one go.
   - Relocate the very last track in an artist group. Verify that the empty artist folder immediately disappears from the tree (instead of lingering showing stale counts).
2. **Test Classifier Sync**:
   - Reassign a track to a new artist in the Library tab.
   - Go to the Classifier tab. Verify that the track is correctly displayed under its new artist entry.
3. **Test Organize Sync**:
   - Reassign a track's artist in the Library tab.
   - Go to the Organize tab and let it build the plan.
   - Verify that the plan proposes moving the file to the correct new artist folder under its genre.
