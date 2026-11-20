const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const modulePath = path.join(process.env.VEXO_SOURCE_DIR || path.join(__dirname, '..', 'aurora'),
  'app/src/main/assets/aurora/caixa.js');

function loadCaixa() {
  const window = {};
  vm.runInNewContext(readFileSync(modulePath, 'utf8'), { window });
  return window.VexoCaixa;
}

function summarize(fields) {
  return { ...loadCaixa().summarize(fields) };
}

test('expõe uma API de caixa congelada para o turno', () => {
  assert.equal(Object.isFrozen(loadCaixa()), true);
  assert.equal(typeof loadCaixa().summarize, 'function');
});

test('dinheiro e Pix classificam apenas partes do total recebido', () => {
  assert.deepEqual(summarize({ received: 200000, cash: '1.234,56', pix: '32.40', reservePerKm: '0,30', meters: 40500 }),
    { cash: 123456, pix: 3240, unclassified: 73304, reserve: 1215, rate: 30 });
  assert.deepEqual(summarize({ received: 2500, pix: '25,00' }),
    { cash: null, pix: 2500, unclassified: 0, reserve: null, rate: null });
});

test('campos em branco ficam ausentes sem sugerir uma taxa de reserva', () => {
  assert.deepEqual(summarize({ received: 22000, cash: ' ', pix: null, reservePerKm: '', meters: 100000 }),
    { cash: null, pix: null, unclassified: 22000, reserve: null, rate: null });
  assert.deepEqual(summarize({ received: 22000, reservePerKm: '0,70', meters: null }),
    { cash: null, pix: null, unclassified: 22000, reserve: null, rate: 70 });
});

test('preserva o zero digitado separado do campo que ficou em branco', () => {
  assert.deepEqual(summarize({ received: 0, cash: '0', pix: '0,00', reservePerKm: '0', meters: 1000 }),
    { cash: 0, pix: 0, unclassified: 0, reserve: 0, rate: 0 });
  assert.equal(summarize({ received: 0, reservePerKm: '1,25', meters: 0 }).reserve, 0);
});

test('rejeita classificação acima do recebido, mesmo que cada parte caiba sozinha', () => {
  assert.throws(() => summarize({ received: 2500, cash: '25,01' }), { field: 'cash' });
  assert.throws(() => summarize({ received: 2500, pix: '25,01' }), { field: 'pix' });
  assert.throws(() => summarize({ received: 2500, cash: '15,01', pix: '10' }), { field: 'pix' });
});

test('rejeita texto monetário inválido e centavos ou metros não inteiros', () => {
  for (const [fields, field] of [
    [{ cash: '-1' }, 'cash'], [{ cash: 1 }, 'cash'], [{ pix: '1e2' }, 'pix'],
    [{ pix: '10,001' }, 'pix'], [{ reservePerKm: '12.34,56' }, 'reservePerKm'],
    [{ received: 1.5 }, 'received'], [{ meters: -1 }, 'meters'], [{ meters: 1.5 }, 'meters'],
  ]) {
    assert.throws(() => summarize({ received: 100, ...fields }), { field });
  }
});

test('reserva arredonda meio centavo para cima sem perder precisão no produto', () => {
  assert.equal(summarize({ received: 0, reservePerKm: '0,01', meters: 499 }).reserve, 0);
  assert.equal(summarize({ received: 0, reservePerKm: '0,01', meters: 500 }).reserve, 1);
  assert.equal(summarize({ received: 0, reservePerKm: '10000000000000,01', meters: 499 }).reserve, 499000000000000);
  assert.throws(() => summarize({ received: 0, reservePerKm: '90071992547409,91', meters: 2000 }),
    { field: 'reservePerKm' });
});
