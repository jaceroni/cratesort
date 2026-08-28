from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
from PyQt6.QtCore import Qt, QEvent, QPoint, QPointF, QRect, QRectF, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QLayout, QVBoxLayout, QFrame, QLabel, QPushButton, QHBoxLayout,
    QComboBox, QGraphicsScene, QGraphicsView,
)

try:
    from PyQt6.QtSvgWidgets import QGraphicsSvgItem
    _SVG_AVAILABLE = True
except ImportError:
    _SVG_AVAILABLE = False

_ASSETS = Path(__file__).parent.parent.parent / 'assets'
_MASCOT_SVG = _ASSETS / 'logo' / 'cs-logo-mascot-only.svg'


class _ModalOverlay(QWidget):
    """Semi-opaque overlay that covers the parent window during modals."""

    def __init__(self, parent_window: QWidget):
        super().__init__(parent_window)
        self._parent_window = parent_window
        self._modal: Optional[QWidget] = None
        self.setStyleSheet('background-color: rgba(26, 26, 26, 217);')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setGeometry(parent_window.rect())
        parent_window.installEventFilter(self)
        self.raise_()

    def set_modal(self, modal: QWidget) -> None:
        self._modal = modal

    def center_modal(self) -> None:
        if self._modal is None:
            return
        self._modal.adjustSize()
        mw = self._modal.width()
        mh = self._modal.height()
        origin = self._parent_window.mapToGlobal(QPoint(0, 0))
        cx = origin.x() + (self._parent_window.width()  - mw) // 2
        cy = origin.y() + (self._parent_window.height() - mh) // 2
        self._modal.move(cx, cy)

    def removeFromParent(self) -> None:
        self._parent_window.removeEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._parent_window and event.type() == QEvent.Type.Resize:
            self.setGeometry(self._parent_window.rect())
            self.center_modal()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:
        event.accept()   # block clicks from reaching widgets underneath


class _AnimatedStatCardWidget(QFrame):
    """Smoothly animates a numeric value towards a moving target at 60 fps.
    The one stat-card look used everywhere in CrateSort — the dashboard's
    scanning-phase progress cards, the Library tab's Analyze Library modal,
    and the post-scan "Your Library" summary cards all render from this same
    class so the frame (background, border, centered text) never changes out
    from under the user, only the numbers inside it do.

    Two independent animation modes, since the two contexts drive the number
    differently:
      - update_target(): repeatedly nudges toward a moving target — used
        while a scan/classify pass is live-incrementing counts.
      - start_animation(): a one-shot eased count-up to a fixed final value,
        optionally replayable by clicking the card — used once a total is
        already known (e.g. post-scan summary stats)."""

    def __init__(self, title: str, suffix: str = '', clickable: bool = False, parent=None):
        super().__init__(parent)
        self._current_value = 0
        self._target_value  = 0
        self._suffix        = suffix

        self.setStyleSheet(
            'QFrame { background-color: #1a1a1a; border: 1px solid #444444; '
            'border-radius: 8px; }'
        )
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value_label = QLabel('0' + suffix)
        self._value_label.setProperty('role', 'stat')
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(
            'font-size: 22px; font-weight: 600; color: #f1e3c8; '
            'background: transparent; border: none;'
        )
        layout.addWidget(self._value_label)

        self._title_label = QLabel(title)
        self._title_label.setProperty('role', 'stat_label')
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # The caption must never wrap: a two-line caption pushes this card's
        # number down a line relative to its siblings in the same row, so the
        # numbers stop sharing a baseline. Instead the card demands enough
        # width for the full caption; the stat rows hand out equal stretch, so
        # every card widens to the longest caption and the numbers stay level.
        self._title_label.setWordWrap(False)
        self._title_label.setStyleSheet(
            'font-size: 10px; color: #a89b85; letter-spacing: 0.06em; '
            'background: transparent; border: none;'
        )
        layout.addWidget(self._title_label)

        _cap_font = QFont()
        _cap_font.setPixelSize(10)
        _cap_w = QFontMetrics(_cap_font).horizontalAdvance(title)
        # horizontalAdvance() doesn't know about the 0.06em QSS letter-spacing
        # (~0.6px per glyph at 10px); add it back, plus the 12px l/r content
        # margins and a few px of slack.
        self.setMinimumWidth(_cap_w + int(len(title) * 0.6) + 24 + 10)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

        # Duration-based count-up (start_animation) — separate timer from the
        # step-decay one above so live scanning updates and a one-shot reveal
        # animation can never fight over the same clock.
        self._duration        = 1400
        self._elapsed         = 0
        self._duration_timer  = QTimer(self)
        self._duration_timer.setInterval(16)
        self._duration_timer.timeout.connect(self._duration_tick)

    def update_target(self, target: int) -> None:
        self._target_value = target
        if not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        diff = self._target_value - self._current_value
        if diff == 0:
            self._timer.stop()
            return
        if diff > 0:
            step = max(1, int(diff * 0.15))
            self._current_value = min(self._target_value, self._current_value + step)
        else:
            step = min(-1, int(diff * 0.15))
            self._current_value = max(self._target_value, self._current_value + step)
        self._value_label.setText(f'{self._current_value:,}{self._suffix}')

    def start_animation(self, target: int, duration_ms: int = 1400) -> None:
        self._target_value = target
        self._duration = duration_ms
        self._elapsed  = 0
        self._value_label.setText('0' + self._suffix)
        self._duration_timer.start()

    def _duration_tick(self) -> None:
        self._elapsed += 16
        t = min(self._elapsed / self._duration, 1.0)
        eased = 1.0 - (1.0 - t) ** 3
        current = int(eased * self._target_value)
        self._value_label.setText(f'{current:,}{self._suffix}')
        if t >= 1.0:
            self._duration_timer.stop()
            self._value_label.setText(f'{self._target_value:,}{self._suffix}')

    def mousePressEvent(self, event) -> None:
        if self._duration_timer.isActive() or self._target_value:
            self.start_animation(self._target_value, self._duration)
        super().mousePressEvent(event)


