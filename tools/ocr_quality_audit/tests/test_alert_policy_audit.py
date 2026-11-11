"""Model-level regressions for user-visible alerts in a fictional capture session."""
import unittest
from dataclasses import replace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alert_policy_audit import Frame, held_card_trace, transition_same_values_trace, replay_value_cooldown


class AlertPolicyTests(unittest.TestCase):
    def test_held_card_causes_duplicate_after_25_seconds(self):
        r = replay_value_cooldown(held_card_trace())
        self.assertEqual(r["eligibleUniqueFixtureOffers"], 1)
        self.assertEqual(r["notificationAttempts"], 2)
        self.assertEqual(r["duplicateAlertsForSameFixtureOffer"], 1)

    def test_map_then_distinct_offer_same_values_misses_second(self):
        r = replay_value_cooldown(transition_same_values_trace())
        self.assertEqual(r["eligibleUniqueFixtureOffers"], 2)
        self.assertEqual(r["notificationAttempts"], 1)
        self.assertEqual(r["eligibleOffersNeverNotified"], 1)

    def test_map_then_distinct_offer_different_value_alerts(self):
        xs = transition_same_values_trace()
        xs[3] = replace(xs[3], fingerprint="opaque-other")
        xs[4] = replace(xs[4], fingerprint="opaque-other")
        r = replay_value_cooldown(xs)
        self.assertEqual(r["notificationAttempts"], 2)
        self.assertEqual(r["eligibleOffersNeverNotified"], 0)

    def test_two_equal_value_offers_without_clear_transition_are_not_separable(self):
        xs = [Frame(0, "OFFER_CANDIDATE", "A", "identical"),
              Frame(1_500, "OFFER_CANDIDATE", "A", "identical"),
              Frame(3_000, "OFFER_CANDIDATE", "B", "identical"),
              Frame(4_500, "OFFER_CANDIDATE", "B", "identical")]
        r = replay_value_cooldown(xs)
        self.assertEqual(r["eligibleUniqueFixtureOffers"], 2)
        self.assertEqual(r["eligibleOffersNeverNotified"], 1)

    def test_only_one_scan_is_not_eligible(self):
        r = replay_value_cooldown([Frame(0, "OFFER_CANDIDATE", "A", "x"),
                                   Frame(100, "NON_OFFER")])
        self.assertEqual(r["eligibleUniqueFixtureOffers"], 0)
        self.assertEqual(r["notificationAttempts"], 0)

    def test_uncertain_screen_resets_consecutive_counter(self):
        xs = [Frame(0, "OFFER_CANDIDATE", "A", "x"),
              Frame(100, "UNCERTAIN"),
              Frame(200, "OFFER_CANDIDATE", "A", "x"),
              Frame(300, "OFFER_CANDIDATE", "A", "x")]
        self.assertEqual(replay_value_cooldown(xs)["notificationAttempts"], 1)

    def test_reject_regressing_fixture_clock(self):
        with self.assertRaises(ValueError):
            replay_value_cooldown([Frame(200, "NON_OFFER"), Frame(100, "NON_OFFER")])


if __name__ == "__main__":
    unittest.main()
