"use strict";
(() => {
  const core = window.VexoTurno;
  if (!core?.preview) return;

  function calculate({received, spent} = {}) {
    try {
      // Reuse the manual turn's exact cent parser and arithmetic without opening a turn.
      const quote = core.preview({outros: received, extra: spent});
      return {received: quote.received, spent: quote.entries.extra, net: quote.net};
    } catch (error) {
      const field = error?.field === "extra" ? "spent" : "received";
      const result = new Error(field === "spent"
        ? "Confira os gastos. Use até duas casas decimais ou deixe em branco."
        : "Confira quanto recebeu. Use até duas casas decimais. Se não recebeu, digite 0.");
      result.field = field;
      throw result;
    }
  }

  window.VexoQuickValue = Object.freeze({calculate});
  if (typeof document === "undefined") return;

  const byId = id => document.getElementById(id);
  const block = byId("quick-value"), form = byId("quick-value-form");
  const received = byId("quick-value-received"), spent = byId("quick-value-spent");
  const answer = byId("quick-value-answer"), amount = byId("quick-value-amount");
  const footnote = byId("quick-value-note"), errorLine = byId("quick-value-error");
  if (!block || !form || !received || !spent || !answer || !amount || !footnote || !errorLine) return;

  const money = new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"});
  function clear() {
    errorLine.textContent = "";
    received.removeAttribute("aria-invalid");
    spent.removeAttribute("aria-invalid");
    answer.hidden = true;
    amount.textContent = "";
    footnote.textContent = "";
  }

  form.addEventListener("input", clear);
  block.addEventListener("toggle", () => {
    if (block.open) return;
    form.reset();
    clear();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    clear();
    try {
      const quote = calculate({received: received.value, spent: spent.value});
      amount.textContent = money.format(quote.net / 100);
      footnote.textContent = quote.spent === null
        ? "Sem gastos informados. A sobra não é o lucro líquido do turno."
        : "Total recebido menos os gastos que você informou.";
      answer.hidden = false;
      answer.focus();
    } catch (error) {
      const field = error.field === "spent" ? spent : received;
      errorLine.textContent = error.message;
      field.setAttribute("aria-invalid", "true");
      field.focus();
    }
  });
  block.hidden = false;
})();
