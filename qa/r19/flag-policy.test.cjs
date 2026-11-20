const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

const sourceDir = process.env.VEXO_SOURCE_DIR || join(__dirname, '..', 'aurora');
const file = join(sourceDir, 'app', 'src', 'main', 'assets', 'aurora', 'product-flags.js');
const source = readFileSync(file, 'utf8');
const nowMs = 1700000000000;
const off = { gps: false, obd2: false, fiscal: false };
const gpsOnly = { gps: true, obd2: false, fiscal: false };
const allCapabilities = { gps: true, obd2: true, fiscal: true };
const allow = { enabled: true, rolloutPercentage: 100 };

function snapshot(flags = { gps: allow }, times = {}) {
  return { issuedAtMs: nowMs - 1000, expiresAtMs: nowMs + 1000, flags, ...times };
}

function capableEvaluator(capabilities = allCapabilities) {
  const module = { exports: {} };
  vm.runInNewContext(source, { module }, { filename: file });
  assert.equal(typeof module.exports.createProductFlagPolicy, 'function');
  return module.exports.createProductFlagPolicy(capabilities).evaluate;
}

test('the manual binary cannot gain GPS, OBD2 or Fiscal from verified or caller-supplied capabilities', () => {
  const window = {};
  vm.runInNewContext(source, { window }, { filename: file });
  const policy = window.VexoProductFlagPolicy;
  assert.equal(typeof policy?.evaluate, 'function');
  const evaluated = policy.evaluate({
    verifiedSnapshot: snapshot({ gps: allow, obd2: allow, fiscal: allow }),
    nowMs,
    cohortKey: 'installation-1',
    buildCapabilities: allCapabilities,
  });
  assert.deepEqual({ ...evaluated }, off);
  assert.equal(Object.isFrozen(evaluated), true);
  assert.equal(Object.isFrozen(policy), true);
  assert.equal(Reflect.set(window, 'VexoProductFlagPolicy', {}), false);
  assert.equal(Reflect.deleteProperty(window, 'VexoProductFlagPolicy'), false);
  assert.deepEqual({ ...window.VexoProductFlags }, { gps: false, obd2: false });
});

test('release capabilities are fixed when the evaluator is created', () => {
  const capabilities = { gps: true, obd2: false, fiscal: false };
  const evaluate = capableEvaluator(capabilities);
  capabilities.obd2 = true;
  capabilities.fiscal = true;
  assert.deepEqual({ ...evaluate({
    nowMs,
    verifiedSnapshot: snapshot({ gps: allow, obd2: allow, fiscal: allow }),
  }) }, gpsOnly);
});

test('a fresh, explicitly verified snapshot can enable only its known opted-in flags', () => {
  const evaluate = capableEvaluator();
  const remote = snapshot({ gps: allow, fiscal: { enabled: false, rolloutPercentage: 100 }, unknown: allow });
  assert.deepEqual({ ...evaluate({ verifiedSnapshot: remote, nowMs }) }, gpsOnly);
  assert.deepEqual({ ...evaluate({ snapshot: { ...remote, verified: true }, nowMs }) }, off);
});

test('missing, invalid, future-dated, expired or overly old snapshots fall back to all off', () => {
  const evaluate = capableEvaluator();
  for (const [label, verifiedSnapshot] of [
    ['missing', undefined],
    ['not a record', 'remote-config'],
    ['no issued time', snapshot(undefined, { issuedAtMs: undefined })],
    ['future issued time', snapshot(undefined, { issuedAtMs: nowMs + 1 })],
    ['expiry reached', snapshot(undefined, { expiresAtMs: nowMs })],
    ['24-hour age limit reached despite long expiry', snapshot(undefined, { issuedAtMs: nowMs - 86400000 })],
    ['invalid flags', snapshot([])],
    ['out-of-range rollout alongside a valid rule', snapshot({ gps: allow, obd2: { ...allow, rolloutPercentage: 101 } })],
    ['non-boolean enabled', snapshot({ gps: { ...allow, enabled: 'true' } })],
    ['non-boolean kill switch', snapshot({ gps: { ...allow, killSwitch: 'false' } })],
    ['inherited snapshot fields', Object.create(snapshot())],
    ['inherited feature rule', snapshot(Object.create({ gps: allow }))],
  ]) assert.deepEqual({ ...evaluate({ verifiedSnapshot, nowMs }) }, off, label);
  assert.deepEqual({ ...evaluate({ verifiedSnapshot: snapshot(), nowMs: NaN }) }, off);
});

test('a missing feature rule cannot be supplied by prototype pollution in the runtime', () => {
  const context = vm.createContext({ module: { exports: {} }, nowMs, verifiedSnapshot: snapshot({}), allCapabilities });
  vm.runInContext(source, context, { filename: file });
  const result = vm.runInContext(`
    Object.prototype.gps = { enabled: true, rolloutPercentage: 100 };
    module.exports.createProductFlagPolicy(allCapabilities).evaluate({ verifiedSnapshot, nowMs });
  `, context);
  assert.deepEqual({ ...result }, off);
});

test('local and remote kill switches independently override a 100% rollout', () => {
  const evaluate = capableEvaluator();
  const verifiedSnapshot = snapshot({ gps: allow, obd2: { ...allow, killSwitch: true }, fiscal: allow });
  assert.deepEqual({ ...evaluate({ verifiedSnapshot, nowMs, localKillSwitches: { gps: true, obd2: false } }) }, {
    gps: false, obd2: false, fiscal: true,
  });
  assert.deepEqual({ ...evaluate({ verifiedSnapshot, nowMs, localKillSwitches: { gps: 'true' } }) }, {
    gps: false, obd2: false, fiscal: true,
  });
});

test('a partial rollout uses stable per-flag cohorts and does not admit a missing key', () => {
  const first = capableEvaluator();
  const second = capableEvaluator();
  const half = { ...allow, rolloutPercentage: 50 };
  const verifiedSnapshot = snapshot({ gps: half, obd2: half, fiscal: { ...allow, rolloutPercentage: 0 } });
  const all = [];
  let distinct = false;
  for (let index = 0; index < 100; index++) {
    const options = { verifiedSnapshot, nowMs, cohortKey: `installation-${index}` };
    const result = first(options);
    assert.deepEqual({ ...second(options) }, { ...result });
    assert.equal(result.fiscal, false);
    all.push(result.gps);
    if (result.gps !== result.obd2) distinct = true;
  }
  assert.ok(all.includes(true), 'some keys should be inside the rollout');
  assert.ok(all.includes(false), 'some keys should be outside the rollout');
  assert.ok(distinct, 'some installations should be in a different cohort for each flag');
  assert.deepEqual({ ...first({ verifiedSnapshot, nowMs }) }, off);
  assert.deepEqual({ ...first({ verifiedSnapshot, nowMs, cohortKey: '   ' }) }, off);
});
