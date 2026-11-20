package com.trackingracing.replay

internal data class ReplayReport(
    val status: String,
    val matched: List<String> = emptyList(),
    val mismatched: List<String> = emptyList(),
    val missing: List<String> = emptyList(),
    val shapeOk: Boolean = false,
) {
    companion object {
        private val expected = "Valor  R\$ 36,70\nBusca  6 min · 1,5 km\nViagem  33 min · 22,5 km\nNota  4,98\nCorridas  243"
        private val labels = listOf("Valor", "Busca", "Viagem", "Nota", "Corridas")
        private val fields = listOf(
            "price" to "R\$ 36,70", "pickup_min" to "6", "pickup_km" to "1,5",
            "trip_min" to "33", "trip_km" to "22,5", "rating" to "4,98", "trip_count" to "243",
        )
        private val terminal = mapOf(
            "A leitura do JPEG falhou." to "READ_ERROR",
            "O OCR não reconheceu texto no JPEG." to "EMPTY_TEXT",
            "O parser não confirmou uma oferta completa." to "PARSER_REJECTED",
        )
        private val leg = Regex("""^([0-9]+) min · ([0-9]+(?:,[0-9]+)?) km$""")

        fun parseWait(arg: String?): Long? =
            if (arg == null) 25_000L else arg.toLongOrNull()?.takeIf { it in 1_000L..120_000L }

        fun failure(status: String) = ReplayReport(status)

        fun classify(text: String): ReplayReport {
            terminal[text]?.let { return failure(it) }
            val lines = text.split('\n')
            fun value(label: String): String? =
                lines.filter { it.startsWith("$label  ") }.singleOrNull()?.removePrefix("$label  ")?.takeIf { it.isNotEmpty() }
            val pickup = value("Busca")?.let(leg::matchEntire)
            val trip = value("Viagem")?.let(leg::matchEntire)
            val actual = listOf(value("Valor"), pickup?.groupValues?.get(1), pickup?.groupValues?.get(2),
                trip?.groupValues?.get(1), trip?.groupValues?.get(2), value("Nota"), value("Corridas"))
            if (labels.none { label -> lines.any { it.startsWith("$label  ") } }) return failure("UNEXPECTED_OUTPUT")
            val matched = mutableListOf<String>()
            val mismatched = mutableListOf<String>()
            val missing = mutableListOf<String>()
            actual.zip(fields).forEach { (observed, field) ->
                when {
                    observed == null -> missing.add(field.first)
                    observed == field.second -> matched.add(field.first)
                    else -> mismatched.add(field.first)
                }
            }
            val lineLabels = lines.map { it.substringBefore("  ", "") }
            val shapeOk = lineLabels == labels
            return ReplayReport(if (text == expected) "PASS" else "FIELD_MISMATCH", matched, mismatched, missing, shapeOk)
        }
    }
}

/** Bounded handoff to a dispatcher. A queued, canceled task cannot run later. */
internal fun <T> awaitDispatched(
    timeoutMs: Long,
    dispatch: (java.util.concurrent.FutureTask<T>) -> Boolean,
    work: () -> T,
): T {
    val task = java.util.concurrent.FutureTask { work() }
    try {
        check(dispatch(task))
        return task.get(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS)
    } finally {
        task.cancel(false)
    }
}
