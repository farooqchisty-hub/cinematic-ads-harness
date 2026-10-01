"""Shared helpers: config from .env, shell, media probes, the run folder, the cost ledger, captions."""
import json, os, subprocess, threading, time, urllib.request

PKG = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FONTS = os.path.join(PKG, "assets", "fonts")
SFX = os.path.join(PKG, "assets", "sfx")
TEMPLATES = os.path.join(PKG, "templates")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def load_env():
    """Keys come from the environment, or a .env in the working directory, or one in the package folder."""
    for f in (os.path.join(os.getcwd(), ".env"), os.path.join(PKG, ".env")):
        if not os.path.exists(f):
            continue
        for line in open(f):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_env()
env = lambda k, d="": (os.environ.get(k) or d).strip()


def sh(cmd, check=True, **kw):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    if check and r.returncode:
        raise RuntimeError(f"command failed: {cmd if isinstance(cmd, str) else ' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")
    return r.stdout


def dur(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).strip())


def download(url, path, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=600) as r, open(path + ".part", "wb") as f:
        f.write(r.read())
    os.replace(path + ".part", path)
    return path


def rj(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


def wj(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, ensure_ascii=False)


class Run:
    """One product run: runs/<slug>/ holds every input, render, take and output, plus state.json."""

    def __init__(self, path):
        self.dir = os.path.abspath(path)
        os.makedirs(self.dir, exist_ok=True)

    def p(self, *a):
        out = os.path.join(self.dir, *a)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        return out

    @property
    def state(self):
        return rj(self.p("state.json"), {})

    def set(self, **kw):
        s = self.state
        s.update(kw)
        s["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        wj(self.p("state.json"), s)


_lock = threading.Lock()


def spend(run, stage, what, usd, final=False, provider="", ref=""):
    """Every paid call lands here. Only rows marked final count as the video's cost (see references/costs.md)."""
    with _lock:
        rows = rj(run.p("ledger.json"), [])
        rows.append({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": stage, "what": what,
                     "provider": provider, "ref": ref, "usd": round(float(usd or 0), 4), "final": bool(final)})
        wj(run.p("ledger.json"), rows)


def text_png(path, text, size, box=True, font="Inter-SemiBold.ttf", maxw=940):
    """A caption or label as a transparent PNG, set in a real font (this ffmpeg build may lack drawtext).
    The look matches the approved Box, Box, Brenda captions exactly."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(os.path.join(FONTS, font), size)
    words, lines, cur = text.split(), [], ""
    d0 = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for w in words:
        t = (cur + " " + w).strip()
        if d0.textlength(t, font=f) <= maxw - 60 or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = int(size * 1.22)
    tw = max(int(d0.textlength(l, font=f)) for l in lines)
    Wd, Ht = tw + 56, lh * len(lines) + 34
    im = Image.new("RGBA", (Wd, Ht), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if box:
        d.rounded_rectangle([0, 0, Wd - 1, Ht - 1], radius=18, fill=(12, 16, 12, 170))
    for k, l in enumerate(lines):
        x = (Wd - d.textlength(l, font=f)) / 2
        if not box:
            d.text((x + 3, 17 + k * lh + 3), l, font=f, fill=(0, 0, 0, 160))
        d.text((x, 17 + k * lh), l, font=f, fill=(255, 255, 255, 255))
    im.save(path)
    return im.size


def no_dashes(text):
    """House rule: no em or en dashes in anything the harness writes for people."""
    return str(text).replace("—", ", ").replace("–", " to ")
