"""Synthetic episode-stage accounting. No OCR text, screenshots or locations."""
import unittest
from collections import Counter

def audit(events):
    counts = Counter()
    seen = set()
    alerted = set()
    first_observed = {}
    first_alert = {}
    for e in events:
        episode = e["episode"]
        stage = e["stage"]
        t = e["ms"]
        if stage not in {"OBSERVED", "UNCERTAIN", "CANDIDATE", "GATE_HELD",
                         "AWAITING_STABLE", "ALERT", "STOP", "STALE"}:
            raise ValueError("unknown stage")
        if not isinstance(t, int) or t < 0:
            raise ValueError("invalid timestamp")
        if not isinstance(episode, int) or episode < 0:
            raise ValueError("episode must be a synthetic integer")
        counts[stage] += 1
        if stage == "OBSERVED":
            seen.add(episode)
            first_observed.setdefault(episode, t)
        if stage == "ALERT":
            if episode not in seen:
                raise ValueError("alert without observation")
            alerted.add(episode)
            first_alert.setdefault(episode, t)
    return {
        "observedEpisodes": len(seen),
        "alertedEpisodes": len(alerted),
        "missedEpisodes": len(seen - alerted),
        "alertEvents": counts["ALERT"],
        "duplicateAlerts": counts["ALERT"] - len(alerted),
        "firstAlertMs": min((first_alert[x] - first_observed[x] for x in alerted), default=None),
        "gateHeldEvents": counts["GATE_HELD"],
        "uncertainEvents": counts["UNCERTAIN"],
        "recallByEpisode": len(alerted) / len(seen) if seen else None,
    }

def ev(episode, stage, ms):
    return {"episode": episode, "stage": stage, "ms": ms}

class EpisodeStageAuditTests(unittest.TestCase):
    def test_30_frames_one_episode_one_alert(self):
        events = [ev(1, "OBSERVED", n * 100) for n in range(30)]
        events += [ev(1, "ALERT", 400), ev(1, "GATE_HELD", 600)]
        result = audit(events)
        self.assertEqual(result["observedEpisodes"], 1)
        self.assertEqual(result["alertEvents"], 1)
        self.assertEqual(result["duplicateAlerts"], 0)
        self.assertEqual(result["firstAlertMs"], 400)

    def test_two_episodes_same_financial_fingerprint(self):
        # Identity comes from synthetic visual oracle, never from equal price/km.
        events = [ev(1, "OBSERVED", 0), ev(1, "ALERT", 300),
                  ev(2, "OBSERVED", 800), ev(2, "ALERT", 1100)]
        self.assertEqual(audit(events)["recallByEpisode"], 1.0)

    def test_held_events_are_not_missed_offers(self):
        events = [ev(1, "OBSERVED", 0), ev(1, "ALERT", 100)]
        events += [ev(1, "GATE_HELD", n) for n in range(17)]
        self.assertEqual(audit(events)["missedEpisodes"], 0)

    def test_jitter_realert_is_duplicate(self):
        events = [ev(1, "OBSERVED", 0), ev(1, "ALERT", 100),
                  ev(1, "ALERT", 9000)]
        self.assertEqual(audit(events)["duplicateAlerts"], 1)

    def test_uncertain_not_equal_to_new_offer(self):
        events = [ev(1, "OBSERVED", 0)]
        events += [ev(1, "UNCERTAIN", n) for n in range(106)]
        result = audit(events)
        self.assertEqual(result["observedEpisodes"], 1)
        self.assertEqual(result["missedEpisodes"], 1)

    def test_no_offer_no_recall_claim(self):
        self.assertIsNone(audit([ev(0, "UNCERTAIN", 0)])["recallByEpisode"])

    def test_no_alert_without_observed_episode(self):
        with self.assertRaises(ValueError):
            audit([ev(1, "ALERT", 0)])

    def test_stale_and_stop_not_alerts(self):
        result = audit([ev(1, "OBSERVED", 0), ev(1, "STALE", 5000),
                        ev(1, "STOP", 5100)])
        self.assertEqual(result["alertEvents"], 0)

if __name__ == "__main__":
    unittest.main()
