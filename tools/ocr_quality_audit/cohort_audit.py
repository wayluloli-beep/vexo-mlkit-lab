#!/usr/bin/env python3
"""Aggregate independently labeled OCR screenshots without double-counting offers.

This helper does not open images, infer offer identity, or score OCR by itself.
Only human supplied, private labels establish live-offer identity and truth.
Output is aggregate-only: never prints IDs, text or geographic data.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

KINDS = {"live_offer", "not_live_offer", "unknown"}
PREDICTIONS = {"offer_candidate", "not_live_offer", "uncertain"}
STATUSES = {"ok", "wrong", "missing", "false_positive"}
FINANCIAL = {"offerPrice", "perKm", "surge", "negotiations", "payment"}
DISTANCE = {"pickupKm", "tripKm", "pickupMin", "tripMin"}


class CohortError(ValueError):
    pass


def _nonempty(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CohortError(f"{key} must be non-empty text")
    return value.strip()


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize metadata only; no implicit mapping from image to unique offer.

    Required fields: imageId, truthKind, predictedKind, fields (per-field status).
    live_offer records may include opaque offerGroupId; without it, their
    image is excluded from per-unique-offer denominators. The group must be
    decided by a human independently of parser results.
    """
    if not isinstance(records, list):
        raise CohortError("records must be a list")
    ids: set[str] = set()
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts = {"totalImages": 0, "truthLiveImages": 0,
              "truthNonLiveImages": 0, "truthUnknownImages": 0,
              "classifiedFalseLiveImages": 0, "classifiedFalseBlockedImages": 0,
              "uncertainPredictions": 0, "evaluatedLiveImages": 0,
              "checkedFieldsAcrossImages": 0, "correctFieldsAcrossImages": 0,
              "liveImagesWithFieldErrors": 0, "liveImagesWithFinancialOrDistanceErrors": 0,
              "liveImagesWithoutOfferGroup": 0, "unlabeledLiveImages": 0,
              "nonLiveImagesWithFieldStatusesIgnored": 0}
    for i, row in enumerate(records):
        if not isinstance(row, dict):
            raise CohortError(f"records[{i}] must be an object")
        image_id = _nonempty(row.get("imageId"), "imageId")
        if image_id in ids:
            raise CohortError("duplicate imageId in input")
        ids.add(image_id)
        truth = row.get("truthKind")
        pred = row.get("predictedKind")
        if truth not in KINDS or pred not in PREDICTIONS:
            raise CohortError(f"invalid kind/prediction in records[{i}]")
        fields = row.get("fields", {})
        if not isinstance(fields, dict):
            raise CohortError("fields must be an object")
        for name, value in fields.items():
            if not isinstance(name, str) or not isinstance(value, dict) or value.get("status") not in STATUSES:
                raise CohortError("fields require named objects with explicit OCR status")
        counts["totalImages"] += 1
        counts["uncertainPredictions"] += int(pred == "uncertain")
        if truth == "unknown":
            counts["truthUnknownImages"] += 1
            continue
        if truth == "not_live_offer":
            counts["truthNonLiveImages"] += 1
            counts["classifiedFalseLiveImages"] += int(pred == "offer_candidate")
            counts["nonLiveImagesWithFieldStatusesIgnored"] += int(bool(fields))
            continue
        counts["truthLiveImages"] += 1
        counts["classifiedFalseBlockedImages"] += int(pred == "not_live_offer")
        if not fields:
            counts["unlabeledLiveImages"] += 1
        else:
            counts["evaluatedLiveImages"] += 1
            counts["checkedFieldsAcrossImages"] += len(fields)
            counts["correctFieldsAcrossImages"] += sum(item["status"] == "ok" for item in fields.values())
            counts["liveImagesWithFieldErrors"] += int(any(item["status"] != "ok" for item in fields.values()))
            counts["liveImagesWithFinancialOrDistanceErrors"] += int(any(
                item["status"] != "ok" and name in FINANCIAL | DISTANCE
                for name, item in fields.items()))
        group_id = row.get("offerGroupId")
        if group_id is None or (isinstance(group_id, str) and not group_id.strip()):
            counts["liveImagesWithoutOfferGroup"] += 1
        else:
            groups[_nonempty(group_id, "offerGroupId")].append(fields)

    group_count = len(groups)
    reviewed_groups = {k: variants for k, variants in groups.items() if any(variants)}
    counts["uniqueLabeledOfferGroups"] = group_count
    counts["uniqueOfferGroupsWithFieldStatus"] = len(reviewed_groups)
    counts["groupsWithMultipleImageVariants"] = sum(len(variants) > 1 for variants in groups.values())
    counts["groupsWithAnyVariantFieldError"] = sum(any(
        any(field["status"] != "ok" for field in variant.values())
        for variant in variants) for variants in reviewed_groups.values())
    counts["groupsWithAnyVariantFinancialOrDistanceError"] = sum(any(
        any(field["status"] != "ok" and name in FINANCIAL | DISTANCE
            for name, field in variant.items())
        for variant in variants) for variants in reviewed_groups.values())
    counts["fieldsErrorRateAcrossImagesPct"] = round(100 * (
        counts["checkedFieldsAcrossImages"] - counts["correctFieldsAcrossImages"]
    ) / counts["checkedFieldsAcrossImages"], 2) if counts["checkedFieldsAcrossImages"] else None
    counts["interpretation"] = (
        "Unique offer group counts are NOT accuracy percentages: duplicate/overlay variants are clustered. "
        "Only reviewed live-offer fields enter field denominators; context controls are separate. "
        "Ground truth and group IDs must be assigned manually, never inferred from OCR content."
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit private OCR cohort labels, aggregate-only")
    parser.add_argument("input", type=Path, help="local JSON array of labeled image metadata (never uploaded)")
    args = parser.parse_args()
    try:
        rows = json.loads(args.input.read_text(encoding="utf-8"))
        print(json.dumps(summarize(rows), indent=2, ensure_ascii=False))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as e:
        print(f"Invalid cohort metadata: {type(e).__name__}", file=__import__('sys').stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
