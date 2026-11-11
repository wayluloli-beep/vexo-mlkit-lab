package com.vexo.mlkitlab;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.content.Context;
import android.content.ClipData;
import android.content.ClipboardManager;
import androidx.core.content.FileProvider;
import java.io.File;
import java.io.FileOutputStream;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Homologação offline e local. Usa EXATAMENTE o mesmo ML Kit e OfferParser
 * da tela de leitura individual. Nenhum teste altera o histórico.
 */
public final class BatchOcrActivity extends Activity {
    private static final int PICK_BATCH = 87, SAVE_REPORT = 88;
    private static final int MAX_ZIP_BYTES = 28 * 1024 * 1024;
    private static final int MAX_ENTRY_BYTES = 7 * 1024 * 1024;
    private static final int MAX_CASES = 200;
    private final int bg = 0xFF0B1018, panel = 0xFF1A2430, cyan = 0xFF1CB8CA;
    private Button select, export, share, copy;
    private TextView status, totals;
    private ProgressBar progress;
    private LinearLayout resultsView;
    private final ArrayList<JSONObject> cases = new ArrayList<>();
    private final HashMap<String,byte[]> images = new HashMap<>();
    private final LinkedHashMap<String,int[]> perField = new LinkedHashMap<>();
    private JSONArray evaluations = new JSONArray();
    private TextRecognizer recognizer;
    private int current, matched, checked, discrepancies, failures;
    private String reportJson = "";

