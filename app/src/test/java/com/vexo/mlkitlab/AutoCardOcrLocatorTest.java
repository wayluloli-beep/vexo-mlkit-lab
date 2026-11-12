package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import org.junit.Test;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import static org.junit.Assert.*;

/** All sample strings and coordinates in this class are INVENTED test fixtures. */
public final class AutoCardOcrLocatorTest {
    private static AutoCardOcrLocator.Line line(String s,int x,int y,int w,int h) {
        return new AutoCardOcrLocator.Line(s,new Box(x,y,w,h));
    }
    private static List<AutoCardOcrLocator.Line> fakeNegotiated(int dx,int dy) {
        return new ArrayList<>(Arrays.asList(
            line("Moto Negocia",50+dx,540+dy,200,36),
            line("R$ 65,40",55+dx,630+dy,240,56),
            line("7 min (1,8 km)",60+dx,830+dy,220,35),
            line("23 min (14,2 km)",60+dx,930+dy,250,36),
            line("Aceitar por R$ 65,40",50+dx,1100+dy,450,46)
        ));
    }
    private static List<AutoCardOcrLocator.Line> fakePaymentCard(int dx,int dy) {
        return new ArrayList<>(Arrays.asList(
            line("Pgto. no app",48+dx,520+dy,190,34),
            line("R$ 9,70",50+dx,590+dy,255,68),
            line("R$ 1,18 Tarifa base dinâmica incl.",55+dx,720+dy,330,29),
            line("4,88 · 467 corridas · Perfil Premium",56+dx,810+dy,410,32),
            line("7 min (1,9 km)",62+dx,920+dy,220,35),
            line("Avenida do Teste, sem número",62+dx,962+dy,470,40),
            line("13 min (5,1 km)",62+dx,1060+dy,250,35),
            line("Rua Exemplo, 100",62+dx,1105+dy,480,40)
        ));
    }

    @Test public void negotiatedCardHasParentAndThreeChildren() {
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(fakeNegotiated(0,0),720,1500);
        assertNotNull(r);
        assertTrue(r.card.x<=r.price.x && r.card.x<=r.origin.x);
        assertTrue(r.card.y<r.price.y);
        assertTrue(r.price.y<r.origin.y && r.origin.y<r.destination.y);
        assertTrue(r.destination.y+r.destination.height<=r.card.y+r.card.height);
    }

    @Test public void structurallyRecognizesPaymentCardWithoutMotoOrAccept() {
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(fakePaymentCard(0,0),720,1500);
        assertNotNull("Payment card layout MUST be visible in LAB",r);
        assertTrue("A screenshot must NEVER assert app provenance",r.visualOnly);
        assertTrue(r.card.width>=720*3/4);
        assertTrue(r.card.y<r.price.y && r.price.y<r.origin.y);
        assertTrue(r.origin.y<r.destination.y);
        assertEquals(590-8,r.price.y);
    }

    @Test public void recognizesSameStructureWhenCardMoves() {
        AutoCardOcrLocator.Result a=AutoCardOcrLocator.locate(fakePaymentCard(0,0),720,1500);
        AutoCardOcrLocator.Result b=AutoCardOcrLocator.locate(fakePaymentCard(20,80),720,1500);
        assertNotNull(a);assertNotNull(b);
        assertEquals(80,b.price.y-a.price.y);
        assertEquals(80,b.origin.y-a.origin.y);
        Box moved=new Box(a.card.x+20,a.card.y+40,a.card.width,a.card.height);
        assertEquals(a.price.x+20,a.place(moved,a.price).x);
        assertEquals(a.origin.y+40,a.place(moved,a.origin).y);
        assertEquals(a.destination.y+40,a.place(moved,a.destination).y);
    }

    @Test public void modelNeverRequiresAcceptButton() {
        List<AutoCardOcrLocator.Line> lines=fakeNegotiated(0,0);
        lines.remove(lines.size()-1);
        assertNotNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void advertisingPriceAloneIsNotCard() {
        assertNull(AutoCardOcrLocator.locate(Arrays.asList(
            line("Liquidação R$ 0,99",40,600,200,35),
            line("Compre agora",40,800,200,45)),720,1500));
    }

    @Test public void noContextHeaderOrTripMarkerIsNotCard() {
        assertNull(AutoCardOcrLocator.locate(Arrays.asList(
            line("R$ 28,10",42,600,210,40),
            line("8 min (2,7 km)",45,850,200,35),
            line("27 min (16,4 km)",45,950,220,36),
            line("Promoção de entrega",40,1000,200,36)),720,1500));
    }

    @Test public void missingPriceDoesNotProduceBoxes() {
        List<AutoCardOcrLocator.Line> l=fakePaymentCard(0,0);
        l.remove(1);l.remove(1); // remove both primary and fare price
        assertNull(AutoCardOcrLocator.locate(l,720,1500));
    }

    @Test public void missingSecondRouteDoesNotProduceBoxes() {
        List<AutoCardOcrLocator.Line> l=fakePaymentCard(0,0);
        l.remove(6);
        assertNull(AutoCardOcrLocator.locate(l,720,1500));
    }

    @Test public void distantUnrelatedRouteIsNotPaired() {
        List<AutoCardOcrLocator.Line> l=fakeNegotiated(0,0);
        l.remove(3);
        l.add(line("34 min (24,0 km)",60,1390,250,30));
        assertNull(AutoCardOcrLocator.locate(l,720,1500));
    }

    @Test public void priceFoundByFontSizeNotExtraTariff() {
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(fakePaymentCard(0,0),720,1500);
        assertNotNull(r);
        assertEquals(590-8,r.price.y);
    }

    @Test public void unsupportedLayoutOrNoValidRoutesRemainsUnknown() {
        assertNull(AutoCardOcrLocator.locate(null,720,1500));
        assertNull(AutoCardOcrLocator.locate(fakePaymentCard(0,0),0,1500));
        assertNull(AutoCardOcrLocator.locate(fakePaymentCard(0,0),720,0));
    }

    @Test public void invalidOcrBoundingBoxesAreRejected() {
        List<AutoCardOcrLocator.Line> l=fakePaymentCard(0,0);
        l.set(1,line("R$ 9,70",650,590,255,68));
        l.set(2,line("R$ 1,18",651,720,300,29));
        assertNull(AutoCardOcrLocator.locate(l,720,1500));
    }

    @Test public void bare99FromCurrencyNeverCountsAsPlatformIdentity() {
        List<AutoCardOcrLocator.Line> l=Arrays.asList(
            line("Publicidade R$0,99",50,500,250,35),
            line("8 min (1,3 km)",50,820,200,35),
            line("22 min (9,1 km)",50,940,200,35),
            line("Anúncio comercial",50,970,220,35)
        );
        assertNull(AutoCardOcrLocator.locate(l,720,1500));
    }
}
