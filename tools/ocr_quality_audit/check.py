#!/usr/bin/env python3
"""Local/CI entrypoint for Vexo OCR audit checks; no Android or third-party libs.

Examples:
    python tools/ocr_quality_audit/check.py
    python tools/ocr_quality_audit/check.py --report /private/path/vexo-report.json

Reports are read locally, never copied, uploaded, or printed verbatim.
"""
from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

from audit import ReportError, _read, analyze

INCONSISTENCY_PREFIXES = (
    "summary.discrepant does not equal",
    "summary.accuracyPct disagrees",
    "perField totals do not reconcile",
    "samples count differs",
    "sample status totals differ",
    "sample field totals disagree",
    "tested differs from recognized",
    "correct differs from ok",
    "unrecognized status",
    "unexpected field",
    "false_positive expected must be null",
    "false_positive actual should be non-empty",
    "status ok but numeric expected/actual differ",
)


def check_report(path: Path) -> int:
    """Use exported numbers as asserted input, not independently verified labels."""
    try:
        result = analyze(_read(path))
    except ReportError as exc:
        print(f"Report rejected: {type(exc).__name__}; see local input schema.", file=sys.stderr)
        return 2
    totals = result["totals"]
    print(
        f"Report {result['appVersion']}: {result['testImages']} images, "
        f"{totals['correct']}/{totals['checked']} fields, "
        f"{totals['errors']} reported errors"
    )
    if result["sampleAudit"]:
        risk = result["sampleAudit"]["offerRisk"]
        print(f"Offers with decision-relevant reported errors: "
              f"{risk['offersWithDecisionRelevantError']}/{risk['evaluatedOffers']} "
              "(checked fields only)")
    issues = [w for w in result["warnings"]
              if any(w.startswith(prefix) or prefix in w for prefix in INCONSISTENCY_PREFIXES)]
    if issues:
        # Do not print per-case details, field raw values, or file contents in CI.
        print(f"FAIL: {len(issues)} internal consistency checks require review.", file=sys.stderr)
        return 3
    print("PASS: report counters reconcile; this does not validate OCR correctness.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path,
                        help="optional locally exported JSON; never upload into CI")
    args = parser.parse_args(argv)
    here = Path(__file__).resolve().parent
    tests = unittest.defaultTestLoader.discover(str(here / "tests"),
                                                 pattern="test_*.py",
                                                 top_level_dir=str(here / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if not result.wasSuccessful():
        return 1
    if args.report:
        return check_report(args.report)
    print("PASS: Python-only synthetic audit checks. Android/ML Kit not executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
