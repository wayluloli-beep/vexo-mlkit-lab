const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const assets = path.join(process.env.VEXO_SOURCE_DIR || path.join(__dirname, '..', 'aurora'),
  'app/src/main/assets/aurora');
const script = fs.readFileSync(path.join(assets, 'turno.js'), 'utf8');
const start = 1_770_000_000_000;
const hour = 3_600_000;

function core() {
  const context = {window: {}};
  vm.runInNewContext(script, context);
  return context.window.VexoTurno;
}

function memory() {
  const data = new Map();
  return {getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value)};
}

const plain = value => JSON.parse(JSON.stringify(value));

test('prévia interpreta valores em centavos e metros sem fechar o turno', () => {
  const api = core();
  const store = memory();
  api.begin(store, start);
  const before = store.getItem(api.key);
  const fields = {uber: '1.234,56', nove: '0', outros: '', fuel: '12,50', extra: '', km: '10,125'};
  const result = plain(api.preview(fields));
  assert.deepEqual(result, {
    received: 123456, spent: 1250, net: 122206, km: 10.125,
    entries: {uber: 123456, nove: 0, outros: null, fuel: 1250, extra: null, km: 10125}
  });
  assert.equal(store.getItem(api.key), before);
  const {startedAt, endedAt, perHour, perKm, ...closed} = plain(api.close(store, fields, start + hour));
  assert.deepEqual(closed, result);
});

test('prévia identifica os mesmos campos inválidos que o fechamento', () => {
  const api = core();
  const store = memory();
  api.begin(store, start);
  const cases = [
    [{fuel: '12,50'}, 'uber'],
    [{uber: '20', extra: '1e3'}, 'extra'],
    [{nove: '20', km: '1,0001'}, 'km'],
    [{outros: '0', fuel: '-1'}, 'fuel']
  ];
  for (const [fields, expected] of cases) {
    assert.throws(() => api.preview(fields), err => err.field === expected);
    assert.throws(() => api.close(store, fields, start + hour), err => err.field === expected);
  }
  assert.deepEqual(plain(api.preview({outros: '0', fuel: '12,50'})), {
    received: 0, spent: 1250, net: -1250, km: null,
    entries: {uber: null, nove: null, outros: 0, fuel: 1250, extra: null, km: null}
  });
});

test('rascunho parcial preserva a digitação e não incorpora dados do histórico', () => {
  const api = core();
  const store = memory();
  api.begin(store, start);
  api.close(store, {uber: '220', fuel: '45', km: '100'}, start + hour);
  const previous = plain(api.read(store)).history;
  api.begin(store, start + 2 * hour);
  assert.equal(api.read(store).active.draft, undefined);
  const before = api.read(store).active.startedAt;
  api.saveDraft(store, {uber: ' 12, ', nove: '0', fuel: '', km: '3,', receipts: '999', history: []});
  const reopened = core();
  const saved = plain(reopened.read(store));
  assert.deepEqual(saved.active, {startedAt: before, draft: {uber: ' 12, ', nove: '0', fuel: '', km: '3,'}});
  assert.deepEqual(saved.history, previous);
  assert.equal(saved.history[0].entries.km, 100000);
  assert.equal(saved.history[0].entries.uber, 22000);
  assert.throws(() => reopened.close(store, saved.active.draft, start + 3 * hour), {field: 'uber'});
  assert.deepEqual(plain(reopened.read(store)), saved);
  const next = reopened.saveDraft(store, {...saved.active.draft, uber: '', km: '3,5'});
  assert.deepEqual(plain(next.active.draft), {uber: '', nove: '0', fuel: '', km: '3,5'});
  const row = reopened.close(store, next.active.draft, start + 3 * hour);
  assert.equal(row.received, 0);
  assert.equal(row.entries.km, 3500);
  assert.equal(reopened.read(store).active, null);
  assert.equal(reopened.begin(store, start + 4 * hour).active.draft, undefined);
});

test('salvar rascunho não cria turno e não sobrescreve armazenamento inválido', () => {
  const api = core();
  const store = memory();
  assert.throws(() => api.saveDraft(store, {uber: '20'}), /Nenhum turno/);
  assert.equal(store.getItem(api.key), null);
  for (const raw of ['not JSON', '{"active":{"startedAt":1,"draft":{"uber":{}}},"history":[]}',
    '{"active":{"startedAt":1},"history":[{"net":100}]}']) {
    store.setItem(api.key, raw);
    assert.throws(() => api.saveDraft(store, {uber: '20'}));
    assert.equal(store.getItem(api.key), raw);
  }
});

test('meio centavo por km arredonda simetricamente com distância fracionada',()=>{
 const api=core(),store=memory(),start=1770000000000;
 api.begin(store,start);
 assert.equal(api.close(store,{uber:'0,33',km:'4,4'},start+3600000).perKm,8);
 api.begin(store,start+7200000);
 assert.equal(api.close(store,{uber:'0',fuel:'0,33',km:'4,4'},start+10800000).perKm,-8);
});
