#!/usr/bin/env python3
"""Static memory-budget review; heuristic, not a substitute for device tests."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re


def review_text(source: str) -> list[dict[str, str]]:
    # Current service allocates a full-size RGBA ImageReader (3 buffers) and
    # at least one full-size Bitmap before downscaling. Never trust resize dims.
    allocations = [m.start() for m in re.finditer(r"\bImageReader\s*\.\s*newInstance\s*\(", source)]
    guarded = []
    for at in allocations:
        # Inspect the immediately preceding code for a centralized budget gate.
        prior = source[max(0, at - 450):at]
        guarded.append(bool(re.search(r"\b(?:checkFrameBudget|withinFrameBudget|requireFrameBudget)\s*\(", prior)))
    # A check in extract() is too late: the reader already allocated buffers.
    return [{
        "code": "FRAME_MEMORY_BUDGET_BEFORE_READER",
        "status": "PASS" if allocations and all(guarded) else "FAIL",
        "detail": f"{len(allocations)} ImageReader allocations; {sum(guarded)} preceded by explicit frame-budget guard"
    }]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    service = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    findings = review_text(service.read_text(encoding="utf-8")) if service.exists() else [
        {"code": "SERVICE_PRESENT", "status": "SKIP", "detail": "No Android service in this branch"}
    ]
    if args.json:
        print(json.dumps({"checks": findings}, ensure_ascii=False, indent=2))
    else:
        for item in findings:
            print(f"{item['status']} {item['code']}: {item['detail']}")
    return int(any(x["status"] == "FAIL" for x in findings))


if __name__ == "__main__":
    raise SystemExit(main())
