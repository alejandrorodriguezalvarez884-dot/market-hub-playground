// Number formatting. Every formatter takes null and returns an em dash for it.
export type N = number | null | undefined;
const DASH = "—";
const ok = (v: N): v is number => typeof v === "number" && Number.isFinite(v);

export function money(v: N, digits = 1): string {
  if (!ok(v)) return DASH;
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (a >= 1e12) return `${sign}$${(a / 1e12).toFixed(digits + 1)}T`;
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(digits)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(digits)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(digits)}K`;
  return `${sign}$${a.toFixed(2)}`;
}

export function price(v: N): string {
  return ok(v) ? `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : DASH;
}

export function pct(v: N, digits = 1, signed = false): string {
  if (!ok(v)) return DASH;
  const s = (v * 100).toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s.replace("-", "−")}%`;
}

export const signedPct = (v: N, digits = 1) => pct(v, digits, true);

export function mult(v: N, digits = 1): string {
  return ok(v) ? `${v.toFixed(digits)}×` : DASH;
}

export function num(v: N, digits = 2): string {
  return ok(v) ? v.toLocaleString("en-US", { maximumFractionDigits: digits }) : DASH;
}

export function count(v: N): string {
  return ok(v) ? Math.round(v).toLocaleString("en-US") : DASH;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

// The formatter for each kind of figure, so tables and charts agree.
export type Kind = "money" | "pct" | "spct" | "mult" | "num" | "price" | "count";
export function fmt(kind: Kind, v: N): string {
  switch (kind) {
    case "money":
      return money(v);
    case "pct":
      return pct(v);
    case "spct":
      return signedPct(v);
    case "mult":
      return mult(v);
    case "price":
      return price(v);
    case "count":
      return count(v);
    default:
      return num(v);
  }
}

// A quote in its own unit: dollars for stocks and commodities, points for indices, a yield for
// rates, four decimals for currency pairs.
export function level(v: N, kind: string): string {
  if (!ok(v)) return DASH;
  if (kind === "rate") return `${v.toFixed(3)}%`;
  if (kind === "fx") return v.toFixed(v < 10 ? 4 : 2);
  const s = v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return kind === "stock" || kind === "etf" ? `$${s}` : s;
}

export function change(v: N, kind: string): string {
  if (!ok(v)) return DASH;
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const a = Math.abs(v);
  return `${sign}${kind === "fx" && a < 1 ? a.toFixed(4) : a.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function compact(v: N): string {
  if (!ok(v)) return DASH;
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(Math.round(v));
}

export function timeAgo(iso: string, now = Date.now()): string {
  const m = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const hrs = Math.round(m / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const d = Math.round(hrs / 24);
  return `${d}d ago`;
}

export const toneClass = (v: N) => (ok(v) ? (v > 0 ? "up" : v < 0 ? "down" : "text-muted") : "text-muted");
