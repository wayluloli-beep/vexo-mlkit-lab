const test = require('node:test');
const assert = require('node:assert/strict');
const { existsSync, readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

const main = join(process.env.VEXO_SOURCE_DIR || join(__dirname, '..', 'aurora'), 'app', 'src', 'main');
const flagsPath = join(main, 'assets', 'aurora', 'product-flags.js');

function loadFlags() {
  assert.ok(existsSync(flagsPath), 'the beta must ship the product flags script');
  const accesses = [];
  const navigator = {};
  for (const name of ['geolocation', 'bluetooth', 'serial', 'usb']) {
    Object.defineProperty(navigator, name, { get() { accesses.push(name); } });
  }
  const window = {
    location: { search: '?gps=true&obd2=true' },
    localStorage: {
      gps: 'true', obd2: 'true',
      getItem(key) { accesses.push(`localStorage:${key}`); return 'true'; },
    },
    navigator,
  };
  const context = vm.createContext({ window, location: window.location, localStorage: window.localStorage, navigator });
  vm.runInContext(readFileSync(flagsPath, 'utf8'), context, { filename: flagsPath });
  return { window, context, accesses };
}

test('manual beta keeps GPS and OBD2 disabled with opt-in values in query and storage', () => {
  const { window } = loadFlags();
  assert.equal(window.VexoProductFlags.gps, false);
  assert.equal(window.VexoProductFlags.obd2, false);
});

test('the published beta flags cannot be modified or replaced', () => {
  const { window, context } = loadFlags();
  const flags = window.VexoProductFlags;
  vm.runInContext('window.VexoProductFlags.gps = true; window.VexoProductFlags.obd2 = true; window.VexoProductFlags = {gps:true,obd2:true}; delete window.VexoProductFlags;', context);
  assert.equal(window.VexoProductFlags, flags);
  assert.equal(flags.gps, false);
  assert.equal(flags.obd2, false);
});

test('loading the flags does not consult storage or initialize hardware adapters', () => {
  assert.deepEqual(loadFlags().accesses, []);
});

test('manual beta manifest requests no Android location or Bluetooth permissions', () => {
  const manifest = readFileSync(join(main, 'AndroidManifest.xml'), 'utf8');
  const declarations = manifest.match(/<uses-permission(?:-sdk-\d+)?\b[^>]*>/g) || [];
  assert.doesNotMatch(declarations.join('\n'), /android\.permission\.(?:ACCESS_(?:COARSE|FINE|BACKGROUND)_LOCATION|BLUETOOTH[A-Z_]*|NEARBY_WIFI_DEVICES)\b/);
});
