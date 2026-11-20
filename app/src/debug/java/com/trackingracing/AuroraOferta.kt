package com.trackingracing

import com.google.mlkit.vision.text.Text
import org.json.JSONObject

internal object AuroraOferta {
    fun from(result: Text): Corrida? {
        val precoComum=AuroraCard99.precoComumSemRotulo(result.text)
        if (!AuroraCard99.aceitaTexto(result.text,precoComum)) return null
        val c=LeituraEspacial99.ler(result)?:return null
        val p=precoComum ?: c.preco
        val busca=c.busca
        val viagem=c.viagem
        if(p==null||!p.isFinite()||p<=0||busca?.km==null||viagem?.km==null||
            busca.minutos<=0||viagem.minutos<=0||busca.km<=0||viagem.km<=0)return null
        val linhas=result.textBlocks.flatMap { it.lines }.mapNotNull { l ->
            val b=l.boundingBox?:return@mapNotNull null
            Lab99Endereco.Linha(l.text,b.left,b.top,b.right,b.bottom)
        }
        val ends=Lab99Endereco.porPosicao(linhas,busca.minutos,busca.km,viagem.minutos,viagem.km)
        return c.copy(preco=p,busca=busca.copy(endereco=ends.busca?.texto),
            viagem=viagem.copy(endereco=ends.destino?.texto))
    }

    fun key(c: Corrida): String = listOf(c.preco,c.busca?.minutos,c.busca?.km,c.viagem?.minutos,c.viagem?.km).joinToString("|")
    private fun trecho(t:Trecho)=JSONObject().put("minutes",t.minutos)
        .put("distanceLabel","${t.km} km").put("address",t.endereco?: "")
    fun json(c: Corrida,id:Int,isNegocia:Boolean)=JSONObject().put("id",id).put("price",c.preco)
        .put("priceFormatted",String.format(java.util.Locale.forLanguageTag("pt-BR"),"%.2f",c.preco))
        .put("rating",c.notaPassageiro?.toString()?:JSONObject.NULL)
        .put("totalRides",c.viagensPassageiro?:JSONObject.NULL)
        .put("isNegocia",isNegocia)
        .put("pickup",trecho(requireNotNull(c.busca)))
        .put("dropoff",trecho(requireNotNull(c.viagem)))
}
