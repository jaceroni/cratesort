from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPixmap, QPolygonF, QPen, QRegion
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSlider, QToolButton, QVBoxLayout, QWidget

from cratesort.src.gui.theme import C, empty_artwork_pixmap, RoundedCornerOverlay
from cratesort.src.gui.library_browser import _fmt_dur
from cratesort.src.gui.playback_controller import PlaybackController

_MUTED = C['text_muted']
_CREAM = C['text']


def _make_play_icon(color: str = _CREAM, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    m = size * 0.22
    p.drawPolygon(QPolygonF([QPointF(m, m * 0.55), QPointF(m, size - m * 0.55), QPointF(size - m * 0.65, size / 2)]))
    p.end()
    return QIcon(pm)


def _make_pause_icon(color: str = _CREAM, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    bar_w = size * 0.2
    p.drawRect(int(size * 0.24), int(size * 0.18), int(bar_w), int(size * 0.64))
    p.drawRect(int(size * 0.56), int(size * 0.18), int(bar_w), int(size * 0.64))
    p.end()
    return QIcon(pm)


def _make_skip_icon(forward: bool, color: str = _MUTED, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))
    m = size * 0.18
    if forward:
        p.drawPolygon(QPolygonF([QPointF(m, m), QPointF(m, size - m), QPointF(size * 0.5, size / 2)]))
        p.drawPolygon(QPolygonF([QPointF(size * 0.5, m), QPointF(size * 0.5, size - m), QPointF(size - m * 1.6, size / 2)]))
        p.drawRect(int(size - m * 1.2), int(m), int(size * 0.08), int(size - 2 * m))
    else:
        p.drawPolygon(QPolygonF([QPointF(size - m, m), QPointF(size - m, size - m), QPointF(size * 0.5, size / 2)]))
        p.drawPolygon(QPolygonF([QPointF(size * 0.5, m), QPointF(size * 0.5, size - m), QPointF(m * 1.6, size / 2)]))
        p.drawRect(int(m * 0.6), int(m), int(size * 0.08), int(size - 2 * m))
    p.end()
    return QIcon(pm)


def _make_volume_icon(muted: bool = False, color: str = _MUTED, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))

    # Speaker cone: body + flared triangle, vertically centered with margin
    # on all sides so nothing hugs (or gets clipped at) the pixmap edge.
    body_w, body_h = size * 0.16, size * 0.26
    body_x, body_y = size * 0.14, (size - body_h) / 2
    p.drawRect(QRectF(body_x, body_y, body_w, body_h))
    cone_tip_x = size * 0.5
    p.drawPolygon(QPolygonF([
        QPointF(body_x + body_w, body_y),
        QPointF(cone_tip_x, size * 0.2),
        QPointF(cone_tip_x, size * 0.8),
        QPointF(body_x + body_w, body_y + body_h),
    ]))

    pen = QPen(QColor(color))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    if muted:
        pen.setWidthF(size * 0.09)
        p.setPen(pen)
        m = size * 0.62
        p.drawLine(QPointF(m, size * 0.3), QPointF(size * 0.86, size * 0.7))
        p.drawLine(QPointF(size * 0.86, size * 0.3), QPointF(m, size * 0.7))
    else:
        pen.setWidthF(size * 0.08)
        p.setPen(pen)
        p.drawArc(QRectF(size * 0.58, size * 0.22, size * 0.3, size * 0.56), -55 * 16, 110 * 16)
        p.drawArc(QRectF(size * 0.68, size * 0.34, size * 0.16, size * 0.32), -55 * 16, 110 * 16)
    p.end()
    return QIcon(pm)


