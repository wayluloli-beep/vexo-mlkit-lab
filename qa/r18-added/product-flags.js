// Release defaults for the manual beta. Query strings and storage cannot opt in.
Object.defineProperty(window, 'VexoProductFlags', {
  value: Object.freeze({ gps: false, obd2: false }),
  writable: false,
  configurable: false,
});
