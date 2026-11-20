package com.trackingracing

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.appcheck.FirebaseAppCheck
import com.google.firebase.appcheck.playintegrity.PlayIntegrityAppCheckProviderFactory
import org.json.JSONObject
import java.io.File
import java.io.ByteArrayOutputStream
import java.net.URL
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger
import javax.net.ssl.HttpsURLConnection

/**
 * Optional Google Cloud neural speech for Aura. No Cloud secret in the Android app.
 * Requests use Firebase App Check; only typed cue/metrics events go to the proxy.
 * Falls back to bundled offline speech on failure. OCR and the driver UI never block.
 */
class AuraGoogleVoice(
    private val context: Context,
    private val offline: AuraVoice
) {
    private val ui=Handler(Looper.getMainLooper())
    private val worker=Executors.newSingleThreadExecutor { task ->
        Thread(task,"Aura-Google-Voice").apply { isDaemon=true }
    }
    private val sequence=AtomicInteger()
    @Volatile private var destroyed=false
    private var player: MediaPlayer?=null
    private var temp: File?=null

    data class Config(
        val endpoint:String,
        val firebaseApiKey:String,
        val firebaseAppId:String,
        val firebaseProjectId:String,
        val firebaseSenderId:String
    )

    private val config:Config? by lazy {
        runCatching {
            val json=JSONObject(context.assets.open("aurora/aura-google-config.json")
                .bufferedReader().use { it.readText() })
            val endpoint=json.optString("endpoint","")
            val apiKey=json.optString("firebaseApiKey","")
            val appId=json.optString("firebaseAppId","")
            val projectId=json.optString("firebaseProjectId","")
            val senderId=json.optString("firebaseSenderId","")
            val parsed=URL(endpoint)
            if (parsed.protocol!="https" ||
                !parsed.host.endsWith(".run.app",ignoreCase=true) ||
                parsed.userInfo!=null || parsed.port !in listOf(-1,443) ||
                parsed.path!="/v1/aura/voice" || parsed.query!=null || parsed.ref!=null ||
                listOf(apiKey,appId,projectId,senderId).any { it.isBlank() })
                null
            else Config(endpoint,apiKey,appId,projectId,senderId)
        }.getOrNull()
    }

    fun isConfigured():Boolean=config!=null && !destroyed

    /** One fixed preview line. Dynamic event calls must originate in validated native data. */
    fun preview():Boolean=dispatch(JSONObject().put("kind","intro"),true)

    /** Not exposed to the WebView: only call once the real metrics are independently validated. */
    fun offerMetrics(perKmCents:Int,perHourCents:Int):Boolean {
        if (perKmCents !in 0..20000 || perHourCents !in 0..30000) return false
        return dispatch(JSONObject().put("kind","offer_metrics")
            .put("perKmCents",perKmCents).put("perHourCents",perHourCents),false)
    }

    private fun firebaseApp(cfg:Config):FirebaseApp {
        val id="vexo-aura-cloud"
        return runCatching { FirebaseApp.getInstance(id) }.getOrElse {
            val options=FirebaseOptions.Builder()
                .setApplicationId(cfg.firebaseAppId)
                .setApiKey(cfg.firebaseApiKey)
                .setProjectId(cfg.firebaseProjectId)
                .setGcmSenderId(cfg.firebaseSenderId)
                .build()
            FirebaseApp.initializeApp(context,options,id)
        }
    }

    private fun dispatch(event:JSONObject,allowMutedPreview:Boolean):Boolean {
        val cfg=config?:return false
        if (destroyed || (!allowMutedPreview && !offline.enabled())) return false
        val requestId=sequence.incrementAndGet()
        // Firebase's token task stays off the OCR pipeline; no blocking network on main.
        ui.post {
            if (destroyed || requestId!=sequence.get())return@post
            try {
                val fb=firebaseApp(cfg)
                val check=FirebaseAppCheck.getInstance(fb)
                check.installAppCheckProviderFactory(PlayIntegrityAppCheckProviderFactory.getInstance())
                check.getAppCheckToken(false)
                    .addOnSuccessListener { token ->
                        if (destroyed || requestId!=sequence.get())return@addOnSuccessListener
                        worker.execute {
                            val audio=runCatching { request(cfg,token.token,event) }.getOrNull()
                            ui.post {
                                if (destroyed || requestId!=sequence.get())return@post
                                if (audio==null) offline.preview()
                                else play(audio,requestId)
                            }
                        }
                    }
                    .addOnFailureListener { fallback(requestId) }
            } catch (e:Exception) {
                Log.w("AuraGoogleVoice","Google voice not configured: "+e.javaClass.simpleName)
                fallback(requestId)
            }
        }
        return true
    }

    private fun fallback(id:Int) {
        if (!destroyed && id==sequence.get())offline.preview()
    }

    private fun request(cfg:Config,appCheckToken:String,event:JSONObject):ByteArray? {
        if(appCheckToken.length !in 16..5000) return null
        val conn=URL(cfg.endpoint).openConnection() as HttpsURLConnection
        try {
            conn.requestMethod="POST"
            conn.connectTimeout=3500
            conn.readTimeout=10000
            conn.instanceFollowRedirects=false
            conn.doOutput=true
            conn.setRequestProperty("Content-Type","application/json")
            conn.setRequestProperty("X-Firebase-AppCheck",appCheckToken)
            val body=event.toString().toByteArray(Charsets.UTF_8)
            if(body.size>500)return null
            conn.outputStream.use { it.write(body) }
            if(conn.responseCode!=200 || !conn.contentType.orEmpty().startsWith("audio/mpeg"))return null
            if(conn.contentLength>900000)return null
            conn.inputStream.use { stream ->
                val output=ByteArrayOutputStream()
                val block=ByteArray(8192)
                while (true) {
                    val count=stream.read(block)
                    if (count<0) break
                    if (output.size()+count>900000) return null
                    output.write(block,0,count)
                }
                val bytes=output.toByteArray()
                if(bytes.size !in 256..900000)return null
                return bytes
            }
        }finally{conn.disconnect()}
    }

    private fun play(audio:ByteArray,id:Int) {
        if(destroyed || id!=sequence.get())return
        releasePlayer()
        val file=File.createTempFile("aura_google_",".mp3",context.cacheDir)
        try {
            file.writeBytes(audio)
            val next=MediaPlayer()
            next.setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            next.setDataSource(file.absolutePath)
            next.setOnPreparedListener {
                if(!destroyed && id==sequence.get()){ offline.stop(); it.start() }
            }
            next.setOnCompletionListener { releasePlayer() }
            next.setOnErrorListener { _,_,_ -> releasePlayer();true }
            temp=file
            player=next
            next.prepareAsync()
        }catch(e:Exception){
            file.delete()
            releasePlayer()
            fallback(id)
        }
    }

    private fun releasePlayer() {
        val old=player
        player=null
        old?.let { runCatching {it.reset()};runCatching {it.release()} }
        temp?.delete()
        temp=null
    }

    fun close() {
        destroyed=true
        sequence.incrementAndGet()
        ui.post { releasePlayer() }
        worker.shutdownNow()
    }
}
