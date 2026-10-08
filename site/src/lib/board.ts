// The board: the widgets a reader has asked for, in order. It lives here, in the page: nothing
// about it is kept anywhere else. The chat changes it (a whole new board comes back from each
// turn) and so does the reader by hand: range, style, size, order and removal.
import { figures, type Catalog, type Data, type Size, type Widget } from "./api";
import { compareView, priceView, type Drawn } from "./charts";
import { add, button, h } from "./dom";
import { price, shortDate, signedPct, toneClass } from "./format";
import { rulerView, tableView } from "./views";

// How much of the board's width a size takes, by the board's own width (not the window's).
const SPAN: Record<Size, string> = {
  s: "col-span-12 @2xl:col-span-6 @5xl:col-span-4",
  m: "col-span-12 @4xl:col-span-6",
  l: "col-span-12",
};
const SIZES: [Size, string][] = [["s", "Small: a third of the board"], ["m", "Medium: half the board"], ["l", "Large: the full width"]];
const PERIOD: Record<string, string> = { "1D": "Today", "1W": "One week", "1M": "One month", "3M": "Three months", "6M": "Six months",
                                         YTD: "This year", "1Y": "One year", "2Y": "Two years", "5Y": "Five years" };

type Slot = { widget: Widget; el: HTMLElement; title: HTMLElement; note: HTMLElement; controls: HTMLElement; tools: HTMLElement;
              body: HTMLElement; foot: HTMLElement; drawn: Drawn | null; data: Data | null; asked: string; seq: number };
export type Board = { get(): Widget[]; set(next: Widget[], fresh?: string[]): void };

const list = (tickers: string[]) => (tickers.length > 4 ? `${tickers.slice(0, 3).join(", ")} and ${tickers.length - 3} more` : tickers.join(", "));
// What decides a widget's figures: a change to anything else redraws nothing.
const asks = (w: Widget) => JSON.stringify([w.type, w.tickers, w.range, w.style, w.averages, w.columns]);

