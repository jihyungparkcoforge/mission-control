import "@testing-library/jest-dom/vitest";

// jsdom does no layout, so charts would measure 0×0 and render nothing. Report a fixed size instead.
class ResizeObserverStub {
  constructor(private cb: ResizeObserverCallback) {}
  observe(target: Element) {
    const rect = { width: 520, height: 78, top: 0, left: 0, right: 520, bottom: 78, x: 0, y: 0 };
    this.cb([{ target, contentRect: rect } as unknown as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom lacks <dialog>.showModal/close.
HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) { this.setAttribute("open", ""); };
HTMLDialogElement.prototype.close ??= function (this: HTMLDialogElement) { this.removeAttribute("open"); };
