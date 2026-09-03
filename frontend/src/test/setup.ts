import '@testing-library/jest-dom/vitest'

// jsdom no implementa scrollIntoView, y el chat lo llama al montar para bajar
// al último mensaje. Sin este stub cualquier render lanza TypeError.
Element.prototype.scrollIntoView = () => {}
