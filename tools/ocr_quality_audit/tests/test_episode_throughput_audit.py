"""Synthetic stream episode tests: independent visual truth vs OCR fingerprints."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from episode_throughput_audit import Frame, inspect

def offer(t,episode="A",fp="x",ok=True):
    return Frame(t,t,t+100,"OFFER",episode,fp,ok)
def other(t,kind="MAP"):
    return Frame(t,t,t+100,kind)

class EpisodeThroughputTests(unittest.TestCase):
    def test_thirty_frames_one_offer_one_alert(self):
        r=inspect([offer(i*700) for i in range(30)])
        self.assertEqual((r["visualEpisodes"],r["alertAttempts"],r["duplicateAlerts"]),(1,1,0))
    def test_two_groups_same_fingerprint_separated_by_map(self):
        frames=[offer(0),offer(700),other(1400),other(2100),offer(2800,"B"),offer(3500,"B")]
        r=inspect(frames)
        self.assertEqual((r["visualEpisodes"],r["notifiedVisualEpisodes"]),(2,2))
    def test_map_post_uncertain_do_not_emit_alerts(self):
        r=inspect([other(0),other(700,"POST"),other(1400,"UNCERTAIN")])
        self.assertEqual((r["alertAttempts"],r["definiteNonOffer"],r["uncertain"]),(0,2,1))
    def test_financial_abstention_breaks_confirmation(self):
        r=inspect([offer(0),offer(700,ok=False),offer(1400),offer(2100)])
        self.assertEqual((r["financialAbstentions"],r["alertAttempts"]),(1,1))
    def test_stop_callback_never_alerts(self):
        r=inspect([Frame(0,0,100,"OFFER","A","x",True,100),
                   Frame(200,200,300,"OFFER","A","x",True,100)])
        self.assertEqual((r["afterStop"],r["alertAttempts"]),(2,0))
    def test_stale_ocr_does_not_confirm(self):
        r=inspect([Frame(0,0,5000,"OFFER","A","x",True),
                   Frame(6000,6000,6100,"OFFER","A","x",True)])
        self.assertEqual((r["stale"],r["alertAttempts"]),(1,0))
    def test_first_alert_latency_is_not_ocr_latency(self):
        r=inspect([offer(0),offer(700)])
        self.assertEqual(r["firstAlertDelayMs"],800)
    def test_persistent_visual_offer_with_wrong_fingerprint_exposes_duplicate(self):
        r=inspect([offer(0),offer(1000),offer(8500,fp="wrong"),
                   offer(9200,fp="wrong"),offer(9900,fp="wrong")])
        self.assertEqual((r["visualEpisodes"],r["duplicateAlerts"]),(1,1))
    def test_invalid_personal_text_rejected(self):
        with self.assertRaises(ValueError):
            inspect([offer(0,episode="Rua Privada")])
    def test_invalid_order_rejected(self):
        with self.assertRaises(ValueError):
            inspect([offer(700),offer(0)])
    def test_empty_has_no_invented_detection(self):
        self.assertIsNone(inspect([])["firstAlertDelayMs"])

if __name__=="__main__":
    unittest.main()
