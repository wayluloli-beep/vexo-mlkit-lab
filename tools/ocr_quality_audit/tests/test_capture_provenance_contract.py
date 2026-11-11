"""Synthetic provenance/episode contract; oracle episode labels are NOT observable in Android."""
from dataclasses import dataclass
import unittest

@dataclass(frozen=True)
class Event:
    epoch: int
    mode: str
    source_verified: bool
    context: str
    visual_episode: str
    fingerprint: str
    stable: bool = True
    stopped: bool = False

def audit(events):
    """Conservative reference policy; visual_episode is synthetic ground truth."""
    active_epoch = None
    alerted = set()
    held = 0
    observed = 0
    alerts = []
    for event in events:
        if event.stopped:
            active_epoch = None
            continue
        if active_epoch is None:
            active_epoch = event.epoch
        if event.epoch != active_epoch:
            held += 1
            continue
        observed += 1
        if event.context != 'OFFER' or not event.stable:
            continue
        if event.mode != 'LIVE' or not event.source_verified:
            held += 1
            continue
        if event.visual_episode in alerted:
            held += 1
            continue
        alerted.add(event.visual_episode)
        alerts.append(event.visual_episode)
    return {'observed': observed, 'alerts': alerts, 'held': held}

def e(episode='A', fingerprint='a', mode='LIVE', verified=True, epoch=1, context='OFFER', stable=True):
    return Event(epoch, mode, verified, context, episode, fingerprint, stable)

class CaptureProvenanceContract(unittest.TestCase):
    def test_lab_gallery_never_notifies_even_if_offer_looks_real(self):
        result = audit([e(mode='LAB', verified=False), e(mode='LAB', verified=False)])
        self.assertEqual(result['observed'], 2)
        self.assertEqual(result['alerts'], [])

    def test_full_screen_consent_does_not_prove_live_app_provenance(self):
        self.assertEqual(audit([e(verified=False)])['alerts'], [])

    def test_same_card_jitter_never_realerts(self):
        result = audit([e(), e(fingerprint='wrong'), e(fingerprint='wrong')])
        self.assertEqual(result['alerts'], ['A'])
        self.assertEqual(result['observed'], 3)

    def test_distinct_card_same_numeric_fingerprint_requires_episode_evidence(self):
        self.assertEqual(audit([e(), e(episode='B')])['alerts'], ['A', 'B'])

    def test_uncertain_and_map_never_notify(self):
        self.assertEqual(audit([e(context='UNCERTAIN'), e(context='MAP')])['alerts'], [])

    def test_stale_epoch_cannot_publish_after_restart(self):
        xs = [e(), Event(1,'LIVE',True,'OFFER','A','a',stopped=True), e(epoch=2,episode='B'), e(epoch=1,episode='C')]
        result = audit(xs)
        self.assertEqual(result['alerts'], ['A','B'])
        self.assertEqual(result['held'], 1)

    def test_unstable_financial_candidate_abstains(self):
        self.assertEqual(audit([e(stable=False)])['alerts'], [])

if __name__ == '__main__':
    unittest.main()
