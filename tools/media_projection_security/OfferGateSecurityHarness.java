package com.vexo.mlkitlab;

/**
 * Executes the actual OfferEpisodeGate.java from an Android PR through javac.
 * All episode labels (A/B) and times are invented. Does not interact with
 * Android, ML Kit, 99, passenger data or shared media.
 */
public final class OfferGateSecurityHarness {
    private int passed = 0, failed = 0;

    private void check(String name, boolean condition) {
        System.out.println((condition ? "PASS " : "FAIL ") + name);
        if (condition) passed++; else failed++;
    }

    void run() {
        OfferEpisodeGate gate = new OfferEpisodeGate();
        check("ONE_READING_NO_ALERT", !gate.observeAt("A", 1000));
        check("SECOND_IDENTICAL_ALERTS", gate.observeAt("A", 2000));
        boolean duplicate = false;
        for (int i=0;i<24;i++) duplicate |= gate.observeAt("A", 2400+i*300L);
        check("MANY_IDENTICAL_FRAMES_NO_DUPLICATE", !duplicate);

        gate.reset();
        gate.observeAt("A", 1000);
        gate.uncertain();
        check("ONE_UNCERTAIN_THEN_SAME_CAN_CONFIRM",
              gate.observeAt("A", 2000));

        gate.reset();
        gate.observeAt("A", 1000);
        gate.uncertain();gate.uncertain();
        check("TWO_UNCERTAIN_BREAK_FIRST_READ", !gate.observeAt("A", 2000));
        check("NEXT_SAME_IS_SECOND_CONFIRMATION", gate.observeAt("A", 2300));

        gate.reset();
        gate.observeAt("A", 1000);
        check("TIME_GAP_BREAKS_FIRST_MATCH", !gate.observeAt("A", 7000));
        check("NEXT_FRESH_READING_CONFIRMS",gate.observeAt("A", 7300));

        gate.reset();
        gate.observeAt("A", 1000);
        gate.observeAt("A", 2000);
        gate.nonOffer();
        check("ONE_MAP_DOES_NOT_END_ALERT", !gate.observeAt("A", 5000));
        gate.nonOffer();gate.nonOffer();
        check("FIRST_NEW_MAP_EPISODE_NOT_ALERT", !gate.observeAt("B", 6400));
        check("SECOND_NEW_MAP_EPISODE_ALERT", gate.observeAt("B", 7000));

        gate.reset();
        gate.observeAt("A", 1000);
        gate.observeAt("A", 2000);
        boolean early=false;
        early |= gate.observeAt("B", 3000);
        early |= gate.observeAt("B", 4000);
        early |= gate.observeAt("B", 5000);
        check("DIFFERENT_WITHOUT_MAP_BEFORE_7500_BLOCKED", !early);

        // Deliberate NEW PRODUCT POLICY in PR37: after 7.5s, three identical
        // observations of different numeric fingerprint can notify even
        // with ZERO definite MAP/expired transitions. This MAY be a separate
        // request or persistent OCR digit error. It is NOT a proven exploit.
        gate.reset();
        gate.observeAt("A", 1000);
        gate.observeAt("A", 2000);
        boolean b1=gate.observeAt("B", 10100);
        boolean b2=gate.observeAt("B", 11100);
        boolean b3=gate.observeAt("B", 12100);
        check("DIFFERENT_NEEDS_THREE_READINGS", !b1 && !b2);
        System.out.println("REVIEW_REQUIRED DIFFERENT_FINGERPRINT_WITHOUT_MAP_ALERT=" + b3 +
            " (source behavior; requires product decision and Android false-positive tests)");

        // Four identical later readings must not generate fourth/fifth alert.
        boolean bAgain=gate.observeAt("B", 13000) || gate.observeAt("B", 14000);
        check("DIFFERENT_EPISODE_NOT_ALERT_EVERY_FRAME", !bAgain);

        System.out.println("TOTAL " + passed + " PASS / " + failed + " FAIL");
        if (failed>0) System.exit(1);
    }

    public static void main(String[] args) {
        new OfferGateSecurityHarness().run();
    }
}
