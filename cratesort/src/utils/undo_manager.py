from __future__ import annotations
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Command:
    """Base class for all undoable crate actions."""
    description: str = ''
    source_tab:  str = 'crates'

    def execute(self) -> None: ...
    def undo(self)    -> None: ...


class UndoManager:
    MAX_STATES = 10

    def __init__(self, on_change: Optional[Callable] = None):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._on_change  = on_change or (lambda: None)

    def push(self, command: Command) -> None:
        command.execute()
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.MAX_STATES:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._on_change()

    def undo(self) -> Optional[str]:
        if not self._undo_stack:
            return None
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._on_change()
        return f'Undone: {cmd.description}'

    def redo(self) -> Optional[str]:
        if not self._redo_stack:
            return None
        cmd = self._redo_stack.pop()
        cmd.execute()
        self._undo_stack.append(cmd)
        self._on_change()
        return f'Redone: {cmd.description}'

    def can_undo(self) -> bool: return bool(self._undo_stack)
    def can_redo(self) -> bool: return bool(self._redo_stack)

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._on_change()


# ---------------------------------------------------------------------------
# Concrete command classes
# ---------------------------------------------------------------------------

class AddTracksCommand(Command):
    def __init__(
        self,
        view,
        crate_path: str,
        track_paths: list[str],
        crate_name: str,
        stay_on_crate: Optional[str] = None,
    ):
        self.view          = view
        self.crate_path    = crate_path
        self.track_paths   = list(track_paths)
        self.stay_on_crate = stay_on_crate  # if set, execute() keeps this crate selected
        self.description   = f'Added {len(track_paths)} track(s) to {crate_name}'

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.add_tracks(self.crate_path, self.track_paths)
        self.view._refresh(select=self.stay_on_crate or self.crate_path)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.remove_tracks(self.crate_path, self.track_paths)
        self.view._refresh(select=self.crate_path)


class RemoveTracksCommand(Command):
    def __init__(self, view, crate_path: str, track_paths: list[str], crate_name: str):
        self.view        = view
        self.crate_path  = crate_path
        self.track_paths = list(track_paths)
        self.description = f'Removed {len(track_paths)} track(s) from {crate_name}'

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.remove_tracks(self.crate_path, self.track_paths)
        self.view._refresh(select=self.crate_path)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.add_tracks(self.crate_path, self.track_paths)
        self.view._refresh(select=self.crate_path)


class ReorderTracksCommand(Command):
    def __init__(self, view, crate_path: str, old_order: list[str], new_order: list[str], crate_name: str):
        self.view        = view
        self.crate_path  = crate_path
        self.old_order   = list(old_order)
        self.new_order   = list(new_order)
        self.description = f'Reordered tracks in {crate_name}'

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.reorder_tracks(self.crate_path, self.new_order)
        self.view._refresh(select=self.crate_path)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.reorder_tracks(self.crate_path, self.old_order)
        self.view._refresh(select=self.crate_path)


class CreateCrateCommand(Command):
    def __init__(self, view, crate_path: str, crate_name: str):
        self.view        = view
        self.crate_path  = crate_path
        self.crate_name  = crate_name
        self.description = f"Created crate '{crate_name}'"

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.create_crate(self.crate_path)
        self.view._refresh(select=self.crate_path)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.delete_crate(self.crate_path)
        self.view._refresh(select=None)


class DeleteCrateCommand(Command):
    def __init__(self, view, crate_path: str, crate_name: str, track_paths: list[str]):
        self.view        = view
        self.crate_path  = crate_path
        self.crate_name  = crate_name
        self.track_paths = list(track_paths)
        self.description = f"Deleted crate '{crate_name}'"

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.delete_crate(self.crate_path)
        self.view._crate_order = {
            k: [p for p in v if p != self.crate_path]
            for k, v in self.view._crate_order.items()
        }
        self.view._save_crate_order()
        self.view._current_crate_path = '__ALL_TRACKS__'
        self.view._refresh(select='__ALL_TRACKS__')

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.create_crate(self.crate_path, self.track_paths)
        self.view._refresh(select=self.crate_path)


class RenameCrateCommand(Command):
    def __init__(self, view, old_path: str, new_path: str, old_name: str, new_name: str):
        self.view        = view
        self.old_path    = old_path
        self.new_path    = new_path
        self.old_name    = old_name
        self.new_name    = new_name
        self.description = f"Renamed '{old_name}' to '{new_name}'"

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.rename_crate(self.old_path, self.new_path)
        self.view._crate_order = {
            k: [self.new_path if p == self.old_path else p for p in v]
            for k, v in self.view._crate_order.items()
        }
        self.view._save_crate_order()
        self.view._refresh(select=self.new_path)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.rename_crate(self.new_path, self.old_path)
        self.view._crate_order = {
            k: [self.old_path if p == self.new_path else p for p in v]
            for k, v in self.view._crate_order.items()
        }
        self.view._save_crate_order()
        self.view._refresh(select=self.old_path)


