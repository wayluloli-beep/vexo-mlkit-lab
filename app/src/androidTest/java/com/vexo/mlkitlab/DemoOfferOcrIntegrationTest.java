package com.vexo.mlkitlab;

import static org.junit.Assert.*;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.view.View;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.TimeUnit;

/**
 * Prova que a TELA SINTÉTICA do próprio Vexo gera pixels legíveis pelo ML Kit.
 * NÃO substitui uma sessão MediaProjection autorizada nem testa a 99.
 * Nada salvo em arquivos, logs ou GitHub.
 */
@RunWith(AndroidJUnit4.class)
public final class DemoOfferOcrIntegrationTest {
    @Test public void demoScreenIsReadableAsOfferByRealMlKit() throws Exception {
        Intent launch=new Intent(InstrumentationRegistry.getInstrumentation()
            .getTargetContext(),DemoOfferActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Activity activity=InstrumentationRegistry.getInstrumentation().startActivitySync(launch);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        final Bitmap[] pixels=new Bitmap[1];
        try {
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                View root=activity.getWindow().getDecorView();
                int w=root.getWidth(), h=root.getHeight();
                if(w<=0 || h<=0) throw new IllegalStateException("Tela do laboratório sem tamanho");
                pixels[0]=Bitmap.createBitmap(w,h,Bitmap.Config.ARGB_8888);
                Canvas canvas=new Canvas(pixels[0]);
                root.draw(canvas); // somente view própria; não MediaProjection
            });
            assertNotNull(pixels[0]);
            try(TextRecognizer reader=TextRecognition.getClient(
                    TextRecognizerOptions.DEFAULT_OPTIONS)) {
                Text ocr=Tasks.await(reader.process(InputImage.fromBitmap(pixels[0],0)),
                    90,TimeUnit.SECONDS);
                OfferParser.Offer parsed=OfferParser.parse(ocr.getText());
                assertEquals("40,70",parsed.get("offerPrice"));
                assertEquals("11,8",parsed.get("tripKm"));
                assertEquals("3",parsed.get("pickupKm"));
                assertTrue(FinancialGuard.assess(parsed).canCalculate);
                assertEquals(ScreenContextClassifier.Kind.OFFER_CANDIDATE,
                    ScreenContextClassifier.classify(ocr.getText()));
            }
        } finally {
            if(pixels[0]!=null) pixels[0].recycle();
            activity.runOnUiThread(activity::finish);
        }
    }
}
