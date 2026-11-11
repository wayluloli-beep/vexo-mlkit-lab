package com.vexo.mlkitlab;

import org.junit.Test;
import org.json.JSONObject;

import static org.junit.Assert.*;

public class OcrEvidenceTest {
    @Test public void distinguishesProbableOcrFromParserWithoutRawText() throws Exception {
        JSONObject fields=new JSONObject()
            .put("tripKm",new JSONObject()
                .put("status","wrong").put("expected",11.8).put("actual","1,8"))
            .put("surge",new JSONObject()
                .put("status","missing").put("expected",2.8).put("actual",""));
        JSONObject diag=OcrEvidence.diagnostic(
            "Moto R$40,70 2,8x\n24 min (1,8 km)\nRua Particular 28", fields
        );
        assertFalse(diag.getJSONObject("tripKm").getBoolean("expectedNumberSeenInRawOCR"));
        assertTrue(diag.getJSONObject("surge").getBoolean("expectedNumberSeenInRawOCR"));
        String dump=diag.toString();
        assertFalse(dump.contains("Particular"));
        assertFalse(dump.contains("Rua"));
        assertTrue(dump.contains("1,8km"));
    }

    @Test public void recognizesDotOrCommaInOCRNumerics() {
        assertTrue(OcrEvidence.containsNumeric("surge 2,8x", "2.8"));
        assertTrue(OcrEvidence.containsNumeric("surge 2.8x", "2,8"));
        assertFalse(OcrEvidence.containsNumeric("surge 12,8x", "2.8"));
    }

    @Test public void doesNotLeakAddressesInCandidates() {
        String tokens=OcrEvidence.numericUnitCandidates(
            "Rua Domingos 132, Centro 5,19/km 11,8 km 2,2x").toString();
        assertFalse(tokens.contains("Domingos"));
        assertFalse(tokens.contains("Centro"));
        assertTrue(tokens.contains("11,8km"));
        assertTrue(tokens.contains("2,2x"));
    }
}
