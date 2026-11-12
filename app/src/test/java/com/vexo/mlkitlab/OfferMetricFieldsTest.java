package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import org.junit.Test;
import java.util.Arrays;
import java.util.List;
import java.util.ArrayList;
import static org.junit.Assert.*;

/** Invented examples exercise the six customer-facing numbers only. */
public final class OfferMetricFieldsTest {
    private static AutoCardOcrLocator.Line l(String t,int x,int y,int w,int h){
        return new AutoCardOcrLocator.Line(t,new Box(x,y,w,h));
    }
    private static List<AutoCardOcrLocator.Line> sample(){
        return new ArrayList<>(Arrays.asList(
            l("Pgto. no app",45,510,235,31),
            l("R$ 8,30",50,585,245,64),
            l("R$ 1,41 Tarifa base dinâmica incl.",52,719,395,33),
            l("4,91 · 486 corridas · Perfil Premium",52,814,425,34),
            l("8 min (2,5 km)",61,930,223,36),
            l("Avenida Exemplo, sem número",60,969,490,37),
            l("9 min (3,7 km)",61,1081,220,35),
            l("Rua Teste 100",61,1119,480,40)
        ));
    }

    @Test public void readsSixNumbersButNotFareAddonOrAddresses() {
        List<AutoCardOcrLocator.Line> lines=sample();
        AutoCardOcrLocator.Result c=AutoCardOcrLocator.locate(lines,720,1500);
        assertNotNull(c);
        OfferMetricFields fields=OfferMetricFields.fromLines(lines,c);
        assertNotNull(fields);
        assertEquals("R$ 8,30",fields.price);
        assertEquals("8",fields.pickupMinutes);
        assertEquals("2,5",fields.pickupKm);
        assertEquals("9",fields.tripMinutes);
        assertEquals("3,7",fields.tripKm);
        assertEquals("4,91",fields.passengerRating);
        String shown=fields.display();
        assertFalse(shown.contains("1,41"));
        assertFalse(shown.contains("Avenida"));
        assertFalse(shown.contains("Rua"));
        assertFalse(shown.contains("corridas"));
    }

    @Test public void handlesHigherVariableOfferWithoutHardcodedPrice() {
        List<AutoCardOcrLocator.Line> lines=sample();
        lines.set(1,l("R$ 42,76",50,585,245,64));
        lines.set(4,l("14 min (7,2 km)",61,930,223,36));
        lines.set(6,l("45 min (31,8 km)",61,1081,220,35));
        OfferMetricFields f=OfferMetricFields.fromLines(lines,
            AutoCardOcrLocator.locate(lines,720,1500));
        assertNotNull(f);
        assertEquals("R$ 42,76",f.price);
        assertEquals("14",f.pickupMinutes);
        assertEquals("7,2",f.pickupKm);
        assertEquals("45",f.tripMinutes);
        assertEquals("31,8",f.tripKm);
    }

    @Test public void noPassengerRatingShowsUnknownNotInvented() {
        List<AutoCardOcrLocator.Line> lines=sample();
        lines.remove(3);
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(lines,720,1500);
        assertNotNull(r);
        OfferMetricFields f=OfferMetricFields.fromLines(lines,r);
        assertNotNull(f);
        assertNull(f.passengerRating);
        assertTrue(f.display().contains("★ —"));
    }

    @Test public void doesNotShowFakeCompleteOfferWhenDistanceMissing() {
        List<AutoCardOcrLocator.Line> lines=sample();
        lines.remove(6);
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(lines,720,1500);
        assertNull(r);
        assertNull(OfferMetricFields.fromLines(lines,r));
    }

    @Test public void extraCurrencyDoesNotOverrideLargeFare() {
        List<AutoCardOcrLocator.Line> lines=sample();
        lines.add(l("R$ 0,99 Taxa semanal",55,865,260,24));
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(lines,720,1500);
        assertNotNull(r);
        OfferMetricFields f=OfferMetricFields.fromLines(lines,r);
        assertNotNull(f);
        assertEquals("R$ 8,30",f.price);
    }
}
