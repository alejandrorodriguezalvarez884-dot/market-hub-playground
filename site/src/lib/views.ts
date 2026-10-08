// The two views of a board that are not charts: the ruler (every move on one scale, as on the
// portal's Today page) and the table.
import type { Column, Data, RulerRow, TableRow } from "./api";
import type { Drawn } from "./charts";
import { add, h } from "./dom";
import { money, mult, num, pct, price, signedPct, toneClass, type N } from "./format";
import { hubQuoteUrl } from "./site";

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const STILL: Drawn = { remove() {} };

// A stock or a fund has its page on the portal; an index, a future or a coin is named as it is.
function symbol(ticker: string, name: string, cls: string): HTMLElement {
  const plain = /^[A-Z][A-Z.\-]*$/.test(ticker) && !ticker.endsWith("-USD");
  const el = plain ? h("a", `${cls} hover:underline`, ticker) : h("span", cls, ticker);
  if (el instanceof HTMLAnchorElement) el.href = hubQuoteUrl(ticker);
  el.title = name;
  return el;
}

// --- The ruler -----------------------------------------------------------------------------------

// The half-width of a ruler, as a fraction: the first round figure that holds the largest move.
const STEPS = [0.01, 0.02, 0.03, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 5, 10];
export function rulerScale(moves: (number | null)[]): number {
  const max = Math.max(0, ...moves.filter(isNum).map(Math.abs));
  return STEPS.find((s) => s >= max - 1e-9) ?? max;
}

// One mark on the ruler: a stem from zero and a dot at the move.
function track(move: number | null, scale: number): HTMLElement {
  const el = h("div", "track");
  el.setAttribute("aria-hidden", "true");
  if (!isNum(move)) return el;
  const reach = Math.min(1, Math.abs(move) / scale) * 50; // % of the track, from the middle
  const tone = move > 0 ? "up" : move < 0 ? "down" : "";
  const fill = tone === "up" ? "bg-up" : tone === "down" ? "bg-down" : "bg-muted";
  const stem = h("span", `track-stem ${fill}`);
  stem.style.width = `${reach}%`;
  stem.style[move < 0 ? "right" : "left"] = "50%";
  const dot = h("span", `track-dot ${fill} ${tone}`);
  dot.style.left = `${50 + (move < 0 ? -reach : reach)}%`;
  return add(el, stem, dot);
}

export function rulerView(host: HTMLElement, d: Data): Drawn {
  const rows = (d.rows ?? []) as RulerRow[];
  const scale = rulerScale(rows.map((r) => r.move));
  const end = `${+(scale * 100).toFixed(1)}%`;
  const axis = add(h("div", "ruler-axis"), h("span", "", `−${end}`), h("span", "", "0"), h("span", "", `+${end}`));
  host.replaceChildren(add(h("div", "ruler"),
    add(h("div", "ruler-row !py-0 pb-1"), h("span"), h("span", "ruler-value"), axis, h("span")),
    ...rows.map((r) => add(h("div", "ruler-row"),
      add(h("span", "flex min-w-0 items-baseline gap-2"), symbol(r.ticker, r.name, "flex-none font-medium text-ink-strong"),
        h("span", "truncate text-[12.5px] text-muted", r.name)),
      h("span", "ruler-value num text-right text-[13px] text-ink", price(r.price)),
      track(r.move, scale),
      h("span", `num text-right text-[13px] ${toneClass(r.move)}`, signedPct(r.move, 2))))));
  return STILL;
}

// --- The table -----------------------------------------------------------------------------------

function cell(kind: string, v: number | string | null): { text: string; cls: string } {
  if (kind === "text") return { text: typeof v === "string" && v ? v : "—", cls: "!font-sans" };
  const n = (typeof v === "number" ? v : null) as N;
  switch (kind) {
    case "price": return { text: price(n), cls: "text-ink-strong" };
    case "spct": return { text: signedPct(n, 1), cls: toneClass(n) };
    case "pct": return { text: pct(n, 1), cls: "" };
    case "money": return { text: money(n), cls: "" };
    case "mult": return { text: mult(n), cls: "" };
    default: return { text: num(n), cls: "" };
  }
}

// Rows by ticker, a figure per column. A column's heading sorts by it: first from the highest,
// then from the lowest; rows without the figure stay last.
export function tableView(host: HTMLElement, d: Data): Drawn {
  const columns = d.columns ?? [];
  const rows = (d.rows ?? []) as TableRow[];
  let sort: { key: string; down: boolean } | null = null;

  function ordered(): TableRow[] {
    if (!sort) return rows;
    const { key, down } = sort;
    const has = (r: TableRow) => r.values[key] !== null && r.values[key] !== undefined;
    return [...rows].sort((a, b) => {
      if (!has(a) || !has(b)) return +has(b) - +has(a);
      const x = a.values[key]!, y = b.values[key]!;
      const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return down ? -order : order;
    });
  }

  function heading(c: Column): HTMLElement {
    const th = h("th");
    th.scope = "col";
    const b = h("button", "hover:text-ink-strong", c.label);
    b.type = "button";
    if (sort?.key === c.key) {
      th.setAttribute("aria-sort", sort.down ? "descending" : "ascending");
      b.classList.add("text-ink-strong");
      b.append(sort.down ? " ↓" : " ↑");
    }
    b.addEventListener("click", () => {
      sort = sort?.key === c.key ? (sort.down ? { key: c.key, down: false } : null) : { key: c.key, down: true };
      draw();
    });
    return add(th, b);
  }

  function draw() {
    const first = h("th", "", "");
    first.scope = "col";
    const table = add(h("table", "data-table"),
      add(h("thead"), add(h("tr"), first, ...columns.map(heading))),
      add(h("tbody"), ...ordered().map((r) => {
        const name = add(h("th", "!py-2 pr-3 text-left font-normal"),
          symbol(r.ticker, r.name, "font-medium text-ink-strong"), h("span", "block max-w-[14rem] truncate text-[12.5px] text-muted", r.name));
        name.scope = "row";
        return add(h("tr"), name, ...columns.map((c) => {
          const { text, cls } = cell(c.kind, r.values[c.key] ?? null);
          return h("td", cls, text);
        }));
      })));
    host.replaceChildren(add(h("div", "overflow-x-auto"), table));
  }
  draw();
  return STILL;
}
