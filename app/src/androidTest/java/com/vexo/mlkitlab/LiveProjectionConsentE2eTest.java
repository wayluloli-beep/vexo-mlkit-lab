package com.vexo.mlkitlab;

import static org.junit.Assert.*;

import android.app.Activity;
import android.content.Intent;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.junit.Test;
import org.junit.runner.RunWith;

/**
 * E2E real (APENAS EMULADOR):
 * clica no diálogo NATIVO do Android, sem injetar token e sem bypass,
 * captura pixels do próprio Vexo e verifica contadores + OCR.
 * Não acessa Uber/99 e não grava pixels, OCR ou tela em arquivos/logs.
 *
 * Falha de teste é evidência de bloqueio, nunca permissão presumida.
 */
@RunWith(AndroidJUnit4.class)
public final class LiveProjectionConsentE2eTest {
    private static final long UI_TIMEOUT_MS=15000;
    private static final long OCR_TIMEOUT_MS=30000;

    private static UiObject2 first(UiDevice device,String...labels) {
        for(String label:labels) {
            UiObject2 control=device.findObject(By.text(label));
            if(control!=null) return control;
        }
        return null;
    }

    private static UiObject2 awaitAny(UiDevice device,long timeout,String...labels)
            throws InterruptedException {
        long end=android.os.SystemClock.elapsedRealtime()+timeout;
        do {
            UiObject2 obj=first(device,labels);
            if(obj!=null) return obj;
            Thread.sleep(200);
        } while(android.os.SystemClock.elapsedRealtime()<end);
        return null;
    }

    private static void expectAndClick(UiDevice device,String label) {
        UiObject2 button=device.wait(Until.findObject(By.text(label)),UI_TIMEOUT_MS);
        assertNotNull("Não apareceu o botão de teste: "+label,button);
        button.click();
    }

    private static void approveThroughSystemDialog(UiDevice device)
            throws Exception {
        // Android 14/15: se o diálogo oferece seleção de app ou tela, escolher
        // explicitamente "Entire screen" APENAS no emulador com dados falsos.
        UiObject2 dropdown=awaitAny(device,UI_TIMEOUT_MS,"A single app","Um único app",
            "Um aplicativo");
        if(dropdown!=null) {
            dropdown.click();
            UiObject2 entire=awaitAny(device,7000,
                "Entire screen","Tela inteira");
            assertNotNull("Android não ofereceu opção de tela inteira no emulador",entire);
            entire.click();
        }
        UiObject2 start=awaitAny(device,UI_TIMEOUT_MS,"Start now","Start",
            "Start recording","Share screen","Começar agora","Iniciar agora","Iniciar");
        assertNotNull("Não foi possível confirmar o diálogo nativo MediaProjection",start);
        start.click();
    }

    private static void requireCount(String stage,int index,long minimum,long timeout)
            throws InterruptedException {
        long end=android.os.SystemClock.elapsedRealtime()+timeout;
        long[] counts;
        do {
            counts=LiveCaptureState.counts();
            if(counts[index]>=minimum) return;
            Thread.sleep(350);
        } while(android.os.SystemClock.elapsedRealtime()<end);
        counts=LiveCaptureState.counts();
        fail(stage+" timeout: frames="+counts[0]+", ocr="+counts[1]+
            ", avisos="+counts[2]+" (apenas contadores agregados)");
    }

    private static void stopAndVerify(android.content.Context context)
            throws InterruptedException {
        Intent stop=new Intent(context,LiveCaptureService.class)
            .setAction(LiveCaptureService.ACTION_STOP);
        context.startService(stop);
        long deadline=android.os.SystemClock.elapsedRealtime()+UI_TIMEOUT_MS;
        while(LiveCaptureState.snapshot().startsWith("CAPTURA ATIVA:") &&
                android.os.SystemClock.elapsedRealtime()<deadline) {
            Thread.sleep(250);
        }
        assertTrue("STOP não encerrou sessão autorizada",
            LiveCaptureState.snapshot().startsWith("SEM CAPTURA:"));
        Thread.sleep(1800);
        assertFalse("OCR antigo reapareceu após STOP",
            LiveCaptureState.snapshot().contains("Preço R$40,70"));
    }

    @Test public void nativeConsentThenFakeOfferProducesRealFramesAndStops()
            throws Exception {
        final android.app.Instrumentation instrumentation=
            InstrumentationRegistry.getInstrumentation();
        final UiDevice device=UiDevice.getInstance(instrumentation);
        final android.content.Context context=instrumentation.getTargetContext();
        Activity control=null;
        Activity demo=null;
        try {
            Intent intent=new Intent(context,LiveCaptureActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            control=instrumentation.startActivitySync(intent);
            instrumentation.waitForIdleSync();

            expectAndClick(device,"Autorizar e iniciar leitura de tela");
            approveThroughSystemDialog(device); // consentimento via UI do SISTEMA

            // Só depois de existir display virtual, o estado será ACTIVE.
            long deadline=android.os.SystemClock.elapsedRealtime()+UI_TIMEOUT_MS;
            while(!LiveCaptureState.snapshot().startsWith("CAPTURA ATIVA:") &&
                    android.os.SystemClock.elapsedRealtime()<deadline) {
                Thread.sleep(300);
            }
            assertTrue("FGS/getMediaProjection/createVirtualDisplay não ativaram",
                LiveCaptureState.snapshot().startsWith("CAPTURA ATIVA:"));

            Intent demoIntent=new Intent(context,DemoOfferActivity.class);
            demoIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            demo=instrumentation.startActivitySync(demoIntent);
            instrumentation.waitForIdleSync();

            try {
                requireCount("ImageReader frames",0,2,OCR_TIMEOUT_MS);
                requireCount("ML Kit OCR concluído",1,2,OCR_TIMEOUT_MS);
                requireCount("Oferta validada/aviso",2,1,OCR_TIMEOUT_MS);
                assertTrue("Card fictício não chegou ao resultado",
                    LiveCaptureState.snapshot().contains("Preço R$40,70"));
            } finally {
                // STOP também é verificado quando frames/OCR/classificação falham.
                stopAndVerify(context);
            }
        } finally {
            Intent stop=new Intent(context,LiveCaptureService.class)
                .setAction(LiveCaptureService.ACTION_STOP);
            try {context.startService(stop);} catch(Exception ignored) {}
            if(demo!=null) demo.runOnUiThread(demo::finish);
            if(control!=null) control.runOnUiThread(control::finish);
        }
    }
}
