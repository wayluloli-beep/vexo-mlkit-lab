// R17 source is hash-checked before this conversion. Preserve the existing garage apart from its former simulator parent.
const fs=require('node:fs');
const vm=require('node:vm');
const [source,target]=process.argv.slice(2);
const text=fs.readFileSync(source,'utf8'),start=text.indexOf('},JC=`')+5,end=text.indexOf('`,ZC=',start);
if(start<5||end<start) throw Error('R17 garage not found');
let html=vm.runInNewContext(text.slice(start,end+1),Object.create(null),{timeout:1000})
  .replace(/<style>\.vx-safety\{[^]*?<\/style>/,'');
html=html.replace('</head>',`<script src="./product-flags.js"></script>
<style>#obd-nav,#obd-live,.obd-garage,#obd-hood-status,.aurora-controls{display:none!important}</style></head>`)
 .replace(/function autoRefuelKm\(\)\s*\{/, '$& if(!window.VexoProductFlags?.obd2)return null;')
 .replace(/addEventListener\('vexo:obd-garage',(?:\s*)e=>\{/, '$& if(!window.VexoProductFlags?.obd2)return;');
if(!html.includes('autoRefuelKm(){ if(!window.VexoProductFlags?.obd2)return null;')||!html.includes('if(!window.VexoProductFlags?.obd2)return;'))throw Error('OBD-off guards not found');
if(!html.startsWith('<!doctype html>')||!html.includes('vexo.meu-veiculo.selecao.v1')||/99Pop|Aceitar por|Expandir Simulador 99/.test(html))throw Error('Unexpected garage content');
fs.writeFileSync(target,html);
