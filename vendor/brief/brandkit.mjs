// The brand kit the compositor sets type with: real fonts, a real logo, a palette with roles.
//
// Two rules carry over from production:
// - Never invent or redraw a logo. If no real logo file is found and verified, ads ship without
//   one and the report says so. Supply one with --logo.
// - Type is set by code in the brand's own font files, so a font that cannot be loaded falls
//   back to a named, visible substitute (recorded in brandkit.json), never a silent one.

import fs from "node:fs";
import path from "node:path";
import { Resvg } from "@resvg/resvg-js";
import { fetchBytes, vision, toDataUrl } from "./providers.mjs";
import { sniffImage, luminance, saturation, hexToRgb, rgbToHex } from "./site.mjs";

const HEX = /^#[0-9a-f]{6}$/i;

// ---- palette -----------------------------------------------------------------------------------
function shade(hex, f) { return rgbToHex(hexToRgb(hex).map((v) => v * f)); }
function tint(hex, f) { return rgbToHex(hexToRgb(hex).map((v) => v + (255 - v) * f)); }

export function resolvePalette(brief, site) {
  const found = site.colours.map((c) => c.hex);
  const p = brief.palette || {};
  const pick = (v, fb) => (HEX.test(v || "") ? v.toLowerCase() : fb);
  const saturated = site.colours.filter((c) => c.sat > 0.35 && c.lum > 0.03 && c.lum < 0.8).map((c) => c.hex);
  const primary = pick(p.primary, saturated[0] || found[0] || "#1f4fd8");
  const dark = pick(p.dark, luminance(primary) < 0.08 ? primary : shade(primary, 0.35));
  const light = pick(p.light, site.colours.find((c) => c.lum > 0.85)?.hex || "#ffffff");
  // The brief's accents first. Raw saturated colours from the CSS are only a fallback: a page's CSS
  // also carries third-party widget colours (chat bubbles, payment buttons, cookie banners).
  const briefAccents = (p.accents || []).filter((a) => HEX.test(a)).map((a) => a.toLowerCase());
  const accents = [...new Set(briefAccents.length ? briefAccents : saturated)]
    .filter((a) => a !== primary && a !== dark && a !== light).slice(0, 4);
  if (!accents.length) accents.push(luminance(primary) < 0.2 ? tint(primary, 0.7) : shade(primary, 0.55));
  // Fields are the colours a whole frame can be painted in. Accents are for one or two elements.
  const fields = { primary, dark, light, white: "#ffffff" };
  if (luminance(primary) > 0.55) delete fields.primary; // a pale primary makes a weak field; keep it as an accent
  for (const [k, v] of Object.entries(fields)) if (Object.entries(fields).some(([k2, v2]) => k2 !== k && v2 === v && k2 < k)) delete fields[k];
  return { primary, dark, light, accents, fields, found: found.slice(0, 12) };
}

// Ink, hero and button colours for a given field, chosen for contrast from the brand's own set.
export function inkFor(field, pal) {
  const dark = luminance(field) < 0.36;
  const contrast = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  // Hero figure and button take a SATURATED brand colour that reads on this field, primary first.
  // A grey that merely has contrast makes a dead hero; with no saturated option the ink colour wins.
  const brandish = [pal.primary, ...pal.accents].filter((c) => c && saturation(c) > 0.3);
  const heroC = brandish.find((c) => contrast(c, field) >= 3) || (dark ? "#ffffff" : "#141414");
  const ctaBg = brandish.find((c) => contrast(c, field) >= 2.2) || (dark ? "#ffffff" : (luminance(pal.dark) < 0.2 ? pal.dark : "#141414"));
  const ctaInk = contrast("#ffffff", ctaBg) >= contrast("#111111", ctaBg) ? "#ffffff" : "#111111";
  return dark
    ? { dark, ink: "#fffdf8", inkSoft: "rgba(255,253,248,0.82)", hero: heroC, ctaBg, ctaInk }
    : { dark, ink: "#141414", inkSoft: "#4a4a4a", hero: heroC, ctaBg, ctaInk };
}

// ---- fonts ------------------------------------------------------------------------------------
const SLOTS = { display: 700, displaySemi: 600, body: 400, bodyMedium: 500, bodySemi: 600 };