class CreateSmartCrateCommand(Command):
    def __init__(self, view, name: str, rules: list, match_all: bool, live_update: bool, tracks: list[str]):
        self.view        = view
        self.name        = name
        self.rules       = list(rules)
        self.match_all   = match_all
        self.live_update = live_update
        self.tracks      = list(tracks)
        self.description = f"Created smart crate '{name}'"

    def execute(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.create(self.name, self.rules, self.match_all, self.live_update, self.tracks)
        self.view._refresh(select=self.view._smart_crate_key(self.name))

    def undo(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.delete(self.name)
        self.view._refresh(select=None)


class DuplicateSmartCrateCommand(Command):
    """Undoable duplicate — captures the source crate's rules/tracks at the
    moment of duplication rather than re-reading the source file on redo, so
    redo is deterministic even if the source crate changes or is deleted."""

    def __init__(
        self, view, source_name: str, new_name: str,
        rules: list, match_all: bool, live_update: bool, tracks: list[str],
    ):
        self.view        = view
        self.source_name = source_name
        self.new_name    = new_name
        self.rules       = list(rules)
        self.match_all   = match_all
        self.live_update = live_update
        self.tracks      = list(tracks)
        self.description = f"Duplicated '{source_name}' as '{new_name}'"

    def execute(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.create(self.new_name, self.rules, self.match_all, self.live_update, self.tracks)
        self.view._refresh(select=self.view._smart_crate_key(self.new_name))

    def undo(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.delete(self.new_name)
        self.view._refresh(select=None)


class UpdateSmartCrateRulesCommand(Command):
    def __init__(
        self, view, name: str,
        old_rules: list, old_match_all: bool, old_live_update: bool, old_tracks: list[str],
        new_rules: list, new_match_all: bool, new_live_update: bool, new_tracks: list[str],
    ):
        self.view            = view
        self.name            = name
        self.old_rules       = list(old_rules)
        self.old_match_all   = old_match_all
        self.old_live_update = old_live_update
        self.old_tracks      = list(old_tracks)
        self.new_rules       = list(new_rules)
        self.new_match_all   = new_match_all
        self.new_live_update = new_live_update
        self.new_tracks      = list(new_tracks)
        self.description     = f"Edited rules on '{name}'"

    def execute(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.update(self.name, self.new_rules, self.new_match_all, self.new_live_update, self.new_tracks)
        self.view._refresh(select=self.view._smart_crate_key(self.name))

    def undo(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.update(self.name, self.old_rules, self.old_match_all, self.old_live_update, self.old_tracks)
        self.view._refresh(select=self.view._smart_crate_key(self.name))


class DeleteSmartCrateCommand(Command):
    def __init__(self, view, name: str, rules: list, match_all: bool, live_update: bool, tracks: list[str]):
        self.view        = view
        self.name        = name
        self.rules       = list(rules)
        self.match_all   = match_all
        self.live_update = live_update
        self.tracks      = list(tracks)
        self.description = f"Deleted smart crate '{name}'"

    def execute(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.delete(self.name)
        self.view._current_crate_path = '__ALL_TRACKS__'
        self.view._refresh(select='__ALL_TRACKS__')

    def undo(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.create(self.name, self.rules, self.match_all, self.live_update, self.tracks)
        self.view._refresh(select=self.view._smart_crate_key(self.name))


class RenameSmartCrateCommand(Command):
    def __init__(self, view, old_name: str, new_name: str):
        self.view        = view
        self.old_name     = old_name
        self.new_name     = new_name
        self.description = f"Renamed '{old_name}' to '{new_name}'"

    def execute(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.rename(self.old_name, self.new_name)
        self.view._refresh(select=self.view._smart_crate_key(self.new_name))

    def undo(self) -> None:
        w = self.view._smart_writer()
        if w:
            w.rename(self.new_name, self.old_name)
        self.view._refresh(select=self.view._smart_crate_key(self.old_name))


class ReorderCratesCommand(Command):
    def __init__(self, view, order_key: str, old_order: list[str], new_order: list[str]):
        self.view      = view
        self.order_key = order_key
        self.old_order = list(old_order)
        self.new_order = list(new_order)
        self.description = 'Reordered crates'

    def execute(self) -> None:
        self.view._crate_order[self.order_key] = list(self.new_order)
        self.view._save_crate_order()
        self.view._refresh(select=self.view._current_crate_path)

    def undo(self) -> None:
        self.view._crate_order[self.order_key] = list(self.old_order)
        self.view._save_crate_order()
        self.view._refresh(select=self.view._current_crate_path)


class EditTrackMetadataCommand(Command):
    """Undoable in-place track metadata edit (title, album, tags, BPM, year, comment)."""
    source_tab = 'crates'

    def __init__(
        self,
        view,
        file_path: str,
        field: str,
        field_col: int,
        old_val: str,
        new_val: str,
        crate_path: Optional[str] = None,
    ):
        self.view       = view
        self.file_path  = file_path
        self.field      = field
        self.field_col  = field_col
        self.old_val    = old_val
        self.new_val    = new_val
        self.crate_path = crate_path
        self.description = f"Edited {field} on '{file_path.rsplit('/', 1)[-1]}'"

    def _apply(self, val: str) -> None:
        self.view._edits.setdefault(self.file_path, {})[self.field] = val
        self.view._save_edits()

        if self.crate_path and self.view._current_crate_path != self.crate_path:
            # Not viewing the crate this edit belongs to — navigate back to it.
            # The async load picks up the just-saved edit, so no manual patch needed.
            self.view._refresh(select=self.crate_path)
            return

        # Already on the right crate — patch immediately for instant feedback
        table = self.view._track_table
        for r in range(table.rowCount()):
            path_cell = table.item(r, 13)  # TC_PATH = 13
            if path_cell and path_cell.text() == self.file_path:
                cell = table.item(r, self.field_col)
                if cell:
                    cell.setText(val)
                self.view._flash_row(r)
                break

    def execute(self) -> None:
        self._apply(self.new_val)

    def undo(self) -> None:
        self._apply(self.old_val)


class ReparentCrateCommand(Command):
    def __init__(self, view, drag_path: str, new_parent_path: str):
        self.view           = view
        self.drag_path      = drag_path
        self.crate_name     = drag_path.split('/')[-1]
        self.old_parent     = '/'.join(drag_path.split('/')[:-1]) if '/' in drag_path else ''
        self.new_parent     = new_parent_path
        self.new_path       = f'{new_parent_path}/{self.crate_name}'
        self.description    = f"Moved '{self.crate_name}' into {new_parent_path.split('/')[-1]}"

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.rename_crate(self.drag_path, self.new_path)
        self.view._refresh(select=self.new_path)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.rename_crate(self.new_path, self.drag_path)
        self.view._refresh(select=self.drag_path)


class PromoteCrateCommand(Command):
    """Undoable: promote a nested crate to the top level — renames the crate
    file, removes it from its old parent's sibling order, and inserts it into
    the top-level order, all as one atomic action."""
    source_tab = 'crates'

    def __init__(
        self, view, drag_path: str, crate_name: str,
        old_parent_key: str, old_parent_order: list, new_top_order: list,
    ):
        self.view             = view
        self.drag_path        = drag_path         # e.g. "Parent/Sub"
        self.crate_name       = crate_name        # e.g. "Sub"
        self.old_parent_key   = old_parent_key    # e.g. "Parent"
        self.old_parent_order = list(old_parent_order)  # old parent's sibling order, drag_path present
        self.new_top_order    = list(new_top_order)     # top-level order, crate_name present
        self.description      = f"Moved '{crate_name}' to top level"

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.rename_crate(self.drag_path, self.crate_name)
        if self.old_parent_key in self.view._crate_order:
            self.view._crate_order[self.old_parent_key] = [
                p for p in self.view._crate_order[self.old_parent_key] if p != self.drag_path
            ]
        self.view._crate_order[''] = list(self.new_top_order)
        self.view._save_crate_order()
        self.view._refresh(select=self.crate_name)

    def undo(self) -> None:
        w = self.view._writer()
        if w:
            w.rename_crate(self.crate_name, self.drag_path)
        self.view._crate_order[''] = [
            p for p in self.view._crate_order.get('', []) if p != self.crate_name
        ]
        self.view._crate_order[self.old_parent_key] = list(self.old_parent_order)
        self.view._save_crate_order()
        self.view._refresh(select=self.drag_path)


class CrateGenreChangeCommand(Command):
    """Undoable genre change for one or more tracks within a crate."""
    source_tab = 'crates'

    def __init__(self, view, crate_path: Optional[str], old_genres: dict, new_genre: str, label: str):
        self.view       = view
        self.crate_path = crate_path
        self.old_genres = dict(old_genres)  # file_path -> prior genre or None
        self.new_genre  = new_genre
        self.description = f"Changed genre on '{label}' to {new_genre}"

    def execute(self) -> None:
        self.view._apply_crate_genre(self.crate_path, {k: self.new_genre for k in self.old_genres})

    def undo(self) -> None:
        self.view._apply_crate_genre(self.crate_path, dict(self.old_genres))


class CrateTagsEditCommand(Command):
    """Undoable style-tags edit for a single track within a crate."""
    source_tab = 'crates'

    def __init__(self, view, crate_path: Optional[str], file_path: str, label: str, old_tags: str, new_tags: str):
        self.view       = view
        self.crate_path = crate_path
        self.file_path  = file_path
        self.old_tags   = old_tags
        self.new_tags   = new_tags
        self.description = f"Edited tags on '{label}'"

    def execute(self) -> None:
        self.view._apply_crate_tags(self.crate_path, self.file_path, self.new_tags)

    def undo(self) -> None:
        self.view._apply_crate_tags(self.crate_path, self.file_path, self.old_tags)


class CrateReassignArtistCommand(Command):
    """Undoable artist reassignment for a single track within a crate."""
    source_tab = 'crates'

    def __init__(
        self, view, crate_path: Optional[str], file_path: str, label: str,
        old_artist: Optional[str], new_artist: str,
    ):
        self.view       = view
        self.crate_path = crate_path
        self.file_path  = file_path
        self.old_artist = old_artist
        self.new_artist = new_artist
        self.description = f"Reassigned '{label}' to {new_artist}"

    def execute(self) -> None:
        self.view._apply_crate_reassign(self.crate_path, {self.file_path: self.new_artist})

    def undo(self) -> None:
        self.view._apply_crate_reassign(self.crate_path, {self.file_path: self.old_artist})


# ---------------------------------------------------------------------------
# Library-tab commands
# ---------------------------------------------------------------------------

class LibraryFieldEditCommand(Command):
    """Undoable inline edit of a single track field (title/album/bpm/year/comment/tags)."""
    source_tab = 'library'

    def __init__(self, view, file_path: str, field: str, old_val: str, new_val: str):
        self.view        = view
        self.file_path    = file_path
        self.field        = field
        self.old_val      = old_val
        self.new_val      = new_val
        self.description  = f"Edited {field} on '{file_path.rsplit('/', 1)[-1]}'"

    def execute(self) -> None:
        self.view._apply_library_field(self.file_path, self.field, self.new_val)

    def undo(self) -> None:
        self.view._apply_library_field(self.file_path, self.field, self.old_val)


class LibraryTagsEditCommand(Command):
    """Undoable style-tags edit for a track or artist in the Library view."""
    source_tab = 'library'

    def __init__(self, view, key: str, label: str, old_tags: str, new_tags: str):
        self.view        = view
        self.key         = key
        self.old_tags    = old_tags
        self.new_tags    = new_tags
        self.description = f"Edited tags on '{label}'"

    def execute(self) -> None:
        self.view._apply_library_tags(self.key, self.new_tags)

    def undo(self) -> None:
        self.view._apply_library_tags(self.key, self.old_tags)


class LibraryGenreChangeCommand(Command):
    """Undoable genre reassignment — covers single-track, sibling-selection,
    artist-level, and bulk mixed-selection genre changes in the Library view."""
    source_tab = 'library'

    def __init__(self, view, old_edits: dict, new_genre: str, disk_old: dict, label: str):
        self.view       = view
        self.old_edits  = dict(old_edits)   # key (path or __artist__X) -> prior genre or None
        self.new_genre  = new_genre
        self.disk_old   = dict(disk_old)    # file_path -> prior on-disk genre
        self.description = f"Changed genre on '{label}' to {new_genre}"

    def execute(self) -> None:
        edits_map = {k: self.new_genre for k in self.old_edits}
        disk_map  = {p: self.new_genre for p in self.disk_old}
        self.view._apply_library_genre(edits_map, disk_map)

    def undo(self) -> None:
        self.view._apply_library_genre(dict(self.old_edits), dict(self.disk_old))


class LibraryReassignArtistCommand(Command):
    """Undoable move of one or more tracks to a different artist group."""
    source_tab = 'library'

    def __init__(self, view, moves: dict, new_artist: str, label: str):
        self.view       = view
        self.moves      = moves   # file_path -> {'prior_edit': dict, 'prior_disk_artist': str, 'group_artist': str}
        self.new_artist = new_artist
        n = len(moves)
        self.description = (
            f"Reassigned '{label}' to {new_artist}" if n == 1
            else f'Reassigned {n} track(s) to {new_artist}'
        )

    def execute(self) -> None:
        edits_map = {
            path: {**info['prior_edit'], 'reassign_artist': self.new_artist, 'original_artist': info['group_artist']}
            for path, info in self.moves.items()
        }
        disk_map = {path: self.new_artist for path in self.moves}
        self.view._apply_library_reassign(edits_map, disk_map)

    def undo(self) -> None:
        edits_map = {path: dict(info['prior_edit']) for path, info in self.moves.items()}
        disk_map  = {path: info['prior_disk_artist'] for path, info in self.moves.items()}
        self.view._apply_library_reassign(edits_map, disk_map)
