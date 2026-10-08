// Tiny DOM helpers. Everything that comes from the API, the model or the reader goes in as text,
// never as markup.
export function h<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

export function add<T extends Element>(parent: T, ...children: (Node | string | null | undefined | false)[]): T {
  for (const c of children) if (c) parent.append(c);
  return parent;
}

export function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}): SVGElementTagNameMap[K] {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
}

// A button that is a word or a sign, with what it does said for a screen reader.
export function button(cls: string, text: string, label: string, onClick: () => void): HTMLButtonElement {
  const b = h("button", cls, text);
  b.type = "button";
  if (label !== text) b.setAttribute("aria-label", label), (b.title = label);
  b.addEventListener("click", onClick);
  return b;
}

// Market Hub's mark: the line of zero and a move to its right.
export function mark(cls: string): SVGSVGElement {
  const el = svg("svg", { viewBox: "0 0 20 20", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "aria-hidden": "true", class: cls });
  return add(el, svg("path", { d: "M4 2v16M4 10h8" }), svg("circle", { cx: 14.5, cy: 10, r: 2.75, fill: "currentColor", stroke: "none" }));
}
