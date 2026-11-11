"""Synthetic metadata-only coverage; no actual 99 screenshots or route data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cohort_audit import CohortError, summarize


def row(image, group, fields, truth="live_offer", pred="offer_candidate"):
    return {"imageId": image, "offerGroupId": group, "truthKind": truth,
            "predictedKind": pred, "fields": {k: {"status": v} for k, v in fields.items()}}


class CohortTests(unittest.TestCase):
    def test_variants_count_as_one_offer_group(self):
        rows = [
            row("a", "offer-1", {"offerPrice": "ok", "tripKm": "ok"}),
            row("b", "offer-1", {"offerPrice": "ok", "tripKm": "missing"}),
            row("c", "offer-2", {"surge": "ok"}),
            row("d", "offer-3", {"rides": "missing"}),
            row("e", "offer-4", {"offerPrice": "ok"}),
            row("f", "offer-5", {"offerPrice": "ok"}),
            row("g", "offer-6", {"surge": "ok"}),
            row("h", "offer-6", {"tripKm": "missing"}),
        ]
        s = summarize(rows)
        self.assertEqual((s["totalImages"], s["truthLiveImages"]), (8, 8))
        self.assertEqual(s["uniqueLabeledOfferGroups"], 6)
        self.assertEqual(s["groupsWithMultipleImageVariants"], 2)
        self.assertEqual(s["groupsWithAnyVariantFieldError"], 3)
        self.assertEqual(s["groupsWithAnyVariantFinancialOrDistanceError"], 2)
        self.assertEqual(s["checkedFieldsAcrossImages"], 10)
        self.assertEqual(s["correctFieldsAcrossImages"], 7)

    def test_non_offer_is_context_only_even_if_it_has_bad_fields(self):
        rows = [
            row("a", None, {"offerPrice": "wrong"}, "not_live_offer", "offer_candidate"),
            row("b", None, {"tripKm": "wrong"}, "not_live_offer", "not_live_offer"),
            row("c", "live", {"offerPrice": "ok"}, "live_offer", "not_live_offer"),
            row("d", None, {}, "unknown", "uncertain"),
        ]
        s = summarize(rows)
        self.assertEqual(s["checkedFieldsAcrossImages"], 1)
        self.assertEqual(s["classifiedFalseLiveImages"], 1)
        self.assertEqual(s["classifiedFalseBlockedImages"], 1)
        self.assertEqual(s["truthNonLiveImages"], 2)
        self.assertEqual(s["truthUnknownImages"], 1)
        self.assertEqual(s["nonLiveImagesWithFieldStatusesIgnored"], 2)

    def test_missing_groups_never_make_up_unique_offers(self):
        s = summarize([row("a", None, {"offerPrice": "ok"}),
                       row("b", "x", {}, pred="uncertain")])
        self.assertEqual(s["liveImagesWithoutOfferGroup"], 1)
        self.assertEqual(s["uniqueLabeledOfferGroups"], 1)
        self.assertEqual(s["uniqueOfferGroupsWithFieldStatus"], 0)
        self.assertEqual(s["evaluatedLiveImages"], 1)

    def test_false_positive_counted_as_error(self):
        s = summarize([row("a", "x", {"surge": "false_positive"})])
        self.assertEqual(s["groupsWithAnyVariantFinancialOrDistanceError"], 1)
        self.assertEqual(s["fieldsErrorRateAcrossImagesPct"], 100.0)

    def test_reject_duplicate_ids_or_unrecognized_statuses(self):
        x = row("a", "x", {"offerPrice": "ok"})
        with self.assertRaises(CohortError):
            summarize([x, x])
        with self.assertRaises(CohortError):
            summarize([row("b", "x", {"offerPrice": "maybe"})])


if __name__ == "__main__":
    unittest.main()
