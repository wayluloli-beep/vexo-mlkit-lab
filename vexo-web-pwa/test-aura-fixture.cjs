// Synthetic regression fixture. Never imports customer records.
function fixture(day='2026-11-25',yesterday='2026-11-24'){
 const gross=[30,25,20,24,15,18,22,28,27.2],km=[12,10,9,11,8,12,13,14,14.38],minutes=[20,18,21,16,14,25,26,22,18];
 const rides=gross.map((v,i)=>['MOB-TEST-'+i,'finished',day+'T'+String(8+i).padStart(2,'0')+':00:00',day+'T'+String(8+i).padStart(2,'0')+':'+String(minutes[i]).padStart(2,'0')+':00',minutes[i]*60,km[i],'Paid by Company',v,i<4?'Uber':'99',1,Math.round((km[i]-1)*100)/100]);
 rides.push(['R-Y','finished',yesterday+'T09:00:00',yesterday+'T09:30:00',1800,15,'Paid by Company',45,'Uber',2,13]);
 return {rides,fills:[['F1',yesterday+'T07:00:00',1000,20,6,'Gasolina',true,'Posto'],['F2',day+'T07:00:00',1200,20,6,'Gasolina',true,'Posto']],expenses:[['D1',day,'Pedágio','Teste',10,0,'']],goals:{revenue:1000,cash:0,reserve:.15},settings:{fuel:6,consumption:10,fixed:0},offer:null,seen:[]};
}
if(typeof module!=='undefined')module.exports=fixture;
