"""Delivery: a share copy, the final contact sheet, 16:9 concept art, and the cost summary.

Cost rule: the video's cost is ONLY the final version, meaning the takes actually in the cut plus the
music sections used. Everything else (unused takes, re-rolls, probes, QA, unused music) stays in the
ledger as test spend. Dashboards show the final number; nothing on them mentions the tests.
"""
import json, os
from .util import rj, wj, sh, dur, FONTS
from .produce import cuts


def share_copy(run, final, limit_mb=29):
    out = final.replace(".mp4", "_share.mp4")
    for crf in (22, 25, 28, 31):
        sh(["ffmpeg", "-y", "-v", "error", "-i", final, "-c:v", "libx264", "-crf", str(crf), "-preset", "slow", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
        if os.path.getsize(out) < limit_mb * 1e6:
            break
    return out


def final_sheet(run, final, title=""):
    from PIL import Image, ImageDraw, ImageFont
    cs = [0.0] + cuts(final) + [dur(final)]
    shots = [(a, b) for a, b in zip(cs, cs[1:]) if b - a > 0.3]
    W, H, pad, cols = 220, 391, 10, 9
    rows = (len(shots) + cols - 1) // cols
    f = lambda s: ImageFont.truetype(os.path.join(FONTS, "Inter-SemiBold.ttf"), s)
    im = Image.new("RGB", (cols * (W + pad) + pad, rows * (H + 30 + pad) + pad + 60), (17, 24, 22))
    d = ImageDraw.Draw(im)
    d.text((pad, 16), f"{title}  ·  final cut  ·  {len(shots)} shots  ·  {dur(final):.1f} s", font=f(26), fill=(240, 240, 230))
    tmp = run.p("out", "_still.png")
    for i, (a, b) in enumerate(shots):
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{a + (b - a) * 0.55:.3f}", "-i", final, "-frames:v", "1", "-vf", f"scale={W}:-2", tmp])
        x, y = pad + (i % cols) * (W + pad), 60 + pad + (i // cols) * (H + 30 + pad)
        im.paste(Image.open(tmp).convert("RGB").resize((W, H)), (x, y))
        d.text((x + 2, y + H + 6), f"{i + 1}  {a:.1f} to {b:.1f}s", font=f(14), fill=(160, 220, 195))
    os.remove(tmp)
    out = run.p("out", "contact_sheet.png")
    im.save(out)
    return out


def concept_art(run, frames, title, logline, chips=(), out=None, clean=None):
    """16:9 key art from real frames of the cut (use a build without captions if you have one: clean=)."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    kit = rj(run.p("brief", "brandkit.json"), {}) or {}
    pal = kit.get("palette", {})
    hexrgb = lambda h, d: tuple(int((h or d).lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    dark, acc = hexrgb(pal.get("dark"), "#0c1412"), hexrgb((pal.get("accents") or [pal.get("primary")])[0], "#f0ff42")
    src = clean or rj(run.p("state.json"), {}).get("final")
    stills = []
    for i, t in enumerate(frames):
        p = run.p("out", f"_art{i}.png")
        sh(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", src, "-frames:v", "1", p])
        stills.append(p)
    Wc, Hc = 1600, 900
    bg = Image.new("RGB", (Wc, Hc), dark)
    back = Image.open(stills[0]).convert("RGB")
    back = back.resize((Wc, int(back.height * Wc / back.width))).crop((0, 300, Wc, 300 + Hc)).filter(ImageFilter.GaussianBlur(28))
    bg = Image.blend(bg, back, 0.35)
    ph, pw, gap = 820, int(820 * 9 / 16), 18
    xs = [Wc - 40 - pw * (len(stills[:2]) - i) - gap * (len(stills[:2]) - 1 - i) for i in range(len(stills[:2]))]
    for x, s in zip(xs, stills[:2]):
        im = Image.open(s).convert("RGB").resize((pw, ph))
        m = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, pw - 1, ph - 1], 18, fill=255)
        bg.paste(im, (x, 40), m)
        ImageDraw.Draw(bg).rounded_rectangle([x, 40, x + pw - 1, 40 + ph - 1], 18, outline=acc, width=3)
    d = ImageDraw.Draw(bg)
    head = lambda s: ImageFont.truetype(os.path.join(FONTS, "BarlowCondensed-ExtraBold.ttf"), s)
    body = lambda s: ImageFont.truetype(os.path.join(FONTS, "Inter-SemiBold.ttf"), s)
    maxw = xs[0] - 96
    y, size = 120, 150
    words, lines, cur = title.upper().split(), [], ""
    while True:
        lines, cur = [], ""
        for w in words:
            if d.textlength((cur + " " + w).strip(), font=head(size)) > maxw and cur:
                lines.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        if len(lines) <= 3 or size <= 80:
            break
        size -= 10
    for l in lines:
        d.text((52, y), l, font=head(size), fill=acc); y += int(size * 0.95)
    y += 24
    words, cur = logline.split(), ""
    for w in words:
        if d.textlength((cur + " " + w).strip(), font=body(28)) > maxw:
            d.text((56, y), cur, font=body(28), fill=(236, 240, 238)); y += 42; cur = w
        else:
            cur = (cur + " " + w).strip()
    d.text((56, y), cur, font=body(28), fill=(236, 240, 238)); y += 70
    x = 56
    for c in chips:
        w = d.textlength(c, font=body(22)) + 36
        d.rounded_rectangle([x, y, x + w, y + 42], 21, fill=acc); d.text((x + 18, y + 9), c, font=body(22), fill=dark); x += w + 12
    logo = (kit.get("logo") or {}).get("file")
    if logo and os.path.exists(logo) and not logo.endswith(".svg"):
        lg = Image.open(logo).convert("RGBA")
        lh = 46
        lg = lg.resize((max(1, int(lg.width * lh / lg.height)), lh))
        bg.paste(lg, (56, Hc - 40 - lh), lg)
    out = out or run.p("out", "concept_art.png")
    bg.save(out)
    for s in stills:
        os.remove(s)
    return out


def costs(run, final_takes=(), final_music=()):
    """Marks the takes in the cut and the music sections used as final; everything else is test spend."""
    rows = rj(run.p("ledger.json"), [])
    ft = {f"take {t}" for t in final_takes} | {f"music {m}" for m in final_music}
    for r in rows:
        if r["what"] in ft or r["stage"] == "assemble":
            r["final"] = True
        elif r["stage"] in ("produce", "score"):
            r["final"] = False
    wj(run.p("ledger.json"), rows)
    fin = round(sum(r["usd"] for r in rows if r["final"]), 2)
    tests = round(sum(r["usd"] for r in rows if not r["final"]), 2)
    summary = {"final_usd": fin, "test_usd": tests, "final_items": [r["what"] for r in rows if r["final"]]}
    wj(run.p("out", "costs.json"), summary)
    return summary
