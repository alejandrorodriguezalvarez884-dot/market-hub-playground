// The two charts of a board, on TradingView's Lightweight Charts (Apache-2.0). A logo on every
// chart of a board would be most of what is seen: the page credits the library once instead
// (chartCredit), as the portal's watchlist does.
import {
  AreaSeries, CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle, createChart,
  type IChartApi, type ISeriesApi, type SeriesType, type Time,
} from "lightweight-charts";
import type { Bar, Data, Series, Widget } from "./api";
import { add, h } from "./dom";
import { price, shortDate, signedPct, toneClass } from "./format";

// The site's tokens (styles/global.css), as the chart library wants them.
export const C = {
  bg: "#0b0c0d", grid: "#17191b", text: "#8c8b86", line: "#222528", cross: "#5f5f5b", label: "#3a3e42",
  ink: "#f2f0ea", up: "#35c98f", down: "#ff6b57", up2: "rgba(53,201,143,0.16)", down2: "rgba(255,107,87,0.16)",
  volume: "rgba(242,240,234,0.13)",
};
// The lines of a comparison. Never green or red: on this site those mean a rise and a fall.
export const LINES = ["#f2f0ea", "#6f93c4", "#c9a45a", "#a388c9", "#5fb0b7", "#c98a6f", "#8c8b86", "#b7c96f"];
// The averages keep one colour each, as on the portal's watchlist.
export const AVERAGES: Record<string, { name: string; color: string }> = {
  "20": { name: "20-day", color: "#c9c7c1" }, "50": { name: "50-day", color: "#6f93c4" }, "200": { name: "200-day", color: "#c9a45a" },
};

export type Drawn = { remove(): void };

function baseChart(el: HTMLElement): IChartApi {
  return createChart(el, {
    autoSize: true,
    // Fixed, so numbers and dates read the same as the rest of the site whatever the browser's locale.
    localization: { locale: "en-US" },
    layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text, fontSize: 11,
              fontFamily: "'IBM Plex Mono', ui-monospace, monospace", attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: C.grid } },
    rightPriceScale: { borderColor: C.line },
    timeScale: { borderColor: C.line, rightOffset: 2, fixLeftEdge: true, fixRightEdge: true },
    crosshair: { mode: CrosshairMode.Magnet, vertLine: { color: C.cross, labelBackgroundColor: C.label },
                 horzLine: { color: C.cross, labelBackgroundColor: C.label } },
    handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
    handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
  });
}

