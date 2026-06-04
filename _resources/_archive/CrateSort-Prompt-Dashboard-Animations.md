# CrateSort — Dashboard Animations: Count-Up & Hover Effects

**Sonnet, high effort. Read every referenced file completely before writing any code.**

---

## Files to Read First

Read these files completely before writing any code:
- `cratesort/src/gui/dashboard.py` — full file
- `cratesort/src/gui/theme.py` — full file

---

## Overview

Two targeted additions to the dashboard:

1. **Stat cards** — numbers animate from 0 up to their final value when the dashboard loads. Clicking a stat card replays the animation for that card only.
2. **Action cards (Go To group)** — the muted step number (`01`–`04`) transitions to orange on mouse enter and back to muted on mouse leave.

No other sections are touched.

---

## Change 1 — Animated Stat Card Widget

### Create a new class `_AnimatedStatCard(QFrame)`

This replaces the plain `QFrame` currently used for stat cards in `_build_stat_cards_section()`.

```python
class _AnimatedStatCard(QFrame):
    def __init__(self, icon: str, target: int, suffix: str, label: str, parent=None):
        super().__init__(parent)
        # store target value and suffix for replay
        self._target = target
        self._suffix = suffix
        self._current = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)
        self._elapsed = 0
        self._duration = 1400  # ms, default

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # styling applied externally or here
```

**Layout inside the card (top to bottom):**
- Icon label (`QLabel`, text = icon character, `font-size: 16px; color: #7a6a55`)
- Number label (`QLabel`, stored as `self._num_label`, `font-size: 26px; font-weight: 500; color: #f1e3c8`, starts showing `"0"` or `"0h"`)
- Stat label (`QLabel`, text = label string, `font-size: 11px; color: #7a6a55; text-transform: uppercase; letter-spacing: 0.08em`)

**Card styling:**
- Background: `#2F2F2F`
- Border: `1px solid #3a3a3a`
- Border radius: `10px`
- Padding: `16px 14px`
- `QSizePolicy.Expanding` horizontally

### Animation logic

Use `QTimer` at 16ms intervals. Track elapsed time manually:

```python
def start_animation(self, duration_ms: int = 1400):
    self._duration = duration_ms
    self._elapsed = 0
    self._current = 0.0
    self._num_label.setText('0' + self._suffix)
    self._timer.start()

def _tick(self):
    self._elapsed += 16
    t = min(self._elapsed / self._duration, 1.0)
    eased = 1.0 - (1.0 - t) ** 3  # cubic ease-out
    self._current = eased * self._target
    val = int(self._current)
    formatted = f'{val:,}{self._suffix}' if self._suffix == '' else f'{val:,}{self._suffix}'
    self._num_label.setText(formatted)
    if t >= 1.0:
        self._timer.stop()
        self._num_label.setText(f'{self._target:,}{self._suffix}')
```

### Click to replay

Override `mousePressEvent`:
```python
def mousePressEvent(self, event):
    self.start_animation(1400)
```

### Auto-start on dashboard load

In `_build_stat_cards_section()`, after all four cards are created and added to the layout, use a single `QTimer.singleShot` with a short delay to start animations with staggered timing:

```python
QTimer.singleShot(100, lambda: cards[0].start_animation(1600))
QTimer.singleShot(220, lambda: cards[1].start_animation(1400))
QTimer.singleShot(340, lambda: cards[2].start_animation(1500))
QTimer.singleShot(460, lambda: cards[3].start_animation(1300))
```

The 100ms base delay ensures the widget is fully painted before animation starts. Store cards in a local list before wiring the timers.

### Number formatting

- Total Tracks: `f'{val:,}'` (e.g. `24,381`)
- Total Crates: `f'{val:,}'` (e.g. `172`)
- Unique Artists: `f'{val:,}'` (e.g. `3,847`)
- Hours of Music: `f'{val:,}h'` (e.g. `1,240h`) — suffix is `'h'`, no space

---

## Change 2 — Hover Effect on Go To Action Cards

### Create a new class `_WorkflowCard(QFrame)`

This replaces the plain `QFrame` currently used for Go To cards in `_build_action_cards_section()`.

```python
class _WorkflowCard(QFrame):
    def __init__(self, step: str, title: str, desc: str, callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # build layout
        # store reference to step number label as self._step_label
```

**Layout inside the card (top to bottom):**
- Step number label (`QLabel`, stored as `self._step_label`, text = e.g. `'01'`)
  - Default style: `font-size: 32px; font-weight: 600; color: #3a3a3a; letter-spacing: -0.02em`
- Title label (`QLabel`, `font-size: 14px; font-weight: 500; color: #f1e3c8`)
- Description label (`QLabel`, `font-size: 11px; color: #7a6a55`)

**Card styling:**
- Background: `#2F2F2F`
- Border: `1px solid #3a3a3a`
- Border radius: `10px`
- Padding: `20px 18px`
- Min height: `130px`

### Hover events

```python
def enterEvent(self, event):
    self._step_label.setStyleSheet(
        'font-size: 32px; font-weight: 600; color: #D17D34; '
        'letter-spacing: -0.02em; background: transparent;'
    )
    super().enterEvent(event)

def leaveEvent(self, event):
    self._step_label.setStyleSheet(
        'font-size: 32px; font-weight: 600; color: #3a3a3a; '
        'letter-spacing: -0.02em; background: transparent;'
    )
    super().leaveEvent(event)
```

### Click

```python
def mousePressEvent(self, event):
    if self._callback:
        self._callback()
```

---

## What Does NOT Change

- Create cards (`New Crate`, `New Smart Crate`) — no hover number effect, no animation. Leave as-is.
- `_build_activity_section()` — untouched.
- `_build_footer_bar()` — untouched.
- `_build_welcome()` — untouched.
- `_build_scanning()` — untouched.
- All signals — untouched.

---

## Constraints

- Use only `QTimer` for animation — no threads, no `QPropertyAnimation`
- Do not use CSS transitions or any browser-style animation — this is PyQt6
- `_AnimatedStatCard` and `_WorkflowCard` should be defined as private classes at module level (above `DashboardWidget`), not nested inside methods
- Verify `QTimer` is already imported — add to imports if not
- Do not hardcode color hex values that already exist as class constants on `DashboardWidget` — use `self._TEAL`, `self._ORANGE`, `self._CREAM`, `self._MUTED`, `self._PANEL`, `self._SEP` where applicable. For the new standalone classes that don't have access to `self._*` constants, inline the hex values directly.
- After writing, confirm `_AnimatedStatCard` is used in `_build_stat_cards_section()` and `_WorkflowCard` is used in `_build_action_cards_section()`

---

## Verification Steps

1. Four stat cards animate on dashboard load with staggered timing — confirm `singleShot` delays are 100, 220, 340, 460ms
2. Clicking any stat card replays its animation independently
3. Hovering a Go To card turns its step number orange; leaving returns it to `#3a3a3a`
4. Create cards are unchanged
5. No `requestAnimationFrame`, no CSS transitions, no threads — pure `QTimer`
