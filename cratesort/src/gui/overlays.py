from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import Qt, QEvent, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QFrame, QLabel, QPushButton, QHBoxLayout
)


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
        own_rect = self.geometry()   # QRect in parent_window local coords
        mw = self._modal.width()
        mh = self._modal.height()
        local_x = own_rect.x() + (own_rect.width()  - mw) // 2
        local_y = own_rect.y() + (own_rect.height() - mh) // 2
        global_pos = self._parent_window.mapToGlobal(QPoint(local_x, local_y))
        self._modal.move(global_pos)

    def removeFromParent(self) -> None:
        self._parent_window.removeEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._parent_window and event.type() == QEvent.Type.Resize:
            self.setGeometry(self._parent_window.rect())
            self.center_modal()
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:
        event.accept()   # block clicks from reaching widgets underneath


class _CrateSortDialog(QDialog):
    """Base dialog for all CrateSort custom dialogs.
    Handles overlay scrim and show/bounce animation."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._elastic = True

        self._overlay: Optional[_ModalOverlay] = None
        parent_win = parent.window() if parent is not None else None
        if parent_win is not None:
            self._overlay = _ModalOverlay(parent_win)
            self._overlay.set_modal(self)
            self._overlay.show()
            self._overlay.raise_()
        self.finished.connect(self._cleanup_overlay)

    def showEvent(self, event) -> None:
        if self._overlay:
            self._overlay.center_modal()
            
        target_rect = self.geometry()
        w = target_rect.width()
        h = target_rect.height()
        
        if getattr(self, '_elastic', True):
            start_rect = QRect(
                target_rect.x() + int(w * 0.15),
                target_rect.y() + int(h * 0.15),
                int(w * 0.7),
                int(h * 0.7)
            )
        else:
            start_rect = QRect(
                target_rect.x() + int(w * 0.05),
                target_rect.y() + int(h * 0.05),
                int(w * 0.9),
                int(h * 0.9)
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

    def _cleanup_overlay(self) -> None:
        if self._overlay is not None:
            self._overlay.removeFromParent()
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None


def _create_dialog_layout(dialog: QDialog, accent_color: str) -> QVBoxLayout:
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

    inner = QVBoxLayout(container)
    inner.setContentsMargins(28, 0, 28, 24)
    inner.setSpacing(16)

    # Accent bar at the top of the dialog card
    accent = QFrame()
    accent.setFixedHeight(4)
    accent.setStyleSheet(f'background-color: {accent_color}; border: none; border-radius: 2px;')
    inner.addWidget(accent)
    inner.addSpacing(6)

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

    layout = _create_dialog_layout(dlg, accent_color)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        'color: #f1e3c8; font-size: 17px; font-weight: 600; '
        'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
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

    layout = _create_dialog_layout(dlg, accent_color)

    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        'color: #f1e3c8; font-size: 17px; font-weight: 600; '
        'font-family: "Charter", "Georgia", serif; background: transparent; border: none;'
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

    confirm_bg    = '#C75B5B' if confirm_danger else '#428175'
    confirm_hover = '#b24c4c' if confirm_danger else '#38706a'
    confirm_press = '#9c3b3b' if confirm_danger else '#2d6358'

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
