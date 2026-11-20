#!/usr/bin/env node
'use strict';
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function* filesUnder(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) yield* filesUnder(full);
    else if (entry.isFile()) yield full;
  }
}

function run(command, args, options = {}) {
  const child = spawnSync(command, args, { stdio: 'inherit', ...options });
  if (child.error) throw child.error;
  if (child.signal) throw new Error(`${command} interrupted by ${child.signal}`);
  if (child.status !== 0) process.exit(child.status ?? 1);
}

function attribute(attributes, name) {
  const match = attributes.match(new RegExp(`(?:^|\\s)${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
  return match?.slice(1).find((value) => value !== undefined);
}

function checkWebSource(source) {
  const assets = path.join(source, 'app/src/main/assets/aurora');
  let js = 0;
  let html = 0;
  let inline = 0;
  for (const file of filesUnder(assets)) {
    const ext = path.extname(file).toLowerCase();
    const label = path.relative(source, file);
    if (ext === '.js') {
      new vm.Script(fs.readFileSync(file, 'utf8'), { filename: label });
      js++;
    } else if (ext === '.mjs') {
      run(process.execPath, ['--check', file]);
      js++;
    } else if (ext === '.html') {
      const markup = fs.readFileSync(file, 'utf8');
      html++;
      for (const match of markup.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
        const [, attrs, code] = match;
        const type = (attribute(attrs, 'type') ?? '').trim().toLowerCase();
        if (attribute(attrs, 'src') !== undefined) continue;
        if (type === 'module') {
          const result = spawnSync(process.execPath, ['--check', '--input-type=module'], { input: code, encoding: 'utf8' });
          if (result.error) throw result.error;
          if (result.status !== 0) throw new Error(`${label}: ${result.stderr || 'invalid module script'}`);
        } else if (!type || /^(text|application)\/(x-)?(java|ecma)script$/.test(type)) {
          const lineOffset = markup.slice(0, match.index).split('\n').length - 1;
          new vm.Script(code, { filename: label, lineOffset });
        } else {
          // Data script tags (e.g. vehicle catalog JSON) are not JavaScript.
          continue;
        }
        inline++;
      }
    }
  }
  if (!html || !js) throw new Error('Materialized WebView assets are missing HTML or JavaScript');
  console.log(`VEXO_CI:WEB_SYNTAX_OK ${html} HTML, ${js} JS, ${inline} inline scripts`);
}

function androidLintIsClean(source) {
  const report = fs.readFileSync(path.join(source, 'app/build/reports/lint-results-debug.xml'), 'utf8');
  if (!/<issues\b[^>]*(?:\/>|>[\s\S]*<\/issues>)/.test(report)) throw new Error('Missing or invalid Android lint findings report');
  const findings = [...report.matchAll(/<issue\s+([^>]*)>/g)].flatMap(([, attrs]) => {
    const severity = attribute(attrs, 'severity');
    return /^(warning|error|fatal)$/i.test(severity ?? '') ? [`${severity}: ${attribute(attrs, 'id') || 'unnamed lint issue'}`] : [];
  });
  if (findings.length) throw new Error(`Android lint has findings (${findings.length}):\n${findings.join('\n')}`);
}

function main(args) {
  const [mode, requestedSource, gradle] = args;
  if (!requestedSource || !((mode === 'web' && args.length === 2) || (mode === 'android' && args.length === 3))) {
    throw new Error('Usage: node qa/ci-manual.cjs web <materialized-aurora-dir> | android <materialized-aurora-dir> <absolute-gradle-executable>');
  }
  const source = path.resolve(requestedSource);
  for (const expected of ['settings.gradle.kts', 'app/build.gradle.kts']) {
    if (!fs.existsSync(path.join(source, expected))) throw new Error(`Invalid materialized Aurora source: missing ${expected}`);
  }
  const tests = fs.readdirSync(__dirname, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.test.cjs'))
    .map((entry) => path.join(__dirname, entry.name)).sort();
  if (!tests.length) throw new Error('No *.test.cjs tests found in qa');

  checkWebSource(source);
  const testEnv = { ...process.env, VEXO_SOURCE_DIR: source };
  // A caller may itself be a node:test case. Start a fresh runner, not a nested worker.
  delete testEnv.NODE_TEST_CONTEXT;
  run(process.execPath, ['--test', ...tests], { env: testEnv });
  console.log('VEXO_CI:WEB_PASS (static syntax and Node tests only)');
  if (mode === 'web') return;

  const sdk = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;
  if (!sdk || !fs.statSync(sdk, { throwIfNoEntry: false })?.isDirectory()) {
    throw new Error('Android SDK not found; install the project SDK and set ANDROID_HOME');
  }
  if (!path.isAbsolute(gradle)) throw new Error('Provide the absolute path to the pinned Gradle executable');
  fs.accessSync(gradle, fs.constants.X_OK);
  run(gradle, ['--project-dir', source, '--no-daemon', '--console=plain', '--max-workers=2', ':app:lintDebug', ':app:testDebugUnitTest']);
  androidLintIsClean(source);
  console.log('VEXO_CI:ANDROID_PASS (lint and Kotlin JVM unit tests; no device or release packaging)');
}

try {
  main(process.argv.slice(2));
} catch (error) {
  console.error(`VEXO_CI:FAIL ${error.stack ?? error.message}`);
  process.exitCode = 1;
}
