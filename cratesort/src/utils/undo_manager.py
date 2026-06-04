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
    def __init__(self, view, crate_path: str, track_paths: list[str], crate_name: str):
        self.view        = view
        self.crate_path  = crate_path
        self.track_paths = list(track_paths)
        self.description = f'Added {len(track_paths)} track(s) to {crate_name}'

    def execute(self) -> None:
        w = self.view._writer()
        if w:
            w.add_tracks(self.crate_path, self.track_paths)
        self.view._refresh(select=self.crate_path)

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
