const assert=require('node:assert/strict'),A=require('./aura-adapter.js'),E=require('./aura-query-engine.js'),C=require('./aura-core.js'),T=require('./aura-mobile-transport.js'),fixture=require('./test-aura-fixture.cjs');
(async()=>{let n=0;const env={engine:E,core:C,now:new Date(2026,10,25,14),readData:async()=>({finance:fixture(),rates:{fuel:.62,reserve:.15,fixed:0,eff:10,cycles:1}})};
const sim={intent:'SIMULATE_RIDE',ride_simulation:{fare_brl:30,distance_km:15,duration_min:25,ride_platform:'UNKNOWN'}},amb={intent:'CLARIFY',clarification_reason:'AMBIGUOUS_UNIT'};
const state=(await A.execute(sim,A.empty(),env)).context,p=A.pendingFor('E por 35?',amb,state);assert.equal(p.candidate_value,35);n++;
for(const u of ['Reais','Reais.','Em reais.','R$','Real','A unidade é em reais']){const r=await A.execute(A.resolvePending(u,p,state).wire,state,env);assert.equal(r.context.active_ride_simulation.fare_brl,35);assert.equal(r.context.active_ride_simulation.distance_km,15);assert.equal(r.context.active_ride_simulation.duration_min,25);assert.match(r.text,/23,45/);n++;}
for(const u of ['Quilômetros','Quilometro','km','Em quilômetros.']){assert.equal(A.resolvePending(u,p,state).wire.ride_simulation.distance_km,35);n++;}
for(const u of ['Minutos','Minuto','min.','Em minutos']){assert.equal(A.resolvePending(u,p,state).wire.ride_simulation.duration_min,35);n++;}
for(const q of ['E por 35 ou 40?', 'Quanto ganhei em 25/11?', 'E por -35?', 'E por R$ 35?', '99 35','35 km']){assert.equal(A.pendingFor(q,amb,state),null);n++;}
assert.equal(A.pendingFor('E por 35?',amb,A.empty()),null);n++;
assert.equal(A.resolvePending('Quanto ganhei hoje?',p,state),null);n++;
assert.equal(A.resolvePending('Reais',null,state),null);n++;
assert.equal(A.resolvePending('Reais e minutos',p,state),null);n++;
assert.ok(A.resolvePending('km',A.pendingFor('E por 4000?',amb,state),state).error);n++;
assert.deepEqual(state.active_ride_simulation,{fare_brl:30,distance_km:15,duration_min:25,platform:'UNKNOWN'});n++;
let timing;const result=await T.run(async()=>({ok:true,status:200,json:async()=>({protocol:5,timing:{server_receive_ms:123,gemini_api_ms:200,server_total_ms:210}})}),{onAttempt:(i,m)=>{timing=m}});
assert.equal(result.kind,'response');assert.equal(timing.gemini_api_ms,200);assert.equal(timing.server_receive_ms,123);n++;

for(const [q,v] of [['E por 35?',35],['E por 40?',40],['E por 50?',50],['Pra 35',35],['E se for 50?',50],['E se forem 15?',15],['E se fosse 30?',30],['E 25?',25],['Por 40',40],['Para 42',42],['Com 30?',30],['Em 35?',35],['E por 35,50?',35.5]]){
 const g=A.localGuard(q,state);assert.equal(g.kind,'ambiguous');assert.equal(g.pending.candidate_value,v);assert.equal(g.pending.expires_after_turns,1);n++;
}
for(const q of ['Quanto ganhei na 99?','meta de 300','corridas do dia 24','2 corridas','E por 35 ou 40?','E por 35 reais?','E se forem 15 km?','E por 40 minutos?','E por R$ 40','E por 99?','Em 99','E 99','99','E por -40?','E por 1.000?','E por 40 e 50','Quanto ganhei hoje?','E na 99?','E por 15/11?','40','E por 100001?','E por 3 horas?']){assert.equal(A.localGuard(q,state),null,q);n++;}
for(const q of ['Reais.','Em reais','R$','Quilômetros','Minutos','Minuto','km','A unidade é em reais']){const g=A.localGuard(q,A.empty());assert.equal(g.kind,'unit_without_pending');assert.match(g.text,/Informe o valor/);assert.equal(g.pending,undefined);n++;}
assert.equal(A.localGuard('E por 40?',A.empty()),null);n++;
const g40=A.localGuard('E por 40?',state);const res40=await A.execute(A.resolvePending('Minutos.',g40.pending,state).wire,state,env);assert.equal(res40.context.active_ride_simulation.duration_min,40);assert.equal(res40.context.active_ride_simulation.fare_brl,30);assert.equal(res40.context.active_ride_simulation.distance_km,15);n++;
assert.equal(A.resolvePending('Quanto ganhei hoje?',g40.pending,state),null);n++;
assert.deepEqual(state.active_ride_simulation,{fare_brl:30,distance_km:15,duration_min:25,platform:'UNKNOWN'});n++;
console.log('Pending clarification, strict guard and telemetry: '+n+' passed');})().catch(e=>{console.error(e);process.exitCode=1});