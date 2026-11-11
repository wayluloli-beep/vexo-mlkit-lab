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

import org.json.JSONObject;
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
    // Emulador com inicialização fria do modelo pode ser lento.
    // Isso não altera as metas de latência para uso real no telefone.
    private static final long OCR_TIMEOUT_MS=60000;

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
        UiObject2 entire=awaitAny(device,3000,
            "Entire screen","Tela inteira");
        if(entire==null) {
            UiObject2 dropdown=awaitAny(device,UI_TIMEOUT_MS,
                "A single app","Share one app","Um único app",
                "Um aplicativo","Compartilhar um app");
            assertNotNull("É obrigatório selecionar a tela inteira no emulador; " +
                "não usar silenciosamente captura de apenas um aplicativo",dropdown);
            dropdown.click();
            entire=awaitAny(device,7000,"Entire screen","Tela inteira");
        }
        assertNotNull("Android não ofereceu tela inteira; teste exige escopo explícito",entire);
        entire.click();
        UiObject2 start=awaitAny(device,UI_TIMEOUT_MS,"Start now","Start",
            "Start recording","Share screen","Começar agora","Iniciar agora","Iniciar");
        assertNotNull("Não foi possível confirmar o diálogo nativo MediaProjection",start);
        start.click();
    }

    private static boolean awaitCounts(int minFrames,int minOcr,int minAlerts,long timeout)
            throws InterruptedException {
        long end=android.os.SystemClock.elapsedRealtime()+timeout;
        do {
            long[] n=LiveCaptureState.counts();
            if(n[0]>=minFrames && n[1]>=minOcr && n[2]>=minAlerts) return true;
            Thread.sleep(350);
        } while(android.os.SystemClock.elapsedRealtime()<end);
        return false;
    }

    @Test public void nativeConsentThenFakeOfferProducesRealFramesAndStops()
            throws Exception {
        final android.app.Instrumentation instrumentation=
            InstrumentationRegistry.getInstrumentation();
        final UiDevice device=UiDevice.getInstance(instrumentation);
        final android.content.Context context=instrumentation.getTargetContext();
        Activity control=null;
        try {
            Intent intent=new Intent(context,LiveCaptureActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            control=instrumentation.startActivitySync(intent);
            instrumentation.waitForIdleSync();

            // Teste voluntário abre a demo assim que consentimento é dado,
            // não desperdiçando OCR lento na tela de controles do Vexo.
            expectAndClick(device,"Autorizar e testar oferta fictícia");
            approveThroughSystemDialog(device); // consentimento via UI do SISTEMA

            // Só depois de existir display virtual, o estado será ACTIVE.
            long deadline=android.os.SystemClock.elapsedRealtime()+UI_TIMEOUT_MS;
            while(!LiveCaptureState.snapshot().startsWith("CAPTURA ATIVA:") &&
                    android.os.SystemClock.elapsedRealtime()<deadline) {
                Thread.sleep(300);
            }
            assertTrue("FGS/getMediaProjection/createVirtualDisplay não ativaram",
                LiveCaptureState.snapshot().startsWith("CAPTURA ATIVA:"));

            UiObject2 demoCard=device.wait(
                Until.findObject(By.text("99 Moto")),UI_TIMEOUT_MS);
            assertNotNull("A tela fictícia não abriu após a autorização",demoCard);
            instrumentation.waitForIdleSync();

            boolean recognized=awaitCounts(2,2,1,OCR_TIMEOUT_MS);
            long[] observed=LiveCaptureState.counts();
            long[] stages=LiveCaptureState.stageCounts();
            long[] timing=LiveCaptureState.ocrLatencyStats();
            long discardedStale=new JSONObject(LiveCaptureState.safeDiagnosticReport())
                .getLong("discardedStaleOcrFrames");
            String latencySummary=" OCR latencySamples="+timing[0]+
                ", OCR p50="+timing[3]+"ms, OCR p95="+timing[4]+"ms"+
                ", descartados por atraso="+discardedStale;
            String visibility=LiveCaptureState.captureVisibility();
            String stageSummary=" contextOffer="+stages[0]+
                ", contextUncertain="+stages[1]+
                ", contextRejected="+stages[2]+
                ", financialGuardBlocked="+stages[3]+
                ", waitingStableReads="+stages[4];
            boolean correctPrice=LiveCaptureState.snapshot().contains("Preço R$40,70");

            // TESTAR STOP MESMO QUANDO A LEITURA FALHA; caso contrário
            // um assert de OCR mascararia regressões no ciclo de vida.
            Intent stop=new Intent(context,LiveCaptureService.class)
                .setAction(LiveCaptureService.ACTION_STOP);
            context.startService(stop);
            long stopDeadline=android.os.SystemClock.elapsedRealtime()+UI_TIMEOUT_MS;
            while(LiveCaptureState.snapshot().startsWith("CAPTURA ATIVA:") &&
                    android.os.SystemClock.elapsedRealtime()<stopDeadline) {
                Thread.sleep(250);
            }
            boolean stopped=LiveCaptureState.snapshot().startsWith("SEM CAPTURA:");
            Thread.sleep(1800);
            boolean noLateOffer=!LiveCaptureState.snapshot().contains("Preço R$40,70");

            assertTrue("STOP não encerrou sessão autorizada",stopped);
            assertTrue("Callback OCR tardio reabriu oferta após STOP",noLateOffer);
            assertTrue("Não chegaram pixels do MediaProjection; frames="+
                observed[0]+", janela="+visibility,observed[0]>=2);
            assertTrue("Pixels chegaram, mas ML Kit não concluiu 2 leituras; "+
                "frames="+observed[0]+", OCR iniciado="+observed[3]+
                ", concluído="+observed[1]+", falhas OCR="+observed[4]+
                ", janela="+visibility+latencySummary,observed[1]>=2);
            assertTrue("ML Kit concluiu, mas nenhuma oferta segura foi emitida; "+
                "frames="+observed[0]+", OCR="+observed[1]+
                ", avisos="+observed[2]+", janela="+visibility+
                stageSummary+latencySummary,
                observed[2]>=1 && recognized);
            assertTrue("Oferta fictícia reconhecida mas preço não exibido",
                correctPrice);
            android.util.Log.i("VexoCaptureE2e","frames="+observed[0]+
                ", leituras="+observed[1]+", alertas="+observed[2]+
                ", STOP confirmado"+latencySummary);
        } finally {
            Intent stop=new Intent(context,LiveCaptureService.class)
                .setAction(LiveCaptureService.ACTION_STOP);
            try {context.startService(stop);} catch(Exception ignored) {}
            try {device.pressBack();} catch(Exception ignored) {}
            if(control!=null) control.runOnUiThread(control::finish);
        }
    }
}
