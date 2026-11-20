package com.trackingracing.replay

/** UI-thread ownership. A hidden view invalidates its pending presentation, not the ML task. */
internal class ReplayGate {
    class Turn internal constructor()

    private var active: Turn? = null
    private var visible = false
    private var acceptResult = false
    val canBegin: Boolean get() = visible && active == null

    fun show() { visible = true }
    fun hide() {
        visible = false
        acceptResult = false
    }

    fun begin(): Turn? {
        if (!canBegin) return null
        return Turn().also {
            active = it
            acceptResult = true
        }
    }

    fun finish(turn: Turn): Boolean {
        if (active !== turn) return false
        active = null
        return visible && acceptResult
    }
}
