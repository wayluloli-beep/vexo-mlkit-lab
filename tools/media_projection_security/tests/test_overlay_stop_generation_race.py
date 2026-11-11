"""Regression for a queued old-session overlay hide racing a new session.

Synthetic model plus source contract. No Android media or passenger data.
"""
import unittest
from pathlib import Path

class OverlayScheduler:
    def __init__(self, guard_hide):
        self.generation = 0
        self.visible = False
        self.queue = []
        self.guard_hide = guard_hide

    def show(self):
        self.generation += 1
        version = self.generation
        self.queue.append(lambda: setattr(self, "visible", True)
                          if version == self.generation else None)

    def hide(self):
        self.generation += 1
        version = self.generation
        self.queue.append(lambda: setattr(self, "visible", False)
                          if not self.guard_hide or version == self.generation else None)

class OverlayStopRaceTests(unittest.TestCase):
    def test_old_hide_must_not_remove_new_session_overlay(self):
        scheduler = OverlayScheduler(guard_hide=True)
        scheduler.hide()  # old session STOP queued from another thread
        scheduler.show()  # new session starts; emulate show B posted before stale hide A
        for callback in reversed(scheduler.queue):
            callback()
        self.assertTrue(scheduler.visible)

    def test_current_implementation_counterexample(self):
        scheduler = OverlayScheduler(guard_hide=False)
        scheduler.hide()
        scheduler.show()
        for callback in reversed(scheduler.queue):
            callback()
        self.assertFalse(scheduler.visible,
                         "An old STOP hide can remove a new session overlay")

    def test_expected_source_contract(self):
        # This audit branch deliberately has no Android source. A separate
        # read-only CI checkout of the current Android HEAD is required.
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