// The day under the crosshair, as the bars name it.
function dayOf(time: Time | undefined): string | null {
  if (time === undefined) return null;
  if (typeof time === "string") return time;
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10);
  return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`;
}

export function chartCredit(): HTMLElement {
  const by = h("a", "hover:text-ink-strong", "TradingView");
  by.href = "https://www.tradingview.com/";
  by.target = "_blank";
  by.rel = "noopener nofollow";
  return add(h("span"), "Charts by ", by, " Lightweight Charts™.");
}

export function swatch(color: string): HTMLElement {
  const el = h("span", "inline-block h-[3px] w-4 flex-none rounded-full align-middle");
  el.style.background = color;
  return el;
}

// One instrument: candles or a line, its volume underneath, its averages on top, and a legend that
// follows the crosshair.
export function priceView(host: HTMLElement, d: Data, w: Widget, height: number): Drawn {
  const bars = d.bars ?? [];
  const box = h("div", "relative");
  box.style.height = `${height}px`;
  const legend = h("div", "pointer-events-none absolute left-0 top-0 z-10 text-[12.5px]");
  host.replaceChildren(add(box, legend));
  const chart = baseChart(box);
  const at = (b: { time: string }) => b.time as Time;
  const start = bars[0].close;
  const rising = bars[bars.length - 1].close >= start;
  // A symbol that only has closes gives bars with no range: they are drawn as a line.
  const flat = bars.every((b) => b.open === b.close && b.high === b.low);
  const candles = w.style !== "line" && !flat;
  let main: ISeriesApi<SeriesType>;
  if (candles) {
    main = chart.addSeries(CandlestickSeries, { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down, priceLineVisible: false });
    main.setData(bars.map((b) => ({ time: at(b), open: b.open, high: b.high, low: b.low, close: b.close })));
  } else {
    main = chart.addSeries(AreaSeries, { lineColor: rising ? C.up : C.down, topColor: rising ? C.up2 : C.down2, bottomColor: "rgba(0,0,0,0)", lineWidth: 2,
      priceLineVisible: false, crosshairMarkerRadius: 3, crosshairMarkerBorderColor: C.bg });
    main.setData(bars.map((b) => ({ time: at(b), value: b.close })));
  }
  main.priceScale().applyOptions({ scaleMargins: { top: 0.14, bottom: 0.22 } });
  if (bars.some((b) => b.volume)) {
    const volume = chart.addSeries(HistogramSeries, { priceScaleId: "volume", priceFormat: { type: "volume" }, color: C.volume, priceLineVisible: false, lastValueVisible: false });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
    volume.setData(bars.map((b) => ({ time: at(b), value: b.volume })));
  }
  const lines = Object.entries(d.averages ?? {}).filter(([n, points]) => AVERAGES[n] && points.length);
  for (const [n, points] of lines) {
    const line = chart.addSeries(LineSeries, { color: AVERAGES[n].color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    line.setData(points.map((p) => ({ time: at(p), value: p.value })));
  }
  chart.timeScale().fitContent();

  const byDay = new Map(bars.map((b) => [b.time, b]));
  function say(b: Bar | null) {
    const parts: (HTMLElement | null)[] = [];
    if (b) {
      parts.push(h("span", "text-muted", shortDate(b.time)));
      if (candles)
        for (const [k, v] of [["O", b.open], ["H", b.high], ["L", b.low], ["C", b.close]] as const)
          parts.push(h("span", "ml-2 text-muted", k), h("span", "num ml-1 text-ink-strong", price(v)));
      else parts.push(h("span", "num ml-2 text-ink-strong", price(b.close)));
      const since = start ? b.close / start - 1 : null;
      parts.push(h("span", `num ml-2 ${toneClass(since)}`, signedPct(since, 2)), h("span", "ml-1 text-muted", "vs. start"));
    } else {
      for (const [n] of lines) parts.push(add(h("span", "mr-3 inline-flex items-center gap-1.5 text-muted"), swatch(AVERAGES[n].color), AVERAGES[n].name));
    }
    legend.replaceChildren(parts.length ? add(h("div", "bg-page/85 pr-2"), ...parts) : "");
  }
  chart.subscribeCrosshairMove((p) => say(byDay.get(dayOf(p.time) ?? "") ?? null));
  say(null);
  return { remove: () => chart.remove() };
}

// Several instruments since the same day, each a line from zero, in percent. The legend carries
// each one's return: over the whole range, or up to the day under the crosshair.
export function compareView(host: HTMLElement, d: Data, height: number): Drawn {
  const series = (d.series ?? []).filter((s) => s.points.length);
  const legend = h("div", "mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px]");
  const box = h("div");
  box.style.height = `${height}px`;
  host.replaceChildren(legend, box);
  const chart = baseChart(box);
  chart.applyOptions({ localization: { locale: "en-US", priceFormatter: (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%` } });
  const drawn = series.map((s, i) => {
    const line = chart.addSeries(LineSeries, { color: LINES[i % LINES.length], lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
      crosshairMarkerRadius: 3, crosshairMarkerBorderColor: C.bg });
    line.setData(s.points.map((p) => ({ time: p.time as Time, value: +(p.value * 100).toFixed(2) })));
    if (!i) line.createPriceLine({ price: 0, color: C.cross, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: false, title: "" });
    return { s, line, color: LINES[i % LINES.length] };
  });
  chart.timeScale().fitContent();

  function say(values: Map<Series, number | null> | null) {
    legend.replaceChildren(...drawn.map(({ s, color }) => {
      const v = values ? values.get(s) ?? null : s.total;
      const name = h("span", "font-medium text-ink-strong", s.ticker);
      name.title = s.name;
      return add(h("span", "inline-flex items-center gap-1.5"), swatch(color), name, h("span", `num ${toneClass(v)}`, signedPct(v, 1)));
    }));
  }
  chart.subscribeCrosshairMove((p) => {
    if (p.time === undefined) return say(null);
    say(new Map(drawn.map(({ s, line }) => {
      const point = p.seriesData.get(line) as { value?: number } | undefined;
      return [s, typeof point?.value === "number" ? point.value / 100 : null];
    })));
  });
  say(null);
  return { remove: () => chart.remove() };
}
