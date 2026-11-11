#!/usr/bin/env python3
"""Offline, read-only quality audit for Vexo OCR batch JSON exports.

The analyzer checks reported arithmetic, flags risk-bearing fields, and compares
version aggregates. It does not re-run OCR or independently verify screenshots.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA = "vexo-ocr-batch-report-v1"
FINANCIAL_DIRECT = "financial_direct"
DISTANCE = "distance_indirect"
OTHER = "other"


class ReportError(ValueError):
    """Report could not be safely understood."""


def _count(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReportError(f"{label} must be a non-negative integer")
    return value


def _name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReportError(f"{label} must be a non-empty string")
    return value.strip()


def _pct(correct: int, checked: int) -> float | None:
    return round(correct * 100 / checked, 2) if checked else None


def _kind(field: str) -> str:
    text = re.sub(r"[^a-z0-9]", "", field.lower())
    # Check rate before generic price/fare, and surge before generic tariff.
    if any(k in text for k in (
        "perkm", "pricekm", "ratekm", "valorpkm", "valorkm", "reaisporkm",
        "rkm", "kmrate", "kmprice", "ganhoporkm", "earningperkm",
    )):
        return FINANCIAL_DIRECT
    if any(k in text for k in (
        "surge", "dynamic", "dinamica", "dinamico", "multiplicador",
        "multiplier", "tarifadyn", "tarifadin",
    )):
        return FINANCIAL_DIRECT
    if any(k in text for k in (
        "offerprice", "finalprice", "fare", "price", "amount", "valor",
        "tarifa", "earnings", "ganhos", "pagamento", "remuneracao",
    )):
        return FINANCIAL_DIRECT
    if any(k in text for k in ("distance", "distancia", "pickupkm", "tripkm", "totalkm", "quilomet")):
        return DISTANCE
    return OTHER


def _number(raw: Any) -> Decimal | None:
    """Parse explicit numerical values only; never infer missing ground truth."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        try:
            dec = Decimal(str(raw))
            return dec if dec.is_finite() else None
        except InvalidOperation:
            return None
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower().replace("\u00a0", " ")
    s = re.sub(r"^(?:r\$|brl)\s*", "", s).strip()
    s = re.sub(r"\s*(?:km|reais|x|r\$/km)\s*$", "", s).strip()
    s = s.replace(" ", "")
    if not re.fullmatch(r"[+-]?[0-9.,]+", s):
        return None
    # Brazilian separators: 1.234,56; English: 1,234.56; simple 12,34.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = Decimal(s)
        return v if v.is_finite() else None
    except InvalidOperation:
        return None


def _same_value(a: Any, b: Any) -> bool:
    x, y = _number(a), _number(b)
    return x == y if x is not None and y is not None else a == b