    private int dp(int n) { return (int)(n * getResources().getDisplayMetrics().density + 0.5f); }
    private GradientDrawable shape(int color) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color); d.setCornerRadius(dp(14)); return d;
    }
    private TextView txt(String value, int size, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(value); t.setTextSize(size); t.setTextColor(color);
        if (bold) t.setTypeface(null, Typeface.BOLD);
        return t;
    }
    private void add(LinearLayout parent, View v, int space) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2);
        lp.topMargin = dp(space); parent.addView(v,lp);
    }
    private Button button(String value, int color) {
        Button b = new Button(this);
        b.setText(value);
        b.setTextColor(color == cyan ? Color.BLACK : Color.WHITE);
        b.setAllCaps(false); b.setBackground(shape(color));
        return b;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(bg);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20),dp(32),dp(20),dp(40));
        scroll.addView(root);
        add(root,txt("VEXO",30,cyan,true),0);
        add(root,txt("OCR • Teste automático 0.3.5",19,Color.WHITE,true),5);
        add(root,txt("Selecione o ZIP de homologação. O ML Kit compara os campos e tenta uma releitura experimental em regiões suspeitas, sem alterar os valores originais.",14,0xFFB1C2D0,false),12);
        add(root,txt("Processamento local; o relatório guarda só valores numéricos e diagnósticos. Sugestões ROI exigem conferência humana; nenhuma oferta é alterada.",12,0xFF87DBC8,false),12);
        select=button("Selecionar ZIP e testar tudo",cyan);
        add(root,select,22); select.setOnClickListener(v -> pickZip());

        progress = new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100); progress.setProgress(0); add(root,progress,16);
        status=txt("Nenhum teste iniciado.",14,0xFFB1C2D0,false);
        add(root,status,8);
        totals=txt("",16,Color.WHITE,true);
        add(root,totals,12);
        export=button("Exportar relatório JSON",0xFF334357);
        export.setEnabled(false); add(root,export,12);
        export.setOnClickListener(v -> chooseExport());
        share=button("Compartilhar JSON direto (sem salvar)",cyan);
        share.setEnabled(false); add(root,share,10);
        share.setOnClickListener(v -> shareReport());
        copy=button("Copiar JSON para a área de transferência",0xFF334357);
        copy.setEnabled(false); add(root,copy,10);
        copy.setOnClickListener(v -> copyReport());

        add(root,txt("RESULTADOS POR IMAGEM",15,cyan,true),25);
        resultsView=new LinearLayout(this);
        resultsView.setOrientation(LinearLayout.VERTICAL);
        add(root,resultsView,10);
        setContentView(scroll);
        reportJson=getSharedPreferences("vexo_batch_report",MODE_PRIVATE).getString("json","");
        if (!reportJson.isEmpty()) {
            export.setEnabled(true); share.setEnabled(true); copy.setEnabled(true);
            status.setText("Relatório anterior recuperado. Pode compartilhar sem repetir o lote.");
        }
    }

    private void pickZip() {
        if (recognizer != null) return;
        Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.setType("*/*");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{
            "application/zip","application/x-zip-compressed","application/octet-stream"
        });
        startActivityForResult(i,PICK_BATCH);
    }
    private void chooseExport() {
        if (reportJson.isEmpty()) return;
        Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);
        i.setType("application/json");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.putExtra(Intent.EXTRA_TITLE,"vexo-ocr-batch-0.3.5-report.json");
        startActivityForResult(i,SAVE_REPORT);
    }
    @Override protected void onActivityResult(int req, int code, Intent data) {
        super.onActivityResult(req,code,data);
        if (code!=RESULT_OK || data==null || data.getData()==null) return;
        if (req==SAVE_REPORT) {
            if (reportJson.isEmpty()) reportJson=getSharedPreferences("vexo_batch_report",MODE_PRIVATE).getString("json","");
            if (reportJson.isEmpty()) {
                status.setText("Sem dados para exportar. Nenhum arquivo vazio foi gravado.");
                return;
            }
            try (OutputStream stream=getContentResolver().openOutputStream(data.getData(),"wt")) {
                if (stream==null) throw new Exception("Arquivo não disponível");
                byte[] output=reportJson.getBytes(StandardCharsets.UTF_8);
                stream.write(output);
                stream.flush();
                Toast.makeText(this,"JSON gravado ("+output.length+" bytes).",Toast.LENGTH_LONG).show();
            } catch (Exception e) { status.setText("Falha ao exportar: "+e.getMessage()); }
        } else if (req==PICK_BATCH) {
            try {
                prepare(data.getData());
                startBatch();
            } catch (Exception e) {
                status.setText("Não foi possível abrir o ZIP: "+e.getMessage());
                select.setEnabled(true);
            }
        }
    }

    private byte[] readEntry(ZipInputStream zin, int maxSize) throws Exception {
        ByteArrayOutputStream buffer=new ByteArrayOutputStream();
        byte[] block=new byte[16384];
        int n,total=0;
        while ((n=zin.read(block)) != -1) {
            total += n;
            if (total > maxSize) throw new Exception("Entrada excede o limite de segurança");
            buffer.write(block,0,n);
        }
        return buffer.toByteArray();
    }

    private void prepare(Uri zipUri) throws Exception {
        cases.clear(); images.clear(); perField.clear();
        evaluations=new JSONArray();
        reportJson="";
        getSharedPreferences("vexo_batch_report",MODE_PRIVATE).edit().remove("json").apply();
        current=matched=checked=discrepancies=failures=0;
        progress.setProgress(0);
        resultsView.removeAllViews();
        export.setEnabled(false);
        share.setEnabled(false);
        copy.setEnabled(false);
        byte[] manifest=null;
        int cumulative=0;
        try (InputStream input=getContentResolver().openInputStream(zipUri)) {
            if (input==null) throw new Exception("Arquivo inacessível");
            try (ZipInputStream zin=new ZipInputStream(input)) {
                ZipEntry entry;
                while ((entry=zin.getNextEntry())!=null) {
                    if (entry.isDirectory()) { zin.closeEntry(); continue; }
                    String name=entry.getName();
                    if (name.contains("..") || name.startsWith("/"))
                        throw new Exception("Caminho inseguro dentro do ZIP");
                    if (name.equals("manifest.jsonl") || 
                        (name.startsWith("images/") && (name.endsWith(".jpg") || name.endsWith(".png")))) {
                        byte[] data=readEntry(zin,MAX_ENTRY_BYTES);
                        cumulative += data.length;
                        if (cumulative > MAX_ZIP_BYTES) throw new Exception("ZIP grande demais");
                        if (name.equals("manifest.jsonl")) manifest=data;
                        else images.put(name,data);
                    }
                    zin.closeEntry();
                }
            }
        }
        if (manifest==null) throw new Exception("manifest.jsonl ausente");
        String[] lines=new String(manifest,StandardCharsets.UTF_8).split("\\r?\\n");
        for (String line:lines) {
            if (line.trim().isEmpty()) continue;
            if (cases.size()>=MAX_CASES) throw new Exception("Mais de 200 casos");
            JSONObject obj=new JSONObject(line);
            String path=obj.getString("image");
            String id=obj.getString("id");
            if (!id.matches("[A-Za-z0-9_-]{1,40}") || !path.matches("images/[A-Za-z0-9_.-]+\\.(jpg|png)"))
                throw new Exception("Identificador ou imagem inválidos");
            if (!images.containsKey(path)) throw new Exception("Imagem ausente: "+path);
            if (!obj.has("ground_truth")) throw new Exception("Gabarito ausente: "+id);
            cases.add(obj);
        }
        if (cases.isEmpty()) throw new Exception("Manifesto sem casos");
        progress.setMax(cases.size());
        totals.setText(cases.size()+" imagens prontas");
    }

    private void startBatch() {
        select.setEnabled(false);
        status.setText("Iniciando o Google ML Kit...");
        recognizer=TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        scanNext();
    }

    private void scanNext() {
        if (current>=cases.size()) { finishBatch(); return; }
        JSONObject item=cases.get(current);
        Bitmap bitmap=null;
        try {
            byte[] jpeg=images.get(item.getString("image"));
            BitmapFactory.Options opts=new BitmapFactory.Options();
            opts.inJustDecodeBounds=true;
            BitmapFactory.decodeByteArray(jpeg,0,jpeg.length,opts);
            if (opts.outWidth<=0 || opts.outHeight<=0 || ((long)opts.outWidth*opts.outHeight)>22000000L)
                throw new Exception("Dimensões de imagem inválidas");
            bitmap=BitmapFactory.decodeByteArray(jpeg,0,jpeg.length);
            if (bitmap==null) throw new Exception("Imagem não decodificada");
            final Bitmap toRelease=bitmap;
            final String id=item.getString("id");
            status.setText("Lendo "+(current+1)+"/"+cases.size()+" • "+id);
            InputImage img=InputImage.fromBitmap(bitmap,0);
            recognizer.process(img)
                .addOnSuccessListener(text -> {
                    OfferParser.Offer baseline=OfferParser.parse(text.getText());
                    // Diagnóstico ROI: NÃO corrige a oferta nem modifica a pontuação original.
                    // Releitura limitada a 3 regiões; resultados apenas numéricos no JSON.
                    java.util.List<OcrRoiRecheck.Region> regions=
                        OcrRoiRecheck.findRegions(text,toRelease,baseline);
                    runRoiDiagnostics(item,baseline,text.getText(),toRelease,
                        regions,0,new JSONObject());
                })
                .addOnFailureListener(err -> {
                    addEvaluation(item,new OfferParser.Offer(),
                        err.getClass().getSimpleName(),null,new JSONObject());
                    completeCase(toRelease);
                });
        } catch (Exception e) {
            if (bitmap!=null) bitmap.recycle();
            addEvaluation(item,new OfferParser.Offer(),e.getClass().getSimpleName(),null,new JSONObject());
            current++;
            progress.setProgress(current);
            scanNext();
        }
    }

    private void completeCase(Bitmap bitmap) {
        if (bitmap!=null && !bitmap.isRecycled()) bitmap.recycle();
        current++;
        progress.setProgress(current);
        scanNext();
    }

    /**
     * A imagem permanece em memória até TODAS as leituras da região terminarem.
     * Nunca armazenar/transmitir o texto bruto nem pixels no relatório.
     */
    private void runRoiDiagnostics(JSONObject item, OfferParser.Offer baseline, String raw,
            Bitmap bitmap, java.util.List<OcrRoiRecheck.Region> regions,
            int index, JSONObject evidence) {
        if (index>=regions.size() || index>=3) {
            addEvaluation(item,baseline,null,raw,evidence);
            completeCase(bitmap);
            return;
        }
        OcrRoiRecheck.Region region=regions.get(index);
        status.setText("Analisando "+(current+1)+"/"+cases.size()+
            " • região "+(index+1)+"/"+Math.min(3,regions.size()));
        try {
            OcrRoiRecheck.recheck(recognizer,bitmap,region)
                .addOnSuccessListener(probe -> {
                    try {
                        JSONObject detail=new JSONObject();
                        detail.put("candidate",probe.suggestion);
                        detail.put("twoVariantsAgree",probe.twoVariantsAgree);
                        detail.put("baselineValue",baseline.get(probe.field));
                        detail.put("status",probe.suggestion.isEmpty()?
                            "not_recovered":"candidate_for_human_review");
                        detail.put("notAutomaticallyApplied",true);
                        evidence.put(probe.field,detail);
                    } catch (Exception ignored) {}
                    runRoiDiagnostics(item,baseline,raw,bitmap,regions,index+1,evidence);
                })
                .addOnFailureListener(err -> {
                    try {
                        evidence.put(region.field,new JSONObject()
                            .put("candidate","")
                            .put("status","recheck_failed")
                            .put("notAutomaticallyApplied",true));
                    } catch(Exception ignored) {}
                    runRoiDiagnostics(item,baseline,raw,bitmap,regions,index+1,evidence);
                });
        } catch(Exception err) {
            try {
                evidence.put(region.field,new JSONObject()
                    .put("candidate","")
                    .put("status","recheck_failed")
                    .put("notAutomaticallyApplied",true));
            } catch(Exception ignored) {}
            runRoiDiagnostics(item,baseline,raw,bitmap,regions,index+1,evidence);
        }
    }

    private void addEvaluation(JSONObject item, OfferParser.Offer predicted, String error, String rawOcr, JSONObject roiEvidence) {
        try {
            JSONObject truth=item.getJSONObject("ground_truth");
            JSONObject row=new JSONObject();
            row.put("id",item.getString("id"));
            if (error!=null) { failures++; row.put("error",error); }
            JSONObject fields=new JSONObject();
            StringBuilder diffs=new StringBuilder();
            int hits=0,fieldsTested=0;
            for (String key:OfferParser.KEYS) {
                Object wanted=ReportFieldPolicy.expectedOrAbsent(target(truth,key));
                String got=predicted.get(key);
                if (got==null) got="";
                if (wanted==null) {
                    // Campo não visível: registrar falso positivo, sem contar acerto por omissão.
                    if (got.isEmpty()) continue;
                    JSONObject mismatch=new JSONObject();
                    mismatch.put("expected",JSONObject.NULL);
                    mismatch.put("actual",got);
                    mismatch.put("status","false_positive");
                    fields.put(key,mismatch);
                    discrepancies++; checked++; fieldsTested++;
                    stats(key,false);
                    diffs.append("• ").append(key).append(": inesperado ").append(got).append("\n");
                    continue;
                }
                boolean ok=equivalent(key,wanted,got);
                JSONObject cell=new JSONObject();
                cell.put("expected",wanted);
                cell.put("actual",got);
                cell.put("status",ok?"ok":(got.isEmpty()?"missing":"wrong"));
                fields.put(key,cell);
                checked++; fieldsTested++;
                if (ok) { matched++; hits++; }
                else {
                    discrepancies++;
                    diffs.append("• ").append(key).append(": esperado ")
                        .append(wanted.toString()).append(" / lido ")
                        .append(got.isEmpty()?"[vazio]":got).append("\n");
                }
                stats(key,ok);
            }
            FinancialGuard.Assessment audit=FinancialGuard.assess(predicted);
            JSONObject safety=new JSONObject();
            safety.put("basicFieldsUsable",audit.canCalculate);
            safety.put("reasons",new JSONArray(audit.reasons));
            row.put("financialSafety",safety);
            row.put("ocrEvidence",OcrEvidence.diagnostic(rawOcr,fields));
            row.put("roiDiagnostics",roiEvidence);
            row.put("fields",fields);
            row.put("correct",hits);
            row.put("tested",fieldsTested);
            evaluations.put(row);
            LinearLayout cardBox=new LinearLayout(this);
            cardBox.setOrientation(LinearLayout.VERTICAL);
            cardBox.setPadding(dp(14),dp(12),dp(14),dp(12));
            cardBox.setBackground(shape(panel));
            add(cardBox,txt(row.getString("id")+"  •  "+hits+"/"+fieldsTested+" campos",16,
                    hits==fieldsTested ? 0xFF77DEB1 : 0xFFFFC27A,true),0);
            if (!audit.canCalculate) add(cardBox,txt("FINANCEIRO: conferir campos — "+String.join("; ",audit.reasons),12,0xFFFFC27A,false),7);
            if (diffs.length()>0) add(cardBox,txt(diffs.toString().trim(),12,0xFFB9C6D0,false),7);
            else add(cardBox,txt("Nenhuma divergência nos campos avaliados.",12,0xFF9FD5BC,false),7);
            add(resultsView,cardBox,10);
            totals.setText(matched+"/"+checked+" campos corretos • "+(current+1)+"/"+cases.size()+" imagens");
        } catch (Exception e) {
            failures++;
            status.setText("Falha ao comparar "+item.optString("id")+": "+e.getMessage());
        }
    }

    private void stats(String key,boolean ok) {
        int[] counts=perField.get(key);
        if (counts==null) { counts=new int[2]; perField.put(key,counts); }
        counts[0]++;
        if (ok) counts[1]++;
    }

    private Object target(JSONObject gt, String key) {
        switch(key) {
            case "platform": return "99";
            case "offerType": {
                String t=gt.optString("offer_kind","");
                if (t.contains("Moto") || t.contains("Negocia") || t.contains("Prioritário") || t.contains("Pgto.")) return t;
                return null;
            }
            case "offerPrice": return gt.opt("price_brl")==JSONObject.NULL ? null : gt.opt("price_brl");
            case "payment": return gt.isNull("payment")?null:gt.opt("payment");
            case "perKm": return gt.isNull("displayed_brl_per_km")?null:gt.opt("displayed_brl_per_km");
            case "pickupMin": return gt.opt("pickup_min");
            case "pickupKm": return gt.opt("pickup_km");
            case "tripMin": return gt.opt("trip_min");
            case "tripKm": return gt.opt("trip_km");
            case "rating": return gt.opt("rating");
            case "rides": return gt.opt("completed_rides");
            case "surge": return gt.isNull("dynamic_multiplier")?null:gt.opt("dynamic_multiplier");
            case "negotiations": return gt.optJSONArray("counteroffers_brl");
            default: return null;
        }
    }

    private boolean equivalent(String field,Object expected,String actual) {
        if ("platform".equals(field)) return "99".equals(actual.trim());
        if ("offerType".equals(field))
            return OfferTypeComparator.equivalent(expected.toString(),actual);
        if ("payment".equals(field))
            return actual.toLowerCase(Locale.ROOT).contains(expected.toString().toLowerCase(Locale.ROOT));
        if ("negotiations".equals(field)) {
            JSONArray list=(JSONArray)expected;
            String[] tokens=actual.trim().isEmpty()?new String[0]:actual.split("\\s*;\\s*");
            if (list.length()!=tokens.length) return false;
            for (int i=0;i<tokens.length;i++) {
                double got=OfferParser.decimal(tokens[i]);
                if (Double.isNaN(got)||Math.abs(got-list.optDouble(i))>0.011) return false;
            }
            return true;
        }
        double value=OfferParser.decimal(actual);
        if (Double.isNaN(value)) return false;
        double expect;
        try { expect=Double.parseDouble(expected.toString()); }
        catch (Exception e) { return false; }
        double tolerance=("pickupKm".equals(field)||"tripKm".equals(field))?0.002:0.011;
        return Math.abs(expect-value)<=tolerance;
    }

    private void finishBatch() {
        try {
            if (recognizer!=null) { recognizer.close(); recognizer=null; }
            select.setEnabled(true);
            images.clear();
            JSONObject report=new JSONObject();
            report.put("schema","vexo-ocr-batch-report-v1");
            report.put("appVersion","0.3.5");
            report.put("generator","Android Google ML Kit + OfferParser 0.3");
            report.put("timestampMs",System.currentTimeMillis());
            report.put("testImages",cases.size());
            JSONObject summary=new JSONObject();
            summary.put("checked",checked); summary.put("correct",matched);
            summary.put("discrepant",discrepancies); summary.put("processingErrors",failures);
            summary.put("accuracyPct",checked==0?JSONObject.NULL:Math.round(matched*10000.0/checked)/100.0);
            JSONObject breakdown=new JSONObject();
            for (Map.Entry<String,int[]> entry:perField.entrySet()) {
                JSONObject field=new JSONObject();
                field.put("checked",entry.getValue()[0]);
                field.put("correct",entry.getValue()[1]);
                breakdown.put(entry.getKey(),field);
            }
            report.put("summary",summary);
            report.put("perField",breakdown);
            report.put("samples",evaluations);
            reportJson=report.toString(2);
            getSharedPreferences("vexo_batch_report",MODE_PRIVATE).edit().putString("json",reportJson).commit();
            export.setEnabled(true);
            share.setEnabled(true);
            copy.setEnabled(true);
            double pct=checked==0?0:100.0*matched/checked;
            totals.setText(String.format(Locale.forLanguageTag("pt-BR"),
                "%d/%d campos corretos (%.1f%%) • %d falhas de processamento",
                matched,checked,pct,failures));
            status.setText("Lote concluído. Exporte o JSON para analisar as divergências.");
        } catch (Exception e) {
            status.setText("Erro ao gerar o relatório: "+e.getMessage());
        }
    }

    /** Envia um arquivo JSON real usando content:// com permissão temporária.
     * Evita depender do gerenciador de arquivos para salvar e depois anexar.
     */
    private void shareReport() {
        if (reportJson.isEmpty()) reportJson=getSharedPreferences("vexo_batch_report",MODE_PRIVATE).getString("json","");
        if (reportJson.isEmpty()) { status.setText("Nenhum relatório disponível."); return; }
        try {
            File folder=new File(getCacheDir(),"reports");
            if (!folder.exists() && !folder.mkdirs()) throw new Exception("Pasta local indisponível");
            File file=new File(folder,"vexo-ocr-relatorio-0.3.5.json");
            byte[] content=reportJson.getBytes(StandardCharsets.UTF_8);
            try (FileOutputStream out=new FileOutputStream(file,false)) {
                out.write(content);
                out.flush();
                out.getFD().sync();
            }
            if (file.length()!=content.length || file.length()==0)
                throw new Exception("Relatório não foi gravado corretamente");
            Uri uri=FileProvider.getUriForFile(this,
                getPackageName()+".fileprovider",file);
            Intent intent=new Intent(Intent.ACTION_SEND);
            intent.setType("application/json");
            intent.putExtra(Intent.EXTRA_STREAM,uri);
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            intent.setClipData(ClipData.newRawUri("Vexo OCR JSON",uri));
            startActivity(Intent.createChooser(intent,"Enviar relatório Vexo"));
        } catch (Exception e) {
            status.setText("Não consegui compartilhar: "+e.getMessage());
        }
    }

    private void copyReport() {
        if (reportJson.isEmpty()) reportJson=getSharedPreferences("vexo_batch_report",MODE_PRIVATE).getString("json","");
        if (reportJson.isEmpty()) { status.setText("Nenhum relatório disponível."); return; }
        ClipboardManager clipboard=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard==null) { status.setText("Área de transferência indisponível"); return; }
        clipboard.setPrimaryClip(ClipData.newPlainText("Vexo OCR relatório",reportJson));
        Toast.makeText(this,"JSON copiado. Cole no ChatGPT.",Toast.LENGTH_LONG).show();
    }

    @Override protected void onDestroy() {
        if (recognizer!=null) { recognizer.close(); recognizer=null; }
        super.onDestroy();
    }
}
