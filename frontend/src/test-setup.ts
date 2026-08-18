import '@testing-library/jest-dom';

// jsdom no implementa ResizeObserver, que recharts usa en ResponsiveContainer.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
}