class _ArrowComboBox(QComboBox):
    """QComboBox that paints itself completely from scratch — box, border,
    label text, and triangle indicator — instead of letting Qt's own
    QComboBox rendering pipeline draw any of it. Shared by every dialog in
    the app that needs a combo box — use this instead of a plain QComboBox
    with custom styling.

    Every narrower attempt before this one still let `super().paintEvent()`
    run, and every one of them still leaked some native drop-down/arrow
    chrome through regardless of what QSS said to do with that subcontrol —
    `image: url(data:...)` never renders at all for `::down-arrow`, the
    border-triangle CSS trick renders as a filled rectangle, zeroing out
    `::drop-down`/`::down-arrow` still left a stray separator artifact, and
    patching over just that region left a visible seam against the border
    drawn separately by `super().paintEvent()`. This finally stops calling
    `super().paintEvent()` at all — nothing native is drawn for this widget
    to conflict with in the first place, on any platform or style backend.
    Popup behavior (click, keyboard nav, the item list) is untouched; only
    the box's own paint is replaced.
    """

    def __init__(self, bg: str = '#1a1a1a', arrow_color: str = '#a89b85', parent=None):
        super().__init__(parent)
        self._bg_color     = QColor(bg)
        self._border_color = QColor('#444444')
        self._text_color   = QColor('#f1e3c8')
        self._arrow_color  = QColor(arrow_color)
        self._popup_open   = False
        # App-wide standard control height — callers can still override with
        # their own setFixedHeight() afterward, but this means a caller that
        # forgets to set one doesn't silently end up with a cramped box (a
        # real regression that happened here once already).
        self.setFixedHeight(36)
        self.setStyleSheet(
            f'QComboBox QAbstractItemView {{ background-color: {bg}; color: #f1e3c8; '
            'border: 1px solid #444444; border-radius: 4px; selection-background-color: #573d26; '
            'selection-color: #f1e3c8; outline: none; }'
            'QComboBox QAbstractItemView::item { padding: 6px 10px; }'
        )

    def showPopup(self) -> None:
        self._popup_open = True
        self.update()

        # Popup width via QSS-styled QAbstractItemView can't be trusted to
        # auto-size to its own content — same class of unreliability as the
        # ::down-arrow subcontrol above — so items were rendering clipped a
        # character or two short of their real width. Compute the width
        # explicitly from font metrics instead of leaving it to Qt/QSS.
        metrics = QFontMetrics(self.font())
        longest = max((metrics.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=0)
        # +20 item padding (10px each side) + ~24 for the native selection
        # checkmark gutter + 2 for the popup border.
        self.view().setMinimumWidth(max(self.width(), longest + 46))

        super().showPopup()

    def hidePopup(self) -> None:
        super().hidePopup()
        self._popup_open = False
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(self._border_color, 1))
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 4, 4)

        text_rect = self.rect().adjusted(8, 0, -24, 0)
        elided = QFontMetrics(self.font()).elidedText(
            self.currentText(), Qt.TextElideMode.ElideRight, text_rect.width(),
        )
        painter.setPen(self._text_color)
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._arrow_color)
        w, h = 9.0, 5.0
        cx = self.width() - 8 - w / 2
        cy = self.height() / 2
        if self._popup_open:
            pts = [QPointF(cx - w / 2, cy + h / 2), QPointF(cx + w / 2, cy + h / 2), QPointF(cx, cy - h / 2)]
        else:
            pts = [QPointF(cx - w / 2, cy - h / 2), QPointF(cx + w / 2, cy - h / 2), QPointF(cx, cy + h / 2)]
        painter.drawPolygon(QPolygonF(pts))
        painter.end()