async function googleFont(family, weight) {
  const q = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(family).replace(/%20/g, "+")}:wght@${weight}`;
  const r = await fetch(q, { signal: AbortSignal.timeout(20000) }); // no user agent: Google serves TTF
  if (!r.ok) return null;
  const url = ((await r.text()).match(/url\((https:[^)]+\.ttf)\)/) || [])[1];
  return url ? fetchBytes(url) : null;
}
async function googleFontNearest(family, weight) {
  for (const w of [weight, weight >= 600 ? 700 : 400, 800, 600, 500, 400, 900]) {
    const b = await googleFont(family, w).catch(() => null);
    if (b) return { bytes: b, weight: w };
  }
  return null;
}

// satori reads TTF, OTF and WOFF. WOFF2 is the most common web format and it cannot, so a
// self-hosted WOFF2-only face falls through to Google Fonts under the same family name.
async function selfHosted(site, family, weight) {
  const faces = site.fonts.faces.filter((f) => f.family.toLowerCase() === family.toLowerCase());
  const ranked = faces.map((f) => ({ f, d: Math.abs((parseInt(f.weight, 10) || 400) - weight) })).sort((a, b) => a.d - b.d);
  for (const { f } of ranked) {
    const src = f.srcs.find((s) => /truetype|ttf|opentype|otf|^woff$/.test(s.format));
    if (!src) continue;
    try {
      const bytes = await fetchBytes(src.url, 30000);
      const sig = bytes.subarray(0, 4).toString("hex");
      if (["00010000", "4f54544f", "774f4646", "74727565"].includes(sig)) return { bytes, weight: parseInt(f.weight, 10) || weight };
    } catch { /* try the next */ }
  }
  return null;
}

export async function resolveFonts(dir, brief, site, overrides = {}) {
  fs.mkdirSync(dir, { recursive: true });
  const wantDisplay = overrides.displayFamily || (brief.fonts?.display && brief.fonts.display !== "unknown" ? brief.fonts.display : site.fonts.families[0]?.name);
  const wantBody = overrides.bodyFamily || (brief.fonts?.body && brief.fonts.body !== "unknown" ? brief.fonts.body : site.fonts.families[1]?.name || wantDisplay);
  const out = {}, report = {};
  for (const [slot, weight] of Object.entries(SLOTS)) {
    const isDisplay = slot.startsWith("display");
    const file = isDisplay ? overrides.display : overrides.body;
    if (file) { out[slot] = { file, weight, family: path.basename(file), source: "operator file" }; continue; }
    const fam = isDisplay ? wantDisplay : wantBody;
    let got = null, source = null, family = fam;
    if (fam) {
      got = await selfHosted(site, fam, weight); source = got && "landing page @font-face";
      if (!got) { got = await googleFontNearest(fam, weight); source = got && "Google Fonts"; }
    }
    if (!got) {
      // Substitute, and say so. Inter Tight for display keeps a tight grotesque headline; Inter for text.
      family = isDisplay ? "Inter Tight" : "Inter";
      got = await googleFontNearest(family, weight); source = `substitute for ${fam || "an unknown font"}`;
    }
    if (!got) throw new Error(`could not load any font for ${slot}`);
    const f = path.join(dir, `${slot}.ttf`);
    fs.writeFileSync(f, got.bytes);
    out[slot] = { file: f, weight: got.weight, family, source };
    report[slot] = `${family} ${got.weight} (${source})`;
  }
  return { slots: out, report };
}

// ---- logo -------------------------------------------------------------------------------------
function svgFills(svg) {
  return [...new Set([...svg.matchAll(/(?:fill|stop-color)\s*[:=]\s*["']?(#[0-9a-f]{3,6}|currentColor|rgb[^;"']+)/gi)].map((m) => m[1].toLowerCase()))]
    .filter((f) => f !== "none");
}
function rasterSvg(svg, width = 600) {
  const r = new Resvg(svg, { fitTo: { mode: "width", value: width }, background: "rgba(0,0,0,0)" });
  const img = r.render();
  return { png: img.asPng(), width: img.width, height: img.height, pixels: img.pixels };
}
function meanOpaque(pixels) {
  let r = 0, g = 0, b = 0, n = 0;
  for (let i = 0; i < pixels.length; i += 4) if (pixels[i + 3] > 128) { r += pixels[i]; g += pixels[i + 1]; b += pixels[i + 2]; n++; }
  return n ? rgbToHex([r / n, g / n, b / n]) : null;
}

export async function resolveLogo(dir, brief, site, overridePath) {
  fs.mkdirSync(dir, { recursive: true });
  const cands = [];
  if (overridePath) {
    const bytes = fs.readFileSync(overridePath);
    const isSvg = /\.svg$/i.test(overridePath);
    cands.push({ kind: isSvg ? "svg" : "img", svg: isSvg ? bytes.toString() : null, bytes: isSvg ? null : bytes,
      mime: isSvg ? "image/svg+xml" : /\.jpe?g$/i.test(overridePath) ? "image/jpeg" : "image/png", hint: "operator file", trusted: true });
  }
  for (const c of site.logos) {
    if (c.kind === "svg") cands.push({ ...c });
    else {
      const got = await sniffImage(c.url);
      if (!got) continue;
      if (got.mime === "image/svg+xml") cands.push({ kind: "svg", svg: got.bytes.toString(), hint: c.hint, url: c.url });
      else if (["image/png", "image/jpeg"].includes(got.mime)) cands.push({ kind: "img", bytes: got.bytes, mime: got.mime, hint: c.hint, url: c.url });
    }
  }
  for (const c of cands) {
    let png, w, h, mean = null;
    try {
      if (c.kind === "svg") {
        let svg = c.svg;
        if (!/xmlns=/.test(svg)) svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
        svg = svg.replace(/currentColor/g, "#111111");
        c.svg = svg;
        const r = rasterSvg(svg); png = r.png; w = r.width; h = r.height; mean = meanOpaque(r.pixels);
      } else { png = c.bytes; }
    } catch { continue; }
    // Prove identity: the file must be this brand's own logo, not a customer's, a partner's or an icon.
    if (!c.trusted) {
      const v = await vision(`Is this image the logo or wordmark of the brand "${brief.brand}" itself (not a customer, partner, payment or social icon, not a generic symbol)? Return ONLY JSON {"is_brand_logo":true,"has_wordmark":true,"why":""}`,
        [toDataUrl(png, c.kind === "svg" ? "image/png" : c.mime)], "logo check");
      if (!v.is_brand_logo) continue;
      c.has_wordmark = !!v.has_wordmark;
    }
    const fills = c.kind === "svg" ? svgFills(c.svg) : [];
    const mono = c.kind === "svg" && fills.length <= 1;
    const file = path.join(dir, c.kind === "svg" ? "logo.svg" : c.mime === "image/jpeg" ? "logo.jpg" : "logo.png");
    fs.writeFileSync(file, c.kind === "svg" ? c.svg : c.bytes);
    if (c.kind !== "svg") {
      // Aspect for raster logos, read from the PNG/JPEG header.
      const dims = imageDims(c.bytes); w = dims?.w; h = dims?.h;
    }
    return { file, kind: c.kind, mime: c.kind === "svg" ? "image/svg+xml" : c.mime, mono, mean, aspect: w && h ? w / h : 3,
      source: c.hint || c.url || "found", has_wordmark: c.has_wordmark ?? true };
  }
  return null;
}

export function imageDims(b) {
  if (!b || b.length < 24) return null;
  if (b.readUInt32BE(0) === 0x89504e47) return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
  if (b[0] === 0xff && b[1] === 0xd8) {
    let i = 2;
    while (i < b.length) {
      if (b[i] !== 0xff) { i++; continue; }
      const m = b[i + 1];
      if (m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)) return { h: b.readUInt16BE(i + 5), w: b.readUInt16BE(i + 7) };
      i += 2 + b.readUInt16BE(i + 2);
    }
  }
  return null;
}

// ---- real assets (product shots, UI screens) --------------------------------------------------
// Downloaded, then checked by vision: an asset is usable only if it really shows the product and
// carries no third-party brand. These become reference images for the product-hero genre and the
// cards for the real-asset genre.
export async function resolveAssets(dir, brief, site, extra = [], max = 6) {
  fs.mkdirSync(dir, { recursive: true });
  const out = [];
  const list = [...extra.map((p) => ({ file: p, hint: "operator file" })), ...site.images];
  for (const c of list) {
    if (out.length >= max) break;
    let bytes, mime;
    if (c.file) { bytes = fs.readFileSync(c.file); mime = /\.jpe?g$/i.test(c.file) ? "image/jpeg" : /\.webp$/i.test(c.file) ? "image/webp" : "image/png"; }
    else { const g = await sniffImage(c.url); if (!g || !["image/png", "image/jpeg", "image/webp"].includes(g.mime)) continue; bytes = g.bytes; mime = g.mime; }
    if (bytes.length < 15000) continue; // thumbnails and spacers
    const v = await vision(`This image comes from the landing page of ${brief.brand} (${brief.product}). Classify it.
Return ONLY JSON {"shows":"product-photo | ui-screen | lifestyle-photo | person | logo-wall | illustration | decorative | other","shows_the_product":true,"third_party_brands":[],"quality":"high | ok | poor","describe":"one line"}`,
      [toDataUrl(bytes, mime)], "asset check");
    if (v._error || !v.shows_the_product || v.quality === "poor" || (v.third_party_brands || []).length) continue;
    if (!["product-photo", "ui-screen", "lifestyle-photo"].includes(v.shows)) continue;
    const ext = mime === "image/jpeg" ? "jpg" : mime === "image/webp" ? "webp" : "png";
    const file = path.join(dir, `asset${out.length + 1}.${ext}`);
    fs.writeFileSync(file, bytes);
    out.push({ id: `asset${out.length + 1}`, file, mime, kind: v.shows, describe: v.describe, source: c.url || c.file, dims: imageDims(bytes) });
  }
  return out;
}
