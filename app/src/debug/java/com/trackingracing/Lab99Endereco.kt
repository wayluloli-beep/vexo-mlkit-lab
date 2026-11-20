package com.trackingracing

import kotlin.math.abs

/** Address-only interpretation. The metrics returned by the existing OCR are unchanged. */
internal object Lab99Endereco {
    data class Linha(val texto:String,val x:Int,val y:Int,val direita:Int,val fundo:Int)
    data class Endereco(val texto:String,val numero:String?)
    data class Resultado(val busca:Endereco?=null,val destino:Endereco?=null)
    private data class Par(val min:Int,val km:Double)
    private val par=Regex("""(?<![\p{L}\d])(\d{1,3})\s*min(?:utos?)?\s*[(]?\s*(\d+(?:[,.]\d+)?)\s*(km|m)\b""",RegexOption.IGNORE_CASE)
    private val rua=Regex("""\b(?:rua|r\.|avenida|av\.?|alameda|travessa|estrada|rodovia|rod\.|praça|largo|viela|beco)\s+""",RegexOption.IGNORE_CASE)
    private val local=Regex("""^(?:shopping|supershopping|estação|terminal|hospital|aeroporto|unifesp|parque|universidade)\b""",RegexOption.IGNORE_CASE)
    private val fim=Regex("""^(?:aceitar|recusar|negocia\b|normal\b|editar|compartilhar|lixeira|adicionar|R\s*[S$]\s*\d|[★☆]|cartão\s+verif|perfil\s+premium|pgto\.|\d+\s+corridas)""",RegexOption.IGNORE_CASE)
    private val numeroRua=Regex("""(?i),\s*(?:n[º°o]\.?\s*)?(s\s*/\s*n|\d{1,6}[a-z]?)(?=\s*(?:$|[,–—-]|\())""")
    private val numeroInicio=Regex("""^(?:\d{1,6}[a-z]?|s\s*/\s*n)(?=\s|[,–—-]|$)""",RegexOption.IGNORE_CASE)
    private val letras=Regex("""\p{L}""")
    private val espacos=Regex("""\s+""")
    private val hifen=Regex("""\s*[–—-]\s*""")
    fun numero(s:String):String? {
        val street=rua.find(s) ?: return null
        return numeroRua.find(s,street.range.last+1)?.groupValues?.get(1)?.replace(espacos,"")?.lowercase()
    }
    private fun clean(s:String)=s.trim().trimStart('•','·',' ','↑','↓')
    private fun parse(s:String):Par? {
        val m=par.find(s) ?: return null
        if(clean(s.substring(0,m.range.first)).trim('(', ' ').any(Char::isLetterOrDigit))return null
        if(par.find(s,m.range.last+1)!=null)return null
        val km=m.groupValues[2].replace(',','.').toDoubleOrNull() ?: return null
        return Par(m.groupValues[1].toInt(),km/(if(m.groupValues[3].equals("m",true))1000 else 1))
    }
    private fun bate(p:Par?,min:Int?,km:Double?)=p!=null&&p.min==min&&km!=null&&abs(p.km-km)<.002
    private fun montar(rows:List<String>):Endereco? {
        val partes=mutableListOf<String>()
        for(raw in rows) {
            val s=clean(raw)
            if(s.isBlank())continue
            if(fim.containsMatchIn(s)||parse(s)!=null)break
            if(partes.isEmpty()&&!rua.containsMatchIn(s)&&!local.containsMatchIn(s)) {
                if(s.length<=4)continue
                return null
            }
            if(partes.isNotEmpty()&&(rua.containsMatchIn(s)||local.containsMatchIn(s))&&
                (rua.containsMatchIn(partes.joinToString(" "))||local.containsMatchIn(s)))break
            if(partes.isNotEmpty()&&!letras.containsMatchIn(s)&&!numeroInicio.containsMatchIn(s))break
            if(partes.size>=3||s.length>150)break
            partes.add(s)
        }
        val text=partes.joinToString(" ").replace(espacos," ").replace(hifen," - ").trimEnd(',', ' ')
        if(text.isBlank()||text.length>230)return null
        return Endereco(text,numero(text))
    }
    fun porTexto(texto:String,bt:Int?,bk:Double?,dt:Int?,dk:Double?):Resultado {
        val ls=texto.lines()
        val anchors=ls.indices.filter { parse(ls[it])!=null }
        if(anchors.size!=2)return Resultado()
        val (a,b)=anchors
        if(!bate(parse(ls[a]),bt,bk)||!bate(parse(ls[b]),dt,dk))return Resultado()
        if(ls.subList(a+1,b).any { fim.containsMatchIn(clean(it)) && !clean(it).equals("normal",true) }) return Resultado()
        return Resultado(montar(ls.subList(a+1,b)),montar(ls.drop(b+1)))
    }
    fun porPosicao(ls:List<Linha>,bt:Int?,bk:Double?,dt:Int?,dk:Double?):Resultado {
        val pares=ls.filter { parse(it.texto)!=null }
        val a=pares.singleOrNull { bate(parse(it.texto),bt,bk) } ?: return Resultado()
        val b=pares.singleOrNull { bate(parse(it.texto),dt,dk) } ?: return Resultado()
        val h=maxOf(10,a.fundo-a.y,b.fundo-b.y)
        val dx=maxOf(15,(h*1.55).toInt())
        if(a.y>=b.y||abs(a.x-b.x)>dx||b.y-a.y>h*15)return Resultado()
        if(pares.any { it!==a&&it!==b&&abs(it.x-a.x)<=dx&&it.y in (a.y-h*5)..(b.y+h*6) })return Resultado()
        if(ls.any { it.y in (a.fundo+1) until b.y && fim.containsMatchIn(clean(it.texto)) &&
            !clean(it.texto).equals("normal",true) && it.direita>a.x && it.x<a.direita })return Resultado()
        fun trecho(ancora:Linha,limite:Int):Endereco? {
            val rows=ls.filter { it!==ancora&&it.y>=ancora.fundo-h/5&&it.y<limite&&
                abs(it.x-ancora.x)<=dx&&it.direita>ancora.x+h }.sortedBy { it.y }
            val bloco=mutableListOf<String>()
            var bottom=ancora.fundo
            for(l in rows) {
                if(l.y-bottom>h*1.65 || fim.containsMatchIn(clean(l.texto)))break
                if(l.y<bottom-h/4)continue
                bloco.add(l.texto)
                bottom=l.fundo
            }
            return montar(bloco)
        }
        return Resultado(trecho(a,b.y),trecho(b,b.fundo+h*7))
    }
}