class PlaybackBar(QWidget):
    """Persistent bottom transport bar — global MainWindow chrome, survives
    tab switches. Pure view over a PlaybackController: owns no QMediaPlayer
    itself. Hidden until the first track plays (never shown on the
    welcome/dashboard screen with nothing loaded). Emits
    `skip_previous_requested`/`skip_next_requested` upward since it has no
    concept of the track tree; everything else (play/pause, seek, volume) it
    drives directly on the controller it was constructed with."""

    skip_previous_requested = pyqtSignal()
    skip_next_requested     = pyqtSignal()

    _ICON_SIZE = QSize(16, 16)

    def __init__(self, controller: PlaybackController, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._scrubbing  = False
        self.setFixedHeight(96)
        self.setObjectName('playback_bar')
        self.setStyleSheet(
            f'#playback_bar {{ background: {C["bg_panel"]}; border-top: 1px solid {C["border"]}; }}'
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(14)

        # ── Left: art + title/artist ────────────────────────────────
        self._art_label = QLabel()
        self._art_label.setFixedSize(56, 56)
        self._art_label.setStyleSheet(f'background: {C["bg_input"]}; border: none;')
        self._art_label.setScaledContents(True)
        self._art_label.setPixmap(empty_artwork_pixmap(54))
        root.addWidget(self._art_label)

        # QSS border-radius only rounds the label's background — the pixmap
        # drawn on top (art or the empty-artwork placeholder) is a plain
        # square and isn't clipped by it. setMask() clips the label's actual
        # rendering at the window level (unlike an alpha-painted overlay, it
        # can't be affected by paint-order/compositing timing), and the
        # overlay on top of it still draws the border stroke.
        _ART_RADIUS = 4
        mask_path = QPainterPath()
        mask_path.addRoundedRect(QRectF(0, 0, 56, 56), _ART_RADIUS, _ART_RADIUS)
        self._art_label.setMask(QRegion(mask_path.toFillPolygon().toPolygon()))

        self._art_corner_overlay = RoundedCornerOverlay(
            C['bg_panel'], _ART_RADIUS, border_color=C['border'], parent=self._art_label
        )
        self._art_corner_overlay.setGeometry(0, 0, 56, 56)
        self._art_corner_overlay.raise_()

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.addStretch()
        self._title_label = QLabel('Nothing playing')
        self._title_label.setStyleSheet(f'color: {C["text"]}; font-size: 13px; font-weight: 600; background: transparent;')
        self._artist_label = QLabel('')
        self._artist_label.setStyleSheet(f'color: {C["text_muted"]}; font-size: 12px; background: transparent;')
        info_col.addWidget(self._title_label)
        info_col.addWidget(self._artist_label)
        info_col.addStretch()
        info_col_wrap = QWidget()
        info_col_wrap.setLayout(info_col)
        info_col_wrap.setFixedWidth(180)
        root.addWidget(info_col_wrap)

        # ── Center: transport (row 1) + scrubber/volume (row 2) ─────
        center = QVBoxLayout()
        center.setSpacing(8)
        center.addStretch()

        transport = QHBoxLayout()
        transport.setSpacing(12)
        transport.addStretch()

        self._back_btn = self._make_tool_button(_make_skip_icon(forward=False), size=28)
        self._back_btn.clicked.connect(self.skip_previous_requested.emit)
        transport.addWidget(self._back_btn)

        self._play_btn = QToolButton()
        self._play_btn.setIcon(_make_play_icon())
        self._play_btn.setIconSize(self._ICON_SIZE)
        self._play_btn.setFixedSize(40, 40)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setStyleSheet(
            f'QToolButton {{ background: {C["orange"]}; border: none; border-radius: 20px; padding: 0; }}'
            f'QToolButton:hover {{ background: {C["orange_hover"]}; }}'
            f'QToolButton:pressed {{ background: {C["orange_press"]}; }}'
        )
        self._play_btn.clicked.connect(self._controller.toggle_play_pause)
        transport.addWidget(self._play_btn)

        self._fwd_btn = self._make_tool_button(_make_skip_icon(forward=True), size=28)
        self._fwd_btn.clicked.connect(self.skip_next_requested.emit)
        transport.addWidget(self._fwd_btn)
        transport.addStretch()
        center.addLayout(transport)

        # Scrubber + volume share one row so they sit on the same baseline.
        scrub_row = QHBoxLayout()
        scrub_row.setSpacing(8)
        self._elapsed_label = QLabel('0:00')
        self._elapsed_label.setStyleSheet(f'color: {C["text_muted"]}; font-size: 11px; background: transparent;')
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setRange(0, 0)
        self._style_slider(self._scrubber)
        self._scrubber.sliderPressed.connect(self._on_scrub_start)
        self._scrubber.sliderReleased.connect(self._on_scrub_end)
        self._total_label = QLabel('—')
        self._total_label.setStyleSheet(f'color: {C["text_muted"]}; font-size: 11px; background: transparent;')

        self._mute_btn = self._make_tool_button(_make_volume_icon(muted=False), size=22)
        self._mute_btn.clicked.connect(self._on_mute_clicked)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(80)
        self._style_slider(self._volume_slider)
        self._volume_slider.valueChanged.connect(self._controller.set_volume)

        scrub_row.addWidget(self._elapsed_label)
        scrub_row.addWidget(self._scrubber, stretch=1)
        scrub_row.addWidget(self._total_label)
        scrub_row.addSpacing(10)
        scrub_row.addWidget(self._mute_btn)
        scrub_row.addWidget(self._volume_slider)
        center.addLayout(scrub_row)
        center.addStretch()

        root.addLayout(center, stretch=1)

        self._controller.set_volume(80)

        # ── Wire controller → bar ────────────────────────────────────
        self._controller.position_changed.connect(self._on_position_changed)
        self._controller.duration_changed.connect(self._on_duration_changed)
        self._controller.playback_state_changed.connect(self._on_playback_state_changed)
        self._controller.now_playing_changed.connect(self._on_now_playing_changed)

        # Hidden until the first track plays — never appears on the welcome/
        # dashboard screen with nothing loaded.
        self.setVisible(False)

    # ── Styling helpers ──────────────────────────────────────────────

    def _make_tool_button(self, icon: QIcon, size: int) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(icon)
        btn.setIconSize(self._ICON_SIZE)
        btn.setFixedSize(size, size)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAutoRaise(True)
        btn.setStyleSheet(
            f'QToolButton {{ background: transparent; border: none; border-radius: {size // 2}px; padding: 0; }}'
            f'QToolButton:hover {{ background: {C["bg_hover"]}; }}'
        )
        return btn

    def _style_slider(self, slider: QSlider) -> None:
        slider.setFixedHeight(16)
        slider.setStyleSheet(
            f'QSlider::groove:horizontal {{ height: 3px; background: {C["border"]}; border-radius: 1px; }}'
            f'QSlider::sub-page:horizontal {{ height: 3px; background: {C["orange"]}; border-radius: 1px; }}'
            f'QSlider::handle:horizontal {{ width: 10px; height: 10px; margin: -4px 0; '
            f'background: {C["text"]}; border-radius: 5px; }}'
        )

    # ── Controller → UI ──────────────────────────────────────────────

    def _on_now_playing_changed(self, rec) -> None:
        self.setVisible(True)
        self.setEnabled(True)
        self._title_label.setText(rec.title or rec.filename)
        self._artist_label.setText(rec.artist or '')
        if rec.duration:
            self._scrubber.setRange(0, int(rec.duration * 1000))
            self._total_label.setText(_fmt_dur(rec.duration))

    def set_now_playing_art(self, pixmap) -> None:
        if pixmap is not None and not pixmap.isNull():
            self._art_label.setPixmap(pixmap)
        else:
            self._art_label.setPixmap(empty_artwork_pixmap(54))

    def _on_position_changed(self, ms: int) -> None:
        if not self._scrubbing:
            self._scrubber.setValue(ms)
        self._elapsed_label.setText(_fmt_dur(ms / 1000))

    def _on_duration_changed(self, ms: int) -> None:
        if ms > 0:
            self._scrubber.setRange(0, ms)
            self._total_label.setText(_fmt_dur(ms / 1000))

    def _on_playback_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play_btn.setIcon(_make_pause_icon() if playing else _make_play_icon())

    # ── UI → controller ──────────────────────────────────────────────

    def _on_scrub_start(self) -> None:
        self._scrubbing = True

    def _on_scrub_end(self) -> None:
        self._scrubbing = False
        self._controller.seek(self._scrubber.value())

    def _on_mute_clicked(self) -> None:
        muted = not self._controller.is_muted()
        self._controller.set_muted(muted)
        self._mute_btn.setIcon(_make_volume_icon(muted=muted))
