#!/usr/bin/env python3
"""Conservative static review of memory budget before ImageReader allocations.

A PASS indicates a lexical guard within the same Java method, NOT proof that
the guard dominates the allocation in every control-flow path, bounds bytes,
or uses overflow-safe arithmetic. Android/emulator validation is still required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

# Supports the ordinary Java method declarations in LiveCaptureService.
# This intentionally does not parse Java grammar; fail closed when uncertain.
_METHOD_START = re.compile(
    r"\b(?:void|[A-Za-z_]\w*(?:\[\])?)\s+[A-Za-z_]\w*\s*"
    r"\([^;{}]*\)\s*(?:throws\s+[A-Za-z_.,\s]+)?\{"
)
_ALLOC = re.compile(r"\bImageReader\s*\.\s*newInstance\s*\(")
_GUARD = re.compile(r"\b(?:checkFrameBudget|withinFrameBudget|requireFrameBudget)\s*\(")
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def review_text(source: str) -> list[dict[str, str]]:
    # A guard in initiate() must not protect a separate resize() method:
    # the former 450-character lookback incorrectly passed this case.
    clean = _COMMENT.sub("", source)
    methods = list(_METHOD_START.finditer(clean))
    allocations = list(_ALLOC.finditer(clean))
    guarded = []
    for alloc in allocations:
        method = next((m for m in reversed(methods) if m.end() <= alloc.start()), None)
        if method is None:
            # Some tiny test fixtures omit a method wrapper. Scan only source
            # up to the allocation, not an unrelated previous method.
            prior = clean[:alloc.start()]
        else:
            prior = clean[method.end():alloc.start()]
        guarded.append(bool(_GUARD.search(prior)))

    return [{
        "code": "FRAME_MEMORY_BUDGET_BEFORE_READER",
        "status": "PASS" if allocations and all(guarded) else "FAIL",
        "detail": f"{len(allocations)} ImageReader allocations; "
                  f"{sum(guarded)} preceded by same-method frame-budget guard"
    }]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    service = Path(args.root) / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    findings = review_text(service.read_text(encoding="utf-8")) if service.exists() else [
        {"code": "SERVICE_PRESENT", "status": "SKIP",
         "detail": "No Android service in this branch"}
    ]
    if args.json:
        print(json.dumps({"checks": findings}, ensure_ascii=False, indent=2))
    else:
        for item in findings:
            print(f"{item['status']} {item['code']}: {item['detail']}")
    return int(any(x["status"] == "FAIL" for x in findings))


if __name__ == "__main__":
    raise SystemExit(main())
