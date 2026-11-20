'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { test } = require('node:test');

function fixture(t) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'vexo-ci-fixture-'));
  t.after(() => fs.rmSync(home, { recursive: true, force: true }));
  const qa = path.join(home, 'qa');
  const source = path.join(home, 'aurora test source');
  const assets = path.join(source, 'app/src/main/assets/aurora');
  fs.mkdirSync(qa, { recursive: true });
  fs.mkdirSync(assets, { recursive: true });
  fs.writeFileSync(path.join(source, 'settings.gradle.kts'), '');
  fs.writeFileSync(path.join(source, 'app/build.gradle.kts'), '');
  fs.writeFileSync(path.join(assets, 'index.html'), '<script type="application/json">{"guard": true}</script><script>window.test = true;</script>');
  fs.writeFileSync(path.join(assets, 'main.js'), 'window.test = true;');
  fs.writeFileSync(path.join(qa, 'check.test.cjs'), `const assert = require('node:assert/strict');
    require('node:test').test('checks materialized source', () => assert.equal(process.env.VEXO_SOURCE_DIR, ${JSON.stringify(source)}));`);
  const cli = path.join(qa, 'ci-manual.cjs');
  const original = path.join(__dirname, 'ci-manual.cjs');
  if (fs.existsSync(original)) fs.copyFileSync(original, cli);

  const sdk = path.join(home, 'sdk');
  const gradle = path.join(home, 'fake-gradle');
  fs.writeFileSync(gradle, `#!/usr/bin/env node
    const fs = require('node:fs');
    const path = require('node:path');
    const args = process.argv.slice(2);
    if (args[0] !== '--project-dir' || !args.includes(':app:lintDebug') || !args.includes(':app:testDebugUnitTest')) process.exit(40);
    if (process.env.VEXO_FIXTURE_GRADLE_FAIL) process.exit(41);
    const d = path.join(args[1], 'app/build/reports');
    fs.mkdirSync(d, { recursive: true });
    fs.writeFileSync(path.join(d, 'lint-results-debug.xml'), process.env.VEXO_FIXTURE_LINT_XML);
  `, { mode: 0o755 });
  return {
    qa, assets, sdk,
    run(target = 'web', extraEnv = {}) {
      return spawnSync(process.execPath, [cli, target, source, ...(target === 'android' ? [gradle] : [])], {
        env: { ...process.env, ANDROID_HOME: '', ANDROID_SDK_ROOT: '', ...extraEnv }, encoding: 'utf8', timeout: 10000,
      });
    },
  };
}

test('Web gate checks good assets and uses the materialized source in its tests', (t) => {
  const f = fixture(t);
  const r = f.run();
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.match(r.stdout, /checks materialized source/);
  assert.match(r.stdout, /WEB_PASS/);
  assert.doesNotMatch(r.stdout, /ANDROID_PASS/);
});

test('Web gate rejects a malformed JavaScript asset before executing tests', (t) => {
  const f = fixture(t);
  fs.writeFileSync(path.join(f.assets, 'main.js'), 'const = broken;');
  const r = f.run();
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /main\.js/);
  assert.doesNotMatch(r.stdout, /checks materialized source/);
});

test('Web gate rejects malformed inline WebView JavaScript', (t) => {
  const f = fixture(t);
  fs.writeFileSync(path.join(f.assets, 'index.html'), '<script>const = broken;</script>');
  const r = f.run();
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /index\.html/);
  assert.doesNotMatch(r.stdout, /WEB_PASS/);
});

test('Web gate rejects a checkout without a test suite', (t) => {
  const f = fixture(t);
  fs.unlinkSync(path.join(f.qa, 'check.test.cjs'));
  const r = f.run();
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /test\.cjs/);
  assert.doesNotMatch(r.stdout, /WEB_PASS/);
});

test('Web gate propagates a failure from any discovered test file', (t) => {
  const f = fixture(t);
  fs.writeFileSync(path.join(f.qa, 'another.test.cjs'), `require('node:test').test('bad result', () => { throw Error('regression'); });`);
  const r = f.run();
  assert.notEqual(r.status, 0);
  assert.match(r.stdout, /regression/);
  assert.doesNotMatch(r.stdout, /WEB_PASS/);
});

test('Android gate fails explicitly when SDK is unavailable', (t) => {
  const f = fixture(t);
  const r = f.run('android');
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /Android SDK/);
  assert.doesNotMatch(r.stdout, /ANDROID_PASS/);
});

test('Android gate propagates Gradle failure', (t) => {
  const f = fixture(t);
  fs.mkdirSync(f.sdk);
  const r = f.run('android', { ANDROID_HOME: f.sdk, VEXO_FIXTURE_GRADLE_FAIL: '1' });
  assert.equal(r.status, 41, r.stderr + r.stdout);
  assert.doesNotMatch(r.stdout, /ANDROID_PASS/);
});

test('Android gate rejects lint warnings even when Gradle returns zero', (t) => {
  const f = fixture(t);
  fs.mkdirSync(f.sdk);
  const r = f.run('android', { ANDROID_HOME: f.sdk, VEXO_FIXTURE_LINT_XML: '<issues><issue id="MissingTranslation" severity="Warning"/></issues>' });
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /MissingTranslation/);
  assert.doesNotMatch(r.stdout, /ANDROID_PASS/);
});

test('Android gate emits success after Web, Gradle and a clean lint report', (t) => {
  const f = fixture(t);
  fs.mkdirSync(f.sdk);
  const r = f.run('android', { ANDROID_HOME: f.sdk, VEXO_FIXTURE_LINT_XML: '<issues format="6" by="lint"></issues>' });
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.match(r.stdout, /WEB_PASS[\s\S]*ANDROID_PASS/);
});
