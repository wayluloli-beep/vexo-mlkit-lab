"""Strict offline adapter for synthetic MediaProjection frame-event reports.

Never accepts screenshots, OCR transcripts, driver profiles, or addresses.
Output contains only aggregate counters and event indexes, no offer IDs.
"""
import argparse
import json
import re
from dataclasses import fields
from pathlib import Path

try:
    from .stream_audit import Event, audit_stream
except ImportError:
    from stream_audit import Event, audit_stream

SCHEMA = "vexo-stream-events-v1"
MAX_FILE_BYTES = 2_000_000
MAX_EVENTS = 20_000
VALID_KINDS = {"start", "stop", "frame", "callback", "inference_start", "inference_end"}
VALID_CONTEXTS = {"OFFER_CANDIDATE", "NON_OFFER", "UNCERTAIN"}
BOOL_FIELDS = {"guard_blocked", "notified", "history_written", "unsafe_financial", "ui_applied"}
INT_FIELDS = {"epoch", "seq", "inference_ms", "roi_passes"}
ALLOWED_FIELDS = {f.name for f in fields(Event)}
GROUP_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\\Z")


class StreamInputError(ValueError):
    pass


def parse_events(doc):
    if not isinstance(doc, dict) or set(doc) != {"schema", "events"} or doc["schema"] != SCHEMA:
        raise StreamInputError("invalid stream envelope")
    rows = doc["events"]
    if not isinstance(rows, list) or len(rows) > MAX_EVENTS:
        raise StreamInputError("events must be an array with bounded size")
    result = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not {"kind", "epoch"}.issubset(row):
            raise StreamInputError(f"event {i}: missing required fields")
        if set(row) - ALLOWED_FIELDS:
            raise StreamInputError(f"event {i}: forbidden or unknown fields")
        if row["kind"] not in VALID_KINDS:
            raise StreamInputError(f"event {i}: invalid kind")
        if "context" in row and row["context"] not in VALID_CONTEXTS:
            raise StreamInputError(f"event {i}: invalid context")
        if "group" in row and (not isinstance(row["group"], str) or
                               (row["group"] and not GROUP_RE.fullmatch(row["group"]))):
            raise StreamInputError(f"event {i}: group must be opaque ASCII token")
        for key in BOOL_FIELDS.intersection(row):
            if type(row[key]) is not bool:
                raise StreamInputError(f"event {i}: invalid boolean field")
        for key in INT_FIELDS.intersection(row):
            if type(row[key]) is not int or row[key] < 0:
                raise StreamInputError(f"event {i}: invalid nonnegative integer field")
        result.append(Event(**row))
    return result


def audit_document(doc):
    return audit_stream(parse_events(doc))


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StreamInputError("duplicate JSON key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline synthetic frame safety audit; aggregates only")
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.input.stat().st_size > MAX_FILE_BYTES:
            raise StreamInputError("file exceeds synthetic event limit")
        with args.input.open("r", encoding="utf-8") as file:
            doc = json.load(file, object_pairs_hook=_no_duplicate_keys)
        report = audit_document(doc)
    except (OSError, UnicodeError, ValueError, TypeError):
        # Suppress exception details: file paths and rejected values may be private.
        print(json.dumps({"error": "invalid synthetic event input"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
