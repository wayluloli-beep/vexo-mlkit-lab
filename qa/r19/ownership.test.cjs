const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const vm = require('node:vm');

const html = readFileSync(join(process.env.VEXO_SOURCE_DIR || join(__dirname, '..', 'aurora'), 'app/src/main/assets/aurora/onboarding.html'), 'utf8');
const scripts = [...html.matchAll(/<script(?:\s+[^>]+)?>([\s\S]*?)<\/script>/g)].map(([, js]) => js);
const profileKey = 'vexo.gain-profile.v1';
const draftKey = 'vexo.gain-draft.v1';
const oldRental = {works: true, type: 'rent', base: '4500', ipva: '120', maintenance: '300', fuel: '1000', goal: '1500', simDays: 25, simHours: 8};

function launch({profile, draft, phase = 'app'} = {}) {
  const store = new Map([['vexo.entry.disclosure.v1', 'vexo-termos-minuta-2026-11-20'], ['vexo.entry.sequence.x4', phase]]);
  if (profile) store.set(profileKey, JSON.stringify(profile));
  if (draft) store.set(draftKey, JSON.stringify(draft));
  const localStorage = {getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key)};
  const nodes = new Map();
  const element = () => ({dataset: {}, n: {}, classList: {add(){}, toggle(){}}, value: '', innerHTML: '', textContent: '',
    addEventListener(event, fn){this.n[event] = fn;}, setAttribute(){}, focus(){}, getContext: () => null,
    querySelector: () => element(), querySelectorAll: () => []});
  const node = id => {if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id);};
  const activations = [], navigation = [];
  const context = vm.createContext({localStorage,
    document: {getElementById: node, addEventListener(){}},
    window: {addEventListener(){}, scrollTo(){}, innerWidth: 360, innerHeight: 740, VexoAndroidOcr: {setHourlyGoalCents: cents => {activations.push(cents); return true;}}},
    location: {replace: path => navigation.push(path)}, matchMedia: () => ({matches: true}), devicePixelRatio: 1, performance, requestAnimationFrame(){},
    FormData: class {constructor(form){this.fields = form.fields;} [Symbol.iterator](){return Object.entries(this.fields)[Symbol.iterator]();}}});
  for (const js of scripts) vm.runInContext(js, context);
  const screen = node('screen');
  const click = dataset => screen.n.click({target: {closest: () => ({dataset, classList: {add(){}}})}});
  return {store, navigation, activations, screen, node, click,
    chooseMode(type) {click({action: 'begin'}); click({choice: 'yes'}); click({choice: type});},
    input(name, value) {screen.n.input({target: {name, value}});},
    submit(fields) {
      const error = {hidden: true, textContent: ''};
      screen.n.submit({preventDefault(){}, target: {fields, querySelector: () => error}});
      return error;
    },
    show(page) {vm.runInContext(`route(${JSON.stringify(page)}, false)`, context);},
    activate() {node('plan-enter').onclick();}};
}

const clean = markup => markup.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

test('a rental form omits owner costs and updates its weekly estimate from typed monthly rent', () => {
  const app = launch();
  app.chooseMode('rent');
  assert.doesNotMatch(app.screen.innerHTML, /name="(?:ipva|maintenance|depreciation)"/);
  assert.match(clean(app.screen.innerHTML), /Aluguel mensal.*Custos pagos à parte/i);
  assert.match(clean(app.screen.innerHTML), /12.*52.*cobrança/i);
  assert.doesNotMatch(app.screen.innerHTML, /1\.038,46/);

  app.input('base', 'R$ 4.500,00');
  assert.match(app.node('rent-weekly').textContent, /1\.038,46/);
  app.input('base', 'inválido');
  assert.doesNotMatch(app.node('rent-weekly').textContent, /1\.038,46/);
  app.input('base', '0');
  assert.match(app.node('rent-weekly').textContent, /0,00/);
});

test('monthly rent and new separately paid costs count once, and old owner values remain ignored', () => {
  const app = launch({profile: oldRental});
  app.chooseMode('rent');
  assert.match(clean(app.screen.innerHTML), /1\.038,46/);
  app.show('plan');
  assert.match(clean(app.screen.innerHTML), /Custos por dia R\$ 220,00.*Meta bruta por hora R\$ 35,00/);

  app.show('costs');
  app.input('rentExtras', '200,00');
  const draft = JSON.parse(app.store.get(draftKey));
  assert.equal(draft.rentExtras, '200,00');
  assert.equal(JSON.parse(app.store.get(profileKey)).rentExtras, undefined);

  const reopened = launch({profile: oldRental, draft});
  reopened.chooseMode('rent');
  assert.match(reopened.screen.innerHTML, /name="rentExtras"[^>]+value="200,00"/);
  assert.equal(reopened.submit({base: '4500', rentExtras: '200,00'}).hidden, true);
  assert.match(reopened.screen.innerHTML, /name="fuel"/);
  reopened.submit({fuel: '1000'});
  assert.match(reopened.screen.innerHTML, /name="goal"/);
  reopened.submit({goal: '1500'});
  assert.match(clean(reopened.screen.innerHTML), /Custos por dia R\$ 228,00.*Meta bruta por hora R\$ 36,00/);
  reopened.activate();
  assert.deepEqual(reopened.activations, [3600]);
  assert.equal(JSON.parse(reopened.store.get(profileKey)).rentExtras, '200,00');
});

test('owned and financed modes keep owner inputs and never include rental extras', () => {
  for (const [type, rate, hasInstallment] of [['own', '14,60', false], ['finance', '19,35', true]]) {
    const app = launch({profile: {...oldRental, type, base: '950', rentExtras: '200'}});
    app.chooseMode(type);
    assert.match(clean(app.screen.innerHTML), /Qual é o teu carro/);
    app.show('costs');
    assert.match(app.screen.innerHTML, /name="ipva"/);
    assert.match(app.screen.innerHTML, /name="maintenance"/);
    assert.doesNotMatch(app.screen.innerHTML, /rentExtras|rent-weekly/);
    assert.equal(app.screen.innerHTML.includes('name="base"'), hasInstallment);
    app.show('plan');
    assert.ok(clean(app.screen.innerHTML).includes(`Meta bruta por hora R$ ${rate}`));
  }
});

test('direct entry and the sample plan do not publish or replace saved rental values', () => {
  const draft = {...oldRental, rentExtras: '200'};
  const app = launch({profile: oldRental, draft, phase: 'interview'});
  app.click({action: 'enter-welcome'});
  assert.deepEqual(app.navigation, ['./index.html']);
  assert.deepEqual(app.activations, []);
  assert.deepEqual(JSON.parse(app.store.get(profileKey)), oldRental);
  assert.deepEqual(JSON.parse(app.store.get(draftKey)), draft);

  const sample = launch({profile: oldRental, draft});
  sample.click({action: 'begin'});
  sample.click({action: 'try'});
  sample.activate();
  assert.deepEqual(sample.activations, []);
  assert.deepEqual(JSON.parse(sample.store.get(profileKey)), oldRental);
  assert.deepEqual(JSON.parse(sample.store.get(draftKey)), draft);
});
