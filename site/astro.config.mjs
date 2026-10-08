// @ts-check
import { existsSync, readFileSync } from "node:fs";
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

// The public address, for canonical links. It lives in the file SITE_URL (one line) so that
// moving to a domain is a one-line change; without the file the links are left relative.
const file = new URL("./SITE_URL", import.meta.url);
const site = existsSync(file) ? readFileSync(file, "utf8").trim() : undefined;

export default defineConfig({
  site,
  trailingSlash: "always",
  vite: {
    plugins: [tailwindcss()],
  },
});
