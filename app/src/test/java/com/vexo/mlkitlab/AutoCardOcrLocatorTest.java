package com.vexo.mlkitlab;

import com.vexo.mlkitlab.FastCardVisualTracker.Box;
import org.junit.Test;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import static org.junit.Assert.*;

public final class AutoCardOcrLocatorTest {
    // These are INVENTED coordinates and labels, not a captured driver's ride.
    private static List<AutoCardOcrLocator.Line> fakeCard(int dx,int dy) {
        return new ArrayList<>(Arrays.asList(
            line("Moto Negocia",50+dx,560+dy,210,36),
            line("R$ 72,32",55+dx,650+dy,230,48),
            line("5 min (1,5 km)",60+dx,840+dy,220,35),
            line("32 min (20,2 km)",60+dx,940+dy,280,36),
            line("Aceitar por R$ 72,32",50+dx,1100+dy,480,45)
        ));
    }
    private static AutoCardOcrLocator.Line line(String text,int x,int y,int w,int h) {
        return new AutoCardOcrLocator.Line(text,new Box(x,y,w,h));
    }

    @Test public void recognizesPriceOriginDestinationWithoutFixedCoordinates() {
        AutoCardOcrLocator.Result r=AutoCardOcrLocator.locate(fakeCard(0,0),720,1500);
        assertNotNull(r);
        assertTrue(r.card.x<=r.price.x && r.card.x<=r.origin.x);
        assertTrue(r.card.y<r.price.y);
        assertTrue(r.price.y<r.origin.y);
        assertTrue(r.origin.y<r.destination.y);
        assertTrue(r.destination.y+r.destination.height<r.card.y+r.card.height);
    }

    @Test public void shiftedCardChangesAllCoordsAndRelativeBoxesFollowTracking() {
        AutoCardOcrLocator.Result a=AutoCardOcrLocator.locate(fakeCard(0,0),720,1500);
        AutoCardOcrLocator.Result b=AutoCardOcrLocator.locate(fakeCard(45,75),720,1500);
        assertNotNull(a); assertNotNull(b);
        assertEquals(45,b.card.x-a.card.x);
        assertEquals(75,b.price.y-a.price.y);
        Box shifted=new Box(a.card.x+40,a.card.y+50,a.card.width,a.card.height);
        assertEquals(a.price.x+40,a.place(shifted,a.price).x);
        assertEquals(a.origin.y+50,a.place(shifted,a.origin).y);
        assertEquals(a.destination.y+50,a.place(shifted,a.destination).y);
    }

    @Test public void priceWithoutRideAndAcceptIsNotOffer() {
        assertNull(AutoCardOcrLocator.locate(Arrays.asList(
            line("Publicidade R$ 0,99",40,600,200,35),
            line("Compre agora",40,800,200,45)),720,1500));
    }

    @Test public void noAcceptRejectsIncompleteCard() {
        List<AutoCardOcrLocator.Line> lines=fakeCard(0,0);
        lines.remove(lines.size()-1);
        assertNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void onlyOneDistanceRejectsIncompleteCard() {
        List<AutoCardOcrLocator.Line> lines=fakeCard(0,0);
        lines.remove(3);
        assertNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void noPriceRejectsIncompleteCard() {
        List<AutoCardOcrLocator.Line> lines=fakeCard(0,0);
        lines.remove(1);
        assertNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void irrelevantDistanceOutsideCardIsIgnored() {
        List<AutoCardOcrLocator.Line> lines=fakeCard(0,0);
        lines.remove(3);
        lines.add(line("32 min (20,2 km)",60,1190,280,30));
        assertNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void doesNotDependOnLiteralPriceOrAddresses() {
        List<AutoCardOcrLocator.Line> lines=fakeCard(0,0);
        lines.set(1,line("R$ 19,88",55,650,230,48));
        lines.set(2,line("9 min (2,7 km)",60,840,220,35));
        lines.set(3,line("27 min (16,4 km)",60,940,280,36));
        assertNotNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void rejectsOutOfBoundsUserControlledRect() {
        List<AutoCardOcrLocator.Line> lines=fakeCard(0,0);
        lines.set(4,line("Aceitar por R$ 72,32",650,1100,480,45));
        assertNull(AutoCardOcrLocator.locate(lines,720,1500));
    }

    @Test public void emptyOrInvalidScreenIsSafe() {
        assertNull(AutoCardOcrLocator.locate(null,720,1500));
        assertNull(AutoCardOcrLocator.locate(fakeCard(0,0),0,1500));
    }
}
