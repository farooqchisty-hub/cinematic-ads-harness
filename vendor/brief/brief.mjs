// The brief: what the product is, who it is for, what it can argue and what it can prove.
//
// The unit of intelligence is the ANGLE, a structured argument (promise, mechanism, enemy,
// proof, objection), not an image idea. And every figure an ad may set huge must come from a
// claims ledger whose entries are quoted verbatim from the landing page. The quote is checked
// against the page text in code: a model paraphrase does not count as a source.

import { copyJson } from "./providers.mjs";

const squash = (s) => String(s || "").toLowerCase().replace(/[‘’]/g, "'").replace(/[“”]/g, '"')
  .replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();

export async function buildBrief(site, { product, audience, competitors = [], market } = {}) {
  const colours = site.colours.slice(0, 14).map((c) => `${c.hex} (weight ${c.count}${c.vars.length ? `, token ${c.vars.join("/")}` : ""}${c.sources.includes("theme-color") ? ", theme-color" : ""}, sat ${c.sat}, lum ${c.lum})`).join("\n  ");
  const fonts = [...site.fonts.families.map((f) => `${f.name} (${f.uses} uses)`), ...site.fonts.googleFamilies.map((g) => `${g} (google fonts link)`)].join(", ");

  const prompt = `You are a senior performance marketer preparing a paid social static ad programme for the
product sold on this landing page. Read it and write the brief the creative team works from.

LANDING PAGE ${site.url}
Title: ${site.title}
Description: ${site.metas["og:description"] || site.metas.description || ""}
${product ? `Operator note on the product: ${product}\n` : ""}${audience ? `Operator note on the audience: ${audience}\n` : ""}${market ? `Market: ${market}\n` : ""}
PAGE TEXT
"""
${site.text.slice(0, 22000)}
"""

COLOURS FOUND IN THE PAGE CSS (by weight)
  ${colours || "(none found)"}
FONT FAMILIES FOUND: ${fonts || "(none found)"}

Write the brief. Rules:
- Everything is grounded in the page. Where the page is silent, say "unknown", never invent.
- ANGLES are arguments a paid ad can make, 6 to 10 of them, each distinct in its PROMISE, not reworded
  twins. Cover pain, benefit, offer, objection handling, proof and identity between them.
- The ENEMY of an angle is a mechanism, habit or old way of doing things, never a named company.
- CLAIMS are figures and hard facts the page states (prices, percentages, counts, times, ratings,
  guarantees, free tiers). Each carries "quote": the sentence or phrase copied EXACTLY as it appears in
  the page text above, character for character, short (under 25 words). No quote, no claim. Only facts
  that help the sale: leave out restrictions and caveats (final sale, shipping delays, exclusions).
- COMPETITORS: any rival brands named on the page, plus the obvious category rivals you are sure of.
  They are listed so ads can be kept free of their names.
- PALETTE: pick from the colours found. "primary" is the brand's signature colour (a token or the
  theme-color beats raw frequency). "dark" is a deep field colour (the primary's dark shade if the
  brand has one, else a near-black the page uses). "light" is the page's light background (cream,
  off-white or white). "accents" are one to three more brand colours. Hex values only.
- FONTS: "display" is the headline family and "body" the text family, from the families found, or
  "unknown".

Return ONLY JSON:
{
  "brand": "brand name as the brand writes it",
  "product": "what is sold, one sentence",
  "category": "the product category in plain words",
  "kind": "physical-product | software | service | course-or-event | marketplace | other",
  "offer": "the current offer or entry point (free trial, price, discount), or unknown",
  "primary_cta": "the page's main call to action, two to four words",
  "audience": "who buys this, concretely",
  "audience_pains": ["three to six pains in the buyer's own words"],
  "positioning": "one sentence: why this over the alternatives",
  "voice": "how the brand writes, a few adjectives plus one sample phrase from the page",
  "angles": [{"id":"kebab-id","label":"","promise":"","mechanism":"how the product delivers it","enemy":"","proof":"what on the page proves it","objection":"the doubt it answers","funnel_stage":"cold | warm | hot","quantitative":false}],
  "claims": [{"id":"c1","figure":"the number or fact as it would be set, e.g. $19 or 4.8 stars","claim":"what it means in plain words","quote":"exact page text"}],
  "proof_assets": ["things on the page that could be shown: product shots, UI screens, reviews count, press"],
  "competitors": ["names"],
  "never_say": ["words, promises or claims the ads must avoid, e.g. regulated terms for this category"],
  "palette": {"primary":"#","dark":"#","light":"#","accents":["#"]},
  "fonts": {"display":"","body":""}
}`;

  const b = await copyJson(prompt, 0.3, "brief");
  const text = squash(site.text);
  // A claim is verified only when its quote is literally on the page. Near misses are kept but
  // marked, so a person can see what the model thought it read.
  b.claims = (b.claims || []).map((c) => {
    const q = squash(c.quote);
    const onPage = q.length >= 4 && text.includes(q);
    const digits = String(c.figure || "").replace(/[^0-9]/g, "");
    const figureInQuote = !digits || q.replace(/[^0-9]/g, "").includes(digits);
    return { ...c, status: onPage && figureInQuote ? "verified" : "unverified",
      why: onPage ? (figureInQuote ? "quote found on the page" : "quote found but the figure is not in it") : "quote not found verbatim on the page" };
  });
  b.competitors = [...new Set([...(b.competitors || []), ...competitors].map((s) => String(s).trim()).filter(Boolean))]
    .filter((n) => n.toLowerCase() !== String(b.brand || "").toLowerCase());
  b.angles = (b.angles || []).filter((a) => a && a.id && a.promise).slice(0, 10);
  if (!b.angles.length) throw new Error("the brief has no angles; the page text is probably too thin (see --page-text)");
  b.source_url = site.url;
  b.created_at = new Date().toISOString();
  return b;
}
