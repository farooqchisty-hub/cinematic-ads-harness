"""Concepts, the storyboard plan, its validator, the storyboard assets, the contact sheet and review pages.

The agent (Claude Code or Codex) WRITES concepts.json and plan.json by following SKILL.md and
references/schemas.md; this module checks them, renders the assets and builds the review pages.
"""
import html, json, os, re
from concurrent.futures import ThreadPoolExecutor
from .util import rj, wj, FONTS, no_dashes
from . import providers as P
from .intake import approved_claims

E = lambda s: html.escape(str(s if s is not None else ""))
SOFT_CLAIMS = re.compile(r"\b(instantly|instant|guarantee[ds]?|love (the|our) results|customers love|boosts? (your )?sales|skyrocket\w*|double[ds]? (your )?\w+|best[- ]in[- ]class|#1|number one|in seconds)\b", re.I)
BANNED = re.compile(r"\b(unlock\w*|seamless\w*|revolutioni[sz]e\w*|game[- ]?changer|supercharg\w*|leverag\w*|empower\w*|effortless\w*|next level|elevate\w*|cutting[- ]edge)\b", re.I)
norm = lambda s: re.sub(r"\W", "", str(s)).lower()
CSS = """:root{--bg:#f7f6f2;--ink:#17201d;--muted:#5d6b66;--card:#fff;--line:#e3e1d8;--acc:#0f7a5a}
@media (prefers-color-scheme:dark){:root{--bg:#121816;--ink:#eef2ef;--muted:#9aa8a2;--card:#1b2320;--line:#2b3531;--acc:#5fd3a5}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 60px}h1{font-size:30px;margin:6px 0}h2{margin-top:34px}
.chip{display:inline-block;background:var(--acc);color:#fff;border-radius:99px;padding:2px 10px;font-size:12px;margin-right:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.card h3{margin:0 0 6px}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden}
td,th{border-bottom:1px solid var(--line);padding:8px 10px;vertical-align:top;text-align:left;font-size:13.5px}th{font-size:12px;color:var(--muted)}
.sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}.sheet figure{margin:0}.sheet img{width:100%;border-radius:8px;display:block}
.sheet figcaption{font-size:12px;color:var(--muted)}"""


def page(title, body):
    return no_dashes(f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                     f'<title>{E(title)}</title><style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>')


# ---- concepts -------------------------------------------------------------------------------------
def concepts_page(run):
    cs = rj(run.p("concepts.json"))
    if not cs:
        raise RuntimeError("write concepts.json first (schema in references/schemas.md)")
    cards = []
    for i, c in enumerate(cs, 1):
        beats = "".join(f"<li><b>{E(k)}:</b> {E(v)}</li>" for k, v in (c.get("beats") or {}).items())
        cards.append(f"""<div class="card"><span class="chip">{i}</span><span class="muted">{E(c.get('genre'))} · {E(c.get('runtime_s'))} s · about ${E(c.get('est_usd'))}</span>
<h3>{E(c.get('title'))}</h3><p>{E(c.get('logline'))}</p><p><b>First 3 seconds:</b> {E(c.get('hook'))}</p>
<p><b>Product proof:</b> {E(c.get('product_proof'))}</p><p><b>Cast:</b> {E(', '.join(c.get('cast', [])))}<br><b>Worlds:</b> {E(', '.join(c.get('locations', [])))}</p>
<ul>{beats}</ul><p class="muted"><b>Devices:</b> {E(', '.join(c.get('devices', [])) or 'plain cutting')}<br><b>Risks:</b> {E(', '.join(c.get('risks', [])) or 'none flagged')}<br><b>From:</b> {E(c.get('evidence'))}</p></div>""")
    out = run.p("concepts.html")
    open(out, "w").write(page("Ad concepts", f"<span class='chip'>Pick one</span><h1>Cinematic ad concepts for {E(run.state.get('brand', ''))}</h1><p class='muted'>Reply with the number to storyboard, or give your own concept.</p><div class='grid'>{''.join(cards)}</div>"))
    return out


def concept_pick(run, n=None, text=None, file=None):
    if n:
        c = rj(run.p("concepts.json"))[int(n) - 1]
        c["source"] = "generated"
    else:
        c = {"source": "user", "text": text or open(file).read()}
    wj(run.p("concept.json"), c)
    run.set(stage="concept", concept=c.get("title") or (c.get("text") or "")[:60])
    return c


