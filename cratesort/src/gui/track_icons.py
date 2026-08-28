"""
The three glyphs a track row shows in its leading icon slot, shared by the
Library tree and the Crates track table so both screens read identically:

    note_icon()  — resting state, not the loaded track
    play_icon()  — hover on any row, or the loaded-but-paused track
    pause_icon() — the row whose track is currently playing

Each is a 9x14 QIcon with a Normal (cream/orange) and Selected (dark) pixmap
so it stays legible on an orange selection bar. Module-cached — build once.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPixmap,
    QPolygonF,
)

_W, _H = 9, 14
_MUTED    = '#a89b85'   # resting note
_ACCENT   = '#D17D34'   # play / pause — the actionable states
_SELECTED = '#2F2F2F'   # on the orange selection bar


def _blank() -> QPixmap:
    pm = QPixmap(_W, _H)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def _note_pm(color: str) -> QPixmap:
    pm = _blank()
    p = QPainter(pm)
    f = p.font()
    f.setPixelSize(12)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, '♪')
    p.end()
    return pm


def _play_pm(color: str) -> QPixmap:
    pm = _blank()
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(1.5, 2), QPointF(1.5, 12), QPointF(8, 7)]))
    p.end()
    return pm


def _pause_pm(color: str) -> QPixmap:
    pm = _blank()
    p = QPainter(pm)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawRect(1, 2, 2, 10)
    p.drawRect(6, 2, 2, 10)
    p.end()
    return pm


def _icon(painter, normal: str) -> QIcon:
    ic = QIcon()
    ic.addPixmap(painter(normal),    QIcon.Mode.Normal)
    ic.addPixmap(painter(_SELECTED), QIcon.Mode.Selected)
    return ic


_CACHE: dict[str, QIcon] = {}


def note_icon() -> QIcon:
    if 'note' not in _CACHE:
        _CACHE['note'] = _icon(_note_pm, _MUTED)
    return _CACHE['note']


def play_icon() -> QIcon:
    if 'play' not in _CACHE:
        _CACHE['play'] = _icon(_play_pm, _ACCENT)
    return _CACHE['play']


def pause_icon() -> QIcon:
    if 'pause' not in _CACHE:
        _CACHE['pause'] = _icon(_pause_pm, _ACCENT)
    return _CACHE['pause']
