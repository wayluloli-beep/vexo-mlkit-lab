"""Offline runner tests use only synthetic reports (no private captures)."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check import check_report  # noqa: E402


def mock_report():
    return {
        "schema": "vexo-ocr-batch-report-v1",
        "appVersion": "synthetic-check",
        "testImages": 1,
        "summary": {
            "checked": 2, "correct": 1, "discrepant": 1,
            "accuracyPct": 50, "processingErrors": 0,
        },
        "perField": {
            "offerPrice": {"checked": 1, "correct": 0},
            "platform": {"checked": 1, "correct": 1},
        },
        "samples": [{
            "id": "synthetic-only", "tested": 2, "correct": 1,
            "fields": {
                "offerPrice": {"expected": None, "actual": "42", "status": "false_positive"},
                "platform": {"expected": "99", "actual": "99", "status": "ok"},
            },
        }],
    }


class CheckRunnerTests(unittest.TestCase):
    def test_cli_validator_passes_reconciled_false_positive(self):
        doc = mock_report()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "local.json")
            path.write_text(json.dumps(doc), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                code = check_report(path)
        self.assertEqual(code, 0)
        self.assertIn("PASS: report counters reconcile", output.getvalue())
        self.assertNotIn("42", output.getvalue())  # no raw OCR values

    def test_cli_validator_rejects_invalid_counter(self):
        doc = mock_report()
        doc["summary"]["correct"] = 2
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "local.json")
            path.write_text(json.dumps(doc), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as errors:
                code = check_report(path)
        self.assertEqual(code, 3)
        self.assertIn("internal consistency", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