def _read(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            doc = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ReportError("top-level report must be a JSON object")
    return doc


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise ReportError("report must be a JSON object")
    if report.get("schema") != SCHEMA:
        raise ReportError(f"unsupported schema (expected {SCHEMA})")
    version = _name(report.get("appVersion"), "appVersion")
    images = _count(report.get("testImages"), "testImages")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ReportError("summary must be an object")
    total = _count(summary.get("checked"), "summary.checked")
    correct = _count(summary.get("correct"), "summary.correct")
    if correct > total:
        raise ReportError("summary.correct exceeds summary.checked")
    discrepancy_count = _count(summary.get("discrepant"), "summary.discrepant")
    processing_errors = _count(summary.get("processingErrors", 0), "summary.processingErrors")
    fields = report.get("perField")
    if not isinstance(fields, dict) or not fields:
        raise ReportError("perField must be a non-empty object")

    warnings: list[str] = []
    if total - correct != discrepancy_count:
        warnings.append("summary.discrepant does not equal checked - correct; review generator definitions")
    claimed_pct = summary.get("accuracyPct")
    if claimed_pct is not None:
        claimed_num = _number(claimed_pct)
        computed = _pct(correct, total)
        if claimed_num is None or computed is None or abs(claimed_num - Decimal(str(computed))) > Decimal("0.11"):
            warnings.append("summary.accuracyPct disagrees with recalculation (or is invalid)")
    if images <= 10:
        warnings.append("small image sample: unsuitable for production-readiness claims")
    if processing_errors:
        warnings.append("processingErrors reported: validate their denominator and impact separately")

    per_field: dict[str, dict[str, Any]] = {}
    checked_sum = correct_sum = 0
    for field, v in fields.items():
        _name(field, "perField field name")
        if not isinstance(v, dict):
            raise ReportError(f"perField.{field} must be an object")
        n = _count(v.get("checked"), f"perField.{field}.checked")
        ok = _count(v.get("correct"), f"perField.{field}.correct")
        if ok > n:
            raise ReportError(f"perField.{field}.correct exceeds checked")
        checked_sum += n
        correct_sum += ok
        per_field[field] = {
            "checked": n, "correct": ok, "errors": n - ok,
            "accuracyPct": _pct(ok, n), "riskCategory": _kind(field),
        }
    if checked_sum != total or correct_sum != correct:
        warnings.append("perField totals do not reconcile with summary; global and field metrics may have different coverage")

    # Only one documented optional detail format is accepted. Unknown case formats
    # are never guessed into measured results.
    details = report.get("discrepancies")
    flagged: list[dict[str, Any]] = []
    if details is None:
        warnings.append("no per-error ground truth: financial severity cannot be confirmed from aggregates")
    elif not isinstance(details, list):
        warnings.append("discrepancies is not an array; individual errors were not interpreted")
    else:
        for i, item in enumerate(details):
            if not isinstance(item, dict) or not isinstance(item.get("field"), str):
                warnings.append(f"discrepancies[{i}] lacks a valid field; skipped")
                continue
            field = item["field"].strip()
            if not field or field not in per_field:
                warnings.append(f"discrepancies[{i}] field not found in perField; skipped")
                continue
            category = _kind(field)
            if category == OTHER:
                continue
            actual_key = "actual" if "actual" in item else "observed"
            if "expected" not in item or actual_key not in item:
                flagged.append({"field": field, "caseId": item.get("caseId"),
                                "riskCategory": category, "status": "unquantified_missing_values"})
                continue
            expected, actual = item["expected"], item[actual_key]
            if _same_value(expected, actual):
                warnings.append(f"discrepancies[{i}] has equal/equivalent values; not flagged as mismatch")
                continue
            x, y = _number(expected), _number(actual)
            # A financial-critical flag means a reported discrepancy in a
            # decision-relevant field; it does NOT prove actual financial loss.
            status = ("critical_review" if category == FINANCIAL_DIRECT else "distance_review")
            flag = {"field": field, "caseId": item.get("caseId"),
                    "riskCategory": category, "status": status}
            if x is not None and y is not None:
                flag["absoluteDifference"] = str(abs(x - y))
            flagged.append(flag)
        if len(details) != discrepancy_count:
            warnings.append("detail count differs from reported discrepancies; details may be incomplete")

    risk_fields = [name for name, d in per_field.items() if d["errors"] and d["riskCategory"] != OTHER]
    if risk_fields and not flagged:
        warnings.append("risk-bearing fields have aggregate errors but no usable mismatch values; criticality is unconfirmed")

    # Dataset markers are optional. If absent, comparisons remain unpaired.
    dataset = {key: report[key] for key in ("datasetId", "datasetHash", "caseSetId")
               if isinstance(report.get(key), str) and report[key].strip()}
    return {
        "schema": SCHEMA, "appVersion": version, "testImages": images,
        "totals": {"checked": total, "correct": correct, "errors": total - correct,
                   "discrepantReported": discrepancy_count, "processingErrors": processing_errors,
                   "accuracyPct": _pct(correct, total)},
        "perField": per_field, "riskBearingFieldsWithErrors": risk_fields,
        "reviewFlags": flagged, "datasetMarkers": dataset, "warnings": warnings,
        "scope": "Arithmetic/metadata audit only; original screenshots were not independently verified",
    }


def compare(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    a, b = old["datasetMarkers"], new["datasetMarkers"]
    matched = [key for key in a if key in b and a[key] == b[key]]
    conflicting = [key for key in a if key in b and a[key] != b[key]]
    if conflicting:
        dataset_status = "different_dataset_markers"
    elif matched:
        dataset_status = "matching_marker_not_independently_verified"
    else:
        dataset_status = "unverified_dataset_identity"
    keys = sorted(set(old["perField"]) | set(new["perField"]))
    fields: dict[str, dict[str, Any]] = {}
    for key in keys:
        before = old["perField"].get(key)
        after = new["perField"].get(key)
        old_pct = before["accuracyPct"] if before else None
        new_pct = after["accuracyPct"] if after else None
        fields[key] = {
            "beforeChecked": before["checked"] if before else None,
            "afterChecked": after["checked"] if after else None,
            "beforeAccuracyPct": old_pct, "afterAccuracyPct": new_pct,
            "deltaPercentagePoints": round(new_pct - old_pct, 2)
            if new_pct is not None and old_pct is not None else None,
        }
    old_pct, new_pct = old["totals"]["accuracyPct"], new["totals"]["accuracyPct"]
    notes = ["A percentage-point delta is descriptive, not proof of better real-world accuracy.",
             "Matching image counts do not establish matching images; fields from one print are correlated."]
    if dataset_status != "matching_marker_not_independently_verified":
        notes.append("Datasets are not confirmed identical; do not label this change regression or improvement.")
    if old["testImages"] != new["testImages"]:
        notes.append("Test-image counts differ; comparison may reflect sample composition.")
    return {
        "beforeVersion": old["appVersion"], "afterVersion": new["appVersion"],
        "datasetStatus": dataset_status,
        "overall": {"beforeAccuracyPct": old_pct, "afterAccuracyPct": new_pct,
                    "deltaPercentagePoints": round(new_pct - old_pct, 2)
                    if old_pct is not None and new_pct is not None else None,
                    "beforeChecked": old["totals"]["checked"],
                    "afterChecked": new["totals"]["checked"]},
        "perField": fields, "notes": notes,
    }


def _fmt(x: Any) -> str:
    return "n/a" if x is None else str(x)


def markdown(audit: dict[str, Any], comparison: dict[str, Any] | None = None) -> str:
    lines = [f"# Vexo OCR audit — {_fmt(audit['appVersion'])}", "",
             "**Scope:** aggregate JSON verification only; not an independent re-reading of screenshots.", "",
             f"- Test images: {audit['testImages']}",
             f"- Fields: {audit['totals']['correct']}/{audit['totals']['checked']} "
             f"({_fmt(audit['totals']['accuracyPct'])}% correct)",
             f"- Reported discrepancies: {audit['totals']['discrepantReported']}",
             f"- Processing errors: {audit['totals']['processingErrors']}", "",
             "## By field", "", "| Field | Correct / Checked | Accuracy | Errors | Risk |",
             "|---|---:|---:|---:|---|"]
    for field, d in sorted(audit["perField"].items()):
        safe = field.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {safe} | {d['correct']} / {d['checked']} | {_fmt(d['accuracyPct'])}% | {d['errors']} | {d['riskCategory']} |")
    lines.extend(["", "## Financial and distance risks", ""])
    if audit["riskBearingFieldsWithErrors"]:
        lines.append("Aggregate errors in risk-bearing fields: " + ", ".join(
            f"{x}" for x in audit["riskBearingFieldsWithErrors"]))
    else:
        lines.append("No aggregate errors flagged in recognized financial/distance field names.")
    if audit["reviewFlags"]:
        lines.append("")
        lines.append("Individual supplied discrepancies (only where the JSON contains details):")
        for flag in audit["reviewFlags"]:
            lines.append(f"- {flag['field']}: {flag['status']}"
                         + (f"; absolute difference {flag['absoluteDifference']}" if "absoluteDifference" in flag else ""))
    lines.extend(["", "**A critical-review flag is a potential decision error, not confirmed monetary loss.**", "",
                  "## Warnings and limitations", ""])
    lines.extend(f"- {w}" for w in audit["warnings"])
    if comparison:
        lines.extend(["", f"## Comparison: {comparison['beforeVersion']} → {comparison['afterVersion']}", "",
                      f"Dataset identity: {comparison['datasetStatus']}.", "",
                      "| Field | Before | After | Δ pp |", "|---|---:|---:|---:|"])
        for field, row in comparison["perField"].items():
            safe = field.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {safe} | {_fmt(row['beforeAccuracyPct'])}% | {_fmt(row['afterAccuracyPct'])}% | {_fmt(row['deltaPercentagePoints'])} |")
        lines.extend(["", f"Overall Δ: {_fmt(comparison['overall']['deltaPercentagePoints'])} pp.", ""])
        lines.extend(f"- {x}" for x in comparison["notes"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Vexo batch JSON to audit")
    parser.add_argument("--compare", type=Path, metavar="OLDER.json", help="older report; report positional arg is newer")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="write result to local file instead of stdout")
    args = parser.parse_args(argv)
    try:
        current = analyze(_read(args.report))
        comparison = compare(analyze(_read(args.compare)), current) if args.compare else None
        output = (markdown(current, comparison) if args.format == "markdown" else
                  json.dumps({"audit": current, "comparison": comparison}, ensure_ascii=False, indent=2) + "\n")
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (ReportError, OSError) as exc:
        print(f"audit error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
