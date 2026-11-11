"""Synthetic fail-closed privacy tests for the new v3 diagnostics."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from diagnostic_v3_review import EXPECTED, NESTED_VALUES, review_text

STATE = (
    "public class LiveCaptureState {\n"
    " private static final AtomicLong staleOcrFrames=new AtomicLong();\n"
    " private static final AtomicLong offerGateHeld=new AtomicLong();\n"
    " private static final AtomicLong offerCandidatesWithoutLogo=new AtomicLong();\n"
    " void begin() {staleOcrFrames.set(0);offerGateHeld.set(0);"
    "offerCandidatesWithoutLogo.set(0);}\n"
    " public static String safeDiagnosticReport() {\n"
    " JSONObject report=new JSONObject();\n"
    " long[] ev=contextEvidence.snapshot();\n"
    " JSONObject evidence=new JSONObject();\n" +
    "".join(f' evidence.put("{name}",{value});\n' for name,value in NESTED_VALUES) +
    "".join(f' report.put("{name}",{value});\n' for name,value in EXPECTED.items()) +
    " return report.toString(2);\n}\n}\n"
)
ACTIVITY = """
public class LiveCaptureActivity {
 void onCreate() {
  copyReport.setOnClickListener(v -> {
   clipboard.setPrimaryClip(ClipData.newPlainText(
       "Vexo", LiveCaptureState.safeDiagnosticReport()));
  });
 }
}
"""
SERVICE = """
public class LiveCaptureService {
 void evaluate(String text,long session) {
  synchronized(sessionLock) {
   if(!sessionAlive(session)) return;
   LiveCaptureState.recordContextEvidence(127);
  }
 }
}
"""

def statuses(state=STATE,activity=ACTIVITY,service=SERVICE):
    return {c["code"]:c["status"] for c in review_text(state,activity,service)}

class V3PrivacyTests(unittest.TestCase):
    def test_safe_v3_baseline(self):
        self.assertTrue(all(x=="PASS" for x in statuses().values()),statuses())

    def test_v2_schema_with_new_fields_is_rejected(self):
        s=STATE.replace("vexo-live-capture-diagnostic-v3","vexo-live-capture-diagnostic-v2")
        self.assertEqual("FAIL",statuses(state=s)["V3_SCHEMA_EXACT"])

    def test_extra_raw_text_field_rejected(self):
        s=STATE.replace(" return report.toString(2);",
                        ' report.put("rawText",rawOcr);\n return report.toString(2);')
        self.assertEqual("FAIL",statuses(state=s)["V3_TOP_KEYS_AND_VALUES_EXACT"])

    def test_stolen_value_in_approved_counter_field_rejected(self):
        s=STATE.replace('report.put("offerGateHeldFrames",offerGateHeld.get())',
                        'report.put("offerGateHeldFrames",lastCandidate)')
        self.assertEqual("FAIL",statuses(state=s)["V3_TOP_KEYS_AND_VALUES_EXACT"])

    def test_nested_extra_field_rejected(self):
        s=STATE.replace(' report.put("schema",',
                        ' evidence.put("passengerAddress",ocrRaw);\n report.put("schema",')
        self.assertEqual("FAIL",statuses(state=s)["V3_NESTED_EVIDENCE_EXACT"])

    def test_nested_approved_field_wrong_value_rejected(self):
        s=STATE.replace('evidence.put("readsWithPriceMarker",ev[1])',
                        'evidence.put("readsWithPriceMarker",rawPrice)')
        self.assertEqual("FAIL",statuses(state=s)["V3_NESTED_EVIDENCE_EXACT"])

    def test_report_reads_candidate_rejected(self):
        s=STATE.replace(" return report.toString(2);",
                        " String leak=lastCandidate;\n return report.toString(2);")
        self.assertEqual("FAIL",statuses(state=s)["V3_NO_PRIVATE_REPORT_REFERENCES"])

    def test_new_counter_not_reset_rejected(self):
        s=STATE.replace("offerGateHeld.set(0);","")
        self.assertEqual("FAIL",statuses(state=s)["V3_RESET_EXTRA_COUNTERS"])

    def test_without_user_click_rejected(self):
        s=ACTIVITY.replace("copyReport.setOnClickListener(v -> {","")
        self.assertEqual("FAIL",statuses(activity=s)["V3_CLIPBOARD_USER_INITIATED"])

    def test_unlocked_counter_rejected(self):
        s=SERVICE.replace("if(!sessionAlive(session)) return;","")
        self.assertEqual("FAIL",statuses(service=s)["V3_SERVICE_HAS_SESSION_CHECK"])

if __name__=="__main__":
    unittest.main()
