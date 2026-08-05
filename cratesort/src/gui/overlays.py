from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional
from PyQt6.QtCore import Qt, QEvent, QPoint, QRect, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QLayout, QVBoxLayout, QFrame, QLabel, QPushButton, QHBoxLayout,
    QGraphicsScene, QGraphicsView,
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
    Shared by the Library tab's Analyze Library modal and the dashboard's
    scanning-phase stat cards — both animate live classification progress."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._current_value = 0
        self._target_value  = 0

        self.setStyleSheet(
            'QFrame { background-color: #1a1a1a; border: 1px solid #444444; '
            'border-radius: 8px; }'
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value_label = QLabel('0')
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
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet(
            'font-size: 10px; color: #a89b85; letter-spacing: 0.06em; '
            'background: transparent; border: none;'
        )
        layout.addWidget(self._title_label)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

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
        self._value_label.setText(f'{self._current_value:,}')


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