# ---- the plan -------------------------------------------------------------------------------------
def everything_text(plan):
    keep = {k: plan.get(k) for k in ("title", "logline", "cast", "locations", "vehicles", "props", "scenes", "keyframes", "units", "lines", "cta", "graphics")}
    return json.dumps(keep, ensure_ascii=False)


def validate(run, plan=None):
    plan = plan or rj(run.p("plan.json"))
    if not plan:
        raise RuntimeError("write plan.json first (schema in references/schemas.md)")
    issues, warn = [], []
    cast = {c["id"]: c for c in plan.get("cast", [])}
    units, lines = plan.get("units", []), plan.get("lines", [])
    body, outro = float(plan.get("body_s") or 0), float(plan.get("outro_s") or 4)
    rt = plan.get("runtime") or {"min": 45, "max": 70}
    if not (rt["min"] <= body + outro <= rt["max"] + 0.5):
        issues.append(f"Runtime is {body + outro:.1f} s with the outro; the plan says {rt['min']} to {rt['max']} s.")
    for u in units:
        if not 4 <= float(u.get("gen_s", 0)) <= 30:
            issues.append(f"Unit {u['id']} generates {u.get('gen_s')} s; Seedance makes 4 to 30 s per generation.")
        if u.get("used_s") is not None and float(u["used_s"]) > float(u["gen_s"]) + 0.51:
            issues.append(f"Unit {u['id']} uses {u['used_s']} s of a {u['gen_s']} s generation.")
        for k in u.get("keyframes", []):
            if not any(x["id"] == k for x in plan.get("keyframes", [])):
                issues.append(f"Unit {u['id']} references missing keyframe {k}.")
    quoted = [norm(q) for u in units for q in re.findall(r'"([^"]+)"', u.get("prompt", ""))]
    for l in lines:
        if l.get("who") not in cast:
            issues.append(f'Line "{l["line"][:50]}" is spoken by unknown "{l.get("who")}".')
        if norm(l["line"]) not in quoted:
            issues.append(f'Line "{l["line"][:60]}" is not quoted in any unit prompt, so it will not be spoken.')
        if not l.get("delivery"):
            warn.append(f'Line "{l["line"][:40]}" has no delivery note (write it as adjectives).')
    words = sum(len(l["line"].split()) for l in lines)
    if body and words / body > 2.0 and not (plan.get("waivers") or {}).get("dialogue_cap"):
        issues.append(f"Dialogue is {words} words in {body:.0f} s ({words / body:.1f} words a second); keep it under 2.0 or add an approved waiver.")
    said = " ".join([l["line"] for l in lines] + [str((plan.get("cta") or {}).get("spoken", "")), str((plan.get("cta") or {}).get("onscreen", ""))]
                    + [json.dumps(g.get("data", {})) for g in plan.get("graphics", [])])
    digits = set()
    for c in approved_claims(run):
        digits |= set(re.findall(r"\d[\d,.]*", str(c.get("figure", "")) + " " + str(c.get("claim", ""))))
    digits = {d.rstrip(".,") for d in digits}
    for n in re.findall(r"\$?\d[\d,.\/]*%?", said):
        bare = n.lstrip("$").rstrip("%").rstrip(".,")
        if bare and bare not in digits:
            issues.append(f'"{n}" is not an approved claim figure (cine claims). Use an approved figure or drop it.')
    for m in set(x.group(0) for x in SOFT_CLAIMS.finditer(said)):
        issues.append(f'"{m}" is an unsourced claim.')
    for m in set(x.group(0) for x in BANNED.finditer(said)):
        issues.append(f'"{m}" is marketing voice; say it plainly.')
    cl = rj(run.p("claims.json"), {}) or {}
    avoid = [b for b in (cl.get("competitors", []) + cl.get("never_say", []) + (plan.get("world") or {}).get("real_brands_to_avoid", [])) if b]
    txt = everything_text(plan)
    for b in avoid:
        if re.search(rf"\b{re.escape(b)}\b", txt, re.I):
            issues.append(f'"{b}" appears in the plan; it is a real or blocked name.')
    if "—" in txt or "–" in txt:
        issues.append("The plan contains em or en dashes; use commas, colons or parentheses.")
    seen = set()
    for l in sorted(lines, key=lambda x: float(x["t0"])):
        if l["who"] in seen:
            continue
        seen.add(l["who"])
        if not l.get("on_camera") and any(x["who"] == l["who"] and x.get("on_camera") for x in lines):
            warn.append(f'{cast.get(l["who"], {}).get("name", l["who"])} is heard before being seen; show them on camera on their first line if you can.')
    out = {"issues": issues, "warnings": warn, "words": words, "body_s": body, "total_s": body + outro, "units": len(units),
           "est_usd": round(sum(float(u.get("gen_s", 0)) * int(u.get("takes", 2)) for u in units) * P.SEEDANCE_USD_S + 2.5, 2)}
    wj(run.p("plan_check.json"), out)
    return out


