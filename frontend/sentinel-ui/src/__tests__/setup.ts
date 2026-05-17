import '@testing-library/jest-dom'

// jsdom does not implement scrollIntoView — stub it so WorkflowStream's
// auto-scroll useEffect does not throw in tests.
Element.prototype.scrollIntoView = vi.fn()
