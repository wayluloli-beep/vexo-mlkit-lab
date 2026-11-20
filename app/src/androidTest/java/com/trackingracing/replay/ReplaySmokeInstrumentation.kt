package com.trackingracing.replay

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.os.SystemClock
import android.widget.Button
import android.widget.TextView

/** Optional on-device smoke. Not in the target APK and not executed by S13. */
class ReplaySmokeInstrumentation : Instrumentation() {
    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        start()
    }

    override fun onStart() {
        var replay: Activity? = null
        try {
            val activity = startActivitySync(Intent(targetContext, ReplayActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            replay = activity
            runOnMainSync {
                check(activity.findViewById<Button>(R.id.replay_start).performClick())
            }
            val limit = SystemClock.uptimeMillis() + 25_000
            var finished = false
            var output = ""
            while (!finished && SystemClock.uptimeMillis() < limit) {
                runOnMainSync {
                    finished = activity.findViewById<Button>(R.id.replay_start).isEnabled
                    if (finished) output = activity.findViewById<TextView>(R.id.replay_output).text.toString()
                }
                if (!finished) SystemClock.sleep(80)
            }
            check(finished) { "Timed out waiting for bundled OCR" }
            check(output == "Valor  R\$ 36,70\nBusca  6 min · 1,5 km\nViagem  33 min · 22,5 km\nNota  4,98\nCorridas  243") {
                "Typed OCR output does not match the manually annotated S05 Pop metrics"
            }
            finish(Activity.RESULT_OK, Bundle().apply { putString("result", "S13 replay matched S05 metrics") })
        } catch (_: Exception) {
            finish(Activity.RESULT_CANCELED, Bundle().apply { putString("result", "S13 replay did not validate") })
        } finally {
            replay?.let { activity -> runOnMainSync { activity.finish() } }
        }
    }
}
