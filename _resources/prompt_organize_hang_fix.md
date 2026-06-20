# CrateSort — Organize Plan Builder Hang Fix

## Context

Run at **Sonnet, high effort**. Read every referenced file completely before writing any code.

This prompt resolves a silent PyQt6 crash on the Organize view where the plan builder worker completes but fails to advance to the Preview screen, locking the app on a spinner state.

---

## Files in scope

- `src/gui/organize_view.py`

---

## Locked rules

- Color system roles (Teal = action, Orange = selection, Red = destructive) must remain intact.
- Keep the 45px header height and 36px track row height app-wide.
- Do not modify plan generation logic in `FileOrganizer` or threading mechanisms in `_PlanWorker`.

---

## Detailed Specifications

In PyQt6, calling `.disconnect()` on a signal that has no connections throws a `TypeError`. The current code in `organize_view.py` intercepts `RuntimeError` but allows `TypeError` to escape, causing crashes inside slots that silently fail and block the GUI state transitions.

### 1. Fix slot disconnection in `_on_plan_ready`

Inside `_on_plan_ready()` (around line 1083), broaden the exception handling block surrounding `self._card_warnings.clicked.disconnect()` to catch both `RuntimeError` and `TypeError` (or generic `Exception`):

```python
        try:
            self._card_warnings.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
```

### 2. Fix slot disconnection in `_start_plan_worker`

Inside `_start_plan_worker()` (around lines 1063–1067), broaden the exception handling block surrounding the plan worker signal disconnect calls to catch `(RuntimeError, TypeError)` or generic `Exception`:

```python
        if self._plan_worker is not None:
            try:
                self._plan_worker.finished.disconnect()
                self._plan_worker.errored.disconnect()
            except (RuntimeError, TypeError):
                pass
```

---

## Cody's Pre-Flight & Blast Radius

- Verify signal/slot connections are established correctly after disconnecting.
- Confirm that catching `TypeError` does not suppress other logic errors (it is limited strictly to the `.disconnect()` calls).
- Verify that if the plan builder raises an actual error, `_on_plan_error()` is still reached, the `status_message` is updated, and the stacked widget returns to `_STATE_GATE` (State 0).

---

## Verification checklist

1. Start CrateSort, load the library, navigate to the **Organize** tab, and click **Plan Reorganization…**.
2. Confirm the Planning Screen spinner displays, finishes processing, and immediately transitions to the **Preview** screen (State 2) with animated count-up cards.
3. Verify that clicking the "Warnings / Conflicts" stat card opens the `_WarningsDetailDialog`.
4. Click **← Cancel & Go Back to Dashboard** from the Preview screen and verify the UI resets cleanly to State 0.
5. Induce a mock exception inside `_PlanWorker.run` and verify that the `_on_plan_error` slot successfully triggers a critical error dialog box and resets the stacked widget index back to State 0.