# ---- storyboard assets ----------------------------------------------------------------------------
FACE_ON = " No helmet, hat, visor or headset on the head: the face and hair are fully visible."


def _realism(plan):
    return f" Photographed, ultra realistic: visible skin pores, fine hair, real fabric texture, {(plan.get('look') or {}).get('camera', 'cinema camera')} look. Not a render, not an illustration."


def asset_jobs(plan):
    jobs = []
    for c in plan.get("cast", []):
        imp = c.get("importance", "support")
        if imp == "voice":
            continue
        if imp in ("lead", "support"):
            jobs.append({"key": f"{c['id']}_sheet", "kind": "character_sheet", "asset": c["id"], "aspect": "3:2"})
        if imp == "lead":
            jobs.append({"key": f"{c['id']}_expr", "kind": "expression_sheet", "asset": c["id"], "aspect": "3:2", "after": [f"{c['id']}_sheet"]})
        jobs.append({"key": f"{c['id']}_card", "kind": "identity_card", "asset": c["id"], "aspect": "2:3",
                     "after": [f"{c['id']}_sheet"] if imp in ("lead", "support") else []})
    for kind, coll in (("location_sheet", "locations"), ("vehicle_sheet", "vehicles"), ("prop_sheet", "props")):
        for a in plan.get(coll, []):
            jobs.append({"key": f"{a['id']}_sheet", "kind": kind, "asset": a["id"], "aspect": "3:2", "after": [b for b in a.get("brands", [])]})
    for b in (plan.get("world") or {}).get("fictional_brands", []):
        jobs.append({"key": b["id"], "kind": "brand_board", "asset": b["id"], "aspect": "3:2"})
    sheets = [j["key"] for j in jobs]
    for k in plan.get("keyframes", []):
        jobs.append({"key": f"kf_{k['id']}", "kind": "keyframe", "asset": k["id"], "aspect": plan.get("aspect", "9:16"), "after": sheets})
    return jobs


def _find(plan, aid):
    for coll in ("cast", "locations", "vehicles", "props", "keyframes"):
        for a in plan.get(coll, []):
            if a["id"] == aid:
                return a, coll
    for b in (plan.get("world") or {}).get("fictional_brands", []):
        if b["id"] == aid:
            return b, "brand"
    return None, None


