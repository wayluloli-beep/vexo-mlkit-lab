"use strict";
(() => {
  const byId = id => document.getElementById(id);
  if (!byId("local-feedback")) return;

  const category = byId("feedback-category");
  const description = byId("feedback-description");
  const preview = byId("feedback-preview");
  const report = byId("feedback-report");
  const status = byId("feedback-status");

  function resetPreview() {
    preview.hidden = true;
    report.value = "";
    status.textContent = "";
  }

  category.addEventListener("change", resetPreview);
  description.addEventListener("input", resetPreview);

  byId("feedback-generate").addEventListener("click", () => {
    if (!category.reportValidity()) return;

    let installedVersion;
    try { installedVersion = window.VexoAndroidOcr?.appVersion?.(); } catch (_) {}
    const version = installedVersion || document.querySelector("#sobre dd")?.textContent.trim() || "indisponível";
    const notes = description.value.trim();
    report.value = `Relato do Vexo\nVersão: ${version}\nProblema: ${category.value}${notes ? `\n\n${notes}` : ""}`;
    status.textContent = "";
    preview.hidden = false;
    report.focus();
  });

  byId("feedback-copy").addEventListener("click", async () => {
    if (preview.hidden || !report.value) return;
    const text = report.value;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        if (report.value === text) status.textContent = "Relato copiado.";
        return;
      }
    } catch (_) {}
    if (report.value !== text) return;
    report.focus();
    report.select();
    status.textContent = "Texto selecionado. Use a opção Copiar do aparelho.";
  });
})();
