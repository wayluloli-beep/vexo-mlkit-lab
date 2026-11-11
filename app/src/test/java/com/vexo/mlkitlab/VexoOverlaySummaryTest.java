package com.vexo.mlkitlab;

import static org.junit.Assert.*;
import org.junit.Test;

public class VexoOverlaySummaryTest {
    @Test public void displaysOnlyThreeNumericOfferFields() {
        assertEquals("R$ 12,64  •  7,3 km / 17 min\nConfira antes de decidir",
            VexoOverlaySummary.format("12,64","7,3","17"));
    }
    @Test public void rejectsRawOcrNamesAddressesAndInvalidFields() {
        String x=VexoOverlaySummary.format("12,64 Rua 123","7,3","17");
        assertEquals("Confira a oferta no aplicativo",x);
        assertFalse(x.contains("Rua"));
        assertEquals("Confira a oferta no aplicativo",
            VexoOverlaySummary.format("12,64",null,"17"));
    }
}
