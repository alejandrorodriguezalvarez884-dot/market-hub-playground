// What the service answers (src/playground/api.py), and the calls to it.
import { API } from "./site";

export type Kind = "price" | "compare" | "ruler" | "table";
export type Size = "s" | "m" | "l";
// A widget says what to show and never carries a figure (src/playground/widgets.py).
export type Widget = {
  id: string; type: Kind; title: string; tickers: string[]; size: Size;
  range?: string; style?: "candles" | "line"; averages?: number[]; columns?: string[];
};

export type Bar = { time: string; open: number; high: number; low: number; close: number; volume: number };
export type Point = { time: string; value: number };
export type Series = { ticker: string; name: string; points: Point[]; total: number | null };
export type RulerRow = { ticker: string; name: string; price: number; move: number | null };
export type Column = { key: string; label: string; kind: string };
export type TableRow = { ticker: string; name: string; values: Record<string, number | string | null> };
// The figures of a widget: each kind brings its own part.
export type Data = {
  missing: string[]; sample: boolean;
  ticker?: string; name?: string; bars?: Bar[]; averages?: Record<string, Point[]>; last?: number; change?: number | null;
  since?: string; series?: Series[];
  rows?: (RulerRow | TableRow)[];
  columns?: Column[];
};

export type Catalog = {
  kinds: Record<Kind, { ranges: string[]; tickers: [number, number] }>;
  metrics: Column[]; styles: string[]; averages: number[];
  limits: { widgets: number; message: number; columns: number };
  sample: boolean;
};
export type Turn = { role: "user" | "assistant"; text: string };
export type ChatOut = { reply: string; board: Widget[]; changed: string[]; problems: string[] };

async function ask<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: body === undefined ? "GET" : "POST", credentials: "include",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    // The service says what happened in words meant for the reader.
    const detail = await res.json().then((b: { detail?: unknown }) => b.detail, () => null);
    throw new Error(typeof detail === "string" ? detail : "Something failed. Try again in a moment.");
  }
  return res.json() as Promise<T>;
}

export const catalog = () => ask<Catalog>("/api/catalog");
export const figures = (widget: Widget) => ask<Data>("/api/data", { widget });
export const chat = (message: string, board: Widget[], history: Turn[]) => ask<ChatOut>("/api/chat", { message, board, history });
