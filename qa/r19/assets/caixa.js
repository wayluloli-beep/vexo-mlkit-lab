(() => {
  'use strict';

  const labels = { cash: 'dinheiro', pix: 'Pix', reservePerKm: 'reserva por km' };

  function fail(field, message) {
    throw Object.assign(new Error(message), { field });
  }

  function cents(input, field) {
    if (input == null) return null;
    const invalid = () => fail(field, `Confira o valor de ${labels[field]}.`);
    if (typeof input !== 'string') invalid();
    const raw = input.trim();
    if (raw === '') return null;
    const normalized = raw.includes(',')
      ? raw.replace(/^(\d{1,3}(?:\.\d{3})+)(?=,)/, whole => whole.replace(/\./g, '')).replace(',', '.')
      : raw;
    const parts = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalized);
    if (!parts) invalid();
    const value = Number(parts[1]) * 100 + Number((parts[2] ?? '').padEnd(2, '0'));
    if (!Number.isSafeInteger(value)) invalid();
    return value;
  }

  function summarize({ received, cash: cashInput, pix: pixInput, reservePerKm, meters }) {
    if (!Number.isSafeInteger(received) || received < 0) fail('received', 'Confira o total recebido.');

    const cash = cents(cashInput, 'cash');
    const pix = cents(pixInput, 'pix');
    const afterCash = received - (cash ?? 0);
    if (afterCash < 0) fail('cash', 'O valor em dinheiro não pode ultrapassar o total recebido.');
    const unclassified = afterCash - (pix ?? 0);
    if (unclassified < 0) fail('pix', 'Dinheiro e Pix não podem ultrapassar o total recebido.');

    const rate = cents(reservePerKm, 'reservePerKm');
    if (meters != null && (!Number.isSafeInteger(meters) || meters < 0)) {
      fail('meters', 'Confira a distância percorrida.');
    }
    let reserve = null;
    if (rate !== null && meters != null) {
      // Keep the exact product until rounding to the nearest cent. Reserve is not a turno expense.
      reserve = Number((BigInt(rate) * BigInt(meters) + 500n) / 1000n);
      if (!Number.isSafeInteger(reserve)) fail('reservePerKm', 'A reserva calculada é muito alta.');
    }

    return { cash, pix, unclassified, reserve, rate };
  }

  window.VexoCaixa = Object.freeze({ summarize });
})();
