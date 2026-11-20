package com.trackingracing

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.window.OnBackInvokedCallback
import android.window.OnBackInvokedDispatcher
import java.io.ByteArrayInputStream
import java.io.InputStream

/** Offline Android shell for the manual product. The legacy bridge name preserves the WebView contract. */
class AuroraActivity : Activity() {
    private lateinit var web: WebView
    private var predictiveBack: OnBackInvokedCallback? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.decorView.setBackgroundColor(Color.BLACK)
        web = WebView(this).apply {
            setBackgroundColor(Color.BLACK)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            settings.mediaPlaybackRequiresUserGesture = false
            settings.setSupportMultipleWindows(false)
            isVerticalScrollBarEnabled = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                    VexoManualWeb.asset(request.url.toString()) == null

                override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse {
                    val asset = VexoManualWeb.asset(request.url.toString()) ?: return blocked()
                    return try {
                        val mime = when (asset.substringAfterLast('.')) {
                            "html" -> "text/html"
                            "js" -> "application/javascript"
                            "css" -> "text/css"
                            "webp" -> "image/webp"
                            "jpg", "jpeg" -> "image/jpeg"
                            "png" -> "image/png"
                            "mp4" -> "video/mp4"
                            else -> "application/octet-stream"
                        }
                        if (mime == "video/mp4") {
                            video(asset, request.requestHeaders.entries.firstOrNull { it.key.equals("Range", true) }?.value)
                        } else {
                            val encoding = if (mime.startsWith("text/") || mime == "application/javascript") "UTF-8" else null
                            WebResourceResponse(mime, encoding, assets.open(asset))
                        }
                    } catch (_: Exception) {
                        blocked()
                    }
                }
            }
            addJavascriptInterface(Bridge(), "VexoAndroidOcr")
        }
        setContentView(web)
        if (Build.VERSION.SDK_INT >= 33) {
            predictiveBack = OnBackInvokedCallback { if (!dispatchWebBack()) finish() }.also {
                onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, it)
            }
        }
        web.loadUrl(VexoManualWeb.entry)
    }

    private fun dispatchWebBack(): Boolean {
        if (!VexoManualWeb.handlesBack(web.url)) return false
        web.evaluateJavascript("window.dispatchEvent(new Event('vexo:android-back'));", null)
        return true
    }

    @Suppress("DEPRECATION")
    @Deprecated("Legacy fallback for Android back dispatch")
    override fun onBackPressed() {
        if (!dispatchWebBack()) super.onBackPressed()
    }

    private fun blocked(): WebResourceResponse = WebResourceResponse(
        "text/plain", "UTF-8", 403, "Forbidden", emptyMap(), ByteArrayInputStream(ByteArray(0))
    )

    private fun video(asset: String, rangeHeader: String?): WebResourceResponse {
        val size = assets.openFd(asset).use { it.length }
        val range = VexoManualWeb.mediaRange(size, rangeHeader) ?: return WebResourceResponse(
            "video/mp4", null, 416, "Range Not Satisfiable",
            mapOf("Content-Range" to "bytes */$size"), ByteArrayInputStream(ByteArray(0))
        )
        val stream = assets.open(asset)
        var skip = range.start
        while (skip > 0) {
            val moved = stream.skip(skip)
            if (moved <= 0) {
                stream.close()
                return blocked()
            }
            skip -= moved
        }
        val limited = object : InputStream() {
            var left = range.length
            override fun read(): Int = if (left <= 0) -1 else stream.read().also { if (it >= 0) left-- }
            override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
                if (length == 0) return 0
                if (left <= 0) return -1
                return stream.read(buffer, offset, minOf(length.toLong(), left).toInt()).also { if (it > 0) left -= it }
            }
            override fun close() = stream.close()
        }
        val headers = mutableMapOf("Accept-Ranges" to "bytes", "Content-Length" to range.length.toString())
        if (range.partial) headers["Content-Range"] = "bytes ${range.start}-${range.end}/$size"
        return WebResourceResponse("video/mp4", null, if (range.partial) 206 else 200,
            if (range.partial) "Partial Content" else "OK", headers, limited)
    }

    override fun onDestroy() {
        if (Build.VERSION.SDK_INT >= 33) {
            predictiveBack?.let { onBackInvokedDispatcher.unregisterOnBackInvokedCallback(it) }
        }
        web.removeJavascriptInterface("VexoAndroidOcr")
        web.destroy()
        super.onDestroy()
    }

    private inner class Bridge {
        private fun fuelPrefs() = getSharedPreferences("aurora_balloon", MODE_PRIVATE)
        private fun goalPrefs() = getSharedPreferences("vexo.gain-goal", MODE_PRIVATE)

        @JavascriptInterface fun appVersion(): String = BuildConfig.VERSION_NAME
        @JavascriptInterface fun kmPerLiter(): Double = fuelPrefs().getString("km", null)?.toDoubleOrNull() ?: 10.5
        @JavascriptInterface fun fuelPrice(): Double = fuelPrefs().getString("price", null)?.toDoubleOrNull() ?: 5.89

        @JavascriptInterface fun saveFuel(km: Double, price: Double): Boolean {
            if (!VexoManualWeb.validFuel(km, price)) return false
            val update = fuelPrefs().edit()
            update.putString("km", km.toString())
            update.putString("price", price.toString())
            return update.commit()
        }

        @JavascriptInterface fun hourlyGoalCents(): Int = runCatching {
            goalPrefs().getInt("hourly_cents", 0)
        }.getOrDefault(0)

        @JavascriptInterface fun setHourlyGoalCents(cents: Double): Boolean {
            val value = VexoManualWeb.hourlyGoal(cents) ?: return false
            val update = goalPrefs().edit()
            update.putInt("hourly_cents", value)
            return update.commit()
        }
    }
}
