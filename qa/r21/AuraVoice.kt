package com.trackingracing

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.util.Log
import com.google.mediapipe.tasks.audio.texttospeech.TextToSpeech
import com.google.mediapipe.tasks.audio.texttospeech.TextToSpeechOptions
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger
import org.json.JSONObject

/**
 * Optional on-device neural voice: independent of Android's system TextToSpeech.
 * Loading and synthesis are confined to an executor, never the UI or OCR thread.
 * The model is shipped with the APK; this component performs no network requests.
 */
class AuraVoice(private val context: Context) {
    private val worker = Executors.newSingleThreadExecutor { task ->
        Thread(task, "Aura-Neural-Voice").apply { isDaemon = true }
    }
    private val epoch = AtomicInteger()
    private val lock = Any()
    private var synth: TextToSpeech? = null
    private var currentTrack: AudioTrack? = null
    @Volatile private var shutDown = false
    private var lastText = ""
    private var lastAt = 0L

    fun enabled(): Boolean = context.getSharedPreferences("aura.voice.v1", Context.MODE_PRIVATE)
        .getBoolean("enabled", false)

    fun setEnabled(value: Boolean): Boolean {
        val committed = context.getSharedPreferences("aura.voice.v1", Context.MODE_PRIVATE)
            .edit().putBoolean("enabled", value).commit()
        if (!value) stop()
        return committed
    }

    fun preview(): Boolean = enqueue("E aí, motora. Eu sou a Aura, sua copiloto. Me diz quanto você quer botar no bolso hoje que eu filtro as corridas pra você.", true)

    fun cue(id: String): Boolean {
        if (!enabled() || !id.matches(Regex("[a-z0-9_]{2,36}"))) return false
        val text = try {
            context.assets.open("aurora/aura-phrases.json").bufferedReader().use { br ->
                JSONObject(br.readText()).optString(id, "")
            }
        } catch (_: Exception) { "" }
        if (text.isBlank()) return false
        // Dynamic numeric alerts must be generated only from verified real readings.
        if (id !in setOf("hello","fuel","meta_salva","consentimento","aura_ativa")) return false
        return enqueue(text, false)
    }

    private fun enqueue(text: String, bypassOptIn: Boolean): Boolean {
        if (shutDown || (!bypassOptIn && !enabled()) || text.length !in 2..280) return false
        val now = android.os.SystemClock.elapsedRealtime()
        synchronized(lock) {
            if (text == lastText && now - lastAt < 12000) return false
            lastText = text
            lastAt = now
        }
        val thisEpoch = epoch.incrementAndGet()
        worker.execute {
            try {
                if (thisEpoch != epoch.get() || shutDown) return@execute
                val tts = synth ?: createEngine().also { synth = it }
                if (thisEpoch != epoch.get() || shutDown) return@execute
                val result = tts.synthesize(text)
                if (thisEpoch != epoch.get() || shutDown) return@execute
                play(result.samples, result.sampleRateHz, thisEpoch)
            } catch (t: Exception) {
                Log.e("AuraVoice", "Voz neural indisponível: " + t.javaClass.simpleName)
            }
        }
        return true
    }

    private fun createEngine(): TextToSpeech {
        val model = modelFile()
        val options = TextToSpeechOptions(
            baseOptions = BaseOptions.builder()
                .setModelAssetPath(model.absolutePath)
                .setDelegate(Delegate.GPU)
                .build(),
            defaultVoiceId = "pf_dora",
            cacheDir = context.cacheDir.absolutePath,
        )
        return TextToSpeech.create(options)
    }

    private fun modelFile(): File {
        val name = "kokoro_int8_gpu_fp16.litertlm"
        val expectedSha256 = "1ef178b127ec48c737daf17eabb4cea5f6b3ffbc510aced270fe5c267bbeac52"
        val target = File(context.noBackupFilesDir, name)
        if (target.isFile && target.length() == 294750530L &&
            digest(target) == expectedSha256) return target
        val temp = File(context.noBackupFilesDir, "$name.pending")
        try {
            context.assets.open("aurora/$name").use { input ->
                temp.outputStream().buffered().use { output -> input.copyTo(output) }
            }
            if (temp.length() != 294750530L || digest(temp) != expectedSha256)
                error("Aura model verification failed")
            if (target.exists() && !target.delete()) error("Old voice could not be removed")
            if (!temp.renameTo(target)) error("Voice model could not be saved")
        } finally {
            if (temp.exists()) temp.delete()
        }
        return target
    }

    private fun digest(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { stream ->
            val block = ByteArray(128 * 1024)
            while (true) {
                val count = stream.read(block)
                if (count < 0) break
                md.update(block, 0, count)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun play(samples: FloatArray, rate: Int, token: Int) {
        if (rate !in 8000..48000 || samples.isEmpty()) return
        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
            .setSampleRate(rate)
            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
            .build()
        val buffer = maxOf(AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_FLOAT), rate * 2)
        if (buffer <= 0) return
        val track = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(format)
            .setBufferSizeInBytes(buffer)
            .setTransferMode(AudioTrack.MODE_STREAM).build()
        synchronized(lock) { currentTrack = track }
        try {
            if (token != epoch.get() || shutDown) return
            track.play()
            var offset = 0
            while (offset < samples.size && token == epoch.get() && !shutDown) {
                val written = track.write(samples, offset, minOf(samples.size - offset, 16000), AudioTrack.WRITE_BLOCKING)
                if (written <= 0) break
                offset += written
            }
            if (token == epoch.get() && !shutDown) {
                // AudioTrack.stop() drains buffered playback on supported Android versions.
                track.stop()
            }
        } finally {
            synchronized(lock) { if (currentTrack === track) currentTrack = null }
            runCatching { track.release() }
        }
    }

    fun stop() {
        epoch.incrementAndGet()
        synchronized(lock) { currentTrack?.let { runCatching { it.pause(); it.flush() } } }
    }

    fun close() {
        shutDown = true
        stop()
        worker.execute { runCatching { synth?.close() }; synth = null }
        worker.shutdown()
    }
}
