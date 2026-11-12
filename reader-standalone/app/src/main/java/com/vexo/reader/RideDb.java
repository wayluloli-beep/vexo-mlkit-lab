package com.vexo.reader;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import java.util.ArrayList;
import java.util.List;

/** Device-local store; there is no network permission or telemetry upload. */
public final class RideDb extends SQLiteOpenHelper {
    public RideDb(Context context) { super(context, "vexo_reader_local.db", null, 1); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE observed_offers (" +
            "id INTEGER PRIMARY KEY AUTOINCREMENT, seen_at INTEGER NOT NULL, " +
            "price_cents INTEGER NOT NULL, origin_min INTEGER NOT NULL, " +
            "origin_km10 INTEGER NOT NULL, destination_min INTEGER NOT NULL, " +
            "destination_km10 INTEGER NOT NULL, origin TEXT NOT NULL, " +
            "destination TEXT NOT NULL, rating TEXT NOT NULL)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) { }

    public synchronized void insert(OfferRecord r) {
        if (!r.hasMinimumFields()) return;
        ContentValues v = new ContentValues();
        v.put("seen_at", r.seenAt);
        v.put("price_cents", r.priceCents);
        v.put("origin_min", r.originMin);
        v.put("origin_km10", r.originTenthsKm);
        v.put("destination_min", r.destinationMin);
        v.put("destination_km10", r.destinationTenthsKm);
        v.put("origin", r.origin);
        v.put("destination", r.destination);
        v.put("rating", r.rating);
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            db.insertOrThrow("observed_offers", null, v);
            // Avoid an unbounded amount of private, screen-derived data.
            db.execSQL("DELETE FROM observed_offers WHERE id NOT IN " +
                "(SELECT id FROM observed_offers ORDER BY id DESC LIMIT 200)");
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }

    public synchronized List<OfferRecord> recent(int limit) {
        List<OfferRecord> list = new ArrayList<>();
        try (Cursor c = getReadableDatabase().query("observed_offers", null, null, null, null,
                null, "id DESC", String.valueOf(Math.max(1, Math.min(limit, 200))))) {
            while (c.moveToNext()) {
                OfferRecord r = new OfferRecord(
                    c.getInt(c.getColumnIndexOrThrow("price_cents")),
                    c.getInt(c.getColumnIndexOrThrow("origin_min")),
                    c.getInt(c.getColumnIndexOrThrow("origin_km10")),
                    c.getInt(c.getColumnIndexOrThrow("destination_min")),
                    c.getInt(c.getColumnIndexOrThrow("destination_km10")),
                    c.getString(c.getColumnIndexOrThrow("origin")),
                    c.getString(c.getColumnIndexOrThrow("destination")),
                    c.getString(c.getColumnIndexOrThrow("rating")),
                    c.getLong(c.getColumnIndexOrThrow("seen_at")));
                r.databaseId = c.getLong(c.getColumnIndexOrThrow("id"));
                list.add(r);
            }
        }
        return list;
    }

    public synchronized void erase() {
        getWritableDatabase().delete("observed_offers", null, null);
    }
}
