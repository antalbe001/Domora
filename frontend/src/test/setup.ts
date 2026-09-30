import '@testing-library/jest-dom/vitest'

// jsdom implements no layout, so it has no scrollIntoView. Every real browser
// does; stubbing it keeps the auto-scroll out of the tests' way.
Element.prototype.scrollIntoView = () => {}
