package com.vexo.mlkitlab;

import static org.junit.Assert.*;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.List;
import java.util.concurrent.TimeUnit;

/** Teste em pixel sintetico, nao em screenshot real nem conta 99. */
@RunWith(AndroidJUnit4.class)
public final class OcrRoiRecheckTest {
    private static Bitmap card(boolean dark,String... lines) {
        Bitmap b=Bitmap.createBitmap(1400,1120,Bitmap.Config.ARGB_8888);
        Canvas c=new Canvas(b);
        c.drawColor(dark?Color.rgb(22,27,37):Color.WHITE);
        Paint p=new Paint(Paint.ANTI_ALIAS_FLAG|Paint.SUBPIXEL_TEXT_FLAG);
        p.setColor(dark?Color.WHITE:Color.BLACK);
        p.setTextSize(70f);
        p.setTypeface(Typeface.create(Typeface.DEFAULT,Typeface.BOLD));
        int y=140;
        for(String line:lines) { c.drawText(line,90,y,p); y+=118; }
        return b;
    }

    @Test public void recoversUnambiguousTripFromRegionWithoutRewritingOffer() throws Exception {
        Bitmap b=card(false,
            "99 Moto",
            "R$40,70",
            "4,98 971 corridas",
            "9 min (3 km)",
            "24 min (11,8 km)");
        try (TextRecognizer reader=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)) {
            Text full=Tasks.await(reader.process(InputImage.fromBitmap(b,0)),90,TimeUnit.SECONDS);
            OfferParser.Offer parsed=OfferParser.parse(full.getText());
            // Simula um resultado principal suspeito sem inventar a leitura.
            parsed.set("tripKm","1,8");
            assertFalse(FinancialGuard.assess(parsed).canCalculate);
            List<OcrRoiRecheck.Region> regions=OcrRoiRecheck.findRegions(full,b,parsed);
            OcrRoiRecheck.Region trip=null;
            for(OcrRoiRecheck.Region r:regions) if(r.field.equals("tripKm")) trip=r;
            assertNotNull("ROI da distancia deve ser localizado por bounding box",trip);
            OcrRoiRecheck.Probe probe=Tasks.await(OcrRoiRecheck.recheck(reader,b,trip),
                90,TimeUnit.SECONDS);
            assertEquals("11,8",probe.suggestion);
            assertTrue(probe.twoVariantsAgree);
            assertEquals("1,8",parsed.get("tripKm")); // NUNCA muda dado original sem revisao
        } finally { b.recycle(); }
    }

    @Test public void detectsSurgeBoxAndRechecksSyntheticDarkCard() throws Exception {
        Bitmap b=card(true,
            "99 Moto",
            "R$40,70",
            "2,8x",
            "4,98 971 corridas",
            "9 min (3 km)",
            "24 min (11,8 km)");
        try (TextRecognizer reader=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)) {
            Text full=Tasks.await(reader.process(InputImage.fromBitmap(b,0)),90,TimeUnit.SECONDS);
            OfferParser.Offer parsed=OfferParser.parse(full.getText());
            parsed.set("surge",""); // Simula campo incerto
            List<OcrRoiRecheck.Region> regions=OcrRoiRecheck.findRegions(full,b,parsed);
            OcrRoiRecheck.Region surge=null;
            for(OcrRoiRecheck.Region r:regions) if(r.field.equals("surge")) surge=r;
            assertNotNull("ROI do multiplicador deve existir",surge);
            OcrRoiRecheck.Probe probe=Tasks.await(OcrRoiRecheck.recheck(reader,b,surge),
                90,TimeUnit.SECONDS);
            assertEquals("2,8",probe.suggestion);
            assertEquals("",parsed.get("surge"));
        } finally { b.recycle(); }
    }

    @Test public void refusesCorruptedDigitsWithoutIndependentVisualEvidence() {
        OfferParser.Offer parsed=OfferParser.parse(
            "99 Moto R$40,70 42,8x 4,98 971 corridas 9 min (3 km) 24 min (1,8 km)");
        assertEquals("",parsed.get("surge"));
        assertFalse(FinancialGuard.assess(parsed).canCalculate);
    }
    @Test public void anchorFallbackFindsRegionWhenOnlyFourXIsRead() throws Exception {
        Bitmap b=card(true,
            "99 Moto",
            "R$40,70",
            "4x",
            "4,98 971 corridas",
            "9 min (3 km)",
            "24 min (11,8 km)");
        try (TextRecognizer reader=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)) {
            Text full=Tasks.await(reader.process(InputImage.fromBitmap(b,0)),90,TimeUnit.SECONDS);
            OfferParser.Offer parsed=OfferParser.parse(full.getText());
            parsed.set("surge","");
            OcrRoiRecheck.Region region=null;
            for (OcrRoiRecheck.Region candidate:OcrRoiRecheck.findRegions(full,b,parsed)) {
                if ("surge".equals(candidate.field)) region=candidate;
            }
            assertNotNull("Uma falha no numero deve usar ancora preco + corridas",region);
            OcrRoiRecheck.Probe candidate=Tasks.await(OcrRoiRecheck.recheck(reader,b,region),
                90,TimeUnit.SECONDS);
            assertEquals("Nao inventar um 2,8 a partir de 4x","",candidate.suggestion);
            assertEquals("",parsed.get("surge"));
        } finally { b.recycle(); }
    }

    @Test public void noProfileAnchorMeansNoBlindSurgeCrop() throws Exception {
        Bitmap b=card(false,
            "99 Moto",
            "R$40,70",
            "Navegacao 4x",
            "9 min (3 km)",
            "24 min (11,8 km)");
        try (TextRecognizer reader=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)) {
            Text full=Tasks.await(reader.process(InputImage.fromBitmap(b,0)),90,TimeUnit.SECONDS);
            OfferParser.Offer parsed=OfferParser.parse(full.getText());
            parsed.set("surge","");
            for(OcrRoiRecheck.Region region:OcrRoiRecheck.findRegions(full,b,parsed))
                assertFalse("Sem ancora de perfil, nao inventar ROI", "surge".equals(region.field));
        } finally { b.recycle(); }
    }

}
