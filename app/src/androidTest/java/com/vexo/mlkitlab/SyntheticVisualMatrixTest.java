package com.vexo.mlkitlab;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Color;
import android.graphics.Typeface;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;
import org.junit.Test;
import org.junit.runner.RunWith;
import java.util.concurrent.TimeUnit;

/**
 * Testes VISUAIS sintéticos no emulador. São diferentes dos testes do parser:
 * estes realmente passam pixels pelo Google ML Kit no Android virtual.
 * NÃO representam amostra de ofertas reais da 99.
 */
@RunWith(AndroidJUnit4.class)
public class SyntheticVisualMatrixTest {
    private static Bitmap card(boolean dark, int fontSize, String... lines) {
        Bitmap bitmap=Bitmap.createBitmap(1450,1250,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(bitmap);
        canvas.drawColor(dark?Color.rgb(18,23,34):Color.rgb(251,251,251));
        Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG | Paint.SUBPIXEL_TEXT_FLAG);
        paint.setColor(dark?Color.rgb(247,247,247):Color.rgb(20,20,20));
        paint.setTypeface(Typeface.create(Typeface.DEFAULT,Typeface.BOLD));
        paint.setTextSize(fontSize);
        float y=130f;
        for (String line:lines) {
            canvas.drawText(line,80f,y,paint);
            y+=115f;
        }
        return bitmap;
    }

    private static OfferParser.Offer scan(Bitmap bitmap) throws Exception {
        try (TextRecognizer recognizer=TextRecognition.getClient(
                TextRecognizerOptions.DEFAULT_OPTIONS)) {
            String text=Tasks.await(recognizer.process(InputImage.fromBitmap(bitmap,0)),
                90,TimeUnit.SECONDS).getText();
            assertTrue("ML Kit nao reconheceu texto da imagem sintética",text.length()>25);
            return OfferParser.parse(text);
        } finally {
            bitmap.recycle();
        }
    }

    @Test public void lightListWithoutCurrencySymbolInPerKm() throws Exception {
        OfferParser.Offer offer=scan(card(false,62,
            "Solicitacoes 99",
            "Negocia",
            "R$11,52   1,28/km",
            "5,00 11 corridas",
            "(6 min 2,7 km)",
            "(17 min 6,3 km)",
            "Aceitar por R$11,52"));
        assertEquals("11,52",offer.get("offerPrice"));
        assertEquals("1,28",offer.get("perKm"));
        assertEquals("2,7",offer.get("pickupKm"));
        assertEquals("6,3",offer.get("tripKm"));
    }

    @Test public void darkMotoWithDoubleDigitKmAndSurge() throws Exception {
        OfferParser.Offer offer=scan(card(true,63,
            "99 Moto",
            "R$40,70",
            "2,8x",
            "4,98 971 corridas",
            "9 min (3 km)",
            "24 min (11,8 km)"));
        assertEquals("40,70",offer.get("offerPrice"));
        assertEquals("11,8",offer.get("tripKm"));
        assertEquals("2,8",offer.get("surge"));
        assertTrue(FinancialGuard.assess(offer).canCalculate);
    }

    @Test public void navigationDistanceOutsideOfferMustNotReplacePickup() throws Exception {
        OfferParser.Offer offer=scan(card(false,59,
            "853 m    Av. Exemplo",
            "99 Prioritario",
            "R$41,40  2,2x",
            "R$5,19/km",
            "4,95 665 corridas",
            "3 min (668 m)",
            "25 min (7,3 km)"));
        assertEquals("41,40",offer.get("offerPrice"));
        assertEquals("0,668",offer.get("pickupKm"));
        assertEquals("7,3",offer.get("tripKm"));
    }
}
