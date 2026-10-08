// Site-wide constants and links.
export const SITE_NAME = "Playground";

// The tool is a section of Market Hub: it carries the portal's private navigation, and a ticker
// links to its page on the portal.
const site = (v: string | undefined, fallback: string) => (v ?? fallback).replace(/\/$/, "");
export const HUB_URL = site(import.meta.env.PUBLIC_HUB_URL, "https://themarkethub.app");
export const RADAR_URL = site(import.meta.env.PUBLIC_RADAR_URL, "https://radar.themarkethub.app");
export const FUNDAMENTALS_URL = site(import.meta.env.PUBLIC_FUNDAMENTALS_URL, "https://fundamentals.themarkethub.app");
export const hubQuoteUrl = (ticker: string) => `${HUB_URL}/quote/?t=${encodeURIComponent(ticker)}`;

// Every internal link goes through here, so the site works under a sub-path too.
export function link(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}${path}`;
}

// The API lives on the same origin in production; in development it is another port.
export const API = (import.meta.env.PUBLIC_API_URL ?? "").replace(/\/$/, "");
