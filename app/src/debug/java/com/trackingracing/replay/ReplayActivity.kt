package com.trackingracing.replay

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.os.Build
import android.os.Bundle
import android.view.WindowInsets
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import com.trackingracing.AuroraOferta

/** Explicitly opened by the private diagnostic harness. No intent extras or external input. */
class ReplayActivity : Activity() {
    private val gate = ReplayGate()
    private lateinit var startButton: Button
    private lateinit var output: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        startButton = Button(this).apply {
            id = R.id.replay_start
            text = "Ler JPEG demo"
            isEnabled = false
            setOnClickListener { replay() }
        }
        output = TextView(this).apply {
            id = R.id.replay_output
            textSize = 18f
            isSaveEnabled = false
            accessibilityLiveRegion = TextView.ACCESSIBILITY_LIVE_REGION_POLITE
        }
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(24), dp(20), dp(24))
            addView(TextView(this@ReplayActivity).apply {
                text = "Aurora · Replay diagnóstico"
                textSize = 24f
            })
            addView(TextView(this@ReplayActivity).apply {
                text = "JPEG de demonstração editado para remover mapa e endereços."
                textSize = 15f
            })
            addView(startButton)
            addView(output)
        }
        setContentView(ScrollView(this).apply {
            isSaveFromParentEnabled = false
            fitsSystemWindows = true
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                setOnApplyWindowInsetsListener { view, insets ->
                    val safe = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                    view.setPadding(safe.left, safe.top, safe.right, safe.bottom)
                    insets
                }
            }
            addView(body)
        })
    }

    override fun onStart() {
        super.onStart()
        gate.show()
        refreshWaiting()
    }

    override fun onStop() {
        gate.hide()
        output.text = ""
        startButton.isEnabled = false
        super.onStop()
    }

    private fun replay() {
        val turn = gate.begin() ?: return
        startButton.isEnabled = false
        output.text = "Reconhecendo a imagem…"

        var bitmap: Bitmap? = null
        var client: TextRecognizer? = null
        try {
            val image = assets.open("demo-pop-sanitized.jpg").use { BitmapFactory.decodeStream(it) }
                ?: error("invalid fixture")
            bitmap = image
            val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            client = recognizer
            // The default Tasks completion listener runs on the main thread even if this screen
            // stopped. Never use an Activity-scoped listener: it could skip resource release.
            recognizer.process(InputImage.fromBitmap(image, 0)).addOnCompleteListener { task ->
                val message = try {
                    if (task.isSuccessful) {
                        val recognized = task.result
                        if (recognized.text.isBlank()) {
                            "O OCR não reconheceu texto no JPEG."
                        } else {
                            ReplayPresentation.offer(AuroraOferta.from(recognized))
                                ?: "O parser não confirmou uma oferta completa."
                        }
                    } else {
                        "A leitura do JPEG falhou."
                    }
                } catch (_: Exception) {
                    "A leitura do JPEG falhou."
                } finally {
                    close(recognizer, image)
                }
                complete(turn, message)
            }
        } catch (_: Exception) {
            close(client, bitmap)
            complete(turn, "A leitura do JPEG falhou.")
        }
    }

    private fun complete(turn: ReplayGate.Turn, message: String) {
        val accepted = gate.finish(turn)
        if (isFinishing || isDestroyed) return
        if (accepted) {
            startButton.isEnabled = gate.canBegin
            output.text = message
        } else if (gate.canBegin) {
            refreshWaiting()
        }
    }

    private fun refreshWaiting() {
        startButton.isEnabled = gate.canBegin
        output.text = if (gate.canBegin) "Pronto para ler o JPEG." else "Aguardando a leitura anterior terminar…"
    }

    private fun close(recognizer: TextRecognizer?, bitmap: Bitmap?) {
        try {
            recognizer?.close()
        } catch (_: Exception) {
            // No raw OCR or SDK exception reaches the presentation or application logs.
        } finally {
            bitmap?.recycle()
        }
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density + 0.5f).toInt()
}
