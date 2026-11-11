package com.vexo.mlkitlab;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class BackupCodecTest {
    private JSONObject record(String id, String price) throws Exception {
        JSONObject fields = new JSONObject();
        for (String key : OfferParser.KEYS) fields.put(key, "");
        fields.put("platform", "99");
        fields.put("offerPrice", price);
        fields.put("pickupMin", "5");
        JSONObject correction = new JSONObject();
        correction.put("field", "tripMin");
        correction.put("before", "");
        correction.put("after", "0");
        return new JSONObject()
            .put("id", id)
            .put("savedAt", 1794382000000L)
            .put("fields", fields)
            .put("corrections", new JSONArray().put(correction));
    }

    @Test public void roundTripPreservesFields() throws Exception {
        JSONArray records = new JSONArray().put(record("00000000-0000-4000-8000-000000000001", "7,70"));
        JSONArray restored = BackupCodec.importArchive(BackupCodec.exportArchive(records));
        assertEquals(1, restored.length());
        assertEquals("7,70",restored.getJSONObject(0).getJSONObject("fields").getString("offerPrice"));
        assertEquals("tripMin", restored.getJSONObject(0).getJSONArray("corrections").getJSONObject(0).getString("field"));
    }

    @Test public void modifiedPayloadIsRejected() throws Exception {
        JSONArray records = new JSONArray().put(record("00000000-0000-4000-8000-000000000001", "7,70"));
        JSONObject archive = new JSONObject(BackupCodec.exportArchive(records));
        archive.put("payload", archive.getString("payload").replace("7,70", "77,70"));
        try {
            BackupCodec.importArchive(archive.toString());
            fail("Corrupted payload should not be accepted");
        } catch (org.json.JSONException expected) { }
    }

    @Test public void duplicateImportsDoNotOverrideLocal() throws Exception {
        String id = "00000000-0000-4000-8000-000000000001";
        JSONArray local = new JSONArray().put(record(id, "7,70"));
        JSONArray imported = new JSONArray().put(record(id, "77,00"))
            .put(record("00000000-0000-4000-8000-000000000002", "43,09"));
        BackupCodec.MergeResult merged = BackupCodec.merge(local, imported);
        assertEquals(1, merged.added);
        assertEquals(1, merged.duplicate);
        assertEquals(2, merged.records.length());
        assertEquals("7,70",merged.records.getJSONObject(0).getJSONObject("fields").getString("offerPrice"));
    }

    @Test public void badOfferIsRejectedBeforeImport() throws Exception {
        JSONArray records = new JSONArray().put(record("00000000-0000-4000-8000-000000000001", "0"));
        try {
            BackupCodec.exportArchive(records);
            fail("Invalid price should be rejected");
        } catch (org.json.JSONException expected) { }
    }

    @Test public void unsupportedSchemaIsRejected() throws Exception {
        JSONArray records = new JSONArray().put(record("00000000-0000-4000-8000-000000000001", "7,70"));
        JSONObject archive = new JSONObject(BackupCodec.exportArchive(records));
        archive.put("schemaVersion", 999);
        try {
            BackupCodec.importArchive(archive.toString());
            fail("Unknown schema should be rejected");
        } catch (org.json.JSONException expected) { }
    }

    @Test public void brokenRecordIsRejectedNonDestructively() throws Exception {
        JSONObject broken = record("00000000-0000-4000-8000-000000000001", "43,09");
        broken.getJSONObject("fields").remove("tripKm");
        try {
            BackupCodec.validate(new JSONArray().put(broken));
            fail("Missing field should be rejected");
        } catch (org.json.JSONException expected) { }
    }
}
