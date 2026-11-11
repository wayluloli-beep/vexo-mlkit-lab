"""PR34 contract fixtures: aggregate synthetic evidence only; no actual OCR."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_diagnostic_audit import analyze, DiagnosticInputError, _unique_keys
from compare_live_diagnostics import compare
from test_diagnostic_version_comparison import report, with_latency


def v2(**overrides):
    base = with_latency(report(framesReceived=120, ocrAttempts=8,
                               ocrCompleted=8, offersAlerted=0,
                               offerContextCandidates=1,
                               screenContextUncertain=7,
                               awaitingTwoStableReadings=1,
                               diagnosticStage="OCR_OK_NO_CONFIRMED_OFFER"),
                        ocrLatencySamples=8, ocrLatencyLastMs=260,
                        ocrLatencyMeanMs=400, ocrLatencyP50Ms=350,
                        ocrLatencyP95Ms=850, ocrLatencyMaxMs=850)
    base['schema'] = 'vexo-live-capture-diagnostic-v2'
    base['contextEvidenceCounts'] = {
        'ocrReadsExamined': 8,
        'readsWithPriceMarker': 2,
        'readsWithActionButton': 1,
        'readsWithOfferModality': 2,
        'readsWithTwoDistances': 1,
        'readsWithTwoTimes': 1,
        'readsWith99Marker': 2,
        'readsWithPartialOfferEvidence': 2,
    }
    base.update(overrides)
    return base


class V2EvidenceTests(unittest.TestCase):
    def test_full_v2_report_is_accepted(self):
        r = analyze(v2())
        self.assertTrue(r['consistentCounters'])
        self.assertEqual(r['contextEvidenceCounts']['ocrReadsExamined'], 8)
        self.assertIn('EVIDENCE_SIGNALS_OVERLAP_NOT_ACCURACY_DENOMINATORS', r['notes'])
        self.assertEqual(r['bottleneckHypothesis'], 'STABILITY_NOT_CONFIRMED_OR_EPISODE_UNCLEAR')

    def test_old_v1_with_latency_stays_supported(self):
        d = v2()
        d['schema'] = 'vexo-live-capture-diagnostic-v1'
        d.pop('contextEvidenceCounts')
        r = analyze(d)
        self.assertTrue(r['consistentCounters'])
        self.assertIsNone(r['contextEvidenceCounts'])

    def test_v2_requires_all_six_latency_fields(self):
        d = v2()
        d.pop('ocrLatencyP95Ms')
        with self.assertRaises(DiagnosticInputError):
            analyze(d)

    def test_v2_requires_all_eight_evidence_fields(self):
        d = v2()
        d['contextEvidenceCounts'].pop('readsWithTwoTimes')
        with self.assertRaises(DiagnosticInputError):
            analyze(d)

    def test_nested_ocr_text_or_address_is_rejected(self):
        for forbidden in ('rawText', 'pickupAddress', 'price', 'platformId', 'trace'):
            with self.subTest(forbidden=forbidden):
                d = v2()
                d['contextEvidenceCounts'][forbidden] = 'private fake text'
                with self.assertRaises(DiagnosticInputError):
                    analyze(d)

    def test_evidence_counter_is_strict_integer(self):
        for unsafe in (True, 2.5, '8', None, -1):
            with self.subTest(unsafe=unsafe):
                d = v2()
                d['contextEvidenceCounts']['ocrReadsExamined'] = unsafe
                with self.assertRaises(DiagnosticInputError):
                    analyze(d)

    def test_evidence_read_count_cannot_exceed_finished_ocr(self):
        d = v2()
        d['contextEvidenceCounts']['ocrReadsExamined'] = 9
        self.assertIn('EVIDENCE_READS_EXCEED_COMPLETED_OCR', analyze(d)['violations'])

    def test_marker_count_cannot_exceed_reads(self):
        d = v2()
        d['contextEvidenceCounts']['readsWith99Marker'] = 9
        self.assertIn('EVIDENCE_SIGNAL_EXCEEDS_READS', analyze(d)['violations'])

    def test_partial_offer_evidence_requires_price_marker(self):
        d = v2()
        d['contextEvidenceCounts']['readsWithPartialOfferEvidence'] = 3
        self.assertIn('PARTIAL_OFFER_EXCEEDS_PRICE_MARKER', analyze(d)['violations'])

    def test_evidence_flags_must_not_sum_to_total_reads(self):
        r = analyze(v2())
        ev = r['contextEvidenceCounts']
        self.assertGreater(sum(ev.values()) - ev['ocrReadsExamined'], ev['ocrReadsExamined'])
        self.assertTrue(r['consistentCounters'])

    def test_stopped_v2_report_accepted(self):
        d = v2(status='CAPTURE_STOPPED')
        self.assertTrue(analyze(d)['consistentCounters'])

    def test_comparison_v2_has_evidence_deltas_without_session_proof(self):
        a = v2()
        b = v2(framesReceived=155, ocrAttempts=10, ocrCompleted=10,
               offerContextCandidates=2, screenContextUncertain=8,
               awaitingTwoStableReadings=2)
        b['contextEvidenceCounts'] = dict(a['contextEvidenceCounts'],
                                          ocrReadsExamined=10,
                                          readsWithPriceMarker=3,
                                          readsWithActionButton=2,
                                          readsWithOfferModality=3,
                                          readsWithTwoDistances=2,
                                          readsWithTwoTimes=2,
                                          readsWith99Marker=3,
                                          readsWithPartialOfferEvidence=3)
        b.update(ocrLatencySamples=10, ocrLatencyMeanMs=385,
                 ocrLatencyP50Ms=350, ocrLatencyLastMs=250)
        result = compare(a, b)
        self.assertTrue(result['canCompare'])
        self.assertFalse(result['sessionContinuityProven'])
        self.assertEqual(result['evidenceDeltasIfSameSession']['ocrReadsExamined'], 2)
        self.assertEqual(result['counterDeltasIfSameSession']['offerContextCandidates'], 1)

    def test_v1_and_v2_must_not_be_compared(self):
        a = v2()
        b = dict(a)
        b['schema'] = 'vexo-live-capture-diagnostic-v1'
        b.pop('contextEvidenceCounts')
        self.assertEqual(compare(a, b)['reason'], 'INCOMPATIBLE_DIAGNOSTIC_VERSIONS')

    def test_reset_of_evidence_counter_invalidates_diff(self):
        a = v2()
        b = v2()
        b['contextEvidenceCounts'] = dict(a['contextEvidenceCounts'],
                                          readsWithActionButton=0)
        result = compare(a, b)
        self.assertFalse(result['canCompare'])
        self.assertIn('readsWithActionButton', result['decreasedCounters'])

    def test_v2_does_not_infer_error_from_82_uncertain_frames(self):
        d = v2(framesReceived=3439, ocrAttempts=83, ocrCompleted=83,
               screenContextUncertain=82)
        d['contextEvidenceCounts']['ocrReadsExamined'] = 83
        d.update(ocrLatencySamples=83, ocrLatencyP95Ms=950,
                 ocrLatencyMaxMs=2481, ocrLatencyMeanMs=421,
                 ocrLatencyP50Ms=342, ocrLatencyLastMs=400)
        result = analyze(d)
        self.assertTrue(result['consistentCounters'])
        self.assertNotIn('OCR_ACCURACY', result['bottleneckHypothesis'])
        self.assertIn('MISSING_MARKERS_MAY_BE_MAP_PLAYER_AD_OR_INCOMPLETE_OCR', result['notes'])

    def test_duplicate_nested_json_keys_are_blocked(self):
        with self.assertRaises(DiagnosticInputError):
            _unique_keys([('ocrReadsExamined', 5), ('ocrReadsExamined', 6)])


if __name__ == '__main__':
    unittest.main()
