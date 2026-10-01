#!/usr/bin/env node
// Stage 1 for the cinematic harness: read the landing page, write brief.json (angles, claims checked
// verbatim against the page), and build the brand kit (palette, fonts, real logo, real product images).
//   node vendor/brief/run-brief.mjs --url <page> --out <run dir> [--product ".."] [--audience ".."] [--market ".."] [--logo file] [--asset file ...]
import fs from "node:fs";
import path from "node:path";
import { readSite } from "./site.mjs";
import { buildBrief } from "./brief.mjs";
import { resolvePalette, resolveFonts, resolveLogo, resolveAssets } from "./brandkit.mjs";
import { checkKeys, ledger } from "./providers.mjs";

const a = process.argv.slice(2), opt = { assets: [] };
for (let i = 0; i < a.length; i++) {
  const k = a[i].replace(/^--/, ""), v = a[i + 1];
  if (k === "asset") { opt.assets.push(v); i++; } else if (v && !v.startsWith("--")) { opt[k] = v; i++; } else opt[k] = true;
}
if (!opt.url || !opt.out) { console.error("usage: run-brief.mjs --url <page> --out <dir>"); process.exit(2); }
const problems = checkKeys({ needImage: false });
if (problems.length) { console.error(problems.join("\n")); process.exit(2); }
const dir = path.resolve(opt.out), bk = path.join(dir, "brandkit");
fs.mkdirSync(bk, { recursive: true });
const W = (f, o) => fs.writeFileSync(path.join(dir, f), JSON.stringify(o, null, 2));
console.log(`reading ${opt.url}`);
const site = await readSite(opt.url, { pageText: opt["page-text"] ? fs.readFileSync(opt["page-text"], "utf8") : null });
W("site.json", { ...site, text: site.text.slice(0, 20000) });
const brief = await buildBrief(site, { product: opt.product, audience: opt.audience, competitors: (opt.competitors || "").split(",").filter(Boolean), market: opt.market });
W("brief.json", brief);
const palette = resolvePalette(brief, site);
const fonts = await resolveFonts(path.join(bk, "fonts"), brief, site, { display: opt["font-display"], body: opt["font-body"] });
const logo = await resolveLogo(bk, brief, site, opt.logo);
const assets = await resolveAssets(path.join(bk, "assets"), brief, site, opt.assets);
W("brandkit.json", { brand: brief.brand, palette, fonts, logo, assets, built_at: new Date().toISOString() });
W("brief_ledger.json", ledger);
const v = brief.claims.filter((c) => c.status === "verified").length;
console.log(JSON.stringify({ brand: brief.brand, claims: brief.claims.length, verified: v, logo: logo ? logo.source : null, assets: assets.length, palette: palette.primary, usd: Math.round(ledger.total * 1000) / 1000 }));
