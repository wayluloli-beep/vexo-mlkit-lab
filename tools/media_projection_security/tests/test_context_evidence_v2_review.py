"""Synthetic privacy / stale-epoch regressions for schema v2 (no real OCR)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_evidence_v2_review import EVIDENCE_KEYS, review_text


STATE_HEAD = """
public final class LiveCaptureState {
 private static volatile boolean active=false;
 private static final CaptureContextEvidence contextEvidence=new CaptureContextEvidence();
 static synchronized void begin() { contextEvidence.reset(); active=true; }
 static void recordContextEvidence(int mask) {
     if(active) contextEvidence.record(mask);
 }
 static synchronized String safeDiagnosticReport() {
     JSONObject report=new JSONObject();
     report.put("schema","vexo-live-capture-diagnostic-v2");
     long[] ev=contextEvidence.snapshot();
     JSONObject evidence=new JSONObject();
"""
STATE_TAIL = """
     report.put("contextEvidenceCounts",evidence);
     return report.toString(2);
 }
}
"""
FIELDS = "\n".join(
    f'     evidence.put("{name}",ev[{i}]);'
    for i, name in enumerate(EVIDENCE_KEYS)
)
STATE = STATE_HEAD + FIELDS + STATE_TAIL

SERVICE_GOOD = """
public final class LiveCaptureService {
 Object sessionLock;
 boolean sessionAlive(long session) { return true; }
 void evaluate(String text,long session) {
   int mask=ScreenContextClassifier.diagnosticEvidenceMask(text);
   synchronized(sessionLock) {
     if(!sessionAlive(session)) return;
     LiveCaptureState.recordContextEvidence(mask);
   }
 }
}
"""
SERVICE_BAD = SERVICE_GOOD.replace(
    "   synchronized(sessionLock) {\n     if(!sessionAlive(session)) return;\n     LiveCaptureState.recordContextEvidence(mask);\n   }",
    "   LiveCaptureState.recordContextEvidence(mask);"
)
COUNTER = """
public final class CaptureContextEvidence {
 private final AtomicLong reads=new AtomicLong();
 private final AtomicLong price=new AtomicLong();
 private final AtomicLong action=new AtomicLong();
 private final AtomicLong modality=new AtomicLong();
 private final AtomicLong twoDistances=new AtomicLong();
 private final AtomicLong twoMinutes=new AtomicLong();
 private final AtomicLong literal99=new AtomicLong();
 private final AtomicLong partialOffer=new AtomicLong();

 void reset() {
    reads.set(0); price.set(0); action.set(0); modality.set(0);
    twoDistances.set(0); twoMinutes.set(0); literal99.set(0);
    partialOffer.set(0);
 }
 void record(int flags) {
    reads.incrementAndGet();
    if((flags&1)!=0) price.incrementAndGet();
 }
}
"""
CLASSIFIER = """
public final class ScreenContextClassifier {
 int diagnosticEvidenceMask(String text) {
  int bits=0;
  bits|=EVIDENCE_PRICE;
  return bits;
 }
 Kind classify(String text) {
  if(text!=null) return Kind.OFFER_CANDIDATE;
  return Kind.UNCERTAIN;
 }
}
"""


def results(state=STATE, service=SERVICE_GOOD, counter=COUNTER,
            classifier=CLASSIFIER):
    return {x["code"]: x["status"] for x in
            review_text(state,service,counter,classifier)}


class EvidenceV2ReviewTests(unittest.TestCase):
    def test_safe_v2_export_and_session_lock_pass(self):
        self.assertTrue(all(v == "PASS" for v in results().values()),
                        results())

    def test_pr34_style_unguarded_service_increment_is_blocked(self):
        self.assertEqual(
            "FAIL", results(service=SERVICE_BAD)["V2_SESSION_GUARD_BEFORE_COUNT"])

    def test_previous_epoch_check_elsewhere_cannot_authorize_count(self):
        bad = SERVICE_BAD.replace(
            "   LiveCaptureState.recordContextEvidence(mask);",
            "   if(epoch.get()!=session) return;\n"
            "   LiveCaptureState.recordContextEvidence(mask);"
        )
        self.assertEqual(
            "FAIL", results(service=bad)["V2_SESSION_GUARD_BEFORE_COUNT"])

    def test_extra_nested_field_is_rejected(self):
        bad = STATE.replace(
            '     report.put("contextEvidenceCounts",evidence);',
            '     evidence.put("route",rawText);\n'
            '     report.put("contextEvidenceCounts",evidence);'
        )
        self.assertEqual(
            "FAIL", results(state=bad)["V2_NESTED_KEYS_VALUES_ALLOWLIST"])

    def test_same_key_can_not_export_raw_price(self):
        bad = STATE.replace(
            'evidence.put("readsWithPriceMarker",ev[1])',
            'evidence.put("readsWithPriceMarker",lastCandidate)')
        self.assertEqual(
            "FAIL", results(state=bad)["V2_NESTED_KEYS_VALUES_ALLOWLIST"])

    def test_dynamic_key_is_not_allowed(self):
        bad = STATE.replace(
            'evidence.put("ocrReadsExamined",ev[0])',
            'evidence.put(dynamicKey,ev[0])')
        self.assertEqual(
            "FAIL", results(state=bad)["V2_NESTED_KEYS_VALUES_ALLOWLIST"])

    def test_schema_v1_with_nested_extra_is_blocked(self):
        bad = STATE.replace(
            'vexo-live-capture-diagnostic-v2',
            'vexo-live-capture-diagnostic-v1')
        self.assertEqual("FAIL", results(state=bad)["V2_SCHEMA_EXACT"])

    def test_no_ocr_string_serialization(self):
        bad = STATE.replace(
            "     return report.toString(2);",
            "     String ignored=lastCandidate;\n"
            "     return report.toString(2);")
        self.assertEqual(
            "FAIL", results(state=bad)["V2_NO_PRIVATE_TEXT_OR_PIXEL_REFERENCES"])

    def test_counters_only_no_text_storage(self):
        bad = COUNTER.replace(
            " private final AtomicLong reads=new AtomicLong();",
            " private String ocrText;\n private final AtomicLong reads=new AtomicLong();"
        )
        self.assertEqual("FAIL", results(counter=bad)["V2_COUNTERS_ONLY_RAM_AND_RESET"])

    def test_missing_reset_must_fail(self):
        bad = COUNTER.replace("partialOffer.set(0);", "")
        self.assertEqual("FAIL", results(counter=bad)["V2_COUNTERS_ONLY_RAM_AND_RESET"])

    def test_remove_counter_reset_between_sessions(self):
        bad = STATE.replace("contextEvidence.reset();", "")
        self.assertEqual("FAIL", results(state=bad)["V2_COUNTERS_ONLY_RAM_AND_RESET"])

    def test_documented_classifier_decision_not_removed(self):
        bad = CLASSIFIER.replace("return Kind.OFFER_CANDIDATE", "return Kind.UNCERTAIN")
        self.assertEqual("FAIL",results(classifier=bad)["V2_DIAGNOSTIC_NOT_OFFER_DECISION"])


if __name__ == "__main__":
    unittest.main()
