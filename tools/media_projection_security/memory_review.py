#!/usr/bin/env python3
"""Conservative review of bounded ImageReader allocations in Java source.

Source matching only; PASS is not memory measured on Android devices. The
known CaptureDimensions.fit implementation must bound pixels + max dimension
and its output dimensions must be assigned before each ImageReader allocation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

_METHOD_START = re.compile(
    r"\b(?:void|[A-Za-z_]\w*(?:\[\])?)\s+[A-Za-z_]\w*\s*"
    r"\([^;{}]*\)\s*(?:throws\s+[A-Za-z_.,\s]+)?\{"
)
_ALLOC = re.compile(r"\bImageReader\s*\.\s*newInstance\s*\(\s*([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*,")
_GUARD = re.compile(r"\b(?:checkFrameBudget|withinFrameBudget|requireFrameBudget)\s*\(")
_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _dimensions_helper_has_bounded_fit(dims_source: str) -> bool:
    clean = _COMMENT.sub("", dims_source)
    start = re.search(r"\bint\s*\[\s*\]\s+fit\s*\(\s*int\s+width\s*,\s*int\s+height\s*\)\s*\{", clean)
    if not start:
        return False
    method = clean[start.end():]
    return bool(
        re.search(r"\bMAX_DIMENSION\s*=\s*[1-9][\d_]*\s*;", clean) and
        re.search(r"\bMAX_PIXELS\s*=\s*[1-9][\d_]*L\s*;", clean) and
        re.search(r"\(\s*long\s*\)\s*width\s*\*\s*height", method) and
        "MAX_DIMENSION" in method and "MAX_PIXELS" in method and
        "Math.min" in method and "Math.sqrt" in method and
        re.search(r"return\s+new\s+int\s*\[\s*\]\s*\{\s*w\s*,\s*h\s*\}", method)
    )


def _fit_output_feeds_allocation(prior: str, first_dim: str, second_dim: str,
                                 verified_helper: bool) -> bool:
    if not verified_helper:
        return False
    for match in re.finditer(r"\bint\s*\[\s*\]\s+([A-Za-z_]\w*)\s*=\s*CaptureDimensions\.fit\s*\(", prior):
        arr = re.escape(match.group(1))
        after_fit = prior[match.end():]
        # fit values must feed the precise w/h that are passed to the reader.
        fit_width = re.search(r"\b" + re.escape(first_dim) +
                              r"\s*=\s*" + arr + r"\s*\[\s*0\s*\]\s*;", after_fit)
        fit_height = re.search(r"\b" + re.escape(second_dim) +
                               r"\s*=\s*" + arr + r"\s*\[\s*1\s*\]\s*;", after_fit)
        if fit_width and fit_height:
            return True
    return False


def _closing_brace(source: str, begin: int) -> int:
    """Find end of a brace-delimited block with string-literal awareness."""
    depth = 1
    quote = None
    escape = False
    for at in range(begin, len(source)):
        c = source[at]
        if quote:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return at
    return len(source)


def _prefix_in_enclosing_method(source: str, position: int,
                                methods: list[tuple[re.Match, int]]) -> str:
    """Exclude previous nested callback methods from guard evidence.

    The most recent method before an allocation may be onStop inside a
    MediaProjection.Callback already CLOSED, rather than initiate itself.
    """
    containing = [(m, end) for m, end in methods
                  if m.end() <= position < end]
    if not containing:
        return source[:position]
    outer, _ = max(containing, key=lambda item: item[0].start())
    prefix = list(source[outer.end():position])
    for inner, end in methods:
        if inner.start() > outer.start() and outer.end() <= inner.start() and end < position:
            # Keep offsets stable while excluding code in prior nested methods.
            lo = max(0, inner.start() - outer.end())
            hi = min(len(prefix), end + 1 - outer.end())
            for i in range(lo, hi):
                prefix[i] = " "
    return "".join(prefix)


def review_text(source: str, dimensions_source: str | None = None) -> list[dict[str, str]]:
    clean = _COMMENT.sub("", source)
    methods = [(m, _closing_brace(clean, m.end()))
               for m in _METHOD_START.finditer(clean)]
    allocations = list(_ALLOC.finditer(clean))
    verified_helper = bool(dimensions_source and _dimensions_helper_has_bounded_fit(dimensions_source))
    guarded = []
    for alloc in allocations:
        prior = _prefix_in_enclosing_method(clean, alloc.start(), methods)
        direct = bool(_GUARD.search(prior))
        via_fit = _fit_output_feeds_allocation(prior, alloc.group(1), alloc.group(2), verified_helper)
        guarded.append(direct or via_fit)

    return [{
        "code": "FRAME_MEMORY_BUDGET_BEFORE_READER",
        "status": "PASS" if allocations and all(guarded) else "FAIL",
        "detail": f"{len(allocations)} ImageReader allocations; "
                  f"{sum(guarded)} with same-method pre-allocation guard "
                  "(explicit budget or verified bounded CaptureDimensions.fit output)"
    }]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    path = root / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
    dims = root / "app/src/main/java/com/vexo/mlkitlab/CaptureDimensions.java"
    findings = review_text(
        path.read_text(encoding="utf-8"),
        dimensions_source=dims.read_text(encoding="utf-8") if dims.exists() else None
    ) if path.exists() else [
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
