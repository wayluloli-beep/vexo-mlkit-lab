package com.trackingracing.replay

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.widget.Button
import android.widget.TextView
import java.util.concurrent.TimeoutException

/** Diagnostic JPEG replay only. Raw OCR and UI text never cross the result boundary. */
class ReplaySmokeInstrumentation : Instrumentation() {
    private var argument: String? = null
    private val main by lazy { Handler(Looper.getMainLooper()) }

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        argument = arguments?.getString("replay_wait_ms")
        start()
    }

    override fun onStart() {
        val limit = ReplayReport.parseWait(argument)
        if (limit == null) {
            respond(ReplayReport.failure("INVALID_WAIT"), null, null, null)
            return
        }
        var replay: Activity? = null
        var clockAtClick: Long? = null
        var elapsed: Long? = null
        var launch: Long? = null
        var phase = "launch"
        var diagnostic: ReplayReport

        try {
            val launchStart = SystemClock.elapsedRealtime()
            val screen = awaitDispatched(30_000, { task ->
                Thread(task, "ReplayActivityLaunch").apply { isDaemon = true }.start()
                true
            }) {
                startActivitySync(Intent(targetContext, ReplayActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            replay = screen
            launch = SystemClock.elapsedRealtime() - launchStart
            phase = "ui"
            val clickClock = onUi(10_000) {
                val button = screen.findViewById<Button>(R.id.replay_start)
                check(button.isEnabled)
                val now = SystemClock.elapsedRealtime()
                check(button.performClick())
                now
            }
            clockAtClick = clickClock
            // The legacy wait budget started after the click and used Android uptime.
            val waitStart = SystemClock.uptimeMillis()
            var output: String? = null
            while (output == null) {
                val remaining = limit - (SystemClock.uptimeMillis() - waitStart)
                if (remaining <= 0) break
                val observation = onUi(remaining.coerceIn(500L, 5_000L)) {
                    if (SystemClock.uptimeMillis() - waitStart < limit &&
                        screen.findViewById<Button>(R.id.replay_start).isEnabled) {
                        screen.findViewById<TextView>(R.id.replay_output).text.toString() to
                            (SystemClock.elapsedRealtime() - clickClock)
                    } else null
                }
                if (observation != null) {
                    output = observation.first
                    elapsed = observation.second
                } else {
                    val idle = limit - (SystemClock.uptimeMillis() - waitStart)
                    if (idle > 0) SystemClock.sleep(minOf(idle, 80))
                }
            }
            if (output == null) elapsed = SystemClock.elapsedRealtime() - clickClock
            diagnostic = output?.let(ReplayReport::classify) ?: ReplayReport.failure("TIMEOUT")
        } catch (_: TimeoutException) {
            diagnostic = ReplayReport.failure(if (phase == "launch") "ACTIVITY_LAUNCH_TIMEOUT" else "UI_TIMEOUT")
            clockAtClick?.let { elapsed = SystemClock.elapsedRealtime() - it }
        } catch (_: Exception) {
            diagnostic = ReplayReport.failure(if (clockAtClick == null) "SETUP_ERROR" else "RUNNER_ERROR")
            clockAtClick?.let { elapsed = SystemClock.elapsedRealtime() - it }
        }

        replay?.let { screen -> runCatching { onUi(500) { screen.finish() } } }
        respond(diagnostic, limit, launch, elapsed)
    }

    private fun <T> onUi(timeoutMs: Long, call: () -> T): T =
        awaitDispatched(timeoutMs, { main.post(it) }, call)

    private fun respond(report: ReplayReport, limit: Long?, launch: Long?, elapsed: Long?) {
        val bundle = Bundle().apply {
            putString("result", if (report.status == "PASS") "S13 replay matched S05 metrics" else "S13 replay did not validate")
            putString("diagnostic", report.status)
            putString("scoped_as", "JPEG_MLKIT_UI_ONLY")
            putString("matched_fields", report.matched.joinToString(","))
            putString("mismatched_fields", report.mismatched.joinToString(","))
            putString("missing_fields", report.missing.joinToString(","))
            putBoolean("shape_ok", report.shapeOk)
            limit?.let { putLong("wait_limit_ms", it) }
            launch?.let { putLong("activity_launch_wall_ms", it) }
            elapsed?.let { putLong("click_to_ui_observation_ms", it) }
        }
        finish(if (report.status == "PASS") Activity.RESULT_OK else Activity.RESULT_CANCELED, bundle)
    }
}
