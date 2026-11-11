package com.vexo.mlkitlab;

import org.json.JSONObject;

/**
 * Null explicitamente rotulado no gabarito significa campo não presente.
 * Não pontuar ausência como erro; se o OCR inventar valor, contar falso positivo.
 */
public final class ReportFieldPolicy {
    private ReportFieldPolicy() {}
    public static Object expectedOrAbsent(Object value) {
        return value==JSONObject.NULL ? null : value;
    }
}