def asset_prompt(plan, job, have):
    a, coll = _find(plan, job["asset"])
    style = (plan.get("look") or {}).get("style", "cinematic, natural")
    kind = job["kind"]
    if kind in ("character_sheet", "expression_sheet", "identity_card"):
        wardrobe = next(iter((a.get("wardrobe") or {}).values()), "") if isinstance(a.get("wardrobe"), dict) else a.get("wardrobe", "")
        person = f"{a.get('id_block') or a.get('description', '')}. Wardrobe: {wardrobe}."
        if kind == "character_sheet":
            return (f"Character turnaround sheet for a video production, on a plain light grey studio background. The same person shown five times in one row, "
                    f"full body: front, three-quarter left, side profile, three-quarter right, back. Identical face, hair, body and wardrobe in every view. Even soft "
                    f"studio light, no text, no labels, no numbers, no logos.{FACE_ON}{_realism(plan)}\nTHE CHARACTER: {person}\nLook: {style}."), []
        if kind == "expression_sheet":
            ex = ", ".join(([*a.get("expressions", []), "neutral", "focused", "laughing"])[:6])
            return (f"Expression sheet for a video production: the same person, head and shoulders, in a 3 by 2 grid on a plain light grey background. Expressions: {ex}. "
                    f"Identical face, hair and top in every panel; only the expression changes.{FACE_ON} Even soft light. No text, no logos.\nTHE CHARACTER: {person}"), [have.get(f"{a['id']}_sheet")]
        return (f"A single photographic portrait of one person, front view, head to waist, looking at the camera with a relaxed neutral expression, on a plain light grey "
                f"studio background. Even soft light. No text, no logo, no other people, no room behind them.{FACE_ON}{_realism(plan)}\nTHE PERSON: {person}\n"
                f"The background stays plain light grey: this card is the identity reference for a video model."), [have.get(f"{a['id']}_sheet")]
    if kind == "brand_board":
        return (f"Brand board for a FICTIONAL brand in a commercial's world, on a clean light background: the logo large and centred, spelled exactly \"{a['name']}\", "
                f"plus three small applications ({a.get('applications', 'signage, a garment patch, packaging')}). {a.get('what', '')}. {a.get('board_prompt', '')} "
                f"Crisp vector-like marks, correct spelling, no other words."), []
    boards = [have.get(b) for b in a.get("brands", [])] if kind != "keyframe" else []
    if kind in ("location_sheet", "vehicle_sheet", "prop_sheet"):
        what = {"location_sheet": "Location reference sheet for a vertical 9:16 video: the same place in three tall panels side by side, a wide establishing view, a medium view of the main area, and a reverse angle. No people. Any screens are dark.",
                "vehicle_sheet": "Vehicle reference sheet on a plain light grey studio floor: the same vehicle five times, front, three-quarter front, side, three-quarter rear, rear. Identical shape and livery in every view.",
                "prop_sheet": "Product and prop reference sheet: the object four times on a plain light grey background, front, three-quarter, side and a close detail."}[kind]
        brand_rule = (" Logos exactly as on the supplied brand boards, spelled correctly; no other text and no real brands." if boards else " No text, letters, numbers or logos.")
        desc = f"{a.get('description', '')}{(' Livery: ' + a['livery']) if a.get('livery') else ''}{(' Key light: ' + a['key_light']) if a.get('key_light') else ''}{(' Time: ' + a['time_of_day']) if a.get('time_of_day') else ''}"
        return f"{what}{brand_rule}{_realism(plan)}\nTHE SUBJECT: {desc}\nLook: {style}.", boards
    # keyframe
    k = a
    scene = next((s for s in plan.get("scenes", []) if s["id"] == k.get("scene")), {})
    loc, _ = _find(plan, scene.get("location")) if scene.get("location") else (None, None)
    refs, names = [], []
    for aid in k.get("assets", []):
        x, c2 = _find(plan, aid)
        if not x:
            continue
        if c2 == "cast":
            for key, label in ((f"{aid}_sheet", f"{x['name']} (character sheet)"), (f"{aid}_card", f"{x['name']}'s face (identity card)")):
                if have.get(key):
                    refs.append(have[key]); names.append(label)
        elif have.get(f"{aid}_sheet"):
            refs.append(have[f"{aid}_sheet"]); names.append(f"{x['name']} ({c2[:-1]})")
    if loc and have.get(f"{loc['id']}_sheet") and loc["id"] not in k.get("assets", []):
        refs.append(have[f"{loc['id']}_sheet"]); names.append(f"{loc['name']} (location)")
    for b in {b for aid in k.get("assets", []) + ([loc["id"]] if loc else []) for b in (_find(plan, aid)[0] or {}).get("brands", [])}:
        if have.get(b):
            refs.append(have[b]); names.append(f"the {b} brand board: reproduce these logos exactly")
    people = [f"{x['name']}: {x.get('id_block', '')}" for x in (_find(plan, aid)[0] for aid in k.get("assets", [])) if x and x.get("id_block")]
    L = plan.get("look") or {}
    branded = bool((plan.get("world") or {}).get("fictional_brands"))
    prompt = "\n".join(filter(None, [
        f"FORMAT: a single frame from a live-action commercial, vertical {plan.get('aspect', '9:16')}, photographed, not rendered.",
        f"SHOT: {k.get('shot', '')}, {k.get('angle', 'eye level')}, {k.get('lens', '35mm')} lens.",
        f"SUBJECT: {' '.join(people)}{(' Expression: ' + k['expression'] + '.') if k.get('expression') else ''}" if people else "",
        f"ACTION, caught mid-motion: {k.get('action', '')}",
        f"LOCATION: {loc.get('name', '')}: {loc.get('description', '')}. {loc.get('time_of_day', '')}." if loc else "",
        f"LIGHT: {(loc or {}).get('key_light', 'motivated practical light')}; everything lit by sources that exist in the scene.",
        f"CAMERA AND FILM: {L.get('camera', 'ARRI Alexa 35 look')}, {L.get('lenses', 'vintage spherical primes')}, {L.get('stock', 'Kodak 500T')} grain, {L.get('grade', 'natural grade')}.",
        "COMPOSITION: faces and key action in the middle band; nothing important in the top 14% or bottom 30%." if not k.get("composition") else f"COMPOSITION: {k['composition']}",
        f"REFERENCES: {'; '.join(f'image {i + 1} is {n}' for i, n in enumerate(names))}. Match faces, hair, wardrobe, vehicles and set exactly." if names else "",
        "Signage, garments and props carry ONLY the fictional logos from the supplied brand boards, spelled correctly; no real brands; screens show abstract glow, no interfaces." if branded
        else "No text, letters, logos or interfaces anywhere; screens are angled away or dark.",
        "Hands natural or out of frame.",
    ]))
    return prompt, refs


