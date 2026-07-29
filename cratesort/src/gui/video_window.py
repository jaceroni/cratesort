from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, QSize, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QIcon, QPixmap, QPainter, QColor, QPen
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QFrame

from cratesort.src.gui.theme import C
from cratesort.src.gui.playback_controller import PlaybackController


def _make_close_icon(color: str = '#f1e3c8', size: int = 14) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(size * 0.15)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    from PyQt6.QtCore import QPointF
    m = size * 0.28
    p.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    p.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    p.end()
    return QIcon(pm)


class FloatingVideoWindow(QWidget):
    """Non-modal floating video player. Deliberately NOT a `_CrateSortDialog`
    subclass (overlays.py) — that class's whole model is built around a
    blocking `QDialog.exec()`/`done()`, incompatible with a window that must
    stay open and interactive while the user keeps browsing the library
    underneath. Borrows its visual language and locked animation constants
    (OutBack/InBack, overshoot 3.0, 320ms in / 384ms out) rather than its
    class. Created lazily by MainWindow and reused (hidden, not destroyed)
    across video plays."""

    closed = pyqtSignal()

    def __init__(self, controller: PlaybackController, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._controller = controller
        self._closing = False
        self._drag_offset: Optional[QPoint] = None

        # Dialog, not Tool — Tool-styled windows on macOS hide themselves
        # whenever the app loses focus, which read as "the video randomly
        # disappeared." Dialog stays visible when you click into another app,
        # same as any of this app's other non-modal windows. Stays on top of
        # every other desktop window while popped out, per spec.
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(640, 420)
        # Freely resizable, no aspect lock — an earlier attempt to lock/
        # auto-fit to the video's aspect ratio during drag-resize caused
        # visible jitter and still didn't reliably eliminate letterboxing
        # across different files, so it was reverted. QVideoWidget's own
        # KeepAspectRatio mode still letterboxes/pillarboxes correctly
        # within whatever size the window is.

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QFrame()
        container.setObjectName('video_container')
        container.setStyleSheet(
            f'#video_container {{ background-color: {C["bg_panel"]}; '
            f'border: 1px solid {C["border"]}; border-radius: 12px; }}'
        )
        outer.addWidget(container)

        cl = QVBoxLayout(container)
        cl.setContentsMargins(1, 1, 1, 1)
        cl.setSpacing(0)

        title_strip = QWidget()
        title_strip.setFixedHeight(32)
        title_strip.setStyleSheet('background: transparent;')
        tl = QHBoxLayout(title_strip)
        tl.setContentsMargins(12, 0, 8, 0)
        self._title_label = QLabel('')
        self._title_label.setStyleSheet(f'color: {C["text_muted"]}; font-size: 12px; background: transparent;')
        tl.addWidget(self._title_label)
        tl.addStretch()
        close_btn = QToolButton()
        close_btn.setIcon(_make_close_icon(size=11))
        close_btn.setIconSize(QSize(11, 11))
        close_btn.setFixedSize(21, 21)
        close_btn.setAutoRaise(True)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            'QToolButton { background: rgba(255,255,255,0.1); border: none; '
            'border-radius: 10px; padding: 0; margin: 0; }'
            f'QToolButton:hover {{ background: {C["error"]}; }}'
        )
        close_btn.setToolTip('Close')
        close_btn.clicked.connect(self.close)
        tl.addWidget(close_btn)
        cl.addWidget(title_strip)

        video_area = QWidget()
        video_area.setStyleSheet('background: black;')
        va_layout = QVBoxLayout(video_area)
        va_layout.setContentsMargins(0, 0, 0, 0)

        self._video_widget = QVideoWidget(video_area)
        self._video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._video_widget.videoSink().videoFrameChanged.connect(self._on_frame)
        va_layout.addWidget(self._video_widget)

        # Same ♪ placeholder as the sidebar art panel and inline video panel,
        # shown until a real frame arrives.
        self._note_label = QLabel('♪', video_area)
        self._note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._note_label.setStyleSheet('QLabel { background: #222222; color: #444444; font-size: 48px; }')
        self._note_label.raise_()

        cl.addWidget(video_area, stretch=1)

        title_strip.mousePressEvent = self._title_mouse_press
        title_strip.mouseMoveEvent = self._title_mouse_move

    def _on_frame(self, frame) -> None:
        self._note_label.setVisible(not frame.isValid())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._note_label.setGeometry(self._video_widget.geometry())

    # ── Drag-to-move via the title strip (frameless window) ─────────────

    def _title_mouse_press(self, event: QMouseEvent) -> None:
        self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def _title_mouse_move(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    # ── Public API ────────────────────────────────────────────────────

    def show_for_playback(self) -> None:
        rec = self._controller.current_track
        if rec is not None:
            self._title_label.setText(rec.title or rec.filename)
        self._controller.set_video_output(self._video_widget)

        if self.isVisible():
            self.raise_()
        else:
            self.show()

    # ── Entrance/exit animation (mirrors _CrateSortDialog's constants) ──

    def showEvent(self, event) -> None:
        w, h = self.width(), self.height()

        # Center over the main window every time, rather than wherever Qt
        # (or a previous drag) last left it — mirrors _CrateSortDialog's
        # centering so it never opens unnoticed in a screen corner.
        parent = self.parentWidget()
        if parent is not None:
            origin = parent.mapToGlobal(QPoint(0, 0))
            cx = origin.x() + (parent.width() - w) // 2
            cy = origin.y() + (parent.height() - h) // 2
        else:
            g = self.geometry()
            cx, cy = g.x(), g.y()

        target_rect = QRect(cx, cy, w, h)
        sw, sh = int(w * 0.7), int(h * 0.7)
        start_rect = QRect(cx + (w - sw) // 2, cy + (h - sh) // 2, sw, sh)

        self.setGeometry(start_rect)
        super().showEvent(event)

        curve = QEasingCurve(QEasingCurve.Type.OutBack)
        curve.setOvershoot(3.0)
        self._anim = QPropertyAnimation(self, b'geometry')
        self._anim.setDuration(320)
        self._anim.setStartValue(start_rect)
        self._anim.setEndValue(target_rect)
        self._anim.setEasingCurve(curve)
        self._anim.start()

    def closeEvent(self, event) -> None:
        # Never actually let Qt destroy/close the window for real — we hide
        # it ourselves once the exit animation finishes, so it can be reused
        # for the next video without rebuilding it.
        event.ignore()
        if self._closing:
            return
        self._closing = True

        if self._controller.is_playing():
            self._controller.toggle_play_pause()

        current_rect = self.geometry()
        w, h = current_rect.width(), current_rect.height()
        cx, cy = current_rect.x() + w // 2, current_rect.y() + h // 2
        sw, sh = int(w * 0.7), int(h * 0.7)
        end_rect = QRect(cx - sw // 2, cy - sh // 2, sw, sh)

        curve = QEasingCurve(QEasingCurve.Type.InBack)
        curve.setOvershoot(3.0)
        self._exit_anim = QPropertyAnimation(self, b'geometry')
        self._exit_anim.setDuration(384)  # 320 * 1.2 — exit always slower than entrance
        self._exit_anim.setStartValue(current_rect)
        self._exit_anim.setEndValue(end_rect)
        self._exit_anim.setEasingCurve(curve)
        self._exit_anim.finished.connect(self._finish_close)
        self._exit_anim.start()

    def _finish_close(self) -> None:
        self.hide()
        self._closing = False
        self.closed.emit()
