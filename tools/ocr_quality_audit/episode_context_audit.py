"""Audit the PR25 OfferEpisodeGate semantics with synthetic frame contexts only.

The CURRENT model follows the source of OfferEpisodeGate.java plus the call
site in LiveCaptureService.java: both UNKNOWN and NON_OFFER call nonOffer().
The PROPOSED model is a conservative design experiment, NOT Android code.
No OCR strings, coordinates, profiles, prices, or identifiers leave the fixture.
"""
from dataclasses import dataclass
from collections import Counter
import re

_OPAQUE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


@dataclass(frozen=True)
class Observation:
    context: str  # OFFER | DEFINITE_NON_OFFER | UNCERTAIN
    group: str = ""  # synthetic human-annotated group, independent of OCR
    fingerprint: str = ""  # fabricated equality token; never OCR-derived


def replay_episode_policy(observations, *, conservative=False):
    """Return aggregate-only counts; intentionally model possible failure modes.

    Conservative mode requires 2 *definite* non-offer observations to end
    an alerted episode. Ambiguous fingerprint changes are not identity proof.
    """
    fingerprint = ""
    matches = 0
    absent = 0
    alerted = False
    attempted = Counter()
    eligible = set()
    seen_offers = set()
    last_group = ""
    stable_group_reads = 0
    tentative_changes_suppressed = 0
    for observation in observations:
        if not isinstance(observation, Observation):
            raise ValueError("invalid observation")
        if observation.context not in {"OFFER", "DEFINITE_NON_OFFER", "UNCERTAIN"}:
            raise ValueError("invalid context")
        for value in (observation.group, observation.fingerprint):
            if type(value) is not str or (value and not _OPAQUE.fullmatch(value)):
                raise ValueError("fixture identity must be opaque")
        if observation.context != "OFFER":
            # PR25 calls nonOffer() even when classify() returned UNCERTAIN,
            # e.g. two OCR misses or an overlay hiding otherwise valid text.
            if not conservative or observation.context == "DEFINITE_NON_OFFER":
                absent = min(2, absent + 1)
                matches = 0
                if absent >= 2 and (fingerprint or alerted):
                    fingerprint, alerted = "", False
            else:
                # Missing OCR evidence is not proof that the offer disappeared.
                absent = 0
                if not alerted:
                    matches = 0
            last_group, stable_group_reads = "", 0
            continue
        if not observation.fingerprint:
            raise ValueError("offer fixture requires opaque fingerprint")
        absent = 0
        if observation.group:
            seen_offers.add(observation.group)
            if observation.group == last_group:
                stable_group_reads += 1
            else:
                last_group, stable_group_reads = observation.group, 1
            if stable_group_reads >= 2:
                eligible.add(observation.group)
        if conservative and alerted and observation.fingerprint != fingerprint:
            # New numeric OCR result need not imply a new visual card.
            tentative_changes_suppressed += 1
            continue
        if observation.fingerprint != fingerprint:
            fingerprint, matches, alerted = observation.fingerprint, 1, False
        else:
            matches = min(2, matches + 1)
        if matches >= 2 and not alerted:
            alerted = True
            if observation.group:
                attempted[observation.group] += 1
    return {
        "fixtureGroupsSeen": len(seen_offers),
        "eligibleGroupsWithTwoConsecutiveObservations": len(eligible),
        "notifiedGroups": len(attempted),
        "alertAttempts": sum(attempted.values()),
        "duplicateAlertsSameGroup": sum(max(0, n - 1) for n in attempted.values()),
        "eligibleGroupsNeverNotified": len(eligible - set(attempted)),
        "unprovenIdentityChangesSuppressed": tentative_changes_suppressed,
        "mode": "proposed_conservative" if conservative else "pr25_source_model",
        "scope": "synthetic Python source model; NOT MediaProjection runtime evidence",
    }


def repeated_card_with_two_unknowns():
    O = Observation
    return [O("OFFER", "A", "same"), O("OFFER", "A", "same"),
            O("UNCERTAIN"), O("UNCERTAIN"),
            O("OFFER", "A", "same"), O("OFFER", "A", "same")]


def separate_cards_with_map():
    O = Observation
    return [O("OFFER", "A", "same"), O("OFFER", "A", "same"),
            O("DEFINITE_NON_OFFER"), O("DEFINITE_NON_OFFER"),
            O("OFFER", "B", "same"), O("OFFER", "B", "same")]


def same_card_with_ocr_variation():
    O = Observation
    return [O("OFFER", "A", "good"), O("OFFER", "A", "good"),
            O("OFFER", "A", "noisy"), O("OFFER", "A", "noisy"),
            O("OFFER", "A", "good"), O("OFFER", "A", "good")]
