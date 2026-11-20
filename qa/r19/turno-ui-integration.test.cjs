const test = require("node:test");
const path = require("node:path");
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = process.env.VEXO_SOURCE_DIR || path.join(__dirname, '..', 'aurora');
const assetRoot=path.join(source, 'app/src/main/assets/aurora') + '/';
const ui=assetRoot+'turno-ui.js';
const fields=['uber','nove','indrive','outros','cash','pix','fuel','extra','km','reservePerKm'];
const backing=new Map();let lastTime=1795186799000;
function mount() {
  const ids={},nodes=[];
  let focus,steps;
  class FakeNode {
    constructor(id, tag='div') {this.id=id;this.tagName=tag.toUpperCase();this.dataset={};this.childNodes=[];this.attrs={};this.events={};this.hidden=false;this.value='';this.ownText='';nodes.push(this);if(id)ids[id]=this}
    get textContent(){return this.ownText+this.childNodes.map(e=>e.textContent).join('')}
    set textContent(x){this.ownText=x;this.childNodes=[];}
    append(...items){this.childNodes.push(...items);for(const item of items)item.parentElement=this;}
    prepend(...items){this.childNodes.unshift(...items);for(const item of items)item.parentElement=this;}
    replaceChildren(...items){this.childNodes=[];this.ownText='';this.append(...items);}
    addEventListener(kind,fn){(this.events[kind]??=[]).push(fn)}
    event(kind){for(const handler of this.events[kind]??[])handler({preventDefault(){},target:this});}
    focus(){focus=this.id}
    setAttribute(k,v){this.attrs[k]=v;}
    getAttribute(k){return this.attrs[k]??null;}
    removeAttribute(k){delete this.attrs[k];}
    querySelectorAll(){return steps;}
    querySelector(){return null;}
    closest(selector){for(let cur=this;cur;cur=cur.parentElement){if(selector===cur.tagName.toLowerCase())return cur;if(selector.startsWith('#')&&cur.id===selector.slice(1))return cur;}return null;}
  }
  const storage={getItem:k=>backing.get(k)??null,setItem:(k,v)=>backing.set(k,v)};
  const document={getElementById:id=>ids[id]??null,createElement:tag=>new FakeNode(null,tag),querySelectorAll:()=>steps};
  class StableDate extends Date {static now(){return lastTime+=1000;}}
  const context=vm.createContext({window:{},document,localStorage:storage,Date:StableDate});
  const form=new FakeNode('turno-form','form');form.hidden=true;
  for(const id of 'action badge state received spent net error step-label next prev confirm cancel preview breakdown last last-title last-values last-rates last-breakdown history history-panel'.split(' '))new FakeNode('turno-'+id);
  const start=new FakeNode('inicio');start.append(form);
  ids['turno-action'].textContent='Iniciar turno';
  ids['turno-history-panel'].append(ids['turno-history']);ids['turno-history-panel'].hidden=true;
  new FakeNode('status');
  steps=[1,2,3].map(n=>{const el=new FakeNode('step-'+n,'fieldset');el.dataset.turnStep=String(n);el.hidden=n!==1;form.append(el);return el});
  const payment=new FakeNode('turno-payment','details'),reserve=new FakeNode('turno-reserve','details');
  steps[0].append(payment);steps[2].append(reserve);
  const inputs=fields.map((field,i)=>{const el=new FakeNode('t-'+field,'input');el.name=field;
    (i===4 || i===5 ? payment : i===9 ? reserve : steps[i<6?0:i<8?1:2]).append(el);return el});
  form.elements={namedItem:f=>inputs.find(e=>e.name===f)};
  form.reset=()=>inputs.forEach(e=>e.value='');
  vm.runInContext(fs.readFileSync(assetRoot+'caixa.js','utf8'),context);
  vm.runInContext(fs.readFileSync(assetRoot+'turno.js','utf8'),context);
  if(fs.existsSync(ui))vm.runInContext(fs.readFileSync(ui,'utf8'),context);
  const core=context.window.VexoTurno, controller=context.window.VexoTurnoUI;
  controller?.refresh();
  return {el:id=>ids['turno-'+id],state:()=>core.read(storage), focus:()=>focus, press:id=>ids['turno-'+id].event('click'), step:n=>steps[n-1], back:()=>controller.handleBack(),
          entry:field=>ids['t-'+field].value, placeholder:field=>ids['t-'+field].getAttribute('placeholder'), type:(field,value)=>{const node=ids['t-'+field];node.value=value;form.events.input?.forEach(f=>f({target:node}));}, submit:()=>form.event('submit')};
}
const moneyStr=node=>node.textContent.replace(/\s/g,' ');
test('Central closes a real manual turn with inDrive, a saved cash split, and a separate reserve',()=>{
let app=mount();
app.press('action');
assert.equal(app.el('action').textContent,'Fechar turno','a new local turn can be started');
app.press('action');
for(const field of fields){assert.equal(app.entry(field),'');assert.equal(app.placeholder(field),null);}
app.press('next');
assert.equal(app.focus(),'t-uber');
assert.equal(app.el('error').hidden,false);
app.type('uber','150,50');
app.type('nove','39,50');
app.type('indrive','30');
app.type('cash','221');
app.press('next');
assert.equal(app.focus(),'t-cash');
assert.equal(app.step(1).hidden,false);
app.type('cash','65');
app.type('pix','100');
app.press('next');
assert.equal(app.step(2).hidden,false);
app.type('fuel','45');
app.type('extra','15');
app.press('next');
app.type('km','-1');
app.submit();
assert.equal(app.focus(),'t-km');
assert.equal(app.step(3).hidden,false);
app.type('km','100');
app.type('reservePerKm','0,25');
assert.equal(app.step(3).hidden,false);
assert.match(moneyStr(app.el('preview')),/R\$ 220,00/);
assert.match(moneyStr(app.el('preview')),/R\$ 60,00/);
assert.match(moneyStr(app.el('preview')),/R\$ 160,00/);
assert.match(moneyStr(app.el('breakdown')),/R\$ 220,00 − R\$ 60,00 = R\$ 160,00/);
assert.match(moneyStr(app.el('breakdown')),/UberR\$ 150,50 · informado/);
assert.equal(app.state().history.length,0);
assert.equal(app.back(),true);
assert.equal(app.step(2).hidden,false);
assert.equal(app.entry('km'),'100');
assert.equal(app.back(),true);
assert.equal(app.step(1).hidden,false);
assert.equal(app.back(),true);
assert.equal(app.back(),false);
assert.equal(app.el('form').hidden,true);
assert.equal(app.state().active.draft.km,'100');
app=mount();
app.press('action');
assert.equal(app.entry('nove'),'39,50');
assert.equal(app.entry('indrive'),'30');
assert.equal(app.entry('cash'),'65');
assert.equal(app.entry('pix'),'100');
app.press('next');
assert.equal(app.entry('fuel'),'45');
app.press('next');
app.submit();
assert.equal(app.state().history.length,1);
assert.equal(app.state().active,null);
const closed=app.state().history[0];
assert.equal(closed.cashFlow.cash,6500);
assert.equal(closed.cashFlow.pix,10000);
assert.equal(closed.cashFlow.unclassified,5500);
assert.equal(closed.cashFlow.reserve,2500);
assert.equal(closed.net,16000);
assert.match(moneyStr(app.el('last-breakdown')),/Pote do carro[^R]*R\$ 25,00/);
assert.match(moneyStr(app.el('last-rates')),/R\$ 1,60\/km/);
assert.match(moneyStr(app.el('last-breakdown')),/CombustívelR\$ 45,00/);
app.press('action');
app.press('action');
assert.equal(app.entry('uber'),'');
assert.equal(app.placeholder('uber'),'Último: 150,50');
app.type('uber','0');
app.press('next');
assert.equal(app.entry('fuel'),'');
app.press('next');
app.submit();
assert.equal(app.el('history-panel').hidden,false);
assert.equal(app.el('history').childNodes.length,1);
assert.match(moneyStr(app.el('history')),/R\$ 160,00/);
});
