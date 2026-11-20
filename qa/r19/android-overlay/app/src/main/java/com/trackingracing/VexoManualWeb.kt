package com.trackingracing

import java.net.URI

internal object VexoManualWeb {
    const val host = "appassets.androidplatform.net"
    const val entry = "https://appassets.androidplatform.net/aurora/index.html"
    private val segment = Regex("[A-Za-z0-9_.-]+")
    private val entryPages = setOf("aurora/index.html", "aurora/central.html", "aurora/onboarding.html")
    private val byteRange = Regex("bytes=(\\d+)-(\\d*)")

    fun asset(url: String?): String? {
        val uri = url?.let { runCatching { URI(it) }.getOrNull() } ?: return null
        if (uri.scheme != "https" || uri.host != host || uri.port != -1 || uri.rawUserInfo != null) return null
        val path = uri.rawPath ?: return null
        if (!path.startsWith("/aurora/")) return null
        return path.removePrefix("/").takeIf { name ->
            name.split('/').all { it != "." && it != ".." && segment.matches(it) }
        }
    }

    fun handlesBack(url: String?): Boolean = asset(url) in entryPages

    fun hourlyGoal(cents: Double): Int? = cents.toInt().takeIf {
        cents == it.toDouble() && it in 1..1_000_000_000
    }

    fun validFuel(km: Double, price: Double): Boolean = km in 1.0..1000.0 && price in 0.5..1000.0

    data class MediaRange(val start: Long, val end: Long, val partial: Boolean) {
        val length: Long get() = end - start + 1
    }

    fun mediaRange(size: Long, header: String?): MediaRange? {
        if (size <= 0) return null
        if (header == null) return MediaRange(0, size - 1, false)
        val match = byteRange.matchEntire(header) ?: return null
        val start = match.groupValues[1].toLongOrNull()?.takeIf { it < size } ?: return null
        val rawEnd = match.groupValues[2]
        val end = if (rawEnd.isEmpty()) size - 1 else rawEnd.toLongOrNull()?.coerceAtMost(size - 1) ?: return null
        return if (end >= start) MediaRange(start, end, true) else null
    }
}