class _CrateSortDialog(QDialog):
    """Base dialog for all CrateSort custom dialogs.
    Handles overlay scrim and show/bounce animation."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # Tool (not plain Dialog) so the OS treats this as a floating panel of
        # the app: it stays above the app's own windows natively, and hides
        # itself when the app is deactivated rather than floating over other
        # apps' windows the way WindowStaysOnTopHint would.
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._elastic = True

        self._overlay: Optional[_ModalOverlay] = None
        # Re-raised whenever the parent app window is (re)activated, so the
        # dialog can never end up stuck behind the app's own window — but it
        # is NOT WindowStaysOnTopHint, so it won't float above other apps.
        self._parent_win = parent.window() if parent is not None else None
        if self._parent_win is not None:
            self._overlay = _ModalOverlay(self._parent_win)
            self._overlay.set_modal(self)
            self._overlay.show()
            self._overlay.raise_()
            self._parent_win.installEventFilter(self)
        self.finished.connect(self._cleanup_overlay)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._parent_win and event.type() in (
            QEvent.Type.WindowActivate, QEvent.Type.Show,
        ):
            self.raise_()
            if self._overlay is not None:
                self._overlay.raise_()
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:
        # Ensure layout is computed so width()/height() are accurate before centering.
        self.adjustSize()
        w, h = self.width(), self.height()

        # Calculate the final centered position directly — never read geometry()
        # after move(), which is async and returns stale coords on some platforms.
        if self._overlay is not None:
            parent_win = self._overlay._parent_window
            origin = parent_win.mapToGlobal(QPoint(0, 0))
            cx = origin.x() + (parent_win.width()  - w) // 2
            cy = origin.y() + (parent_win.height() - h) // 2
        else:
            g = self.geometry()
            cx, cy = g.x(), g.y()

        target_rect = QRect(cx, cy, w, h)

        if getattr(self, '_elastic', True):
            sw, sh = int(w * 0.7), int(h * 0.7)
        else:
            sw, sh = int(w * 0.9), int(h * 0.9)

        start_rect = QRect(
            cx + (w - sw) // 2,
            cy + (h - sh) // 2,
            sw, sh,
        )

        self.setGeometry(start_rect)
        super().showEvent(event)
        self.run_bounce_animation(target_rect, start_rect)

    def run_bounce_animation(self, target_rect: QRect, start_rect: QRect) -> None:
        if getattr(self, '_elastic', True):
            duration = 320
            curve = QEasingCurve(QEasingCurve.Type.OutBack)
            curve.setOvershoot(3.0)  # Elastic bounce
        else:
            duration = 200
            curve = QEasingCurve(QEasingCurve.Type.OutBack)
            curve.setOvershoot(1.0)  # Subtle transition

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(duration)
        self._anim.setStartValue(start_rect)
        self._anim.setEndValue(target_rect)
        self._anim.setEasingCurve(curve)
        self._anim.start()

    def done(self, result: int) -> None:
        # Mirror the entrance bounce on the way out — same duration/overshoot,
        # just the reverse curve — so accept/cancel/Escape never feel like a
        # sharp cut. Real QDialog.done() (which hides the window, sets the
        # result, and unblocks exec()) is deferred until the shrink finishes.
        if getattr(self, '_closing', False):
            return
        self._closing = True
        self._pending_result = result

        # Lift the dialog's own minimum-size floor (setMinimumWidth, etc.) and its
        # layout's size constraint — both actively clamp any attempt to shrink an
        # already-laid-out widget below its natural size, which would otherwise
        # stop the exit animation from reaching its shrink target.
        self.setMinimumSize(0, 0)
        if self.layout() is not None:
            self.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

        current_rect = self.geometry()
        w, h = current_rect.width(), current_rect.height()
        cx = current_rect.x() + w // 2
        cy = current_rect.y() + h // 2

        # Exit runs 20% slower than the entrance — same shape, more room to feel the spring.
        if getattr(self, '_elastic', True):
            duration = 384  # 320 * 1.2
            curve = QEasingCurve(QEasingCurve.Type.InBack)
            curve.setOvershoot(3.0)
            sw, sh = int(w * 0.7), int(h * 0.7)
        else:
            duration = 240  # 200 * 1.2
            curve = QEasingCurve(QEasingCurve.Type.InBack)
            curve.setOvershoot(1.0)
            sw, sh = int(w * 0.9), int(h * 0.9)

        end_rect = QRect(cx - sw // 2, cy - sh // 2, sw, sh)

        self._exit_anim = QPropertyAnimation(self, b"geometry")
        self._exit_anim.setDuration(duration)
        self._exit_anim.setStartValue(current_rect)
        self._exit_anim.setEndValue(end_rect)
        self._exit_anim.setEasingCurve(curve)
        self._exit_anim.finished.connect(self._finish_close)
        self._exit_anim.start()

    def _finish_close(self) -> None:
        super().done(self._pending_result)

    def _cleanup_overlay(self) -> None:
        if self._parent_win is not None:
            self._parent_win.removeEventFilter(self)
        if self._overlay is not None:
            self._overlay.removeFromParent()
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None


def _create_dialog_layout(dialog: QDialog) -> QVBoxLayout:
    """Helper to create a standardized premium dialog layout inside a rounded QFrame container.
    Returns the QVBoxLayout inside the container where widgets should be added."""
    root = QVBoxLayout(dialog)
    root.setContentsMargins(0, 0, 0, 0)

    container = QFrame()
    container.setObjectName('dialog_container')
    container.setStyleSheet(
        'QFrame#dialog_container { background-color: #2F2F2F; '
        'border: 1px solid #444444; border-radius: 12px; }'
    )
    root.addWidget(container)

    # Clear space around the content, computed from the real screen DPI rather
    # than a guessed pixel count — symmetric on all four sides (top included).
    screen = QApplication.primaryScreen()
    # physicalDotsPerInch (not logical) — macOS reports a fixed legacy 72 for
    # logical DPI regardless of the real screen, which would undershoot a true
    # physical inch on any actual display.
    dpi = screen.physicalDotsPerInch() if screen else 96.0
    pad = int(round(dpi * 0.7 * 0.8))  # ~1 inch, dialed back 30% then another 20%

    inner = QVBoxLayout(container)
    inner.setContentsMargins(pad, pad, pad, pad)
    inner.setSpacing(16)

    # An inch of padding on each side would crush content on dialogs whose
    # minimum width was tuned around the old, much smaller margin — grow the
    # floor so there's still real room left for lists/fields/buttons.
    _MIN_CONTENT_WIDTH = 320
    needed_width = pad * 2 + _MIN_CONTENT_WIDTH
    if dialog.minimumWidth() < needed_width:
        dialog.setMinimumWidth(needed_width)

    return inner


def _ov_alert(parent: QWidget, title: str, body: str) -> None:
    """CrateSort-styled one-button alert (no choice required)."""
    dlg = _CrateSortDialog(parent)
    dlg.setMinimumWidth(480)

    # Determine accent color: Red for errors/failures, Teal otherwise
    title_lower = title.lower()
    accent_color = '#C75B5B' if ('error' in title_lower or 'fail' in title_lower or 'warning' in title_lower or 'invalid' in title_lower) else '#428175'

    if accent_color == '#C75B5B':
        dlg._elastic = False

    layout = _create_dialog_layout(dlg)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        'color: #f1e3c8; font-size: 22px; font-weight: 600; '
        'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
    )
    layout.addWidget(title_lbl)
    layout.addSpacing(6)

    body_lbl = QLabel()
    body_lbl.setTextFormat(Qt.TextFormat.RichText)
    body_lbl.setText(f'<div style="line-height: 145%;">{body}</div>')
    body_lbl.setWordWrap(True)
    body_lbl.setStyleSheet(
        'color: #d5c7ad; font-size: 14px; background: transparent; border: none;'
    )
    layout.addWidget(body_lbl)
    layout.addSpacing(12)

    ok_btn = QPushButton('OK')
    ok_btn.setFixedHeight(36)
    ok_btn.setFixedWidth(100)
    ok_btn.setStyleSheet(
        'QPushButton { background-color: #428175; color: #ffffff; border: none; '
        'border-radius: 6px; font-size: 13px; font-weight: 600; }'
        'QPushButton:hover { background-color: #38706a; }'
        'QPushButton:pressed { background-color: #2d6358; }'
    )
    ok_btn.clicked.connect(dlg.accept)
    ok_btn.setDefault(True)   # Return dismisses; Escape does too (QDialog built-in)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)

    dlg.exec()


def _ov_confirm(
    parent: QWidget,
    title: str,
    body: str,
    confirm_text: str = 'Confirm',
    cancel_text: str = 'Cancel',
    confirm_danger: bool = False,
) -> bool:
    """CrateSort-styled confirmation dialog. Returns True if the user confirmed."""
    dlg = _CrateSortDialog(parent)
    dlg.setMinimumWidth(480)

    # Determine accent color: Red for danger/destructive, Orange otherwise (choices)
    accent_color = '#C75B5B' if confirm_danger else '#D17D34'

    if confirm_danger:
        dlg._elastic = False

    layout = _create_dialog_layout(dlg)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        'color: #f1e3c8; font-size: 22px; font-weight: 600; '
        'font-family: "Helvetica Neue", Arial, Helvetica; background: transparent; border: none;'
    )
    layout.addWidget(title_lbl)
    layout.addSpacing(6)

    body_lbl = QLabel()
    body_lbl.setTextFormat(Qt.TextFormat.RichText)
    body_lbl.setText(f'<div style="line-height: 145%;">{body}</div>')
    body_lbl.setWordWrap(True)
    body_lbl.setStyleSheet(
        'color: #d5c7ad; font-size: 14px; background: transparent; border: none;'
    )
    layout.addWidget(body_lbl)
    layout.addSpacing(12)

    confirm_bg    = '#c35050' if confirm_danger else '#428175'
    confirm_hover = '#b03c3c' if confirm_danger else '#38706a'
    confirm_press = '#973434' if confirm_danger else '#2d6358'

    yes_btn = QPushButton(confirm_text)
    yes_btn.setFixedHeight(36)
    yes_btn.setStyleSheet(
        f'QPushButton {{ background-color: {confirm_bg}; color: #ffffff; border: none; '
        f'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 600; }}'
        f'QPushButton:hover {{ background-color: {confirm_hover}; }}'
        f'QPushButton:pressed {{ background-color: {confirm_press}; }}'
    )
    yes_btn.clicked.connect(dlg.accept)

    no_btn = QPushButton(cancel_text)
    no_btn.setFixedHeight(36)
    no_btn.setStyleSheet(
        'QPushButton { background: transparent; color: #a89b85; border: 1px solid #444444; '
        'border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }'
        'QPushButton:hover { color: #f1e3c8; border-color: #f1e3c8; background: rgba(241, 227, 200, 0.05); }'
        'QPushButton:pressed { background: rgba(241, 227, 200, 0.1); }'
    )
    no_btn.clicked.connect(dlg.reject)

    # Return triggers the primary action; Escape always cancels (QDialog
    # built-in → reject). For a destructive confirm the SAFE choice takes the
    # default instead — Return must never be a shortcut to a delete.
    if confirm_danger:
        no_btn.setDefault(True)
        yes_btn.setAutoDefault(False)
    else:
        yes_btn.setDefault(True)
        no_btn.setAutoDefault(False)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(12)
    btn_row.addWidget(no_btn)
    btn_row.addStretch()
    btn_row.addWidget(yes_btn)
    layout.addLayout(btn_row)

    return dlg.exec() == QDialog.DialogCode.Accepted


class _LaunchingSeratoDialog(_CrateSortDialog):
    """Transient, non-interactive modal shown while CrateSort saves crate
    state and hands off to Serato, right before quitting. No buttons, can't
    be dismissed early — `do_work` (checkpoint save + the actual Serato
    launch) runs partway through a short choreographed beat, and the dialog
    reports back via `exec()`'s result whether the handoff actually worked."""

    def __init__(self, parent: QWidget, do_work: Callable[[], bool]):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._do_work = do_work

        layout = _create_dialog_layout(self)
        layout.setSpacing(0)

        mascot_row = QHBoxLayout()
        mascot_row.addStretch()

        self._mascot_item = None
        self._scale_anim: Optional[QPropertyAnimation] = None
        self._wiggle_anim: Optional[QPropertyAnimation] = None
        if _SVG_AVAILABLE and _MASCOT_SVG.exists():
            scene = QGraphicsScene()
            scene.setBackgroundBrush(QColor('#2F2F2F'))  # matches _create_dialog_layout's container bg

            item = QGraphicsSvgItem(str(_MASCOT_SVG))
            native_rect = item.boundingRect()
            item.setTransformOriginPoint(native_rect.center())
            scene.addItem(item)

            view = QGraphicsView(scene)
            view.setFixedSize(96, 96)
            view.setFrameShape(QFrame.Shape.NoFrame)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setStyleSheet('background: transparent; border: none;')
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Leaves headroom around the mascot's natural size so the scale
            # pulse below (up to 1.18x) never clips against the view edge.
            padded = native_rect.adjusted(
                -native_rect.width() * 0.14, -native_rect.height() * 0.14,
                native_rect.width() * 0.14, native_rect.height() * 0.14,
            )
            view.fitInView(padded, Qt.AspectRatioMode.KeepAspectRatio)
            mascot_row.addWidget(view)
            self._mascot_view = view
            self._mascot_item = item

            scale_anim = QPropertyAnimation(item, b'scale', self)
            scale_anim.setDuration(900)
            scale_anim.setKeyValueAt(0.0, 0.92)
            scale_anim.setKeyValueAt(0.5, 1.18)
            scale_anim.setKeyValueAt(1.0, 0.92)
            scale_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            scale_anim.setLoopCount(-1)

            wiggle_anim = QPropertyAnimation(item, b'rotation', self)
            wiggle_anim.setDuration(700)
            wiggle_anim.setKeyValueAt(0.0, -8)
            wiggle_anim.setKeyValueAt(0.5, 8)
            wiggle_anim.setKeyValueAt(1.0, -8)
            wiggle_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
            wiggle_anim.setLoopCount(-1)

            self._scale_anim = scale_anim
            self._wiggle_anim = wiggle_anim

        mascot_row.addStretch()
        layout.addLayout(mascot_row)
        layout.addSpacing(16)

        self._status_lbl = QLabel('Saving your crates…')
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            'color: #f1e3c8; font-size: 15px; font-weight: 600; '
            'background: transparent; border: none;'
        )
        layout.addWidget(self._status_lbl)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._scale_anim is not None:
            self._scale_anim.start()
            self._wiggle_anim.start()
        QTimer.singleShot(700, self._run_work)

    def _run_work(self) -> None:
        self._status_lbl.setText('Launching Serato…')
        success = self._do_work()
        if self._scale_anim is not None:
            self._scale_anim.stop()
            self._wiggle_anim.stop()
        if success:
            QTimer.singleShot(550, self.accept)
        else:
            self._status_lbl.setText("Couldn't find Serato")
            QTimer.singleShot(650, self.reject)

    def keyPressEvent(self, event) -> None:
        event.ignore()  # can't be cancelled mid-sequence — Escape does nothing here

    def closeEvent(self, event) -> None:
        event.ignore()  # same — no title bar/close box exists, but block just in case


def show_launching_serato_dialog(parent: QWidget, do_work: Callable[[], bool]) -> bool:
    """Shows the animated "Saving your crates… Launching Serato…" modal and
    runs `do_work` (checkpoint save + the actual Serato launch attempt)
    partway through. Returns True if `do_work` reported success."""
    dlg = _LaunchingSeratoDialog(parent, do_work)
    return dlg.exec() == QDialog.DialogCode.Accepted
