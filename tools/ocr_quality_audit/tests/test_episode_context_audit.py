"""Regressions model PR25 source behavior, using only synthetic tokens."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from episode_context_audit import (
    Observation as O, replay_episode_policy,
    repeated_card_with_two_unknowns, separate_cards_with_map,
    same_card_with_ocr_variation,
)


class EpisodeContextTests(unittest.TestCase):
    def test_two_unknown_readings_reopen_same_card_in_pr25(self):
        result = replay_episode_policy(repeated_card_with_two_unknowns())
        self.assertEqual(result["fixtureGroupsSeen"], 1)
        self.assertEqual(result["alertAttempts"], 2)
        self.assertEqual(result["duplicateAlertsSameGroup"], 1)

    def test_two_unknown_readings_do_not_end_proposed_episode(self):
        result = replay_episode_policy(repeated_card_with_two_unknowns(), conservative=True)
        self.assertEqual(result["alertAttempts"], 1)
        self.assertEqual(result["duplicateAlertsSameGroup"], 0)

    def test_two_definite_map_frames_separate_same_value_offers(self):
        for conservative in (False, True):
            with self.subTest(conservative=conservative):
                r = replay_episode_policy(separate_cards_with_map(), conservative=conservative)
                self.assertEqual(r["notifiedGroups"], 2)
                self.assertEqual(r["eligibleOffersNeverNotified"], 0)
                self.assertEqual(r["duplicateAlertsSameGroup"], 0)

    def test_two_plausible_ocr_misreads_trigger_extra_alerts_in_pr25(self):
        r = replay_episode_policy(same_card_with_ocr_variation())
        self.assertEqual(r["alertAttempts"], 3)
        self.assertEqual(r["duplicateAlertsSameGroup"], 2)

    def test_proposed_policy_abstains_on_unproved_fingerprint_changes(self):
        r = replay_episode_policy(same_card_with_ocr_variation(), conservative=True)
        self.assertEqual(r["alertAttempts"], 1)
        self.assertEqual(r["unprovenIdentityChangesSuppressed"], 2)

    def test_one_uncertain_frame_cannot_repeat_notification(self):
        events = [O("OFFER", "A", "same"), O("OFFER", "A", "same"),
                  O("UNCERTAIN"), O("OFFER", "A", "same"),
                  O("OFFER", "A", "same")]
        for conservative in (False, True):
            self.assertEqual(replay_episode_policy(events, conservative=conservative)["alertAttempts"], 1)

    def test_unobservable_transition_remains_fundamentally_ambiguous(self):
        # Same fields and no context gap: even a better policy cannot infer identity.
        xs = [O("OFFER", "A", "same"), O("OFFER", "A", "same"),
              O("OFFER", "B", "same"), O("OFFER", "B", "same")]
        for conservative in (False, True):
            r = replay_episode_policy(xs, conservative=conservative)
            self.assertEqual(r["eligibleGroupsWithTwoConsecutiveObservations"], 2)
            self.assertEqual(r["eligibleGroupsNeverNotified"], 1)

    def test_proposed_policy_chooses_abstention_on_new_ungapped_values(self):
        xs = [O("OFFER", "A", "first"), O("OFFER", "A", "first"),
              O("OFFER", "B", "second"), O("OFFER", "B", "second")]
        r = replay_episode_policy(xs, conservative=True)
        self.assertEqual(r["alertAttempts"], 1)
        self.assertEqual(r["eligibleGroupsNeverNotified"], 1)

    def test_reject_nonopaque_identifiers_and_bad_context(self):
        for sample in (
            O("OFFER", "two words", "ok"),
            O("OFFER", "A", "invalid value with spaces"),
            O("MAGIC", "A", "ok"),
        ):
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                replay_episode_policy([sample])


if __name__ == "__main__":
    unittest.main()
