// Model providers. One place that knows how to talk to text, vision and image models, so every
// other module asks for "a JSON answer" or "a square scene" and never for a vendor.
//
// Routing, in order of preference, picked from whichever keys are present:
//   text + vision : OpenRouter (one key covers every model) -> OpenAI
//   image         : OpenRouter -> OpenAI -> Replicate
// Every call is logged to the run's cost ledger so a batch reports what it spent.

import fs from "node:fs";
import path from "node:path";
import os from "node:os";

// Keys come from the environment, or from a .env file in the working directory. Nothing is read
// from anywhere else, so the package behaves the same on every machine.
function loadDotEnv() {
  const f = path.resolve(process.cwd(), ".env");
  if (!fs.existsSync(f)) return;
  for (const line of fs.readFileSync(f, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^['"]|['"]$/g, "");
  }
}
loadDotEnv();

const env = (k) => (process.env[k] || "").trim();

export const CONFIG = {
  openrouter: env("OPENROUTER_API_KEY") || env("OPENROUTER_KEY"),
  openai: env("OPENAI_API_KEY"),
  replicate: env("REPLICATE_API_TOKEN") || env("REPLICATE_KEY"),
  scrapecreators: env("SCRAPECREATORS_API_KEY"),
  // Model ids. Defaults are what the harness was tuned on; any can be overridden.
  models: {
    copy: env("ADS_MODEL_COPY") || (env("OPENROUTER_API_KEY") || env("OPENROUTER_KEY") ? "anthropic/claude-sonnet-5" : "gpt-5"),
    vision: env("ADS_MODEL_VISION") || (env("OPENROUTER_API_KEY") || env("OPENROUTER_KEY") ? "openai/gpt-5.6-luna" : "gpt-5"),
    image: env("ADS_MODEL_IMAGE") || (env("OPENROUTER_API_KEY") || env("OPENROUTER_KEY") ? "openai/gpt-image-2" : "gpt-image-2"),
    imageQuality: env("ADS_IMAGE_QUALITY") || "medium",
  },
};

export function checkKeys({ needImage = true } = {}) {
  const problems = [];
  if (!CONFIG.openrouter && !CONFIG.openai) problems.push("no text/vision key: set OPENROUTER_API_KEY or OPENAI_API_KEY");
  if (needImage && !CONFIG.openrouter && !CONFIG.openai && !CONFIG.replicate)
    problems.push("no image key: set OPENROUTER_API_KEY, OPENAI_API_KEY or REPLICATE_API_TOKEN");
  return problems;
}

// ---- cost ledger ------------------------------------------------------------------------------
export const ledger = { calls: [], total: 0 };
function spend(kind, model, usd, note) {
  const v = Number(usd) || 0;
  ledger.calls.push({ at: new Date().toISOString(), kind, model, usd: Math.round(v * 10000) / 10000, note });
  ledger.total += v;
}
// List prices used only when a provider does not report cost itself.
const EST = { image_medium: 0.05, image_high: 0.19, image_low: 0.02 };

// ---- JSON extraction --------------------------------------------------------------------------
export function extractJson(text) {
  if (!text) return null;
  const s = String(text);
  const fenced = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  const cands = [fenced?.[1], s];
  for (const c of cands) {
    if (!c) continue;
    const a = c.indexOf("{"), b = c.lastIndexOf("}");
    if (a < 0 || b <= a) continue;
    try { return JSON.parse(c.slice(a, b + 1)); } catch { /* try next */ }
  }
  return null;
}

// ---- chat -------------------------------------------------------------------------------------
async function post(url, headers, body, timeoutMs) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body), signal: AbortSignal.timeout(timeoutMs) });
  const text = await r.text();
  let j; try { j = JSON.parse(text); } catch { j = { raw: text.slice(0, 300) }; }
  if (!r.ok || j.error) throw new Error(`${new URL(url).host} ${r.status}: ${JSON.stringify(j.error || j).slice(0, 300)}`);
  return j;
}

