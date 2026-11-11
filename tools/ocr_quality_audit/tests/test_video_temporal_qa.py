"""No screenshots, fares, locations, OCR text, route data or real media."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video_temporal_qa import Alert, Window, score_timeline, long_recording_fixture, short_recording_fixture


class TemporalVideoAuditTests(unittest.TestCase):
    def test_eight_frames_are_only_one_visual_episode(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(190, financial_guard_passed=True)], observed_frame_count=8)
        self.assertEqual((r['observedFrames'], r['cardEpisodes'], r['cardEpisodesAlerted']), (8, 1, 1))
        self.assertEqual(r['firstCardAlertP95Seconds'], 2)

    def test_map_earnings_no_offer_false_alarm(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(100, financial_guard_passed=True), Alert(230, financial_guard_passed=True)])
        self.assertEqual(r['falseAlerts'], 2)
        self.assertEqual(r['missedCardEpisodes'], 1)

    def test_no_alert_is_missed_event_not_8_misses(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [], observed_frame_count=8)
        self.assertEqual(r['missedCardEpisodes'], 1)

    def test_two_sightings_same_values_are_separate_visual_episodes(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [Alert(2, financial_guard_passed=True), Alert(35, financial_guard_passed=True)])
        self.assertEqual((r['cardEpisodes'], r['cardEpisodesAlerted'], r['duplicateAlerts']), (2, 2, 0))
        self.assertEqual(r['firstCardAlertP95Seconds'], 2)

    def test_duplicate_alarm_same_episode_is_detected(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(189, financial_guard_passed=True), Alert(195, financial_guard_passed=True)])
        self.assertEqual((r['cardEpisodesAlerted'], r['duplicateAlerts']), (1, 1))

    def test_advertising_price_is_not_a_ride(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [Alert(72, financial_guard_passed=True)])
        self.assertEqual((r['advertAlerts'], r['falseAlerts']), (1, 1))

    def test_expired_request_cannot_alert(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [Alert(61.5, 'LIST_REVIEW')])
        self.assertEqual((r['expiredAlerts'], r['falseAlerts']), (1, 1))

    def test_request_list_is_review_not_confirmed_ride(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [Alert(54, 'LIST_REVIEW')])
        self.assertEqual(r['listReviewEpisodes'], 1)
        self.assertEqual(r['cardEpisodesAlerted'], 0)
        self.assertEqual(r['falseAlerts'], 0)

    def test_request_list_cannot_be_silently_confirmed_card(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [Alert(54, 'CARD_ALERT', True)])
        self.assertEqual((r['wrongKindAlerts'], r['falseAlerts']), (1, 1))

    def test_absence_of_list_alert_not_counted_as_missed_card(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [])
        self.assertEqual(r['missedCardEpisodes'], 2)
        self.assertEqual(r['listAwaitingReview'], 1)

    def test_unverified_card_alert_is_unsafe(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(190)])
        self.assertEqual(r['unsafeAlerts'], 1)

    def test_slow_detection_beyond_three_seconds_is_separate_metric(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(196, financial_guard_passed=True)])
        self.assertEqual(r['lateFirstAlerts'], 1)
        self.assertEqual(r['firstCardAlertP95Seconds'], 8)

    def test_unlabeled_gap_is_unknown_not_false_positive(self):
        duration, windows = short_recording_fixture()
        r = score_timeline(duration, windows, [Alert(48, financial_guard_passed=True)])
        self.assertEqual(r['unscoredAlerts'], 1)
        self.assertEqual(r['falseAlerts'], 0)

    def test_callback_after_stop_is_false(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(190, financial_guard_passed=True)], stop_s=189)
        self.assertEqual((r['afterStopAlerts'], r['falseAlerts']), (1, 1))

    def test_unsafe_alert_does_not_count_as_safe_detection(self):
        duration, windows = long_recording_fixture()
        r = score_timeline(duration, windows, [Alert(190)])
        self.assertEqual((r["unsafeAlerts"], r["missedCardEpisodes"], r["falseAlerts"]), (1, 1, 1))

    def test_unordered_alert_events_rejected(self):
        duration, windows = long_recording_fixture()
        with self.assertRaises(ValueError):
            score_timeline(duration, windows, [Alert(195, financial_guard_passed=True), Alert(190, financial_guard_passed=True)])

    def test_no_endpoints_or_overlapping_labels(self):
        for ws in ([Window(0, 10, 'CARD', 'a'), Window(9, 11, 'CARD', 'b')],
                   [Window(0, 10, 'CARD', 'a'), Window(10, 20, 'CARD', 'a')],
                   [Window(0, 10, 'AD', 'named')]):
            with self.subTest(ws=ws), self.assertRaises(ValueError):
                score_timeline(30, ws, [])

    def test_reject_bad_alert_and_sensitive_fixture_identity(self):
        with self.assertRaises(ValueError):
            score_timeline(30, [Window(1, 5, 'CARD', 'private route address 123')], [])
        with self.assertRaises(ValueError):
            score_timeline(30, [Window(1, 5, 'CARD', 'safe')], [Alert(2, 'UNKNOWN')])


if __name__ == '__main__':
    unittest.main()
