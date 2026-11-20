"use strict";
(() => {
  const root = document.documentElement;
  const oled = document.getElementById("comfort-oled");
  const hand = document.getElementById("comfort-hand");
  const status = document.getElementById("comfort-status");
  const themeColor = document.querySelector('meta[name="theme-color"]');
  const defaultThemeColor = themeColor?.content;
  const oledKey = "vexo.comfort.oled.v1";
  const handKey = "vexo.comfort.hand.v1";
  const validHand = value => value === "left" || value === "right" ? value : "off";

  function read(key) {
    try { return window.localStorage.getItem(key); }
    catch (_) { return null; }
  }

  function applyOled(on) {
    if (on) root.dataset.comfortOled = "on";
    else delete root.dataset.comfortOled;
    if (oled) oled.checked = on;
    if (themeColor) themeColor.content = on ? "#000000" : defaultThemeColor;
  }

  function applyHand(value) {
    const side = validHand(value);
    if (side === "off") delete root.dataset.comfortHand;
    else root.dataset.comfortHand = side;
    if (hand) hand.value = side;
  }

  function save(key, value) {
    try {
      window.localStorage.setItem(key, value);
      if (status) status.textContent = "";
    } catch (_) {
      if (status) status.textContent = "Não deu para salvar. A mudança vale só nesta tela.";
    }
  }

  applyOled(read(oledKey) === "on");
  applyHand(read(handKey));
  oled?.addEventListener("change", () => {
    applyOled(oled.checked);
    save(oledKey, oled.checked ? "on" : "off");
  });
  hand?.addEventListener("change", () => {
    applyHand(hand.value);
    save(handKey, hand.value);
  });
  window.addEventListener("storage", event => {
    if (event.key === oledKey || event.key === null) applyOled(read(oledKey) === "on");
    if (event.key === handKey || event.key === null) applyHand(read(handKey));
  });
})();