// content: a string, or an array of {type:"text"} / {type:"image", url} parts.
export async function chat(content, { model, temperature = 0.7, timeoutMs = 240000, label = "chat" } = {}) {
  const parts = typeof content === "string" ? [{ type: "text", text: content }] : content;
  const msg = parts.map((p) => p.type === "image"
    ? { type: "image_url", image_url: { url: p.url } } : { type: "text", text: p.text });
  if (CONFIG.openrouter) {
    const j = await post("https://openrouter.ai/api/v1/chat/completions",
      { Authorization: `Bearer ${CONFIG.openrouter}` },
      { model, temperature, messages: [{ role: "user", content: msg }], usage: { include: true } }, timeoutMs);
    spend("text", model, j.usage?.cost, label);
    return j.choices?.[0]?.message?.content || "";
  }
  if (CONFIG.openai) {
    const bare = model.replace(/^openai\//, "");
    const body = { model: bare, messages: [{ role: "user", content: msg }] };
    if (!/^gpt-5|^o\d/.test(bare)) body.temperature = temperature;
    const j = await post("https://api.openai.com/v1/chat/completions",
      { Authorization: `Bearer ${CONFIG.openai}` }, body, timeoutMs);
    spend("text", bare, null, label);
    return j.choices?.[0]?.message?.content || "";
  }
  throw new Error("no text provider configured");
}

export async function chatJson(content, opts = {}, tries = 2) {
  let last = "";
  for (let i = 0; i < tries; i++) {
    try {
      const out = await chat(content, opts);
      const j = extractJson(out);
      if (j) return j;
      last = `no json in: ${out.slice(0, 120)}`;
    } catch (e) { last = e.message; }
  }
  throw new Error(`model returned no usable json (${opts.label || "chat"}): ${String(last).slice(0, 200)}`);
}

export const copyJson = (prompt, temperature, label) => chatJson(prompt, { model: CONFIG.models.copy, temperature, label });
export const judgeJson = (prompt, label) => chatJson(prompt, { model: CONFIG.models.copy, temperature: 0, label });

// Vision. Images go in as data URLs, so nothing has to be hosted anywhere.
export async function vision(prompt, images, label = "vision") {
  const parts = [{ type: "text", text: prompt }, ...[].concat(images).map((url) => ({ type: "image", url }))];
  try { return await chatJson(parts, { model: CONFIG.models.vision, temperature: 0, timeoutMs: 120000, label }); }
  catch (e) { return { _error: e.message }; }
}

export const toDataUrl = (bytes, mime = "image/png") => `data:${mime};base64,${Buffer.from(bytes).toString("base64")}`;

// ---- image ------------------------------------------------------------------------------------
// Returns PNG bytes. `refs` are data URLs or public URLs of images the render must stay faithful to
// (a product photo, a source ad).
export async function renderImage(prompt, { aspect = "1:1", refs = [], label = "render" } = {}) {
  const errors = [];
  const quality = CONFIG.models.imageQuality;
  if (CONFIG.openrouter) {
    try {
      const j = await post("https://openrouter.ai/api/v1/images", { Authorization: `Bearer ${CONFIG.openrouter}` }, {
        model: CONFIG.models.image, prompt, aspect_ratio: aspect, quality, n: 1,
        ...(refs.length ? { input_references: refs.slice(0, 8).map((url) => ({ type: "image_url", image_url: { url } })) } : {}),
      }, 300000);
      const b64 = j.data?.[0]?.b64_json;
      if (b64) { spend("image", CONFIG.models.image, j.usage?.cost ?? EST[`image_${quality}`], label); return Buffer.from(b64, "base64"); }
      const url = j.data?.[0]?.url;
      if (url) { spend("image", CONFIG.models.image, j.usage?.cost ?? EST[`image_${quality}`], label); return fetchBytes(url); }
      errors.push("openrouter: no image in response");
    } catch (e) { errors.push(`openrouter: ${e.message}`); if (/moderation|safety|flagged/i.test(e.message)) throw new Error(errors.join(" | ")); }
  }
  if (CONFIG.openai) {
    try {
      const size = aspect === "9:16" || aspect === "2:3" ? "1024x1536" : aspect === "16:9" || aspect === "3:2" ? "1536x1024" : "1024x1024";
      const model = CONFIG.models.image.replace(/^openai\//, "");
      let j;
      if (refs.length) {
        const form = new FormData();
        form.append("model", model); form.append("prompt", prompt); form.append("size", size); form.append("quality", quality);
        for (const [i, r] of refs.slice(0, 8).entries()) {
          const bytes = r.startsWith("data:") ? Buffer.from(r.split(",")[1], "base64") : await fetchBytes(r);
          form.append("image[]", new Blob([bytes], { type: "image/png" }), `ref${i}.png`);
        }
        const res = await fetch("https://api.openai.com/v1/images/edits", { method: "POST",
          headers: { Authorization: `Bearer ${CONFIG.openai}` }, body: form, signal: AbortSignal.timeout(300000) });
        j = await res.json();
        if (!res.ok) throw new Error(`${res.status}: ${JSON.stringify(j.error || j).slice(0, 200)}`);
      } else {
        j = await post("https://api.openai.com/v1/images/generations", { Authorization: `Bearer ${CONFIG.openai}` },
          { model, prompt, size, quality, n: 1 }, 300000);
      }
      const b64 = j.data?.[0]?.b64_json;
      if (b64) { spend("image", model, EST[`image_${quality}`], label); return Buffer.from(b64, "base64"); }
      errors.push("openai: no image in response");
    } catch (e) { errors.push(`openai: ${e.message}`); }
  }
  if (CONFIG.replicate) {
    try { return await renderReplicate(prompt, aspect, refs, quality, label); }
    catch (e) { errors.push(`replicate: ${e.message}`); }
  }
  throw new Error(errors.join(" | ") || "no image provider configured");
}

async function renderReplicate(prompt, aspect, refs, quality, label) {
  if (aspect === "4:5") aspect = "3:4";
  const auth = { Authorization: `Bearer ${CONFIG.replicate}` };
  const r = await fetch("https://api.replicate.com/v1/models/openai/gpt-image-2/predictions", {
    method: "POST", headers: { ...auth, "Content-Type": "application/json", Prefer: "wait=55" },
    body: JSON.stringify({ input: { prompt, aspect_ratio: aspect, quality, output_format: "png", number_of_images: 1,
      ...(refs.length ? { input_images: refs.slice(0, 8) } : {}) } }),
    signal: AbortSignal.timeout(90000),
  });
  const j = JSON.parse((await r.text()).replace(/[\u0000-\u001f]/g, " "));
  if (!r.ok) throw new Error(`${r.status}: ${JSON.stringify(j).slice(0, 200)}`);
  let out = j.output;
  for (let i = 0; !out && j.urls?.get && i < 60; i++) {
    await new Promise((x) => setTimeout(x, 5000));
    const d = await (await fetch(j.urls.get, { headers: auth })).json().catch(() => ({}));
    if (d.status === "succeeded") out = d.output;
    if (d.status === "failed" || d.status === "canceled") throw new Error(d.error || d.status);
  }
  const url = Array.isArray(out) ? out[0] : out;
  if (!url) {
    // A prediction left in the queue still runs and bills later, with nobody waiting for it.
    if (j.urls?.cancel) await fetch(j.urls.cancel, { method: "POST", headers: auth }).catch(() => {});
    throw new Error("no render after the wait, cancelled");
  }
  spend("image", "replicate/openai/gpt-image-2", EST[`image_${quality}`], label);
  return fetchBytes(url);
}

export async function fetchBytes(url, timeoutMs = 60000) {
  const r = await fetch(url, { signal: AbortSignal.timeout(timeoutMs), headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error(`fetch ${r.status} ${url.slice(0, 80)}`);
  return Buffer.from(await r.arrayBuffer());
}

export const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";
export const HOME = os.homedir();
