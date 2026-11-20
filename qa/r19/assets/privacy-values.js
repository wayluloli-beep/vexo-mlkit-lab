"use strict";
(() => {
  const key = "vexo.privacy-values.v1", idleMs = 30000;
  let saved;
  try { saved = JSON.parse(localStorage.getItem(key)); } catch (_) {}
  let manual = saved?.manual === true, auto = saved?.auto === true, timed = false;
  let timer = null, deadline = 0;
  const masked = () => manual || timed;
  const maskDocument = () => document.documentElement.toggleAttribute("data-vexo-values-hidden", masked());
  const persist = () => {
    try { localStorage.setItem(key, JSON.stringify({manual, auto})); } catch (_) {}
  };

  // This script runs in the head so remembered masking applies before Home can paint.
  maskDocument();
  document.addEventListener("DOMContentLoaded", () => {
    const controls = document.getElementById("privacy-values");
    const toggle = document.getElementById("privacy-toggle");
    const option = document.getElementById("privacy-auto");
    const status = document.getElementById("privacy-status");
    const form = document.getElementById("turno-form");
    if (!controls || !toggle || !option || !status || !form) return;

    const moneyFields = [...form.querySelectorAll("input[inputmode='decimal']:not([name='km'])")];
    const hints = new Map();
    function hideHint(field) {
      const previous = field.getAttribute("placeholder");
      if (previous === null) return;
      hints.set(field, previous);
      field.removeAttribute("placeholder");
    }
    // These placeholders contain past amounts, not the numbers the driver is editing.
    const suggestions = new MutationObserver(records => {
      for (const {target, attributeName} of records) {
        if (attributeName === "hidden" && form.hidden) hints.clear();
        else if (attributeName === "placeholder" && masked()) hideHint(target);
      }
    });
    suggestions.observe(form, {attributes:true, attributeFilter:["hidden"]});
    for (const field of moneyFields) suggestions.observe(field, {attributes:true, attributeFilter:["placeholder"]});

    function update() {
      const hidden = masked();
      maskDocument();
      toggle.textContent = hidden ? "Mostrar valores" : "Ocultar valores";
      status.textContent = hidden ? "Resumos e valores sugeridos do Início ocultos. O que você digita continua visível." : "";
      if (hidden) moneyFields.forEach(hideHint);
      else {
        for (const [field, previous] of hints) field.setAttribute("placeholder", previous);
        hints.clear();
      }
    }

    function checkDeadline() {
      clearTimeout(timer);
      timer = null;
      if (!auto || masked() || !deadline) return;
      const remaining = deadline - Date.now();
      if (remaining > 0) timer = setTimeout(checkDeadline, remaining);
      else { deadline = 0; timed = true; update(); }
    }

    function arm() {
      deadline = auto && !masked() ? Date.now() + idleMs : 0;
      checkDeadline();
    }

    toggle.addEventListener("click", () => {
      manual = !masked();
      timed = false;
      persist();
      update();
      arm();
    });
    option.addEventListener("change", () => {
      auto = option.checked;
      if (!auto) timed = false;
      persist();
      update();
      arm();
    });
    for (const event of ["pointerdown", "touchstart", "keydown", "input", "click", "wheel", "focusin"]) {
      document.addEventListener(event, () => { if (auto && !masked()) arm(); }, {capture:true, passive:true});
    }
    document.addEventListener("visibilitychange", checkDeadline);
    window.addEventListener("pageshow", checkDeadline);

    option.checked = auto;
    update();
    controls.hidden = false;
    arm();
  }, {once:true});
})();
