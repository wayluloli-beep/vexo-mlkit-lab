package com.vexo.mlkitlab;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.net.Uri;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import android.text.InputType;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

import org.json.JSONArray;
import org.json.JSONObject;

import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.util.LinkedHashMap;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int PICK_IMAGE = 42;
    private static final int CREATE_BACKUP = 43;
    private static final int OPEN_BACKUP = 44;
    private final int dark = 0xFF0B0F16;
    private final int card = 0xFF19202B;
    private final int blue = 0xFF1AB7CF;
    private final int muted = 0xFFADBCC9;
    private final LinkedHashMap<String,EditText> inputs = new LinkedHashMap<>();
    private TextView status, rawOutput, memory, safetyStatus;
    private LinearLayout results, rawPanel;
    private Button choose, confirm, openOriginal, toggleRaw;
    private Uri chosenUri;
    private String lastText = "";
    private boolean currentSaved = false;
    private OfferParser.Offer baseline = new OfferParser.Offer();
    private SharedPreferences prefs;

    private int px(float dp) {
        return (int)(dp * getResources().getDisplayMetrics().density + 0.5f);
    }
    private GradientDrawable bg(int color, int radius) {
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(color); gd.setCornerRadius(px(radius)); return gd;
    }
    private TextView label(String text, int size, int color, boolean strong) {
        TextView v = new TextView(this);
        v.setText(text); v.setTextSize(size); v.setTextColor(color);
        if (strong) v.setTypeface(null, Typeface.BOLD);
        return v;
    }
    private void append(LinearLayout root, View item, int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2);
        lp.topMargin = px(top); root.addView(item, lp);
    }
    private Button button(String name, int color, int textColor) {
        Button b = new Button(this);
        b.setText(name); b.setTextColor(textColor);
        b.setTextSize(15); b.setAllCaps(false); b.setBackground(bg(color,14));
        return b;
    }
    private LinearLayout panel() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setPadding(px(18),px(18),px(18),px(18));
        l.setBackground(bg(card,16));
        return l;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("vexo_ocr_v03", MODE_PRIVATE);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true); scroll.setBackgroundColor(dark);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(px(20),px(32),px(20),px(38));
        scroll.addView(root);

        append(root, label("VEXO",30,blue,true),0);
        append(root,label("Leitor de ofertas  •  Laboratório 0.3.4",18,Color.WHITE,true),6);
        append(root,label("O ML Kit reconhece as letras. O Vexo separa os campos. Você confere e só depois salva.",14,muted,false),12);

        choose = button("Escolher print da galeria", blue, Color.BLACK);
        append(root,choose,24); choose.setOnClickListener(v -> chooseImage());

        Button batch = button("Teste automático · lote de prints",0xFF334357,Color.WHITE);
        append(root,batch,10);
        batch.setOnClickListener(v -> startActivity(new Intent(this,BatchOcrActivity.class)));

        status = label("Selecione uma imagem para começar",14,muted,false);
        append(root,status,14);

        memory = label("",13,0xFF82DDBF,false);
        append(root,memory,8); updateMemory();

        LinearLayout backupPanel = panel();
        append(root,backupPanel,14);
        backupPanel.addView(label("MEUS DADOS E BACKUP",15,blue,true));
        append(backupPanel,label("Exporte um arquivo JSON para proteger seus registros. O backup não tem senha: guarde em local privado. Importar não apaga ofertas existentes.",13,muted,false),8);
        Button exportButton = button("Exportar backup JSON",0xFF303D4E,Color.WHITE);
        append(backupPanel,exportButton,14);
        exportButton.setOnClickListener(v -> chooseBackupLocation());
        Button importButton = button("Importar backup JSON",0xFF303D4E,Color.WHITE);
        append(backupPanel,importButton,10);
        importButton.setOnClickListener(v -> chooseBackupFile());
        append(backupPanel,label("Esta 0.3 instala separadamente da 0.2. Ela não consegue acessar automaticamente os registros salvos na 0.2; mantenha a versão antiga instalada.",12,0xFFF2C67C,false),12);

        results = panel();
        append(root,results,18);
        results.setVisibility(View.GONE);
        results.addView(label("OFERTA INTERPRETADA",14,blue,true));
        append(results,label("Confira os campos com o print. Se o OCR não encontrar algo, deixe vazio ou preencha manualmente.",13,muted,false),8);
        safetyStatus=label("",14,0xFFF4C27C,true);
        append(results,safetyStatus,12);

        for (int i=0; i<OfferParser.KEYS.length; i++) {
            String key=OfferParser.KEYS[i];
            TextView fieldLabel=label(OfferParser.LABELS[i],13,muted,false);
            append(results, fieldLabel,16);
            EditText field=new EditText(this);
            field.setSingleLine(true);
            field.setTextSize(17);
            field.setTextColor(Color.WHITE);
            field.setHintTextColor(0xFF657486);
            field.setHint("Não identificado — toque para conferir");
            field.setPadding(px(12),px(12),px(12),px(12));
            field.setBackground(bg(0xFF0E1520,10));
            field.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
            if ("negotiations".equals(key)) field.setSingleLine(false);
            append(results,field,5);
            inputs.put(key,field);
        }

        openOriginal=button("Abrir print original para conferir",0xFF303D4E,Color.WHITE);
        append(results,openOriginal,18);
        openOriginal.setOnClickListener(v -> {
            if (chosenUri==null) return;
            try {
                Intent in=new Intent(Intent.ACTION_VIEW);
                in.setDataAndType(chosenUri,"image/*");
                in.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                startActivity(in);
            } catch (Exception err) {
                Toast.makeText(this,"Abra o print na galeria e confira os valores.",Toast.LENGTH_LONG).show();
            }
        });

        confirm=button("Confirmar e guardar correções",blue,Color.BLACK);
        append(results,confirm,12);
        confirm.setOnClickListener(v -> saveConfirmation());

        toggleRaw=button("Mostrar texto bruto do ML Kit",0xFF25313D,Color.WHITE);
        append(root,toggleRaw,16);
        toggleRaw.setOnClickListener(v -> {
            boolean visible = rawPanel.getVisibility()==View.VISIBLE;
            rawPanel.setVisibility(visible?View.GONE:View.VISIBLE);
            toggleRaw.setText(visible?"Mostrar texto bruto do ML Kit":"Ocultar texto bruto");
        });
        rawPanel=panel();
        append(root,rawPanel,10);
        rawPanel.setVisibility(View.GONE);
        rawPanel.addView(label("TEXTO RECONHECIDO",14,Color.WHITE,true));
        rawOutput=label("Escolha um print para ver o resultado.",14,0xFFD8E3EA,false);
        rawOutput.setTextIsSelectable(true);
        append(rawPanel,rawOutput,12);

        Button copy=button("Copiar texto bruto",0xFF303D4E,Color.WHITE);
        append(rawPanel,copy,12);
        copy.setOnClickListener(v -> {
            if (lastText.isEmpty()) return;
            ClipboardManager clipboard=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
            clipboard.setPrimaryClip(ClipData.newPlainText("Vexo OCR",lastText));
            Toast.makeText(this,"Texto copiado; confira antes de compartilhar.",Toast.LENGTH_SHORT).show();
        });

        append(root,label("PRIVACIDADE: os prints são processados localmente, com o modelo ML Kit incluído no aplicativo. Só os campos confirmados e as diferenças das correções ficam guardados neste aparelho; imagens e endereços não são salvos pelo laboratório. Nenhuma correção altera o modelo do Google.",12,0xFF91A4B5,false),18);
        setContentView(scroll);
    }

    private void chooseImage() {
        Intent in=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        in.setType("image/*");
        in.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(in,PICK_IMAGE);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if (resultCode!=RESULT_OK || data==null || data.getData()==null) return;
        if (requestCode==CREATE_BACKUP) {
            writeBackup(data.getData());
            return;
        }
        if (requestCode==OPEN_BACKUP) {
            loadBackup(data.getData());
            return;
        }
        if (requestCode!=PICK_IMAGE) return;
        chosenUri=data.getData();
        currentSaved=false;
        confirm.setEnabled(true);
        choose.setEnabled(false);
        status.setText("Lendo texto com Google ML Kit...");
        results.setVisibility(View.GONE);
        rawOutput.setText("Processando...");
        lastText="";
        try {
            InputImage input=InputImage.fromFilePath(this,chosenUri);
            com.google.mlkit.vision.text.TextRecognizer recognizer =
                TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            recognizer.process(input)
                .addOnSuccessListener(scan -> {
                    lastText=scan.getText();
                    rawOutput.setText(lastText.isEmpty()?"Nenhum texto encontrado.":lastText);
                    if (lastText.trim().isEmpty()) {
                        status.setText("Não encontrei texto neste print. Tente outra imagem.");
                        return;
                    }
                    baseline=OfferParser.parse(lastText);
                    for (String key: OfferParser.KEYS) {
                        EditText field=inputs.get(key);
                        if(field!=null) field.setText(baseline.get(key));
                    }
                    FinancialGuard.Assessment audit=FinancialGuard.assess(baseline);
                    safetyStatus.setText(audit.message);
                    safetyStatus.setTextColor(audit.canCalculate ? 0xFF9FE0C1 : 0xFFFFC27A);
                    results.setVisibility(View.VISIBLE);
                    status.setText("Leitura concluída: "+baseline.filled()+" de "+
                        OfferParser.KEYS.length+" campos preenchidos. Confira e corrija antes de salvar.");
                })
                .addOnFailureListener(err -> {
                    lastText=""; results.setVisibility(View.GONE);
                    rawOutput.setText("Falha ao reconhecer a imagem.");
                    status.setText("Falha do ML Kit: "+err.getClass().getSimpleName());
                })
                .addOnCompleteListener(task -> {
                    recognizer.close(); choose.setEnabled(true);
                });
        } catch(Exception e) {
            results.setVisibility(View.GONE);
            status.setText("Não consegui abrir esta imagem: "+e.getClass().getSimpleName());
            choose.setEnabled(true);
        }
    }

    private JSONArray readHistory() throws Exception {
        JSONArray rows = new JSONArray(prefs.getString("historico","[]"));
        BackupCodec.validate(rows);
        return rows;
    }

    private void chooseBackupLocation() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        intent.putExtra(Intent.EXTRA_TITLE, "vexo-ocr-0.3-backup.json");
        startActivityForResult(intent,CREATE_BACKUP);
    }

    private void chooseBackupFile() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(intent,OPEN_BACKUP);
    }

    private void writeBackup(Uri destination) {
        try {
            String backup = BackupCodec.exportArchive(readHistory());
            try (OutputStream output = getContentResolver().openOutputStream(destination, "wt")) {
                if (output==null) throw new java.io.IOException("Destino indisponível");
                output.write(backup.getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
            status.setText("Backup exportado! Confira o arquivo no local escolhido e guarde-o em segurança.");
            Toast.makeText(this,"Backup salvo no local escolhido.",Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            status.setText("Não consegui exportar o backup: "+e.getMessage());
        }
    }

    private void loadBackup(Uri source) {
        try {
            byte[] bytes;
            try (InputStream input = getContentResolver().openInputStream(source);
                 ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
                if (input==null) throw new java.io.IOException("Arquivo indisponível");
                byte[] temp = new byte[8192];
                int n;
                while ((n=input.read(temp))!=-1) {
                    if (buffer.size()+n > 3_000_000) throw new java.io.IOException("Arquivo muito grande");
                    buffer.write(temp,0,n);
                }
                bytes=buffer.toByteArray();
            }
            JSONArray incoming = BackupCodec.importArchive(new String(bytes,StandardCharsets.UTF_8));
            JSONArray local = readHistory();
            BackupCodec.MergeResult merged = BackupCodec.merge(local,incoming);
            String message = "O arquivo foi validado. Encontradas "+incoming.length()+
                " oferta(s). Novas: "+merged.added+
                ". Já existentes: "+merged.duplicate+
                ".\n\nNenhum registro atual será substituído. Deseja importar?";
            new android.app.AlertDialog.Builder(this)
                .setTitle("Conferir importação")
                .setMessage(message)
                .setNegativeButton("Cancelar",null)
                .setPositiveButton("Importar",(dialog,which) -> {
                    boolean ok=prefs.edit().putString("historico",merged.records.toString()).commit();
                    if (ok) {
                        updateMemory();
                        status.setText("Importação concluída: "+merged.added+" nova(s) oferta(s).");
                    } else {
                        status.setText("Falha ao salvar: dados anteriores preservados.");
                    }
                }).show();
        } catch(Exception e) {
            status.setText("Backup não importado: "+e.getMessage()+
                ". Nenhum registro foi modificado.");
        }
    }

    private void updateMemory() {
        try {
            JSONArray rows=readHistory();
            int edits=0;
            for(int i=0;i<rows.length();i++) {
                edits+=rows.getJSONObject(i).getJSONArray("corrections").length();
            }
            memory.setText("Memória local: "+rows.length()+" oferta(s) confirmada(s) • "+
                edits+" campo(s) corrigido(s)");
        } catch(Exception e) {
            memory.setText("Histórico local indisponível: preserve os dados e não reinstale.");
        }
    }

    private void saveConfirmation() {
        if(currentSaved) {
            status.setText("Esta leitura já foi salva. Escolha outro print para continuar.");
            return;
        }
        try {
            String price=inputs.get("offerPrice").getText().toString().trim();
            double priceValue=OfferParser.decimal(price);
            if(Double.isNaN(priceValue)||Double.isInfinite(priceValue)||priceValue<=0||priceValue>10000) {
                status.setText("Confirme o valor da oferta (R$) antes de salvar.");
                inputs.get("offerPrice").requestFocus();
                return;
            }
            JSONArray history=readHistory();
            if(history.length()>=BackupCodec.MAX_RECORDS) {
                status.setText("Limite local atingido. Exporte um backup antes de continuar.");
                return;
            }
            JSONObject corrected=new JSONObject();
            JSONArray changed=new JSONArray();
            for(String key:OfferParser.KEYS) {
                String current=inputs.get(key).getText().toString().trim();
                corrected.put(key,current);
                String original=baseline.get(key);
                if(!current.equals(original)) {
                    JSONObject diff=new JSONObject();
                    diff.put("field",key);
                    diff.put("before",original);
                    diff.put("after",current);
                    changed.put(diff);
                }
            }
            JSONObject entry=new JSONObject();
            entry.put("id",UUID.randomUUID().toString());
            entry.put("savedAt",System.currentTimeMillis());
            entry.put("fields",corrected);
            entry.put("corrections",changed);
            BackupCodec.validate(new JSONArray().put(entry));
            history.put(entry);
            boolean ok=prefs.edit().putString("historico",history.toString()).commit();
            if(!ok) throw new java.io.IOException("Falha de gravação");
            currentSaved=true;
            confirm.setEnabled(false);
            updateMemory();
            status.setText("Oferta confirmada e salva! "+changed.length()+
                " campo(s) corrigido(s). Faça backup para proteger o histórico.");
            Toast.makeText(this,"Conferência salva!",Toast.LENGTH_LONG).show();
        } catch(Exception e) {
            status.setText("Não foi possível salvar: "+e.getMessage());
        }
    }
}