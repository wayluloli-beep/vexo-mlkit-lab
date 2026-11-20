"use strict";
(() => {
  const turno = window.VexoTurno;
  const storage = window.VexoTurnoStorage || localStorage;
  const byId = id => document.getElementById(id);
  const form = byId("turno-form"), action = byId("turno-action"), errorLine = byId("turno-error");
  const stepLabel = byId("turno-step-label"), next = byId("turno-next"), previous = byId("turno-prev");
  const confirm = byId("turno-confirm"), cancel = byId("turno-cancel");
  const preview = byId("turno-preview"), breakdown = byId("turno-breakdown");
  const steps = form ? [...form.querySelectorAll("[data-turn-step]")] : [];
  if (!turno || !action || !errorLine || !stepLabel || !next || !previous || !confirm || !cancel || !preview || !breakdown || steps.length !== 3) return;

  const income = ["uber", "nove", "indrive", "outros", "cash", "pix"];
  const costs = ["fuel", "extra"];
  const results = ["km", "reservePerKm"];
  const fields = [...income, ...costs, ...results];
  const breakdownLabels = {uber:"Uber", nove:"99", indrive:"inDrive", outros:"Outros recebimentos", fuel:"Combustível", extra:"Outros gastos", km:"Quilômetros rodados"};
  const currency = new Intl.NumberFormat("pt-BR", {style: "currency", currency: "BRL"});
  const amount = new Intl.NumberFormat("pt-BR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const distance = new Intl.NumberFormat("pt-BR", {maximumFractionDigits: 3});
  const date = new Intl.DateTimeFormat("pt-BR", {day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"});
  const reais = cents => currency.format(cents / 100);
  const input = name => form.elements.namedItem(name);
  const setText = (id, text) => { const el = byId(id); if (el) el.textContent = text; };
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  let step = 1, hydratedStart = null, lastSavedDraft = "", invalidInput = null;

  function readFields(names = fields) {
    return Object.fromEntries(names.map(name => [name, input(name).value]));
  }

  function clearProblem() {
    errorLine.textContent = "";
    errorLine.hidden = true;
    if (!invalidInput) return;
    invalidInput.removeAttribute("aria-invalid");
    const descriptions = (invalidInput.getAttribute("aria-describedby") || "").split(/\s+/).filter(id => id && id !== errorLine.id);
    if (descriptions.length) invalidInput.setAttribute("aria-describedby", descriptions.join(" "));
    else invalidInput.removeAttribute("aria-describedby");
    invalidInput = null;
  }

  function problem(error, draftFailed = false) {
    clearProblem();
    const fieldProblem = fields.includes(error?.field) && !form.hidden;
    errorLine.textContent = fieldProblem || error?.message?.startsWith("Ainda não há tempo")
      ? error.message
      : draftFailed
        ? "Não consegui salvar o rascunho no aparelho. Os campos continuam preenchidos nesta tela."
        : "Não consegui acessar o turno. Nenhum registro foi apagado. Tente de novo.";
    errorLine.hidden = false;
    if (fieldProblem) {
      showStep(income.includes(error.field) ? 1 : costs.includes(error.field) ? 2 : 3, false);
      const field = input(error.field);
      const details = field.closest("details");
      if (details) details.open = true;
      const descriptions = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
      field.setAttribute("aria-describedby", [...new Set([...descriptions, errorLine.id])].join(" "));
      field.setAttribute("aria-invalid", "true");
      invalidInput = field;
      field.focus();
    }
  }

  function rememberDraft() {
    const data = readFields();
    const signature = JSON.stringify(data);
    if (signature === lastSavedDraft) return;
    try {
      turno.saveDraft(storage, data);
      lastSavedDraft = signature;
    } catch (error) { problem(error, true); }
  }

  function item(label, value) {
    const row = element("div");
    row.append(element("dt", label), element("dd", value));
    return row;
  }

  function addCashRows(totals, flow) {
    if (!flow) return;
    const add = (label, value) => {
      const row = item(label, value);
      row.className = "turno-cash-values";
      totals.append(row);
    };
    if (flow.cash != null || flow.pix != null) {
      if (flow.cash != null) add("Em espécie", reais(flow.cash));
      if (flow.pix != null) add("Na conta ou Pix", reais(flow.pix));
      add("Sem forma de pagamento informada", reais(flow.unclassified));
    }
    if (flow.rate != null) {
      add("Pote do carro · sugestão separada da sobra", flow.reserve == null
        ? "Informe os quilômetros para calcular" : reais(flow.reserve));
    }
  }

  function renderBreakdown(container, entries, cashFlow) {
    if (!container) return;
    container.replaceChildren(...(entries ? Object.entries(breakdownLabels).map(([name, label]) => {
      const value = entries[name];
      return item(label, !Number.isFinite(value) ? "Não informado" : name === "km" ? distance.format(value / 1000) + " km · informado" : reais(value) + " · informado");
    }) : []));
    addCashRows(container, cashFlow);
  }

  function renderPreview(values) {
    const totals = element("dl", undefined, "turno-totals");
    totals.append(item("Recebido", reais(values.received)), item("Gastos informados", reais(values.spent)), item("Sobra após gastos", reais(values.net)));
    const km = element("p", values.km === null ? "Quilometragem não informada." : distance.format(values.km) + " km informados.", "detail");
    preview.replaceChildren(totals, km);
    renderBreakdown(breakdown, values.entries, values.cashFlow);
    breakdown.prepend(item("Conta da sobra (calculada)", reais(values.received)+" − "+reais(values.spent)+" = "+reais(values.net)));
  }

  function showStep(number, moveFocus = true) {
    step = number;
    const current = steps.find(node => Number(node.dataset.turnStep) === step);
    for (const node of steps) node.hidden = node !== current;
    stepLabel.textContent = `Etapa ${step} de 3`;
    previous.hidden = step === 1;
    next.hidden = step === 3;
    confirm.hidden = step !== 3;
    if (moveFocus) (current.querySelector("legend") || stepLabel).focus();
  }

  function showForm(state) {
    if (hydratedStart !== state.active.startedAt) {
      form.reset();
      for (const field of fields) {
        const draft = state.active.draft?.[field];
        if (typeof draft === "string") input(field).value = draft;
      }
      hydratedStart = state.active.startedAt;
      lastSavedDraft = JSON.stringify(readFields());
    }
    const entries = state.history[0]?.entries;
    for (const field of fields) {
      const value = entries?.[field] ?? state.history[0]?.cashFlow?.[field === "reservePerKm" ? "rate" : field];
      if (Number.isFinite(value)) input(field).setAttribute("placeholder", "Último: " + (field === "km" ? distance.format(value / 1000) : amount.format(value / 100)));
      else input(field).removeAttribute("placeholder");
    }
    byId("turno-payment").open = Boolean(input("cash").value || input("pix").value);
    byId("turno-reserve").open = Boolean(input("reservePerKm").value);
    form.hidden = false;
    action.hidden = true;
    action.setAttribute("aria-expanded", "true");
    showStep(1);
  }

  function hideForm(restoreFocus = false) {
    form.hidden = true;
    action.hidden = false;
    action.setAttribute("aria-expanded", "false");
    if (restoreFocus) action.focus();
  }

  function valuesLine(row) {
    return "Recebido " + reais(row.received) + " · Gastos " + reais(row.spent) + " · Sobra " + reais(row.net);
  }

  function ratesLine(row) {
    const minutes = Math.floor((row.endedAt - row.startedAt) / 60000);
    const hours = Math.floor(minutes / 60);
    const elapsed = hours ? hours + " h " + (minutes % 60) + " min" : minutes > 0 ? minutes + " min" : "menos de 1 min";
    const byKm = row.perKm === null ? "sem média por km" : reais(row.perKm) + "/km";
    return elapsed + " · Sobra média " + reais(row.perHour) + "/h · " + byKm;
  }

  function renderHistory(history) {
    const lastPanel = byId("turno-last"), lastBreakdown = byId("turno-last-breakdown");
    const [last, ...earlier] = history;
    lastPanel.hidden = !last;
    if (last) {
      setText("turno-last-values", valuesLine(last));
      setText("turno-last-rates", date.format(new Date(last.endedAt)) + " · " + ratesLine(last));
    }
    renderBreakdown(lastBreakdown, last?.entries, last?.cashFlow);
    const lastDetails = lastBreakdown?.closest("details");
    if (lastDetails) lastDetails.hidden = !last?.entries;

    const historyList = byId("turno-history");
    if (!historyList) return;
    historyList.hidden = earlier.length === 0;
    const historyPanel = byId("turno-history-panel") || historyList.closest("details");
    if (historyPanel) historyPanel.hidden = historyList.hidden;
    historyList.replaceChildren(...earlier.map(row => {
      const entry = element("li");
      const ended = new Date(row.endedAt);
      const time = element("time", date.format(ended));
      time.dateTime = ended.toISOString();
      entry.append(time, element("p", valuesLine(row)), element("p", ratesLine(row), "detail"));
      if (row.entries) {
        const details = element("details", undefined, "turno-breakdown-box");
        const values = element("dl");
        renderBreakdown(values, row.entries, row.cashFlow);
        details.append(element("summary", "Ver a conta"), values);
        entry.append(details);
      }
      return entry;
    }));
  }

  function refresh() {
    try {
      const state = turno.read(storage), totals = turno.today(state);
      setText("turno-received", totals.count ? reais(totals.received) : "—");
      setText("turno-spent", totals.count ? reais(totals.spent) : "—");
      setText("turno-net", totals.count ? reais(totals.net) : "—");
      byId("turno-badge").hidden = !state.active;
      setText("turno-state", state.active ? "Turno iniciado em " + date.format(new Date(state.active.startedAt)) + "." : "Sem turno em andamento.");
      action.textContent = state.active ? "Fechar turno" : "Iniciar turno";
      if (!state.active) {
        hydratedStart = null;
        hideForm();
      }
      renderHistory(state.history);
    } catch (error) { problem(error); }
  }

  action.addEventListener("click", () => {
    clearProblem();
    try {
      const state = turno.read(storage);
      if (state.active) showForm(state);
      else { turno.begin(storage); refresh(); }
    } catch (error) { problem(error); }
  });

  function advance() {
    if (form.hidden || step === 3) return;
    clearProblem();
    try {
      turno.preview(readFields(step === 1 ? income : [...income, ...costs]));
      rememberDraft();
      showStep(step + 1);
      if (step === 3) refreshPreview();
    } catch (error) { problem(error); }
  }

  function refreshPreview() {
    try { renderPreview(turno.preview(readFields())); }
    catch (error) { preview.textContent=error?.message || "Confira os dados informados."; breakdown.replaceChildren(); }
  }

  function backStep() {
    if (form.hidden || step === 1) return;
    clearProblem();
    rememberDraft();
    showStep(step - 1);
  }

  function leave() {
    if (form.hidden) return;
    clearProblem();
    rememberDraft();
    hideForm(true);
  }

  function handleBack() {
    if (form.hidden) return false;
    if (step > 1) backStep();
    else leave();
    return true;
  }

  next.addEventListener("click", advance);
  previous.addEventListener("click", backStep);
  cancel.addEventListener("click", leave);
  form.addEventListener("input", event => {
    if (!fields.includes(event.target.name)) return;
    clearProblem();
    rememberDraft();
    if(step===3)refreshPreview();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (form.hidden) return;
    if (step < 3) { advance(); return; }
    clearProblem();
    try { turno.close(storage, readFields()); }
    catch (error) { problem(error); return; }
    form.reset();
    refresh();
    setText("status", "Turno fechado e salvo.");
    const title = byId("turno-last-title");
    title.tabIndex = -1;
    title.focus();
  });

  window.VexoTurnoUI = Object.freeze({refresh, handleBack});
})();
