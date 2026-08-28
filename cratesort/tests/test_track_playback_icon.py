"""
The track-row play/pause affordance, shared by the Library tree and the
Crates track table:

  * click the row's icon -> load & play in the bottom player
  * click it again      -> pause (NOT restart)
  * click a third time  -> resume
  * the loaded row shows a pause glyph while playing, a play glyph while paused
  * any other row shows a play glyph on hover, a note glyph at rest

Requires a QApplication; skipped if PyQt6 can't start.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import QApplication, QTableWidgetItem

from cratesort.src.core.scanner import TrackRecord
from cratesort.src.gui.playback_controller import PlaybackController
from cratesort.src.gui.track_icons import note_icon, pause_icon, play_icon


def _rec(title: str, artist: str = "ACDC") -> TrackRecord:
    p = Path("/tmp/lib") / artist / f"{title}.mp3"
    return TrackRecord(
        path=p, parent_dir=p.parent, filename=p.name, extension=".mp3",
        file_size=1, is_audio=True, is_video=False, title=title, artist=artist,
    )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_shared_glyphs_are_cached_and_distinct(qapp):
    assert note_icon() is note_icon()
    assert play_icon() is play_icon()
    assert pause_icon() is pause_icon()
    keys = {note_icon().cacheKey(), play_icon().cacheKey(), pause_icon().cacheKey()}
    assert len(keys) == 3


def test_play_or_toggle_routes_same_track_to_toggle_not_reload(qapp):
    # Spy on the two paths — asserting real QMediaPlayer state needs an audio
    # device and a real file, which the headless test box lacks.
    c = PlaybackController()
    a, b = _rec("Highway to Hell"), _rec("Hells Bells")
    calls = []
    c.play = lambda rec: (calls.append(("play", str(rec.path))), setattr(c, "_current_track", rec))
    c.toggle_play_pause = lambda: calls.append(("toggle", None))

    c.play_or_toggle(a)                       # nothing loaded -> play
    c.play_or_toggle(a)                       # same track -> toggle (pause)
    c.play_or_toggle(a)                       # same track -> toggle (resume)
    c.play_or_toggle(b)                       # different track -> play

    assert calls == [
        ("play", str(a.path)),
        ("toggle", None),
        ("toggle", None),
        ("play", str(b.path)),
    ]


def test_library_row_icon_is_three_state(qapp):
    from cratesort.src.gui.library_browser import LibraryBrowserView

    v = LibraryBrowserView(undo_manager=None)
    p = str(_rec("Highway to Hell").path)

    assert v._row_icon_for(p, hovered=False) is note_icon()
    assert v._row_icon_for(p, hovered=True) is play_icon()

    v.set_now_playing(p)
    assert v._row_icon_for(p, hovered=False) is pause_icon()   # playing
    v.set_playing_state(False)
    assert v._row_icon_for(p, hovered=False) is play_icon()    # paused
    v.set_playing_state(True)
    assert v._row_icon_for(p, hovered=False) is pause_icon()


def test_crates_row_icon_is_three_state_and_emits_play_requested(qapp):
    from cratesort.src.gui.crate_manager import CrateManagerView, TC_PATH, TC_TITLE

    rec = _rec("Highway to Hell")
    cm = CrateManagerView(undo_manager=None)
    cm._resolve_track = lambda path: rec if path == str(rec.path) else None

    tbl = cm._track_table
    tbl.setRowCount(1)
    title = QTableWidgetItem(rec.title)
    title.setIcon(note_icon())
    tbl.setItem(0, TC_TITLE, title)
    tbl.setItem(0, TC_PATH, QTableWidgetItem(str(rec.path)))
    qapp.processEvents()

    assert cm._row_icon_for(str(rec.path), hovered=False) is note_icon()
    assert cm._row_icon_for(str(rec.path), hovered=True) is play_icon()

    got = []
    cm.play_requested.connect(got.append)

    from PyQt6.QtCore import QPoint
    r = tbl.visualRect(tbl.model().index(0, TC_TITLE))
    icon_zone = QPoint(r.left() + 6, r.center().y())
    title_far = QPoint(r.left() + 80, r.center().y())

    # Hover is whole-row (matches the Library tree): swaps even far from the icon.
    cm._update_hover_play_icon(title_far)
    assert tbl.item(0, TC_TITLE).icon().cacheKey() == play_icon().cacheKey()
    cm._clear_hover_play_icon()
    assert tbl.item(0, TC_TITLE).icon().cacheKey() == note_icon().cacheKey()

    # Click only plays inside the narrow icon zone.
    assert cm._title_icon_row_at(icon_zone) == 0
    assert cm._title_icon_row_at(title_far) == -1
    assert cm._handle_play_icon_click(title_far) is False
    assert cm._handle_play_icon_click(icon_zone) is True
    assert len(got) == 1 and str(got[0].path) == str(rec.path)

    cm.set_now_playing(str(rec.path))
    assert tbl.item(0, TC_TITLE).icon().cacheKey() == pause_icon().cacheKey()
    cm.set_playing_state(False)
    assert tbl.item(0, TC_TITLE).icon().cacheKey() == play_icon().cacheKey()
