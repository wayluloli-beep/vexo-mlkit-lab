(function () {
  'use strict';

  const manualBuildCapabilities = Object.freeze({ gps: false, obd2: false, fiscal: false });
  const disabledFlags = Object.freeze({ gps: false, obd2: false, fiscal: false });
  const flagNames = Object.keys(disabledFlags);
  const maxSnapshotAgeMs = 24 * 60 * 60 * 1000;

  function isRecord(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  // Use own data properties without invoking accessors or following prototypes.
  function ownValue(record, key) {
    return Object.getOwnPropertyDescriptor(record, key)?.value;
  }

  function readVerifiedRules(snapshot, nowMs) {
    if (!isRecord(snapshot) || !Number.isSafeInteger(nowMs) || nowMs < 0) return null;
    const issuedAtMs = ownValue(snapshot, 'issuedAtMs');
    const expiresAtMs = ownValue(snapshot, 'expiresAtMs');
    const flags = ownValue(snapshot, 'flags');
    if (!Number.isSafeInteger(issuedAtMs) || issuedAtMs < 0 || issuedAtMs > nowMs ||
        !Number.isSafeInteger(expiresAtMs) || expiresAtMs <= nowMs ||
        nowMs - issuedAtMs >= maxSnapshotAgeMs || !isRecord(flags)) return null;

    const rules = Object.create(null);
    for (const flag of flagNames) {
      const entry = Object.getOwnPropertyDescriptor(flags, flag);
      if (!entry) continue;
      if (!isRecord(entry.value)) return null;
      const enabled = ownValue(entry.value, 'enabled');
      const rolloutPercentage = ownValue(entry.value, 'rolloutPercentage');
      const killSwitch = Object.getOwnPropertyDescriptor(entry.value, 'killSwitch');
      if (typeof enabled !== 'boolean' || !Number.isInteger(rolloutPercentage) ||
          rolloutPercentage < 0 || rolloutPercentage > 100 ||
          (killSwitch && typeof killSwitch.value !== 'boolean')) return null;
      rules[flag] = { enabled, rolloutPercentage, killed: killSwitch?.value === true };
    }
    return rules;
  }

  // FNV-1a over the flag name and caller-supplied stable cohort key, with no I/O.
  function cohortBucket(flag, cohortKey) {
    const input = `${flag}:${cohortKey}`;
    let hash = 2166136261;
    for (let i = 0; i < input.length; i++) hash = Math.imul(hash ^ input.charCodeAt(i), 16777619);
    return (hash >>> 0) % 100;
  }

  function createProductFlagPolicy(buildCapabilities) {
    const availableFlags = isRecord(buildCapabilities)
      ? flagNames.filter(flag => ownValue(buildCapabilities, flag) === true)
      : [];

    // verifiedSnapshot must come from a trusted verifier before calling evaluate.
    // This module provides no network, remote provider or authenticity check.
    // The snapshot contains issuedAtMs, expiresAtMs and flags. Each known rule has
    // enabled, rolloutPercentage (0–100) and optionally killSwitch. Local switches
    // may only deny. An invalid or missing snapshot always leaves the features off.
    function evaluate(options) {
      if (!availableFlags.length || !isRecord(options)) return disabledFlags;
      const nowMs = Object.getOwnPropertyDescriptor(options, 'nowMs');
      const rules = readVerifiedRules(ownValue(options, 'verifiedSnapshot'), nowMs ? nowMs.value : Date.now());
      if (!rules) return disabledFlags;

      const local = Object.getOwnPropertyDescriptor(options, 'localKillSwitches');
      if (local && !isRecord(local.value)) return disabledFlags;
      const cohortKey = ownValue(options, 'cohortKey');
      const hasCohortKey = typeof cohortKey === 'string' && cohortKey.trim() !== '';
      const evaluated = { ...disabledFlags };
      for (const flag of availableFlags) {
        const localSwitch = local && Object.getOwnPropertyDescriptor(local.value, flag);
        const rule = rules[flag];
        if ((localSwitch && localSwitch.value !== false) || !rule?.enabled || rule.killed) continue;
        evaluated[flag] = rule.rolloutPercentage === 100 ||
          (rule.rolloutPercentage > 0 && hasCohortKey && cohortBucket(flag, cohortKey) < rule.rolloutPercentage);
      }
      return Object.freeze(evaluated);
    }

    return Object.freeze({ evaluate });
  }

  if (typeof window !== 'undefined') {
    // The manual binary does not contain GPS, OBD2 or Fiscal capabilities.
    // Runtime flags (remote or otherwise) cannot change these release capabilities.
    Object.defineProperties(window, {
      VexoProductFlags: { value: Object.freeze({ gps: false, obd2: false }) },
      VexoProductFlagPolicy: { value: createProductFlagPolicy(manualBuildCapabilities) },
    });
  } else if (typeof module === 'object' && module?.exports) {
    // The factory is for non-browser builds and exercising future capabilities in QA.
    module.exports = Object.freeze({ createProductFlagPolicy });
  }
}());