def render_assets(run, only=None, force=False, workers=4):
    plan = rj(run.p("plan.json"))
    jobs = asset_jobs(plan)
    out = lambda key: run.p("storyboard", f"{key}.png")
    have = {j["key"]: out(j["key"]) for j in jobs if os.path.exists(out(j["key"]))}
    todo = [j for j in jobs if (force or j["key"] not in have) and (not only or j["key"] in only)]
    print(f"  {len(todo)} storyboard renders ({len(have)} already done)")
    def one(j):
        prompt, refs = asset_prompt(plan, j, have)
        P.render_image(run, "storyboard", prompt, [r for r in refs if r][:8], out(j["key"]), j["aspect"])
        have[j["key"]] = out(j["key"])
        print(f"  done {j['key']}")
    # Order matters: boards and turnarounds first, then the sheets that carry boards, then identity
    # cards (rendered from the turnaround), then keyframes (rendered from all of them).
    for kinds in (("brand_board", "character_sheet"), ("location_sheet", "vehicle_sheet", "prop_sheet"),
                  ("identity_card", "expression_sheet"), ("keyframe",)):
        batch = [j for j in todo if j["kind"] in kinds]
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(one, batch))
    return have


def contact_sheet(run):
    from PIL import Image, ImageDraw, ImageFont
    plan = rj(run.p("plan.json"))
    kfs = [k for k in plan.get("keyframes", []) if os.path.exists(run.p("storyboard", f"kf_{k['id']}.png"))]
    if not kfs:
        raise RuntimeError("no keyframes rendered yet")
    W, H, pad, cap, cols = 240, 427, 12, 70, 6
    rows = (len(kfs) + cols - 1) // cols
    f = lambda s: ImageFont.truetype(os.path.join(FONTS, "Inter-SemiBold.ttf"), s)
    sh_ = Image.new("RGB", (cols * (W + pad) + pad, rows * (H + cap + pad) + pad + 64), (17, 24, 22))
    d = ImageDraw.Draw(sh_)
    d.text((pad, 18), f"{plan.get('title', '')}  ·  storyboard  ·  {len(kfs)} keyframes", font=f(26), fill=(240, 240, 230))
    for i, k in enumerate(kfs):
        x, y = pad + (i % cols) * (W + pad), 64 + pad + (i // cols) * (H + cap + pad)
        sh_.paste(Image.open(run.p("storyboard", f"kf_{k['id']}.png")).convert("RGB").resize((W, H)), (x, y))
        d.rectangle([x, y, x + W, y + 22], fill=(0, 0, 0))
        d.text((x + 6, y + 3), f"{k['id']}  {k.get('scene', '')}", font=f(13), fill=(150, 220, 190))
        words, line, ln = str(k.get("action", "")).split(), "", 0
        for w in words:
            if d.textlength(line + " " + w, font=f(13)) > W - 4:
                d.text((x + 2, y + H + 4 + ln * 17), line, font=f(13), fill=(225, 225, 225)); ln += 1; line = w
                if ln == 3:
                    break
            else:
                line = (line + " " + w).strip()
        if ln < 3:
            d.text((x + 2, y + H + 4 + ln * 17), line, font=f(13), fill=(225, 225, 225))
    out = run.p("storyboard", "contact_sheet.png")
    sh_.save(out)
    return out


def storyboard_page(run):
    plan = rj(run.p("plan.json"))
    chk = validate(run, plan)
    cast = {c["id"]: c for c in plan.get("cast", [])}
    rows = "".join(f"<tr><td>{float(l['t0']):.1f} to {float(l['t1']):.1f}s</td><td><b>{E(cast.get(l['who'], {}).get('name', l['who']))}</b>{' (on camera)' if l.get('on_camera') else ''}</td>"
                   f"<td>“{E(l['line'])}”<div class='muted'>{E(l.get('delivery', ''))}</div></td><td>{E(l.get('unit', ''))}</td></tr>" for l in plan.get("lines", []))
    units = "".join(f"<div class='card'><h3>{E(u['id'])}: {E(u.get('world', ''))}</h3><p>{E(u.get('purpose', ''))}</p><p class='muted'>{E(u.get('gen_s'))} s, {E(u.get('takes', 2))} takes, starts at {E(u.get('t0', 0))} s</p></div>" for u in plan.get("units", []))
    gfx = "".join(f"<tr><td>{E(g.get('t', ''))}</td><td>{E(g.get('template'))}</td><td>{E(g.get('purpose', ''))}</td><td>{E(g.get('sound') or 'silent')}</td></tr>" for g in plan.get("graphics", []))
    kf = "".join(f"<figure><img src='storyboard/kf_{E(k['id'])}.png' loading='lazy'><figcaption><b>{E(k['id'])}</b> {E(k.get('action', ''))}</figcaption></figure>"
                 for k in plan.get("keyframes", []) if os.path.exists(run.p("storyboard", f"kf_{k['id']}.png")))
    sheets = "".join(f"<figure><img src='storyboard/{E(f)}' loading='lazy'><figcaption>{E(f[:-4])}</figcaption></figure>"
                     for f in sorted(os.listdir(run.p("storyboard"))) if f.endswith(".png") and not f.startswith(("kf_", "contact"))) if os.path.exists(run.p("storyboard")) else ""
    snd = "".join(f"<li><b>{E(k)}:</b> {E(v)}</li>" for k, v in (plan.get("sound") or {}).items())
    mus = "".join(f"<li><b>{E(k)}:</b> {E(v)}</li>" for k, v in (plan.get("music") or {}).items())
    issues = "".join(f"<li>{E(i)}</li>" for i in chk["issues"]) or "<li>none</li>"
    warns = "".join(f"<li>{E(i)}</li>" for i in chk["warnings"]) or "<li>none</li>"
    body = f"""<span class="chip">For approval</span><h1>{E(plan.get('title'))}</h1><p>{E(plan.get('logline'))}</p>
<p class="muted">{chk['total_s']:.1f} s with the outro · {chk['words']} words of dialogue · {chk['units']} generation units · estimated ${chk['est_usd']}</p>
<h2>Rule check</h2><p><b>Open issues</b></p><ul>{issues}</ul><p><b>Warnings</b></p><ul>{warns}</ul>
<h2>Generation units</h2><div class="grid">{units}</div>
<h2>Keyframes</h2><div class="sheet">{kf}</div>
<h2>Dialogue, with delivery</h2><table><tr><th>Time</th><th>Who</th><th>Line</th><th>Unit</th></tr>{rows}</table>
<h2>Motion graphics</h2><table><tr><th>At</th><th>Template</th><th>Purpose</th><th>Sound</th></tr>{gfx}</table>
<h2>Sound</h2><ul>{snd}</ul><h2>Music</h2><ul>{mus}</ul>
<h2>Cast, locations and brand boards</h2><div class="sheet">{sheets}</div>"""
    out = run.p("storyboard.html")
    open(out, "w").write(page(plan.get("title", "Storyboard"), body))
    return out
