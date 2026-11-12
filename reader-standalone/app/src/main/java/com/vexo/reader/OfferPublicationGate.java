package com.vexo.reader;

/** Frame generations reset confirmation. Only observed offer evidence can reopen persistence. */
final class OfferPublicationGate {
    enum Decision { INCOMPLETE, CONFIRMING, ALREADY_RECORDED, SAVE }

    private String candidate;
    private int candidateEpoch;
    private String recorded;
    private int clearReadings;

    Decision observe(String fingerprint, int frameEpoch, boolean clearlyNoOffer) {
        if (fingerprint == null) {
            candidate = null;
            clearReadings = clearlyNoOffer ? Math.min(2, clearReadings + 1) : 0;
            if (clearReadings == 2) recorded = null;
            return Decision.INCOMPLETE;
        }

        clearReadings = 0;
        if (frameEpoch != candidateEpoch || !fingerprint.equals(candidate)) {
            candidateEpoch = frameEpoch;
            candidate = fingerprint;
            return Decision.CONFIRMING;
        }
        return fingerprint.equals(recorded) ? Decision.ALREADY_RECORDED : Decision.SAVE;
    }

    void saved(String fingerprint) {
        recorded = fingerprint;
    }

    void reset() {
        candidate = null;
        recorded = null;
        clearReadings = 0;
    }
}
