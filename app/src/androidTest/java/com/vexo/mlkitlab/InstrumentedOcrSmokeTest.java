package com.vexo.mlkitlab;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
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
 * Android real dentro de emulador no GitHub Actions; imagem de teste sintética,
 * criada em memória. Nunca usa conta da 99, login nem prints de passageiros.
 *
 * Emula OCR real do ML Kit (não mocks), incluindo processamento e interpretação.
 * Não garante desempenho com ofertas reais, aparelhos distintos nem MediaProjection.
 */
@RunWith(AndroidJUnit4.class)
public class InstrumentedOcrSmokeTest {

    private static Bitmap renderCard(String... lines) {
        Bitmap bitmap=Bitmap.createBitmap(1360,1450,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(bitmap);
        canvas.drawColor(Color.WHITE);
        Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG | Paint.SUBPIXEL_TEXT_FLAG);
        paint.setColor(Color.BLACK);
        paint.setTypeface(Typeface.create(Typeface.DEFAULT,Typeface.BOLD));
        paint.setTextSize(67f);
        float y=145f;
        for (String line:lines) {
            canvas.drawText(line,85f,y,paint);
            y+=124f;
        }
        return bitmap;
    }

    @Test public void googleMlKitRunsOnEmulatorUsingSynthetic99Offer() throws Exception {
        Bitmap bitmap=renderCard(
            "99 Moto Negocia",
            "R$ 72,32",
            "3,2x",
            "4,73 114 corridas",
            "5 min (1,5 km)",
            "32 min (20,2 km)",
            "Aceitar por R$72,32");
        try (TextRecognizer recognizer=TextRecognition.getClient(
                TextRecognizerOptions.DEFAULT_OPTIONS)) {
            String text=Tasks.await(recognizer.process(InputImage.fromBitmap(bitmap,0)),
                75,TimeUnit.SECONDS).getText();
            assertNotNull(text);
            assertTrue("ML Kit nao reconheceu palavras na imagem sintética",text.length()>20);
            OfferParser.Offer parsed=OfferParser.parse(text);
            assertEquals("99",parsed.get("platform"));
            assertEquals("72,32",parsed.get("offerPrice"));
            assertEquals("20,2",parsed.get("tripKm"));
            assertTrue("O teste só valida dados sintéticos; confira prints reais",
                FinancialGuard.assess(parsed).canCalculate);
        } finally {
            bitmap.recycle();
        }
    }

    @Test public void potentiallyDangerousLostDigitIsFlaggedOffline() {
        OfferParser.Offer offer=OfferParser.parse(
            "99 Moto R$40,70 42,8x 4,98 971 corridas "
            +"9 min (3 km) 24 min (1,8 km)");
        assertFalse(FinancialGuard.assess(offer).canCalculate);
        assertTrue(FinancialGuard.assess(offer).message.contains("conferir"));
    }
}
