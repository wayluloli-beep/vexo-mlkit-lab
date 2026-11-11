"""Synthetic temporal safety tests: no screenshot, video, address or OCR text."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from temporal_offer_safety import Frame, Kind, NotificationPolicy, review_source


def e(kind, c, done=None, fingerprint="dummy-A", financial_safe=True, actionable=True):
    return Frame(kind, c, c + 200 if done is None else done,
                 fingerprint=fingerprint,
                 financial_safe=financial_safe,
                 actionable=actionable)


class TemporalOfferSafetyTests(unittest.TestCase):
    def test_long_map_without_card_does_not_alert(self):
        p = NotificationPolicy()
        for i in range(300):
            self.assertFalse(p.observe(e(Kind.MAP, i * 800)))
        self.assertEqual([], p.alerts)

    def test_one_short_visual_episode_emits_exactly_one_alert(self):
        p = NotificationPolicy()
        notifications = [p.observe(e(Kind.OFFER, 1000 + i * 400))
                         for i in range(25)]
        self.assertEqual(1, sum(notifications))
        self.assertEqual(1, len(p.alerts))

    def test_single_frame_never_entitles_notification(self):
        p = NotificationPolicy()
        self.assertFalse(p.observe(e(Kind.OFFER, 1000)))
        self.assertEqual(0, len(p.alerts))

    def test_uncertainty_before_second_confirmation_resets_count(self):
        p = NotificationPolicy()
        seq = [Kind.OFFER, Kind.UNCERTAIN, Kind.OFFER, Kind.OFFER]
        counts = [p.observe(e(k, i * 1000)) for i, k in enumerate(seq)]
        self.assertEqual([False, False, False, True], counts)

    def test_overlay_on_still_visible_card_does_not_realert(self):
        p = NotificationPolicy()
        seq = [Kind.OFFER, Kind.OFFER, Kind.UNCERTAIN,
               Kind.UNCERTAIN, Kind.OFFER, Kind.OFFER]
        self.assertEqual(1, sum(p.observe(e(k, i * 1000))
                                for i, k in enumerate(seq)))

    def test_same_numbers_after_confirmed_map_are_two_visual_episodes(self):
        p = NotificationPolicy()
        seq = [Kind.OFFER, Kind.OFFER, Kind.MAP, Kind.MAP,
               Kind.OFFER, Kind.OFFER]
        self.assertEqual(2, sum(p.observe(e(k, i * 1100))
                                for i, k in enumerate(seq)))
        # Two visual episodes are NOT evidence of two different passengers.

    def test_one_definite_map_is_insufficient_for_new_episode(self):
        p = NotificationPolicy()
        seq = [Kind.OFFER, Kind.OFFER, Kind.MAP,
               Kind.OFFER, Kind.OFFER]
        self.assertEqual(1, sum(p.observe(e(k, i * 700))
                                for i, k in enumerate(seq)))

    def test_offer_list_requires_two_safe_actionable_readings(self):
        p = NotificationPolicy()
        self.assertFalse(p.observe(e(Kind.OFFER_LIST, 1000)))
        self.assertTrue(p.observe(e(Kind.OFFER_LIST, 2000)))
        self.assertEqual(1, len(p.alerts))

    def test_non_actionable_list_does_not_alert(self):
        p = NotificationPolicy()
        for i in range(3):
            self.assertFalse(p.observe(e(Kind.OFFER_LIST, i * 900,
                                         actionable=False)))
        self.assertEqual([], p.alerts)

    def test_expired_list_does_not_generate_alert_even_with_repeated_text(self):
        p = NotificationPolicy()
        self.assertFalse(p.observe(e(Kind.OFFER_LIST, 1000)))
        self.assertFalse(p.observe(e(Kind.EXPIRED, 1500)))
        self.assertFalse(p.observe(e(Kind.OFFER_LIST, 2000)))
        self.assertFalse(p.observe(e(Kind.OFFER_LIST, 3000)))
        self.assertEqual([], p.alerts)

    def test_expiry_requires_verified_transition_before_rearming(self):
        p = NotificationPolicy()
        seq = [Kind.OFFER_LIST, Kind.EXPIRED, Kind.OFFER_LIST,
               Kind.MAP, Kind.MAP, Kind.OFFER_LIST, Kind.OFFER_LIST]
        self.assertEqual(1, sum(p.observe(e(k, i * 750))
                                for i, k in enumerate(seq)))

    def test_ad_with_currency_is_never_a_ride_notification(self):
        p = NotificationPolicy()
        for i in range(10):
            self.assertFalse(p.observe(e(Kind.ADVERTISEMENT, i * 1000)))
        self.assertEqual([], p.alerts)

    def test_ad_after_offer_blocks_old_offer(self):
        p = NotificationPolicy()
        seq = [Kind.OFFER, Kind.OFFER, Kind.ADVERTISEMENT,
               Kind.OFFER, Kind.OFFER]
        self.assertEqual(1, sum(p.observe(e(k, i * 850))
                                for i, k in enumerate(seq)))

    def test_callback_from_before_expiry_cannot_reactivate_expired_offer(self):
        p = NotificationPolicy()
        self.assertFalse(p.observe(e(Kind.OFFER_LIST, 1000)))
        self.assertFalse(p.observe(e(Kind.EXPIRED, 1700)))
        # Captured before expiry but ML Kit only finishes later.
        self.assertFalse(p.observe(e(Kind.OFFER_LIST, 1500, 2200)))
        self.assertEqual([], p.alerts)

    def test_old_frame_completion_after_three_seconds_rejected(self):
        p = NotificationPolicy(max_frame_age_ms=3000)
        self.assertFalse(p.observe(e(Kind.OFFER, 1000, 4101)))
        self.assertFalse(p.observe(e(Kind.OFFER, 2000, 5101)))
        self.assertEqual([], p.alerts)

    def test_stale_frame_not_counted_as_first_of_two(self):
        p = NotificationPolicy()
        seq = [e(Kind.OFFER, 0, 4000),
               e(Kind.OFFER, 4500, 4700),
               e(Kind.OFFER, 5000, 5200)]
        self.assertEqual([False, False, True],
                         [p.observe(frame) for frame in seq])

    def test_failed_financial_guard_cannot_alert(self):
        p = NotificationPolicy()
        self.assertFalse(p.observe(e(Kind.OFFER, 1000, financial_safe=False)))
        self.assertFalse(p.observe(e(Kind.OFFER, 2000, financial_safe=False)))
        self.assertEqual([], p.alerts)

    def test_stop_blocks_pending_completion_forever(self):
        p = NotificationPolicy()
        p.observe(e(Kind.OFFER, 1000))
        self.assertFalse(p.observe(e(Kind.STOP, 1600)))
        self.assertFalse(p.observe(e(Kind.OFFER, 1200, 2300)))
        self.assertFalse(p.observe(e(Kind.OFFER, 3000)))
        self.assertEqual([], p.alerts)

    def test_no_freshness_without_valid_clock(self):
        p = NotificationPolicy()
        self.assertFalse(p.observe(e(Kind.OFFER, -1, 1)))
        self.assertFalse(p.observe(e(Kind.OFFER, 700, 600)))
        self.assertEqual([], p.alerts)

    def test_out_of_order_callbacks_are_rejected_in_fixture(self):
        p = NotificationPolicy()
        p.observe(e(Kind.MAP, 3000, 3300))
        with self.assertRaises(ValueError):
            p.observe(e(Kind.OFFER, 1000, 1100))

    def test_max_age_must_be_positive(self):
        with self.assertRaises(ValueError):
            NotificationPolicy(0)

    def test_source_missing_explicit_guards_is_reported_not_silently_passed(self):
        result = review_source("void evaluate() { notifyOffer(); }",
                               "enum Kind { OFFER_CANDIDATE, UNCERTAIN }")
        self.assertEqual(["FAIL"] * 3, [x["status"] for x in result])

    def test_source_contract_signals_can_be_found(self):
        service = """long frameCapturedAt=now();
          if(now()-frameCapturedAt>MAX_FRAME_AGE_MS) return;"""
        classifier = "enum Kind { OFFER_EXPIRED, OFFER_LIST_CANDIDATE }"
        result = review_source(service, classifier)
        self.assertEqual(["PASS"] * 3, [x["status"] for x in result])


if __name__ == "__main__":
    unittest.main()
