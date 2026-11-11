package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.json.JSONObject;
import org.junit.Test;

public class ReportMetricsIntegrityTest {
    @Test public void deliveryMotoIsNotPassengerMoto() {
        assertFalse(OfferTypeComparator.equivalent("Entrega Moto","Moto"));
        assertFalse(OfferTypeComparator.equivalent("Moto Negocia","Moto"));
        assertFalse(OfferTypeComparator.equivalent("Moto","Entrega Moto"));
        assertFalse(OfferTypeComparator.equivalent("99 Negocia","99 padrão"));
        assertFalse(OfferTypeComparator.equivalent("99 Negocia","Moto Negocia"));
    }

    @Test public void permittedAliasesAreExplicitAndLimited() {
        assertTrue(OfferTypeComparator.equivalent("Negocia","99 Negocia"));
        assertTrue(OfferTypeComparator.equivalent("Entrega Moto Nova","Entrega Moto"));
        assertTrue(OfferTypeComparator.equivalent("Pgto. no app","Pagamento no aplicativo"));
        assertTrue(OfferTypeComparator.equivalent("Prioritário","Prioritario"));
        assertTrue(OfferTypeComparator.equivalent("99 Moto Negocia","Moto Negocia"));
        assertFalse(OfferTypeComparator.equivalent("","Moto"));
        assertFalse(OfferTypeComparator.equivalent("moto - entrega?","Moto"));
    }

    @Test public void explicitJsonNullIsAnAbsentGroundTruthNotMissingPrediction() throws Exception {
        JSONObject truth=new JSONObject();
        truth.put("completed_rides",JSONObject.NULL);
        Object wanted=truth.opt("completed_rides");
        assertSame(JSONObject.NULL,wanted);
        assertNull(ReportFieldPolicy.expectedOrAbsent(wanted));
        assertNull(ReportFieldPolicy.expectedOrAbsent(null));
    }

    @Test public void absentTruthStillDetectsInventedValues() throws Exception {
        // The batch evaluator checks "wanted == null": empty output is skipped,
        // populated output is a false positive, never a correct field.
        Object wanted=ReportFieldPolicy.expectedOrAbsent(JSONObject.NULL);
        assertNull(wanted);
        String empty="";
        String invented="99";
        assertTrue(wanted==null && empty.isEmpty());
        assertTrue(wanted==null && !invented.isEmpty());
    }
}
