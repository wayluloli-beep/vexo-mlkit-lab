(() => {
  'use strict';
  const key = 'vexo.turno-manual.v1';
  const labels={uber:'Uber',nove:'99',indrive:'inDrive',outros:'Outros recebimentos',fuel:'Combustível',extra:'Outros gastos',km:'Quilômetros'};
  const receiptFields=['uber','nove','indrive','outros'];
  const caixaFields=['cash','pix','reservePerKm'];
  const own = (obj,field) => Object.prototype.hasOwnProperty.call(obj,field);
  const stamp = x => Number.isSafeInteger(x) && x >= 0 && x <= 8640000000000000;
  const validRow = r => r && stamp(r.startedAt) && stamp(r.endedAt) && r.endedAt > r.startedAt &&
    ['received','spent','net','perHour'].every(k => Number.isSafeInteger(r[k])) &&
    (r.perKm === null || Number.isSafeInteger(r.perKm)) && (r.km === null || (Number.isFinite(r.km) && r.km >= 0));
  const validDraft = draft => draft && typeof draft === 'object' && !Array.isArray(draft) &&
    Object.entries(draft).every(([field,value]) => (own(labels,field)||caixaFields.includes(field)) && typeof value === 'string');
  function read(storage) {
    const raw = storage.getItem(key);
    if (raw === null) return {active:null,history:[]};
    const saved = JSON.parse(raw);
    if (!saved || !Array.isArray(saved.history) || !saved.history.every(validRow) ||
      !(saved.active === null || (saved.active && stamp(saved.active.startedAt) &&
        (!own(saved.active,'draft') || validDraft(saved.active.draft))))) throw Error('invalid turno storage');
    return saved;
  }
  function write(storage,state) {
    const json=JSON.stringify(state);
    storage.setItem(key,json);
    if(storage.getItem(key)!==json) throw Error('turno storage not confirmed');
  }
  function begin(storage,now=Date.now()) {
    const state=read(storage);
    if(state.active) return state;
    if(!stamp(now)) throw Error('invalid date');
    const next={...state,active:{startedAt:now}};
    write(storage,next);
    return next;
  }
  function saveDraft(storage,fields) {
    const state=read(storage);
    if(!state.active) throw Error('Nenhum turno está em andamento.');
    const draft={};
    for(const field of [...Object.keys(labels),...caixaFields]) {
      if(fields && own(fields,field) && typeof fields[field]==='string') draft[field]=fields[field];
    }
    const next={...state,active:{...state.active,draft}};
    write(storage,next);
    return next;
  }
  function scaled(input,digits,max) {
    const raw=String(input??'').trim();
    if(raw==='') return null;
    const clean=raw.includes(',')?raw.replace(/^(\d{1,3}(?:\.\d{3})+)(?=,)/, x=>x.replace(/\./g,'' )).replace(',','.'):raw;
    const m=clean.match(new RegExp('^(\\d{1,9})(?:\\.(\\d{1,'+digits+'}))?$'));
    if(!m) return NaN;
    const n=Number(m[1])*10**digits+Number((m[2]??'').padEnd(digits,'0'));
    return Number.isSafeInteger(n)&&n<=max?n:NaN;
  }
  function preview(fields) {
    const entries={};
    for (const [field,label] of Object.entries(labels)) {
      if(field==='indrive' && !(fields && own(fields,field))) continue;
      const v=scaled(fields?.[field],field==='km'?3:2,1_000_000_000);
      if(Number.isNaN(v)){const e=Error('Confira o valor de '+label+'.');e.field=field;throw e;}
      entries[field]=v;
    }
    if(receiptFields.every(k=>(entries[k]??null)===null)) {
      const e=Error('Informe pelo menos um recebimento. Digite 0 se não recebeu nada.');e.field='uber';throw e;
    }
    const received=receiptFields.reduce((sum,field)=>sum+(entries[field]??0),0);
    const spent=(entries.fuel??0)+(entries.extra??0);
    const km=entries.km===null?null:entries.km/1000;
    const result={received,spent,net:received-spent,km,entries};
    if(caixaFields.some(field=>typeof fields?.[field]==='string'&&fields[field].trim()!=='')) {
      const summarize=window.VexoCaixa?.summarize;
      if(!summarize) throw Error('Separação de caixa indisponível.');
      result.cashFlow=summarize({received, cash:fields.cash, pix:fields.pix, reservePerKm:fields.reservePerKm, meters:entries.km});
    }
    return result;
  }
  function close(storage,fields,now=Date.now()) {
    const state=read(storage);
    const start=state.active?.startedAt;
    if(!stamp(start)) throw Error('Nenhum turno está em andamento.');
    if(!stamp(now)||now<=start) throw Error('Ainda não há tempo válido no turno. Confira o relógio do aparelho.');
    const result=preview(fields);
    const {net,km}=result;
    const duration=now-start;
    // Round only the displayed rates, using integer cents and metres.
    const displayRatio=(scale,divisor)=>{
      const n=BigInt(Math.abs(net))*BigInt(scale), d=BigInt(divisor);
      const q=Number(n/d+((n%d)*2n>=d?1n:0n));
      return net<0&&q!==0?-q:q;
    };
    const perHour=displayRatio(3600000,duration), perKm=km>0?displayRatio(1000,result.entries.km):null;
    const row={startedAt:start,endedAt:now,...result,perHour,perKm};
    if(!validRow(row)) throw Error('Não foi possível calcular as médias deste turno.');
    write(storage,{active:null,history:[row,...state.history]});
    return row;
  }
  function today(state,now=Date.now()) {
    const day=new Date(now).toDateString();
    return state.history.reduce((sum,row)=>{
      if(new Date(row.endedAt).toDateString()===day) {
        sum.received+=row.received;sum.spent+=row.spent;sum.net+=row.net;sum.count++;
      }
      return sum;
    },{received:0,spent:0,net:0,count:0});
  }
  window.VexoTurno=Object.freeze({key,read,begin,saveDraft,preview,close,today});
})();
