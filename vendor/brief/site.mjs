// Read a landing page: its words, its colours, its fonts, its logo and its images.
//
// Everything downstream is only as honest as this step. The claims ledger is built from the
// page's own sentences, so the text must be the page's text and nothing else. When a page is
// rendered by JavaScript and a plain fetch returns an empty shell, the harness says so instead
// of guessing: supply the text with --page-text (a host agent with a browser can save it).

import { UA, fetchBytes } from "./providers.mjs";

const decode = (s) => String(s || "")
  .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
  .replace(/&rsquo;|&lsquo;/g, "'").replace(/&rdquo;|&ldquo;/g, '"').replace(/&mdash;|&ndash;/g, "-");

export function htmlToText(html) {
  return decode(String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, " ").replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ").replace(/<svg[\s\S]*?<\/svg>/gi, " ")
    .replace(/<(br|\/p|\/div|\/li|\/h[1-6]|\/section|\/tr|\/button|\/a)[^>]*>/gi, "\n")
    .replace(/<[^>]+>/g, " "))
    .split("\n").map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean)
    .filter((l, i, a) => a.indexOf(l) === i).join("\n");
}

const attr = (tag, name) => {
  const m = tag.match(new RegExp(`\\b${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, "i"));
  return m ? decode(m[2] ?? m[3] ?? m[4]) : null;
};
const abs = (u, base) => { try { return new URL(u, base).href; } catch { return null; } };

export async function readSite(url, { pageText } = {}) {
  const res = await fetch(url, { headers: { "User-Agent": UA, Accept: "text/html,*/*" }, redirect: "follow",
    signal: AbortSignal.timeout(45000) });
  const html = res.ok ? await res.text() : "";
  const finalUrl = res.url || url;
  const notes = [];
  if (!res.ok) notes.push(`landing page returned HTTP ${res.status}`);

  const metas = {};
  for (const tag of html.match(/<meta\b[^>]*>/gi) || []) {
    const k = (attr(tag, "property") || attr(tag, "name") || "").toLowerCase();
    const v = attr(tag, "content");
    if (k && v && !metas[k]) metas[k] = v;
  }
  const title = decode((html.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1] || "").trim();

  let text = pageText || htmlToText(html);
  if (!pageText && text.length < 600) {
    notes.push(`the page returned only ${text.length} characters of text; it is probably rendered by JavaScript. Pass --page-text <file> with the visible text for a faithful claims ledger.`);
  }

  // Stylesheets: inline plus up to six linked sheets, which is where brand colours and fonts live.
  const cssParts = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)].map((m) => m[1]);
  const inlineStyles = [...html.matchAll(/\bstyle\s*=\s*"([^"]*)"/gi)].map((m) => m[1]).join(";");
  const sheetUrls = (html.match(/<link\b[^>]*>/gi) || [])
    .filter((t) => /rel\s*=\s*["']?stylesheet/i.test(t)).map((t) => abs(attr(t, "href"), finalUrl)).filter(Boolean);
  const googleFontLinks = sheetUrls.filter((u) => /fonts\.googleapis\.com/.test(u));
  for (const u of sheetUrls.filter((u) => !/fonts\.googleapis\.com/.test(u)).slice(0, 6)) {
    try {
      const r = await fetch(u, { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(20000) });
      if (r.ok) cssParts.push((await r.text()).slice(0, 1_500_000));
    } catch { /* a missing sheet is not fatal */ }
  }
  const css = cssParts.join("\n") + "\n" + inlineStyles;

  return {
    url: finalUrl, title, metas, text: text.slice(0, 40000), notes,
    colours: colourStats(css, html, metas),
    fonts: fontStats(css, googleFontLinks, finalUrl),
    logos: logoCandidates(html, finalUrl, metas),
    images: imageCandidates(html, finalUrl, metas),
  };
}

// ---- colours ----------------------------------------------------------------------------------
function norm(hex) {
  let h = hex.replace("#", "").toLowerCase();
  if (h.length === 3 || h.length === 4) h = h.slice(0, 3).split("").map((c) => c + c).join("");
  if (h.length === 8) h = h.slice(0, 6);
  return h.length === 6 ? `#${h}` : null;
}
export function hexToRgb(hex) { const h = hex.replace("#", ""); return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)); }
export function rgbToHex(rgb) { return "#" + rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join(""); }
export function saturation(hex) { const [r, g, b] = hexToRgb(hex).map((v) => v / 255); const mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx === 0 ? 0 : (mx - mn) / mx; }
export function luminance(hex) {
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const [r, g, b] = hexToRgb(hex).map((v) => lin(v / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function colourStats(css, html, metas) {
  const counts = new Map();
  const add = (hex, w = 1, source = "css") => {
    const n = norm(hex); if (!n) return;
    const cur = counts.get(n) || { hex: n, count: 0, vars: new Set(), sources: new Set() };
    cur.count += w; cur.sources.add(source); counts.set(n, cur);
    return cur;
  };
  for (const m of css.matchAll(/#([0-9a-f]{3,8})\b/gi)) add(`#${m[1]}`);
  for (const m of css.matchAll(/rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})/gi)) add(rgbToHex([+m[1], +m[2], +m[3]]));
  // Custom properties named like brand tokens carry far more signal than raw frequency.
  for (const m of css.matchAll(/--([a-z0-9-_]*(?:brand|primary|accent|secondary|main|theme)[a-z0-9-_]*)\s*:\s*(#[0-9a-f]{3,8})/gi)) {
    const c = add(m[2], 25, "token"); if (c) c.vars.add(m[1]);
  }
  if (metas["theme-color"]) add(metas["theme-color"], 40, "theme-color");
  if (metas["msapplication-tilecolor"]) add(metas["msapplication-tilecolor"], 20, "tile-color");
  for (const m of html.matchAll(/\b(?:fill|stroke|stop-color)\s*=\s*"(#[0-9a-f]{3,6})"/gi)) add(m[1], 2, "svg");
  return [...counts.values()]
    .map((c) => ({ hex: c.hex, count: c.count, vars: [...c.vars].slice(0, 3), sources: [...c.sources],
      sat: Math.round(saturation(c.hex) * 100) / 100, lum: Math.round(luminance(c.hex) * 100) / 100 }))
    .sort((a, b) => b.count - a.count).slice(0, 24);
}

// ---- fonts ------------------------------------------------------------------------------------
function fontStats(css, googleFontLinks, base) {
  const fam = new Map();
  for (const m of css.matchAll(/font-family\s*:\s*([^;}{]+)/gi)) {
    const first = m[1].split(",")[0].replace(/["']/g, "").trim();
    if (!first || /^(inherit|initial|var\(|sans-serif|serif|monospace|system-ui|-apple-system)/i.test(first)) continue;
    fam.set(first, (fam.get(first) || 0) + 1);
  }
  const faces = [];
  for (const m of css.matchAll(/@font-face\s*{([^}]*)}/gi)) {
    const body = m[1];
    const name = (body.match(/font-family\s*:\s*["']?([^;"']+)/i) || [])[1]?.trim();
    const weight = (body.match(/font-weight\s*:\s*([^;]+)/i) || [])[1]?.trim() || "400";
    const srcs = [...body.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)\s*(?:format\(\s*["']?([^"')]+))?/gi)]
      .map((s) => ({ url: abs(s[1], base), format: (s[2] || s[1].split(".").pop() || "").toLowerCase() }));
    if (name) faces.push({ family: name, weight, srcs });
  }
  const googleFamilies = googleFontLinks.flatMap((u) => [...u.matchAll(/family=([^&:]+)/g)].map((m) => decodeURIComponent(m[1]).replace(/\+/g, " ")));
  return {
    families: [...fam.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, uses]) => ({ name, uses })),
    faces: faces.slice(0, 30), googleFamilies,
  };
}

// ---- logo and images -------------------------------------------------------------------------
function logoCandidates(html, base, metas) {
  const out = [];
  const header = (html.match(/<header[\s\S]*?<\/header>/i) || [])[0] || html.slice(0, 60000);
  for (const tag of header.match(/<img\b[^>]*>/gi) || []) {
    const src = attr(tag, "src") || attr(tag, "data-src");
    const hint = `${attr(tag, "alt") || ""} ${attr(tag, "class") || ""} ${src || ""}`;
    if (src && /logo|brand/i.test(hint)) out.push({ kind: "img", url: abs(src, base), hint: hint.slice(0, 80), score: 10 });
  }
  // Inline SVG logos, common on modern sites: kept as markup so they can be recoloured.
  for (const m of header.matchAll(/<a\b[^>]*>([\s\S]{0,200}?)(<svg[\s\S]*?<\/svg>)/gi)) {
    const svg = m[2];
    if (svg.length < 200 || svg.length > 60000) continue;
    const near = m[0].slice(0, 400);
    const score = /logo|brand|home/i.test(near) ? 9 : 4;
    out.push({ kind: "svg", svg, hint: "inline svg in header link", score });
  }
  for (const tag of html.match(/<link\b[^>]*>/gi) || []) {
    const rel = (attr(tag, "rel") || "").toLowerCase();
    const href = attr(tag, "href");
    if (!href) continue;
    if (rel.includes("mask-icon")) out.push({ kind: "img", url: abs(href, base), hint: "mask-icon", score: 3 });
    else if (rel.includes("apple-touch-icon")) out.push({ kind: "img", url: abs(href, base), hint: "apple-touch-icon (icon, not wordmark)", score: 2 });
  }
  if (metas["og:logo"]) out.push({ kind: "img", url: abs(metas["og:logo"], base), hint: "og:logo", score: 8 });
  return out.filter((c) => c.kind === "svg" || c.url).sort((a, b) => b.score - a.score).slice(0, 8);
}

function imageCandidates(html, base, metas) {
  const seen = new Set();
  const out = [];
  const push = (u, hint, score) => {
    const a = abs(u, base); if (!a || seen.has(a) || /\.svg(\?|$)|data:|sprite|icon|logo|pixel|tracking|1x1/i.test(a)) return;
    seen.add(a); out.push({ url: a, hint: String(hint || "").slice(0, 100), score });
  };
  if (metas["og:image"]) push(metas["og:image"], "og:image", 6);
  for (const tag of html.match(/<img\b[^>]*>/gi) || []) {
    const srcset = attr(tag, "srcset") || attr(tag, "data-srcset");
    const best = srcset ? srcset.split(",").map((s) => s.trim().split(/\s+/)).sort((a, b) => parseInt(b[1] || 0) - parseInt(a[1] || 0))[0]?.[0] : null;
    const src = best || attr(tag, "src") || attr(tag, "data-src");
    const w = parseInt(attr(tag, "width") || "0", 10);
    const alt = attr(tag, "alt") || "";
    if (src && (w === 0 || w >= 300)) push(src, alt, /product|hero|screen|dashboard|app/i.test(`${alt} ${src}`) ? 5 : 2);
  }
  return out.sort((a, b) => b.score - a.score).slice(0, 24);
}

export async function sniffImage(url) {
  try {
    const bytes = await fetchBytes(url, 30000);
    const sig = bytes.subarray(0, 12).toString("hex");
    const mime = sig.startsWith("89504e47") ? "image/png" : sig.startsWith("ffd8") ? "image/jpeg"
      : sig.includes("57454250") ? "image/webp" : /^\s*<(\?xml|svg)/.test(bytes.subarray(0, 100).toString()) ? "image/svg+xml"
      : sig.startsWith("47494638") ? "image/gif" : null;
    return mime ? { bytes, mime } : null;
  } catch { return null; }
}