export function createBoard(host: HTMLElement, catalog: Catalog, onChange: (board: Widget[]) => void): Board {
  let widgets: Widget[] = [];
  const slots = new Map<string, Slot>();

  // --- Changes by hand ---------------------------------------------------------------------------

  const patch = (id: string, change: Partial<Widget>) => set(widgets.map((w) => (w.id === id ? { ...w, ...change } : w)));
  const remove = (id: string) => set(widgets.filter((w) => w.id !== id));
  function shift(id: string, by: number) {
    const from = widgets.findIndex((w) => w.id === id);
    const to = from + by;
    if (from < 0 || to < 0 || to >= widgets.length) return;
    const next = [...widgets];
    next.splice(to, 0, ...next.splice(from, 1));
    set(next);
    slots.get(id)?.tools.querySelector<HTMLElement>(`[data-shift="${by}"]`)?.focus();
  }

  // --- One widget --------------------------------------------------------------------------------

  function slot(w: Widget): Slot {
    const title = h("h3", "sec-title min-w-0 truncate");
    const note = h("p", "sec-note");
    const tools = h("div", "widget-tools");
    const controls = h("div", "flex flex-wrap items-center gap-x-6 gap-y-1 pb-3 empty:hidden");
    const body = h("div");
    const foot = h("p", "mt-2 text-[12.5px] text-muted empty:hidden");
    const el = add(h("section", "sec widget"),
      add(h("header", "flex items-start justify-between gap-3 pb-2"), add(h("div", "min-w-0"), title, note), tools),
      controls, body, foot);
    el.dataset.id = w.id;
    return { widget: w, el, title, note, controls, tools, body, foot, drawn: null, data: null, asked: "", seq: 0 };
  }

  function tabs(items: string[], current: string | undefined, label: string, pick: (v: string) => void, names?: Record<string, string>): HTMLElement {
    const el = h("div", "tabs");
    el.setAttribute("role", "group");
    el.setAttribute("aria-label", label);
    for (const v of items) {
      const b = button("tab-btn", names?.[v] ?? v, names?.[v] ?? PERIOD[v] ?? v, () => pick(v));
      b.setAttribute("aria-selected", String(v === current));
      b.setAttribute("aria-pressed", String(v === current));
      el.append(b);
    }
    return el;
  }

  // The frame of a widget: its title, what it can be set to by hand, and its tools. Drawn again on
  // every change, which costs nothing; the figures are only asked for again when they would differ.
  function frame(s: Slot) {
    const { widget: w, data: d } = s;
    s.el.className = `sec widget ${SPAN[w.size]}`;
    const ranges = catalog.kinds[w.type].ranges;
    s.controls.replaceChildren(
      ranges.length ? tabs(ranges, w.range, "Range", (range) => patch(w.id, { range })) : "",
      w.type === "price" ? tabs(catalog.styles, w.style, "Style", (style) => patch(w.id, { style: style as Widget["style"] }), { candles: "Candles", line: "Line" }) : "");
    const at = widgets.findIndex((x) => x.id === w.id);
    const earlier = button("tool-btn", "←", "Move earlier on the board", () => shift(w.id, -1));
    const later = button("tool-btn", "→", "Move later on the board", () => shift(w.id, 1));
    earlier.dataset.shift = "-1", later.dataset.shift = "1";
    earlier.disabled = at <= 0, later.disabled = at === widgets.length - 1;
    s.tools.replaceChildren(
      ...SIZES.map(([size, label]) => {
        const b = button("tool-btn", size.toUpperCase(), label, () => patch(w.id, { size }));
        b.setAttribute("aria-pressed", String(w.size === size));
        return b;
      }),
      h("span", "mx-1 h-3 w-px bg-line"), earlier, later, button("tool-btn", "×", "Remove from the board", () => remove(w.id)));

    // The title the reader gave it, or one made from what it shows.
    const period = PERIOD[w.range ?? ""] ?? "";
    let name: (Node | string)[] = [list(w.tickers)], says: (Node | string)[] = [];
    if (w.type === "price") {
      name = [w.tickers[0], d?.name && d.name !== w.tickers[0] ? h("span", "ml-2 font-normal text-muted", d.name) : ""];
      if (d?.bars?.length) says = [h("span", "num text-ink-strong", price(d.last)), " ", h("span", `num ${toneClass(d.change)}`, signedPct(d.change, 2)), ` ${period.toLowerCase()}`];
    } else if (w.type === "compare") says = [d?.since ? `Return since ${shortDate(d.since)}` : `Return over ${period.toLowerCase()}`];
    else if (w.type === "ruler") name = [`${period}, on one scale`];
    if (w.title) {
      if (w.type !== "price") says = [list(w.tickers), says.length ? " · " : "", ...says];
      name = [w.title];
    }
    s.title.replaceChildren(...name);
    s.title.title = w.title || (w.type === "price" && d?.name ? `${w.tickers[0]} · ${d.name}` : s.title.textContent ?? "");
    s.note.replaceChildren(...says);
    s.foot.textContent = d?.missing?.length && shows(w, d) ? `No data for ${d.missing.join(", ")}.` : "";
  }

  const shows = (w: Widget, d: Data) => !!(w.type === "price" ? d.bars?.length : w.type === "compare" ? d.series?.length : d.rows?.length);

  function message(s: Slot, text: string, retry?: () => void) {
    s.drawn?.remove();
    s.drawn = null;
    s.body.replaceChildren(add(h("div", "flex min-h-[120px] flex-col items-center justify-center gap-3 text-center text-sm text-muted"),
      h("p", "max-w-xs", text), retry ? button("btn btn-ghost py-1 text-[13px]", "Try again", "Try again", retry) : null));
  }

  function draw(s: Slot) {
    const { widget: w, data: d } = s;
    if (!d) return;
    s.drawn?.remove();
    s.drawn = null;
    if (!shows(w, d)) return message(s, d.missing.length ? `No data for ${d.missing.join(", ")}. Check the ticker.` : "Nothing to show.");
    const height = w.size === "l" ? 380 : 300;
    s.drawn = w.type === "price" ? priceView(s.body, d, w, height) : w.type === "compare" ? compareView(s.body, d, height)
      : w.type === "ruler" ? rulerView(s.body, d) : tableView(s.body, d);
  }

  async function load(s: Slot) {
    const seq = ++s.seq;
    s.asked = asks(s.widget);
    if (!s.data) {
      const chart = s.widget.type === "price" || s.widget.type === "compare";
      s.body.replaceChildren(h("div", `skeleton ${chart ? "h-[300px]" : "h-[160px]"}`));
    } else s.body.classList.add("opacity-50");
    try {
      const data = await figures(s.widget);
      if (seq !== s.seq) return; // asked again since: this answer is of an older setting
      s.data = data;
      draw(s);
    } catch (e) {
      if (seq !== s.seq) return;
      s.data = null;
      message(s, e instanceof Error ? e.message : "Something failed.", () => load(s));
    } finally {
      if (seq === s.seq) s.body.classList.remove("opacity-50"), frame(s);
    }
  }

  // --- The whole board ---------------------------------------------------------------------------

  // Puts the board in a new state: widgets that are gone leave, new ones arrive, the rest keep
  // their place in the page and only fetch again if what they show changed. `fresh` are the ones
  // a turn of the chat made or changed: they are brought into view.
  function set(next: Widget[], fresh: string[] = []) {
    widgets = next;
    for (const [id, s] of slots) {
      if (next.some((w) => w.id === id)) continue;
      s.seq++;
      s.drawn?.remove();
      s.el.remove();
      slots.delete(id);
    }
    next.forEach((w, i) => {
      const s = slots.get(w.id) ?? slot(w);
      slots.set(w.id, s);
      s.widget = w;
      if (host.children[i] !== s.el) host.insertBefore(s.el, host.children[i] ?? null);
      frame(s);
      if (s.asked !== asks(w)) void load(s);
    });
    const first = fresh.map((id) => slots.get(id)).find(Boolean);
    for (const id of fresh) {
      const el = slots.get(id)?.el;
      if (!el) continue;
      el.classList.remove("widget-new");
      void el.offsetWidth; // so the animation runs again on a widget that was already here
      el.classList.add("widget-new");
    }
    first?.el.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
    onChange(widgets);
  }

  return { get: () => widgets, set };
}
