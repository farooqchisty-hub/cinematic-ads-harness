"""Motion graphics from templates, filled with the product's brand kit and real page captures.

graphics.json (written by the agent from the storyboard):
  [{"id": "G1", "template": "toast", "duration": 2.4, "pos": {"x": 70, "y": 300},
    "data": {"icon": "brief/brandkit/logo.png", "title": "...", "text": "...", "stamp": "..."},
    "sfx": [{"rel_s": 0.3, "kind": "pop"}]}, ...]
Templates: toast, message, product_card, claim_card, callout, tracker, stamp, cta, outro (see each template's
index.html for its data fields). Image paths are relative to the run folder. Every graphic renders to a
transparent WebM in graphics/out/, and graphics/out/cues.json records its sounds and bounding box for the edit.
A graphic's sound is opt-in: give it an sfx entry only when the audience must register the event.
"""
import json, os, shutil, subprocess
from .util import rj, wj, sh, TEMPLATES, FONTS, PKG
from .intake import HF


def brand_tokens(run):
    kit = rj(run.p("brief", "brandkit.json"), {}) or {}
    pal = kit.get("palette", {})
    slots = (kit.get("fonts") or {}).get("slots", {})
    fonts, head_fam, body_fam = [], "Barlow Condensed", "Inter"
    for slot, f in slots.items():
        if f.get("file") and os.path.exists(f["file"]):
            fonts.append({"slot": slot, "family": f.get("family", slot), "path": f["file"], "weight": f.get("weight", 400)})
            if slot.startswith("display"):
                head_fam = f.get("family", head_fam)
            else:
                body_fam = f.get("family", body_fam)
    ov = rj(run.p("graphics", "brand.json"), {}) or {}   # optional overrides the user or agent sets
    return {"primary": pal.get("primary"), "dark": pal.get("dark"), "light": pal.get("light"),
            "accent": (pal.get("accents") or [None])[0], "ink": "#111111", "on_primary": "#ffffff",
            "font_head_family": head_fam, "font_body_family": body_fam, "_fonts": fonts,
            "logo": (kit.get("logo") or {}).get("file"), **ov}


def _stage(run, cue, brand):
    d = run.p("graphics", cue["id"])
    if os.path.exists(d):
        shutil.rmtree(d)
    src = os.path.join(TEMPLATES, "graphics", cue["template"])
    if not os.path.exists(src):
        raise RuntimeError(f"unknown template {cue['template']}")
    shutil.copytree(src, d)
    a = os.path.join(d, "assets")
    shutil.copytree(os.path.join(TEMPLATES, "graphics", "_shared"), a)
    os.makedirs(os.path.join(a, "fonts"), exist_ok=True)
    for f in ("Inter-SemiBold.ttf", "BarlowCondensed-ExtraBold.ttf"):
        shutil.copy(os.path.join(FONTS, f), os.path.join(a, "fonts", f))
    b = {k: v for k, v in brand.items() if not k.startswith("_") and v}
    b["fonts"] = []
    for i, f in enumerate(brand["_fonts"]):
        dst = f"assets/fonts/brand{i}{os.path.splitext(f['path'])[1]}"
        shutil.copy(f["path"], os.path.join(d, dst))
        b["fonts"].append({"family": f["family"], "file": dst, "weight": f["weight"]})
    if brand.get("logo") and os.path.exists(brand["logo"]):
        ext = os.path.splitext(brand["logo"])[1]
        shutil.copy(brand["logo"], os.path.join(a, f"logo{ext}"))
        b["logo"] = f"assets/logo{ext}"
        if ext != ".png":   # templates default to assets/logo.png
            shutil.copy(brand["logo"], os.path.join(a, "logo.png"))
    data = dict(cue.get("data", {}))
    for k, v in list(data.items()):   # copy referenced images in, rewrite to local paths
        if isinstance(v, str) and os.path.splitext(v)[1].lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg") and not v.startswith("assets/"):
            srcf = v if os.path.isabs(v) else run.p(v)
            if os.path.exists(srcf):
                dst = f"assets/img_{k}{os.path.splitext(srcf)[1]}"
                shutil.copy(srcf, os.path.join(d, dst))
                data[k] = dst
    cuejs = {"brand": b, "pos": cue.get("pos"), **data}
    open(os.path.join(d, "cue.js"), "w").write("window.CUE = " + json.dumps(cuejs, ensure_ascii=False) + ";\n")
    h = open(os.path.join(d, "index.html")).read().replace("__DUR__", str(cue.get("duration", 2.6)))
    open(os.path.join(d, "index.html"), "w").write(h)
    json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json", "paths": {"assets": "assets"}, "media": {"autoProxy": True}},
              open(os.path.join(d, "hyperframes.json"), "w"))
    json.dump({"id": cue["id"].lower(), "name": cue["id"]}, open(os.path.join(d, "meta.json"), "w"))
    json.dump({"name": cue["id"].lower(), "private": True, "type": "module"}, open(os.path.join(d, "package.json"), "w"))
    return d


def bbox(webm, fps=5):
    """Union of the non-transparent area over the whole graphic, for placement checks against faces."""
    from PIL import Image
    tmp = webm + ".frames"
    os.makedirs(tmp, exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-c:v", "libvpx-vp9", "-i", webm, "-vf", f"fps={fps}", "-pix_fmt", "rgba", os.path.join(tmp, "%03d.png")])
    bb = None
    for f in sorted(os.listdir(tmp)):
        b = Image.open(os.path.join(tmp, f)).split()[-1].point(lambda v: 255 if v > 40 else 0).getbbox()
        if b:
            bb = b if not bb else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    shutil.rmtree(tmp)
    return bb


def render(run, only=None):
    cues = rj(run.p("graphics.json"))
    if not cues:
        raise RuntimeError("write graphics.json first (see this module's docstring)")
    brand = brand_tokens(run)
    out_dir = run.p("graphics", "out", "x")[:-2]
    index = rj(os.path.join(out_dir, "cues.json"), {"cues": []}) or {"cues": []}
    have = {c["id"]: c for c in index["cues"]}
    for cue in cues:
        if only and cue["id"] not in only:
            continue
        d = _stage(run, cue, brand)
        webm = os.path.join(out_dir, f"{cue['id']}.webm")
        r = subprocess.run(["npx", "--yes", HF, "render", ".", "--format", "webm", "-q", "high", "--fps", "30", "-o", webm],
                           cwd=d, capture_output=True, text=True)
        if r.returncode or not os.path.exists(webm):
            raise RuntimeError(f"render failed for {cue['id']}: {(r.stderr or r.stdout)[-800:]}")
        have[cue["id"]] = {"id": cue["id"], "template": cue["template"], "duration_s": cue.get("duration", 2.6),
                           "sfx": [{"rel_s": s["rel_s"], "cue": s["kind"]} for s in cue.get("sfx", [])], "bbox": bbox(webm)}
        print(f"  {cue['id']} ({cue['template']}) -> {webm}  bbox {have[cue['id']]['bbox']}")
    wj(os.path.join(out_dir, "cues.json"), {"cues": list(have.values())})
    return out_dir
