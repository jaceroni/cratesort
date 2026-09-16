#!/usr/bin/env python3
"""Generate the branded background image for the CrateSort DMG installer window.

Run from the build venv (needs PyQt6 for SVG rendering):
    .build-venv/bin/python packaging/generate_dmg_background.py

Produces packaging/dmg_background.png — a 660x420 @2x (1320x840 actual pixels)
image matching the DMG window layout set up in packaging/CrateSort.spec's DMG
build step: CrateSort.app on the left, an arrow, the Applications alias on
the right, and the optional Uninstaller tucked below/between as a secondary
item. Rendered at 2x and referenced at logical 660x420 so it stays sharp on
a Retina display, same convention as everything else in this app's asset
pipeline (see the app-icon regeneration note in CLAUDE-CS.md).
"""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PyQt6.QtSvg import QSvgRenderer

_app = QGuiApplication(sys.argv)  # needed for QFont/QFontMetrics/text rendering

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOGO_SVG = os.path.join(ROOT, 'cratesort', 'assets', 'logo', 'cs-logo-lockup-horiz.svg')
OUT_PNG = os.path.join(os.path.dirname(__file__), 'dmg_background.png')

# Logical (1x) window content size — must match the `bounds` set on the
# Finder window in build_dmg.sh's AppleScript layout step.
W, H = 660, 420
SCALE = 2  # render @2x for Retina

_BG = QColor('#1a1a1a')       # app's own primary dark background
_CREAM = QColor('#f1e3c8')    # app's primary text color
_MUTED = QColor('#a89b85')    # app's muted/secondary text color

# Icon centers — must match the `position of item ...` calls in
# build_dmg.sh's AppleScript layout step. CrateSort.app (primary) on the
# left, Applications alias on the right with a connecting arrow between them
# (the standard drag-to-install convention); the optional uninstaller sits
# in its own row below, secondary role, no callout drawn near it (Finder's
# own filename label sits close enough beneath UNINSTALL_Y that any text
# painted here would collide with it).
APP_X, ROW_Y = 150, 190
APPLICATIONS_X = 510
UNINSTALL_Y = 330


def main() -> None:
    img = QImage(W * SCALE, H * SCALE, QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(SCALE)
    img.fill(_BG)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    # Wordmark, centered near the top.
    renderer = QSvgRenderer(LOGO_SVG)
    logo_w = 300.0
    logo_h = logo_w * (157.61 / 450.99)  # native viewBox aspect ratio
    logo_rect = QRectF((W - logo_w) / 2, 34, logo_w, logo_h)
    renderer.render(p, logo_rect)

    # Tagline directly under the wordmark.
    tagline_font = QFont('Helvetica Neue')
    tagline_font.setPixelSize(13)
    p.setFont(tagline_font)
    p.setPen(_MUTED)
    tagline_rect = QRectF(0, logo_rect.bottom() + 6, W, 20)
    p.drawText(tagline_rect, int(Qt.AlignmentFlag.AlignHCenter), 'Get your shit together.')

    # Arrow from the app icon to the Applications alias, at the icon row's
    # vertical center. Icons are placed by Finder itself (see
    # build_dmg.sh) — this only draws the connecting graphic between them.
    arrow_y = ROW_Y
    arrow_start_x = APP_X + 74   # clear of the app icon's own footprint
    arrow_end_x = APPLICATIONS_X - 74
    pen = QPen(_CREAM, 3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(arrow_start_x, arrow_y), QPointF(arrow_end_x, arrow_y))
    # Arrowhead.
    head = 10.0
    tip = QPointF(arrow_end_x, arrow_y)
    p.drawLine(tip, QPointF(tip.x() - head, tip.y() - head))
    p.drawLine(tip, QPointF(tip.x() - head, tip.y() + head))

    # No caption drawn near the second (Uninstaller) row on purpose — Finder
    # renders each icon's own filename directly beneath it, close enough to
    # UNINSTALL_Y's icon that any text painted into the background here would
    # collide with that native label. The filename is self-explanatory.

    p.end()

    if not img.save(OUT_PNG, 'PNG'):
        print('FAILED to save', OUT_PNG, file=sys.stderr)
        sys.exit(1)
    print('wrote', OUT_PNG, f'({img.width()}x{img.height()} px, {W}x{H} logical)')


if __name__ == '__main__':
    main()
