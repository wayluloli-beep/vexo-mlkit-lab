package com.vexo.mlkitlab;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * Tela exclusivamente sintética para conferir MediaProjection sem abrir 99.
 * Os dados e o botão "Aceitar" são ficção visual e NÃO acionam corridas.
 */
public final class DemoOfferActivity extends Activity {
    private int dp(int n) {
        return (int)(n*getResources().getDisplayMetrics().density+0.5f);
    }

    private TextView line(String message,int size,boolean bold,int color) {
        TextView view=new TextView(this);
        view.setText(message);
        view.setTextSize(size);
        view.setTextColor(color);
        if(bold) view.setTypeface(null,Typeface.BOLD);
        view.setPadding(dp(5),dp(7),dp(5),dp(7));
        return view;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(0xff0a0e16);
        LinearLayout root=new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22),dp(28),dp(22),dp(24));
        scroll.addView(root);

        root.addView(line("VEXO • TESTE DE CAPTURA",20,true,0xff45d4e2));
        root.addView(line("DADOS FICTÍCIOS — isto NÃO é uma corrida real",13,true,0xffffcc8e));
        root.addView(line("Deixe esta tela visível por alguns segundos com a captura ativa. Depois volte ao Vexo para conferir o resultado.",14,false,0xffa1b7ca));

        LinearLayout card=new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(17),dp(16),dp(17),dp(16));
        GradientDrawable bg=new GradientDrawable();
        bg.setColor(Color.WHITE);
        bg.setCornerRadius(dp(18));
        LinearLayout.LayoutParams cardLp=new LinearLayout.LayoutParams(-1,-2);
        cardLp.topMargin=dp(24);
        card.setBackground(bg);
        root.addView(card,cardLp);

        card.addView(line("99 Moto",27,true,0xff252a30));
        card.addView(line("R$40,70",38,true,0xff161b1e));
        card.addView(line("2,8x",25,true,0xff161b1e));
        card.addView(line("4,98 971 corridas",20,false,0xff343b40));
        card.addView(line("9 min (3 km)",24,true,0xff212529));
        card.addView(line("24 min (11,8 km)",24,true,0xff212529));
        TextView fake= line("Aceitar",23,true,Color.WHITE);
        fake.setGravity(Gravity.CENTER);
        fake.setBackgroundColor(0xffe4a900);
        card.addView(fake);
        root.addView(line("O botão 'Aceitar' acima é APENAS um texto ilustrativo. O Vexo nunca aceita ou recusa corridas.",13,false,0xffa1b7ca));

        Button back=new Button(this);
        back.setAllCaps(false);
        back.setText("Voltar para o Vexo e conferir resultado");
        root.addView(back);
        back.setOnClickListener(v -> {
            android.content.Intent i=new android.content.Intent(this,LiveCaptureActivity.class);
            i.addFlags(android.content.Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
            startActivity(i);
        });
        setContentView(scroll);
    }
}
