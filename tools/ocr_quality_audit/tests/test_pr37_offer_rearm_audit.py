"""Source-model regressions; intentionally distinct from running Android Java."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pr37_offer_rearm_audit import Sample, replay, one_card_with_consistent_numeric_jitter, distinct_cards_without_map

def offer(t, group="A", fingerprint="same"):
    return Sample(t, "OFFER", group, fingerprint)

def map_frame(t):
    return Sample(t, "DEFINITE_NON_OFFER")


class Pr37RearmTests(unittest.TestCase):
    def test_one_card_three_stable_misreads_can_duplicate(self):
        r = replay(one_card_with_consistent_numeric_jitter())
        self.assertEqual(r["visualEpisodes"], 1)
        self.assertEqual(r["alertAttempts"], 2)
        self.assertEqual(r["duplicatesSameVisualEpisode"], 1)

    def test_two_real_distinct_cards_can_both_alert_after_gap(self):
        r = replay(distinct_cards_without_map())
        self.assertEqual(r["visualEpisodes"], 2)
        self.assertEqual(r["notifiedVisualEpisodes"], 2)
        self.assertEqual(r["duplicatesSameVisualEpisode"], 0)

    def test_one_stable_long_card_only_one_alert(self):
        frames = [offer(i * 1000) for i in range(25)]
        r = replay(frames)
        self.assertEqual(r["alertAttempts"], 1)

    def test_early_numeric_jitter_cannot_rearm_before_7500(self):
        xs = [offer(0), offer(1000)] + [offer(t, "A", "wrong") for t in (2000, 3000, 4000)]
        self.assertEqual(replay(xs)["alertAttempts"], 1)

    def test_two_confirmed_map_frames_allow_equal_value_episode(self):
        xs = [offer(0, "A"), offer(1000, "A"), map_frame(2000),
              map_frame(2500), offer(3000, "B"), offer(4000, "B")]
        r = replay(xs)
        self.assertEqual(r["notifiedVisualEpisodes"], 2)
        self.assertEqual(r["alertAttempts"], 2)

    def test_single_map_frame_does_not_reset_existing_alert(self):
        xs = [offer(0), offer(1000), map_frame(2000), offer(3000), offer(4000)]
        self.assertEqual(replay(xs)["alertAttempts"], 1)

    def test_single_uncertain_between_valid_confirmations(self):
        xs = [offer(0), Sample(400, "UNCERTAIN"), offer(1000)]
        self.assertEqual(replay(xs)["alertAttempts"], 1)

    def test_two_uncertain_clear_first_pending_confirmation(self):
        xs = [offer(0), Sample(400, "UNCERTAIN"), Sample(600, "UNCERTAIN"), offer(1000)]
        self.assertEqual(replay(xs)["alertAttempts"], 0)

    def test_more_than_5500_gap_does_not_reuse_old_confirmation(self):
        self.assertEqual(replay([offer(0), offer(6000)])["alertAttempts"], 0)

    def test_same_values_two_visual_episodes_without_gap_are_ambiguous(self):
        xs = [offer(0, "A"), offer(1000, "A"), offer(3000, "B"), offer(4000, "B")]
        r = replay(xs)
        self.assertEqual(r["visualEpisodes"], 2)
        self.assertEqual(r["notifiedVisualEpisodes"], 1)
        self.assertEqual(r["visualEpisodesNotAlerted"], 1)

    def test_two_different_values_after_alert_not_enough_to_rearm(self):
        xs = [offer(0), offer(1000), offer(8500, "A", "wrong"), offer(9200, "A", "wrong")]
        self.assertEqual(replay(xs)["alertAttempts"], 1)

    def test_uncertain_resets_new_fingerprint_confirmation(self):
        xs = [offer(0), offer(1000),
              offer(8500, "A", "wrong"),
              Sample(9000, "UNCERTAIN"),
              offer(9200, "A", "wrong"), offer(9900, "A", "wrong")]
        self.assertEqual(replay(xs)["alertAttempts"], 1)

    def test_time_regression_or_nonopaque_fixture_rejected(self):
        for xs in ([offer(1000), offer(0)], [offer(0, "real street name")],
                   [Sample(0, "OFFER", "A", " R$10,77 ")]):
            with self.subTest(xs=xs), self.assertRaises(ValueError):
                replay(xs)


if __name__ == "__main__":
    unittest.main()
