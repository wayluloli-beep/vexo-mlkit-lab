package com.vexo.mlkitlab;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;

/**
 * Backup transport for lab data only.
 * A SHA-256 digest detects accidental file corruption, not authenticity or tampering by an attacker.
 */
public final class BackupCodec {
    public static final int SCHEMA_VERSION = 1;
    public static final int MAX_RECORDS = 2000;
    private static final String APP_ID = "vexo-ocr-lab";

    private BackupCodec() {}

    public static String exportArchive(JSONArray records) throws Exception {
        validate(records);
        String payload = records.toString();
        JSONObject archive = new JSONObject();
        archive.put("app", APP_ID);
        archive.put("schemaVersion", SCHEMA_VERSION);
        archive.put("createdAt", System.currentTimeMillis());
        archive.put("payload", payload);
        archive.put("sha256", sha256(payload));
        return archive.toString(2);
    }

    public static JSONArray importArchive(String data) throws Exception {
        JSONObject archive = new JSONObject(data);
        if (!APP_ID.equals(archive.optString("app"))) {
            throw new JSONException("Este arquivo não é um backup Vexo OCR válido.");
        }
        if (archive.optInt("schemaVersion", -1) != SCHEMA_VERSION) {
            throw new JSONException("Versão de backup não compatível.");
        }
        String payload = archive.getString("payload");
        String digest = archive.getString("sha256");
        if (!sha256(payload).equalsIgnoreCase(digest)) {
            throw new JSONException("O conteúdo do backup foi alterado ou corrompido.");
        }
        JSONArray items = new JSONArray(payload);
        validate(items);
        return items;
    }

    public static void validate(JSONArray records) throws JSONException {
        if (records.length() > MAX_RECORDS) {
            throw new JSONException("Backup excede o limite seguro de registros.");
        }
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < records.length(); i++) {
            JSONObject rec = records.getJSONObject(i);
            String id = rec.getString("id");
            if (!id.matches("[0-9a-fA-F-]{36}") || !ids.add(id)) {
                throw new JSONException("Identificador inválido ou duplicado.");
            }
            long savedAt = rec.getLong("savedAt");
            if (savedAt <= 0L) throw new JSONException("Data inválida.");
            JSONObject fields = rec.getJSONObject("fields");
            for (String key : OfferParser.KEYS) {
                String val = fields.getString(key);
                if (val.length() > 200) throw new JSONException("Campo extenso demais: " + key);
            }
            double price = OfferParser.decimal(fields.getString("offerPrice"));
            if (Double.isNaN(price) || Double.isInfinite(price) || price <= 0.0 || price > 10000.0)
                throw new JSONException("Oferta contém valor inválido.");
            JSONArray corrections = rec.getJSONArray("corrections");
            if (corrections.length() > OfferParser.KEYS.length)
                throw new JSONException("Quantidade inválida de correções.");
            for (int j = 0; j < corrections.length(); j++) {
                JSONObject correction = corrections.getJSONObject(j);
                String key = correction.getString("field");
                boolean validKey = false;
                for (String allowed : OfferParser.KEYS) if (allowed.equals(key)) validKey = true;
                if (!validKey || correction.getString("before").length() > 200 ||
                        correction.getString("after").length() > 200) {
                    throw new JSONException("Correção inválida.");
                }
            }
        }
    }

    public static final class MergeResult {
        public final JSONArray records;
        public final int added;
        public final int duplicate;
        MergeResult(JSONArray records, int added, int duplicate) {
            this.records = records;
            this.added = added;
            this.duplicate = duplicate;
        }
    }

    /** Merge never overrides an existing entry; IDs already stored always win. */
    public static MergeResult merge(JSONArray local, JSONArray imported) throws JSONException {
        validate(local);
        validate(imported);
        JSONArray out = new JSONArray();
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < local.length(); i++) {
            JSONObject row = local.getJSONObject(i);
            out.put(row);
            ids.add(row.getString("id"));
        }
        int added = 0;
        int duplicate = 0;
        for (int i = 0; i < imported.length(); i++) {
            JSONObject row = imported.getJSONObject(i);
            if (ids.contains(row.getString("id"))) {
                duplicate++;
            } else {
                if (out.length() >= MAX_RECORDS) throw new JSONException("Limite de registros atingido. Exporte o histórico antes de continuar.");
                out.put(row);
                ids.add(row.getString("id"));
                added++;
            }
        }
        return new MergeResult(out, added, duplicate);
    }

    private static String sha256(String input) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256")
            .digest(input.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder(digest.length * 2);
        for (byte b : digest) hex.append(String.format("%02x", b & 0xff));
        return hex.toString();
    }
}
