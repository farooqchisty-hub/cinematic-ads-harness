#!/usr/bin/env node
// One image render with references, through whichever image key is set (OpenRouter, OpenAI, Replicate).
//   node vendor/brief/run-render.mjs <job.json>   job: {prompt, aspect, refs:[local paths or https urls], out}
import fs from "node:fs";
import path from "node:path";
import { renderImage, ledger, toDataUrl } from "./providers.mjs";
const job = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const refs = (job.refs || []).map((r) => /^https?:|^data:/.test(r) ? r : toDataUrl(fs.readFileSync(r), r.endsWith(".jpg") || r.endsWith(".jpeg") ? "image/jpeg" : "image/png"));
const bytes = await renderImage(job.prompt, { aspect: job.aspect || "9:16", refs, label: path.basename(job.out) });
fs.mkdirSync(path.dirname(job.out), { recursive: true });
fs.writeFileSync(job.out, bytes);
console.log(JSON.stringify({ out: job.out, usd: Math.round(ledger.total * 10000) / 10000 }));
