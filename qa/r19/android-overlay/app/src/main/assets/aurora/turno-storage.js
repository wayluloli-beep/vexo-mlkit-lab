"use strict";
(() => {
  const key = window.VexoTurno?.key;
  const native = window.VexoAndroidOcr;
  if (!key || typeof native?.readManualTurn !== "function" || typeof native?.writeManualTurn !== "function") return;

  // Native storage becomes the source of truth as soon as a write is confirmed.
  // A valid older WebView copy remains readable until the first write from this edition.
  const failure = () => Error("Falha no armazenamento do turno no aparelho.");
  window.VexoTurnoStorage = Object.freeze({
    getItem(name) {
      if (name !== key) throw failure();
      const raw = native.readManualTurn();
      if (typeof raw !== "string") throw failure();
      return raw === "" ? localStorage.getItem(key) : raw;
    },
    setItem(name, raw) {
      if (name !== key || !raw || native.writeManualTurn(raw) !== true) throw failure();
    }
  });
})();
