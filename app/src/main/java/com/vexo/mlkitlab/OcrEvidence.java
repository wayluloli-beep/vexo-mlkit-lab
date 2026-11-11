package com.vexo.mlkitlab;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.LinkedHashSet;
import java.math.BigDecimal;

/**
 * Diagnóstico do lote: nunca exporta a transcrição original, ruas ou endereços.
 * Salva apenas possíveis valores numéricos próximos a unidades conhecidas e
 * sinaliza se o valor do gabarito parece presente no texto OCR.
 *
 * Observação: presença do número por si só NÃO prova sua posição nem significado.
 */
public final class OcrEvidence {
    private OcrEvidence() {}

    private static final Pattern CANDIDATE=Pattern.compile(
        "(?<!\\d)(?:R\\s*\\$\\s*)?(\\d{1,4}(?:[.,]\\d{1,3})?)\\s*(/\\s*km|/\\s*hora|km|m|x|×)\\b",
        Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE
    );

    public static JSONObject diagnostic(String raw, JSONObject comparedFields) {
        JSONObject result=new JSONObject();
        if (raw == null) raw="";
        try {
            JSONArray unitValues=numericUnitCandidates(raw);
            for (String field:new String[]{"tripKm","pickupKm","perKm","surge","offerPrice"}) {
                JSONObject item=comparedFields.optJSONObject(field);
                if (item==null || "ok".equals(item.optString("status"))) continue;
                Object expected=item.opt("expected");
                if (expected==null || expected==JSONObject.NULL) continue;
                JSONObject detail=new JSONObject();
                boolean seen=containsNumeric(raw,expected.toString());
                detail.put("expectedNumberSeenInRawOCR",seen);
                detail.put("numericWithUnitCandidates",unitValues);
                detail.put("interpretation",seen ?
                    "Número aparente presente; investigar parser/posição e símbolos" :
                    "Número esperado não encontrado literalmente; investigar OCR");
                detail.put("confidence","indicativo; não é prova da origem do erro");
                result.put(field,detail);
            }
        } catch(Exception ignored) {
            // Diagnóstico não pode derrubar um lote de OCR real.
        }
        return result;
    }

    public static JSONArray numericUnitCandidates(String raw) {
        LinkedHashSet<String> set=new LinkedHashSet<>();
        Matcher m=CANDIDATE.matcher(raw == null ? "" : raw);
        while (m.find() && set.size()<32) {
            String clean=m.group(1).replace(".",",");
            String unit=m.group(2).replaceAll("\\s+","").toLowerCase(java.util.Locale.ROOT);
            set.add(clean+unit);
        }
        JSONArray arr=new JSONArray();
        for (String val:set) arr.put(val);
        return arr;
    }

    public static boolean containsNumeric(String raw, String expected) {
        if (raw == null || expected == null) return false;
        try {
            String canonical=new BigDecimal(expected.replace(",","."))
                .stripTrailingZeros().toPlainString();
            String[] parts=canonical.split("\\.");
            String body=Pattern.quote(parts[0]);
            if (parts.length>1) body+="[.,]"+Pattern.quote(parts[1]);
            return Pattern.compile("(?<!\\d)"+body+"(?!\\d)").matcher(raw).find();
        } catch(Exception e) { return false; }
    }
}
