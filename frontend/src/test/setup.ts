import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// jsdom has no layout, so it leaves these browser APIs out.
Element.prototype.scrollIntoView = vi.fn();
window.matchMedia = vi.fn().mockReturnValue({ matches: false });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
