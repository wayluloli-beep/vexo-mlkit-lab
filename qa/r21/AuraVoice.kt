package com.trackingracing

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.util.Log

/** Plays on-device neural recordings bundled with Vexo. No system TTS or network. */
class AuraVoice(private val context: Context) {
    private var player: MediaPlayer? = null
    private var closed = false
    private var lastKey = ""
    private var lastAt = 0L

    fun enabled(): Boolean = context.getSharedPreferences("aura.voice.v1", Context.MODE_PRIVATE)
        .getBoolean("enabled", false)

    fun setEnabled(value: Boolean): Boolean {
        val saved = context.getSharedPreferences("aura.voice.v1", Context.MODE_PRIVATE)
            .edit().putBoolean("enabled", value).commit()
        if (!value) stop()
        return saved
    }

    fun preview(): Boolean = play("hello", bypassOptIn = true)

    fun cue(key: String): Boolean {
        val fixed = setOf("hello", "fuel", "meta_salva", "aura_ativa")
        if (!enabled() || key !in fixed) return false
        return play(key)
    }

    @Synchronized private fun play(key: String, bypassOptIn: Boolean = false): Boolean {
        if (closed || (!bypassOptIn && !enabled())) return false
        val now = android.os.SystemClock.elapsedRealtime()
        if (lastKey == key && now - lastAt < 8000) return false
        lastKey = key
        lastAt = now
        stop()
        return try {
            val next = MediaPlayer()
            context.assets.openFd("aurora/voice/$key.ogg").use {
                next.setDataSource(it.fileDescriptor, it.startOffset, it.length)
            }
            next.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            next.setOnPreparedListener { prepared ->
                if (!closed) prepared.start()
            }
            next.setOnCompletionListener { finished ->
                if (player === finished) player = null
                finished.release()
            }
            next.setOnErrorListener { broken, _, _ ->
                if (player === broken) player = null
                broken.release()
                true
            }
            player = next
            next.prepareAsync()
            true
        } catch (e: Exception) {
            Log.w("AuraVoice", "Bundled voice failed: "+e.javaClass.simpleName)
            stop()
            false
        }
    }

    @Synchronized fun stop() {
        val previous = player
        player = null
        if (previous != null) {
            runCatching { previous.reset() }
            runCatching { previous.release() }
        }
    }

    fun close() {
        closed = true
        stop()
    }
}
