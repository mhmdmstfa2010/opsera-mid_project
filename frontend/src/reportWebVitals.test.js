import reportWebVitals from './reportWebVitals';

// reportWebVitals guards on the callback being a real function and then
// dynamically imports `web-vitals`. That library touches
// performance.getEntriesByName and PerformanceObserver, which jsdom does not
// implement, so the metrics path cannot be exercised here without stubbing the
// whole performance API. What is verifiable — and what matters — is the guard:
// anything that is not a callable is ignored instead of throwing.
describe('reportWebVitals', () => {
    it('ignores a missing callback', () => {
        expect(() => reportWebVitals()).not.toThrow();
    });

    it('ignores a callback that is not a function', () => {
        expect(() => reportWebVitals('nope')).not.toThrow();
        expect(() => reportWebVitals(42)).not.toThrow();
        expect(() => reportWebVitals({})).not.toThrow();
        expect(() => reportWebVitals(null)).not.toThrow();
    });
});
