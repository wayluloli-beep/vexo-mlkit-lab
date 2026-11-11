"""Privacy-preserving temporal QA for *synthetic* metadata inspired by private recordings.

No pixels, screenshots, prices, OCR strings, addresses or route data accepted.
This scores alerts, not the accuracy of ML Kit; visual episode != unique ride.
"""
from dataclasses import dataclass
from math import ceil, isfinite
import re

KINDS = frozenset({'CARD', 'LIST', 'MAP', 'NON_OFFER', 'EXPIRED', 'AD'})
ALERT_KINDS = frozenset({'CARD_ALERT', 'LIST_REVIEW'})
OPAQUE = re.compile(r'[A-Za-z0-9_-]{1,48}\Z')


@dataclass(frozen=True)
class Window:
    start_s: float
    end_s: float
    kind: str
    episode: str = ''  # human-labeled synthetic visual episode, not ride identity
    value_group: str = ''  # synthetic equality token; deliberately NOT used for grouping


@dataclass(frozen=True)
class Alert:
    at_s: float
    kind: str = 'CARD_ALERT'
    financial_guard_passed: bool = False


def _finite_time(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


def _p95(values):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[ceil(len(ordered) * .95) - 1]


def score_timeline(duration_s, windows, alerts, *, max_first_alert_s=3.0,
                   stop_s=None, observed_frame_count=0):
    """Report counts only. An alert in an *unannotated* gap is unknown, not false.

    Windows are non-overlapping half-open intervals. CARD is a visual offer;
    LIST is a separate *review-only* opportunity; expired or ads never qualify.
    The client must label windows independently of its OCR outputs.
    """
    if not _finite_time(duration_s) or duration_s == 0:
        raise ValueError('invalid synthetic duration')
    if not _finite_time(max_first_alert_s) or type(observed_frame_count) is not int or observed_frame_count < 0:
        raise ValueError('invalid metric parameters')
    if stop_s is not None and (not _finite_time(stop_s) or stop_s > duration_s):
        raise ValueError('invalid stop time')
    ordered = sorted(windows, key=lambda w: w.start_s)
    previous_end = 0
    episode_keys = set()
    for w in ordered:
        if not isinstance(w, Window) or w.kind not in KINDS or not all(
            _finite_time(t) for t in (w.start_s, w.end_s)):
            raise ValueError('invalid window')
        if w.start_s < previous_end or not w.start_s < w.end_s <= duration_s:
            raise ValueError('overlapping or invalid windows')
        previous_end = w.end_s
        if w.kind in {'CARD', 'LIST'}:
            if not OPAQUE.fullmatch(w.episode) or w.episode in episode_keys:
                raise ValueError('episode label must be a unique opaque fixture token')
            episode_keys.add(w.episode)
        elif w.episode:
            raise ValueError('non-offer window cannot have an episode')
        if w.value_group and not OPAQUE.fullmatch(w.value_group):
            raise ValueError('value group must be a synthetic token')
    per_episode = {w.episode: 0 for w in ordered if w.episode}
    latency = []
    counters = dict(cardEpisodes=0, cardEpisodesAlerted=0,
                    missedCardEpisodes=0, listOpportunities=0,
                    listReviewEpisodes=0, listAwaitingReview=0,
                    cardAlertAttempts=0, listReviewAttempts=0,
                    duplicateAlerts=0, falseAlerts=0,
                    expiredAlerts=0, advertAlerts=0, unscoredAlerts=0,
                    unsafeAlerts=0, wrongKindAlerts=0,
                    afterStopAlerts=0, lateFirstAlerts=0,
                    observedFrames=observed_frame_count)
    first_at = {}
    for w in ordered:
        if w.kind == 'CARD':
            counters['cardEpisodes'] += 1
        elif w.kind == 'LIST':
            counters['listOpportunities'] += 1
    previous_alert_at = -1
    for a in alerts:
        if not isinstance(a, Alert) or a.kind not in ALERT_KINDS or not _finite_time(a.at_s) or a.at_s >= duration_s or type(a.financial_guard_passed) is not bool:
            raise ValueError('invalid synthetic alert')
        if a.at_s < previous_alert_at:
            raise ValueError('alerts must be provided in event order')
        previous_alert_at = a.at_s
        if stop_s is not None and a.at_s >= stop_s:
            counters['afterStopAlerts'] += 1
            counters['falseAlerts'] += 1
            continue
        if a.kind == 'CARD_ALERT':
            counters['cardAlertAttempts'] += 1
        else:
            counters['listReviewAttempts'] += 1
        if a.kind == 'CARD_ALERT' and not a.financial_guard_passed:
            counters['unsafeAlerts'] += 1
            counters['falseAlerts'] += 1
            continue  # unsafe alert never earns safe episode-detection credit
        matched = next((w for w in ordered if w.start_s <= a.at_s < w.end_s), None)
        if matched is None:
            counters['unscoredAlerts'] += 1  # No ground truth: do not invent a false positive.
            continue
        if matched.kind in {'CARD', 'LIST'}:
            expected = 'CARD_ALERT' if matched.kind == 'CARD' else 'LIST_REVIEW'
            if a.kind != expected:
                counters['wrongKindAlerts'] += 1
                counters['falseAlerts'] += 1
                continue
            per_episode[matched.episode] += 1
            if per_episode[matched.episode] > 1:
                counters['duplicateAlerts'] += 1
            else:
                first_at[matched.episode] = a.at_s - matched.start_s
                if matched.kind == 'CARD':
                    latency.append(first_at[matched.episode])
                    if first_at[matched.episode] > max_first_alert_s:
                        counters['lateFirstAlerts'] += 1
        else:
            counters['falseAlerts'] += 1
            if matched.kind == 'EXPIRED':
                counters['expiredAlerts'] += 1
            if matched.kind == 'AD':
                counters['advertAlerts'] += 1
    counters['cardEpisodesAlerted'] = sum(per_episode[w.episode] > 0 for w in ordered if w.kind == 'CARD')
    counters['missedCardEpisodes'] = counters['cardEpisodes'] - counters['cardEpisodesAlerted']
    counters['listReviewEpisodes'] = sum(per_episode[w.episode] > 0 for w in ordered if w.kind == 'LIST')
    counters['listAwaitingReview'] = counters['listOpportunities'] - counters['listReviewEpisodes']
    counters['firstCardAlertP95Seconds'] = _p95(latency)
    counters['scoredVisualEpisodes'] = counters['cardEpisodes'] + counters['listOpportunities']
    counters['scope'] = ('synthetic label-derived replay only; visual episode is NOT a unique ride; '
                         'not a MediaProjection or 99 OCR accuracy measurement')
    return counters


def long_recording_fixture():
    """Approx. timing labels, no private media. One ~10-second CARD window."""
    return 307.55, [Window(0, 188, 'MAP'),
                    Window(188, 198, 'CARD', 'fixture-visual-1'),
                    Window(198, 307.55, 'NON_OFFER')]


def short_recording_fixture():
    """Two sightings with equal values: separate VISUAL episodes, not proven rides."""
    return 103.1, [Window(0, 7, 'CARD', 'visual-a', 'same-values'),
                   Window(7, 33, 'MAP'),
                   Window(33, 43, 'CARD', 'visual-b', 'same-values'),
                   Window(51, 61, 'LIST', 'list-c'),
                   Window(61, 64, 'EXPIRED'),
                   Window(64, 103.1, 'AD')]
